"""MethaneX — Production FastAPI Backend (v2)"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import json
import os
import random
import ssl
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
import urllib.parse
import urllib.request

# Ensure project root is importable when running from server/.
ROOT = Path(__file__).resolve().parents[2]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.config import METHANE_GWP, SEV_HIGH, SEV_LOW, SEV_MODERATE  # noqa: E402
from ai.pipelines.pipeline_manager_v2 import PLANT_DB, PipelineManager  # noqa: E402
from ai.models.inference_model import model_available, torch_available  # noqa: E402
from ai.data.sentinel2_fetcher import fetch_sentinel2_image, preflight_sentinelhub  # noqa: E402
from ai.data.emit_fetcher import emit_availability  # noqa: E402
from ai.utils.logger import get_logger, log_error, log_request, log_result  # noqa: E402

logger = get_logger("ignisia.api")

app = FastAPI(title="IGNISIA Methane Detection API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Scan-Duration-Ms"],
)


# Runtime state
_START_TIME = time.time()
_REQ_COUNT = 0
_LAT_LOG: list[float] = []

# Best-effort model load (keeps demo mode if unavailable)
try:
    import torch  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    torch = None

DEVICE = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
MODEL = None
legacy_model_dir = ROOT / "model"
if torch is None:
    logger.info("Torch unavailable; running in demo mode for /predict.")
elif not legacy_model_dir.exists():
    logger.info(
        "Legacy model package not found at %s; running in demo mode for /predict.",
        str(legacy_model_dir),
    )
else:
    try:
        from model.unet import UNet  # type: ignore

        model_path = legacy_model_dir / "best_unet.pth"
        if model_path.exists():
            model_obj = UNet().to(DEVICE)
            model_obj.load_state_dict(torch.load(model_path, map_location=DEVICE))
            model_obj.eval()
            MODEL = model_obj
            logger.info("Model weights loaded from %s", str(model_path))
        else:
            logger.info(
                "Legacy model weights not found at %s; running in demo mode for /predict.",
                str(model_path),
            )
    except Exception as exc:
        logger.info("Legacy model load failed; running in demo mode for /predict (%s)", exc)

pipeline = PipelineManager(model=MODEL, device=DEVICE)
CLIENT_PUBLIC = ROOT / "client" / "public"
_LAST_GEOCODE_TS = 0.0

_TIERS = {
    "basic": {"price_usd": 50, "scans_per_month": 10, "alerts": False, "api_access": False},
    "pro": {"price_usd": 200, "scans_per_month": 100, "alerts": True, "api_access": True},
    "enterprise": {"price_usd": 500, "scans_per_month": -1, "alerts": True, "api_access": True},
}
_SCAN_COUNTERS = {"api": 0, "geo": 0}


class LivePredictRequest(BaseModel):
    lat: float
    lon: float
    wind_speed_ms: Optional[float] = None
    radius_km: Optional[float] = None
    prefer_emit: Optional[bool] = None
    mask_mode: Optional[str] = None
    require_live_satellite: Optional[bool] = None


def _fetch_url_text(req: urllib.request.Request, timeout: int = 15) -> str:
    """
    Fetch URL text with TLS fallbacks for environments missing system CA roots.
    """
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as exc:
        cert_error = isinstance(exc, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc)
        if not cert_error:
            raise

    # Retry with certifi CA bundle when available.
    try:
        import certifi  # type: ignore

        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8")
    except Exception as certifi_exc:
        insecure_ssl = os.getenv("GEOCODE_INSECURE_SSL", "0") == "1"
        if insecure_ssl:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8")
        raise RuntimeError(
            "TLS verification failed for geocoding. "
            "Install certifi (`pip install certifi`) or set GEOCODE_INSECURE_SSL=1 for local dev only."
        ) from certifi_exc


def _normalize_coordinates(lat: float, lon: float) -> tuple[float, float, str]:
    """
    Accept broader coordinate inputs and normalize to valid WGS84 bounds.
    """
    notes: list[str] = []
    lat_n = float(lat)
    lon_n = float(lon)

    # Common user mistake: swapped lat/lon (e.g., lon in [-90,90], lat outside).
    if abs(lat_n) > 90.0 and abs(lon_n) <= 90.0:
        lat_n, lon_n = lon_n, lat_n
        notes.append("swapped lat/lon")

    # Wrap longitude to [-180, 180].
    if abs(lon_n) > 180.0:
        lon_n = ((lon_n + 180.0) % 360.0) - 180.0
        notes.append("wrapped longitude")

    # Clamp latitude to avoid invalid poles input.
    if lat_n > 90.0:
        lat_n = 90.0
        notes.append("clamped latitude")
    elif lat_n < -90.0:
        lat_n = -90.0
        notes.append("clamped latitude")

    return lat_n, lon_n, ", ".join(notes)


def _normalize_gray_u8(arr: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    lo = float(np.percentile(x, 1))
    hi = float(np.percentile(x, 99))
    if hi - lo < 1e-6:
        return np.zeros_like(x, dtype=np.uint8)
    y = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return (y * 255).astype(np.uint8)


def _normalize_rgb_u8(rgb: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(rgb.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    if x.max() > 1.5:
        x = x / 255.0
    out = np.zeros_like(x, dtype=np.float32)
    for c in range(3):
        ch = x[:, :, c]
        lo = float(np.percentile(ch, 1))
        hi = float(np.percentile(ch, 99))
        if hi - lo < 1e-6:
            out[:, :, c] = np.clip(ch, 0.0, 1.0)
        else:
            out[:, :, c] = np.clip((ch - lo) / (hi - lo), 0.0, 1.0)
    out = np.power(np.clip(out, 0.0, 1.0), 0.85)
    return (out * 255).astype(np.uint8)


def _rgb_png_response(rgb_u8: np.ndarray) -> Response:
    ok, buf = cv2.imencode(".png", cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2BGR))
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode image.")
    return Response(content=buf.tobytes(), media_type="image/png")


@app.get("/health")
def health() -> dict:
    avg_lat = round(sum(_LAT_LOG) / max(len(_LAT_LOG), 1), 1)
    return {
        "status": "ok",
        "version": "1.0.0",
        "device": DEVICE,
        "model_loaded": MODEL is not None,
        "inference_model_available": model_available(),
        "torch_available": torch_available(),
        "demo_mode": MODEL is None,
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "total_requests": _REQ_COUNT,
        "avg_latency_ms": avg_lat,
    }


@app.get("/live")
def live_page() -> FileResponse:
    page = CLIENT_PUBLIC / "live.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="live.html not found.")
    return FileResponse(page)


@app.get("/")
def root_page() -> FileResponse:
    return live_page()


@app.get("/satellite/latest")
def latest_satellite(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    radius_km: float = Query(5.0, ge=0.1, le=200.0),
) -> Response:
    if (lat is None) ^ (lon is None):
        raise HTTPException(status_code=400, detail="Provide both lat and lon, or neither.")
    if lat is not None and lon is not None:
        lat_n, lon_n, _ = _normalize_coordinates(lat, lon)
        try:
            bands = fetch_sentinel2_image(lat_n, lon_n, size=512, radius_km=radius_km)
            rgb = _normalize_rgb_u8(bands["rgb"])
            return _rgb_png_response(rgb)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Satellite fetch failed: {exc}") from exc

    img_path = ROOT / "outputs" / "latest_satellite.png"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Satellite image not available yet.")
    return FileResponse(img_path)


@app.get("/satellite/swir")
def swir_satellite(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    radius_km: float = Query(5.0, ge=0.1, le=200.0),
) -> Response:
    if (lat is None) ^ (lon is None):
        raise HTTPException(status_code=400, detail="Provide both lat and lon, or neither.")
    if lat is not None and lon is not None:
        lat_n, lon_n, _ = _normalize_coordinates(lat, lon)
        try:
            bands = fetch_sentinel2_image(lat_n, lon_n, size=512, radius_km=radius_km)
            base = _normalize_rgb_u8(bands["rgb"])
            b11 = np.asarray(bands["B11"], dtype=np.float32)
            b12 = np.asarray(bands["B12"], dtype=np.float32)
            swir_ratio = (b12 - b11) / (b12 + b11 + 1e-6)
            heat_u8 = _normalize_gray_u8(swir_ratio)
            heat = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
            overlay = cv2.addWeighted(cv2.cvtColor(base, cv2.COLOR_RGB2BGR), 0.55, heat, 0.45, 0)
            ok, buf = cv2.imencode(".png", overlay)
            if not ok:
                raise HTTPException(status_code=500, detail="Failed to encode SWIR image.")
            return Response(content=buf.tobytes(), media_type="image/png")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"SWIR fetch failed: {exc}") from exc

    img_path = ROOT / "outputs" / "swir_false.png"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="SWIR image not available yet.")
    return FileResponse(img_path)


@app.get("/preflight/sentinel")
def preflight() -> dict:
    """
    Connectivity check for Sentinel Hub token endpoint.
    """
    return preflight_sentinelhub()


@app.get("/emit/availability")
def emit_availability_endpoint(
    lat: float = Query(...),
    lon: float = Query(...),
    days: int = Query(60, ge=1, le=365),
    radius_km: float = Query(5.0, ge=1.0, le=50.0),
) -> dict:
    """
    Check EMIT hyperspectral availability for a location.
    """
    try:
        return emit_availability(lat, lon, days=days, radius_km=radius_km)
    except Exception as exc:
        return {"available": False, "error": str(exc)}


@app.get("/geocode")
def geocode(address: str = Query(..., min_length=3)) -> dict:
    """
    Proxy to Nominatim with proper headers.
    """
    global _LAST_GEOCODE_TS
    now = time.time()
    if now - _LAST_GEOCODE_TS < 1.0:
        raise HTTPException(status_code=429, detail="Rate limited. Try again in a moment.")
    _LAST_GEOCODE_TS = now

    user_agent = os.getenv(
        "GEOCODE_USER_AGENT",
        "IGNISIA-Geocoder/1.0 (contact: geocode@ignisia.local)",
    )
    params = {
        "q": address,
        "format": "json",
        "limit": "1",
        "addressdetails": "1",
    }
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", user_agent)
    req.add_header("Accept", "application/json")

    try:
        data = _fetch_url_text(req, timeout=15)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Geocoding failed: {exc}") from exc

    try:
        payload = json.loads(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Invalid geocoding response: {exc}") from exc

    if not payload:
        return {"ok": False, "message": "No results found", "results": []}

    first = payload[0]
    return {
        "ok": True,
        "lat": float(first.get("lat")),
        "lon": float(first.get("lon")),
        "display_name": first.get("display_name", ""),
        "raw": first,
    }


@app.post("/predict")
async def predict(file: UploadFile = File(...)) -> JSONResponse:
    global _REQ_COUNT
    _REQ_COUNT += 1
    t0 = log_request(logger, "/predict", file.filename or "unknown")

    if not file.content_type or not file.content_type.startswith("image/"):
        log_error(logger, "/predict", "invalid content type")
        raise HTTPException(status_code=400, detail="Image files only.")

    raw = await file.read()
    arr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        log_error(logger, "/predict", "cannot decode image")
        raise HTTPException(status_code=400, detail="Cannot decode image.")

    result = pipeline.run_pipeline(raw_image=img)
    elapsed_ms = log_result(
        logger,
        t0,
        bool(result.get("methane_detected")),
        float(result.get("emission", {}).get("emission_kghr", 0.0)),
        str(result.get("emission", {}).get("severity", "None")),
    )
    _LAT_LOG.append(elapsed_ms)
    if len(_LAT_LOG) > 500:
        _LAT_LOG.pop(0)

    _SCAN_COUNTERS["api"] += 1
    return JSONResponse(result)


@app.post("/predict/geo")
async def predict_geo(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
) -> JSONResponse:
    global _REQ_COUNT
    _REQ_COUNT += 1
    lat_n, lon_n, coord_note = _normalize_coordinates(lat, lon)
    t0 = log_request(logger, "/predict/geo", f"lat={lat_n},lon={lon_n}")
    result = pipeline.run_pipeline(lat=lat_n, lon=lon_n)
    if isinstance(result, dict):
        result["used_coordinates"] = {"lat": float(lat_n), "lon": float(lon_n)}
        if coord_note:
            result["coordinate_note"] = coord_note
    elapsed_ms = log_result(
        logger,
        t0,
        bool(result.get("methane_detected")),
        float(result.get("emission", {}).get("emission_kghr", 0.0)),
        str(result.get("emission", {}).get("severity", "None")),
    )
    _LAT_LOG.append(elapsed_ms)
    if len(_LAT_LOG) > 500:
        _LAT_LOG.pop(0)

    _SCAN_COUNTERS["geo"] += 1
    return JSONResponse(result)


@app.post("/predict/live")
async def predict_live(payload: LivePredictRequest) -> JSONResponse:
    global _REQ_COUNT
    _REQ_COUNT += 1
    lat_n, lon_n, coord_note = _normalize_coordinates(payload.lat, payload.lon)
    t0 = log_request(logger, "/predict/live", f"lat={lat_n},lon={lon_n}")
    try:
        result = pipeline.run_live_pipeline(
            lat=lat_n,
            lon=lon_n,
            wind_speed_ms=payload.wind_speed_ms,
            radius_km=payload.radius_km,
            prefer_emit=payload.prefer_emit,
            mask_mode=payload.mask_mode,
            require_live_satellite=payload.require_live_satellite,
        )
        if isinstance(result, dict) and coord_note:
            result["coordinate_note"] = coord_note
        elapsed_ms = log_result(
            logger,
            t0,
            bool(result.get("plume_detected")),
            float(result.get("emission_kghr", 0.0)),
            "Live",
        )
    except Exception as exc:
        log_error(logger, "/predict/live", str(exc))
        return JSONResponse({"error": "Live pipeline failed", "details": str(exc)}, status_code=500)
    _LAT_LOG.append(elapsed_ms)
    if len(_LAT_LOG) > 500:
        _LAT_LOG.pop(0)

    _SCAN_COUNTERS["geo"] += 1

    # Align with requested response shape while keeping extras
    response = {
        "plume_detected": bool(result.get("plume_detected", False)),
        "emission_kghr": float(result.get("emission_kghr", 0.0)),
        "source": str(result.get("source", "unknown")),
        "confidence": float(result.get("confidence", 0.0)),
        "image_source": str(result.get("image_source", "Sentinel-2 L2A")),
    }
    response.update(result)
    return JSONResponse(response)


@app.post("/predict_bbox")
async def predict_bbox(
    lat_min: float = Query(...),
    lat_max: float = Query(...),
    lon_min: float = Query(...),
    lon_max: float = Query(...),
) -> dict:
    plants_in = [
        p
        for p in PLANT_DB
        if lat_min <= p["lat"] <= lat_max and lon_min <= p["lon"] <= lon_max
    ]

    plumes = []
    for plant in plants_in:
        e = round(random.uniform(30, 600), 1)
        if e > SEV_HIGH / 2:
            sev = "High"
        elif e > SEV_LOW:
            sev = "Moderate"
        else:
            sev = "Low"
        plumes.append(
            {
                "plant_id": plant["id"],
                "plant_name": plant["name"],
                "lat": plant["lat"],
                "lon": plant["lon"],
                "emission_kghr": e,
                "severity": sev,
                "co2_equivalent_kghr": round(e * METHANE_GWP, 1),
            }
        )

    return {
        "bbox": [lat_min, lat_max, lon_min, lon_max],
        "area_scanned_km2": round((lat_max - lat_min) * (lon_max - lon_min) * 111**2, 1),
        "plumes_detected": len(plumes),
        "plumes": plumes,
        "status": "simulated",
    }


@app.get("/scan/scheduled")
def scheduled_scan() -> dict:
    avg_lat = round(sum(_LAT_LOG) / max(len(_LAT_LOG), 1), 1)
    results = []
    for plant in PLANT_DB:
        res = pipeline.run_pipeline(lat=plant["lat"], lon=plant["lon"])
        e = float(res.get("emission", {}).get("emission_kghr", 0.0))
        sev = str(res.get("emission", {}).get("severity", "None"))
        alert = sev in ("High", "Critical")
        results.append(
            {
                "plant_id": plant["id"],
                "plant_name": plant["name"],
                "emission_kghr": e,
                "severity": sev,
                "alert": alert,
            }
        )

    alerts = [r for r in results if r["alert"]]
    return {
        "scan_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "plants_scanned": len(PLANT_DB),
        "alerts_raised": len(alerts),
        "results": results,
        "alerts": alerts,
        "avg_latency_ms": avg_lat,
        "plants": len(PLANT_DB),
    }


@app.get("/ping")
async def ping():
    return {"ok": True, "service": "MethaneX API", "version": "1.0.0"}


@app.get("/history/{plant_id}")
def get_history(plant_id: str) -> dict:
    return pipeline.get_plant_history(plant_id)


@app.get("/plants")
def get_plants() -> dict:
    return {"plants": PLANT_DB}


@app.get("/subscription")
def subscription_info(
    tier: str = Query("pro", pattern="^(basic|pro|enterprise)$"),
) -> dict:
    plan = _TIERS[tier]
    used = _SCAN_COUNTERS.get("api", 0) + _SCAN_COUNTERS.get("geo", 0)
    limit = plan["scans_per_month"]
    return {
        "tier": tier,
        "price_usd_month": plan["price_usd"],
        "scans_limit": limit if limit > 0 else "unlimited",
        "scans_used": used,
        "scans_remaining": max(0, limit - used) if limit > 0 else "unlimited",
        "alerts_enabled": plan["alerts"],
        "api_access": plan["api_access"],
        "annual_saving_pct": 17 if tier != "basic" else 0,
    }


if __name__ == "__main__":
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise SystemExit(
            "uvicorn is required to run the API. Install server requirements first."
        ) from exc

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "0") == "1",
    )
