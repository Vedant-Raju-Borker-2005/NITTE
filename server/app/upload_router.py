"""
MethaneX — Drone Upload Router
================================
POST /upload/drone    → Extract GPS from EXIF, run Sentinel-2 pipeline, return results
GET  /upload/drone/image → Serve latest uploaded drone image
GET  /upload/history  → Return last 10 upload scan sessions
"""

from __future__ import annotations

import io
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

# Ensure project root (parent of server/) is importable so ai.* modules resolve.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

upload_router = APIRouter()

# In-memory scan history (last 10 sessions)
upload_scan_history: list[dict] = []

# Output directory (relative to CWD when uvicorn is launched from project root)
_OUTPUTS = Path("outputs")


# ─────────────────────────────────────────────────────────────────────────────
# EXIF GPS extractor
# ─────────────────────────────────────────────────────────────────────────────

def extract_gps_from_exif(image_bytes: bytes) -> dict | None:
    """
    Extract GPS lat/lon from image EXIF data.
    Returns {"lat": float, "lon": float, "altitude_m": float|None}
    or None if no GPS data found.
    """
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS

        img = Image.open(io.BytesIO(image_bytes))
        exif_data = img._getexif()  # type: ignore[attr-defined]
        if not exif_data:
            return None

        gps_info: dict = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value

        if not gps_info or "GPSLatitude" not in gps_info:
            return None

        def dms_to_decimal(dms, ref: str) -> float:
            d, m, s = [float(x) for x in dms]
            decimal = d + m / 60 + s / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return round(decimal, 7)

        lat = dms_to_decimal(
            gps_info["GPSLatitude"],
            gps_info.get("GPSLatitudeRef", "N"),
        )
        lon = dms_to_decimal(
            gps_info["GPSLongitude"],
            gps_info.get("GPSLongitudeRef", "E"),
        )
        alt: float | None = (
            float(gps_info["GPSAltitude"]) if "GPSAltitude" in gps_info else None
        )

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None

        return {"lat": lat, "lon": lon, "altitude_m": alt}
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# POST /upload/drone
# ─────────────────────────────────────────────────────────────────────────────

@upload_router.post("/drone")
async def upload_drone_image(
    file: UploadFile = File(...),
    manual_lat: Optional[float] = Form(None),
    manual_lon: Optional[float] = Form(None),
    wind_speed_ms: float = Form(5.0),
    radius_km: float = Form(3.0),
) -> JSONResponse:
    # ── 1. Validate file ──────────────────────────────────────────────────────
    allowed_types = {"image/jpeg", "image/png", "image/tiff"}
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_FILE_TYPE",
                "message": (
                    f"Upload must be JPG, PNG, or TIFF. Received: {content_type}"
                ),
            },
        )

    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:  # 50 MB
        raise HTTPException(
            status_code=413,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": "Maximum file size is 50 MB",
            },
        )

    # ── 2. Extract GPS from EXIF ──────────────────────────────────────────────
    gps = extract_gps_from_exif(contents)
    gps_source = "exif"

    if not gps:
        if manual_lat is not None and manual_lon is not None:
            gps = {"lat": manual_lat, "lon": manual_lon, "altitude_m": None}
            gps_source = "manual"
        else:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "NO_GPS_DATA",
                    "message": (
                        "No GPS metadata found in this image. "
                        "Please enter the coordinates manually."
                    ),
                    "requires_manual_coordinates": True,
                },
            )

    # ── 3. Save drone image for frontend display ──────────────────────────────
    _OUTPUTS.mkdir(parents=True, exist_ok=True)
    drone_filename = _OUTPUTS / f"drone_upload_{uuid.uuid4().hex[:8]}.jpg"
    with open(drone_filename, "wb") as fh:
        fh.write(contents)
    with open(_OUTPUTS / "latest_drone.jpg", "wb") as fh:
        fh.write(contents)

    # ── 4. Run full Sentinel-2 pipeline on extracted coordinates ──────────────
    # Import pipeline here to avoid circular imports at module load time.
    # The pipeline module path matches what main.py uses.
    try:
        from ai.pipelines.pipeline_manager_v2 import PipelineManager  # noqa: E402

        _pipeline = PipelineManager()
        result: dict = _pipeline.run_live_pipeline(
            lat=gps["lat"],
            lon=gps["lon"],
            wind_speed_ms=wind_speed_ms,
            radius_km=radius_km,
            prefer_emit=False,
            mask_mode="auto",
            require_live_satellite=False,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "PIPELINE_ERROR",
                "message": f"Sentinel-2 pipeline failed: {exc}",
            },
        ) from exc

    # ── 5. Build response ─────────────────────────────────────────────────────
    scan_id = str(uuid.uuid4())
    emission_kghr = result.get("emission_kghr") or 0.0
    response: dict = {
        # Standard pipeline fields (identical shape to /predict/live)
        "scan_id": scan_id,
        "plume_detected": result.get("plume_detected", False),
        "emission_kghr": emission_kghr,
        "confidence": result.get("confidence"),
        "quantification_confidence": (
            result.get("quantification", {}).get("emission_kghr") if result.get("quantification") else None
        ),
        "source": result.get("source"),
        "source_plant_id": (
            result.get("graph_attribution", {}).get("primary_source", {}).get("plant_id")
            if result.get("graph_attribution") else None
        ),
        "cost_loss_usd_per_hour": result.get("cost_loss_usd_per_hour"),
        "co2_equivalent_kghr": round(emission_kghr * 28, 4) if emission_kghr else None,
        "severity": (
            result.get("quantification", {}).get("method")
            if False  # Compute severity from emission_kghr below
            else _severity_from_kghr(emission_kghr)
        ),
        "attribution": (
            result.get("graph_attribution", {}).get("top_candidates", [])
            if result.get("graph_attribution") else []
        ),
        "processing_time_ms": result.get("processing_time_ms"),
        "image_source": result.get("image_source", "Sentinel-2 L2A"),
        "wind_speed_ms": wind_speed_ms,
        "wind_direction_deg": result.get("wind_direction_deg"),

        # Drone-specific extra fields
        "analysis_mode": "drone_geolocated",
        "drone_image_available": True,
        "gps_source": gps_source,
        "extracted_lat": gps["lat"],
        "extracted_lon": gps["lon"],
        "drone_altitude_m": gps.get("altitude_m"),
        "original_filename": file.filename,
        "uploaded_at": datetime.utcnow().isoformat() + "Z",

        # Pass through full pipeline result for debugging
        "pipeline_result": result,
    }

    # ── 6. Prepend to in-memory history ──────────────────────────────────────
    upload_scan_history.insert(0, {
        "scan_id": scan_id,
        "filename": file.filename,
        "uploaded_at": response["uploaded_at"],
        "severity": response["severity"],
        "plume_detected": response["plume_detected"],
        "emission_kghr": emission_kghr,
        "gps_source": gps_source,
        "lat": gps["lat"],
        "lon": gps["lon"],
    })
    del upload_scan_history[10:]  # keep last 10 only

    return JSONResponse(content=response)


# ─────────────────────────────────────────────────────────────────────────────
# GET /upload/drone/image
# ─────────────────────────────────────────────────────────────────────────────

@upload_router.get("/drone/image")
async def get_drone_image() -> FileResponse:
    """Serves the most recently uploaded drone image (raw bytes, image/jpeg)."""
    path = _OUTPUTS / "latest_drone.jpg"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NO_DRONE_IMAGE",
                "message": "No drone image uploaded yet in this session",
            },
        )
    return FileResponse(
        str(path),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /upload/history
# ─────────────────────────────────────────────────────────────────────────────

@upload_router.get("/history")
async def get_upload_history() -> dict:
    """Returns last 10 drone upload scans."""
    return {"scans": upload_scan_history}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _severity_from_kghr(emission_kghr: float) -> str:
    if emission_kghr >= 800:
        return "CRITICAL"
    if emission_kghr >= 400:
        return "HIGH"
    if emission_kghr >= 100:
        return "MODERATE"
    return "LOW"
