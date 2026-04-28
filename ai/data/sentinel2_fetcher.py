from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import os
import ssl
from typing import Optional

import numpy as np
import urllib.parse
import urllib.request
from sentinelhub import (
    BBox,
    CRS,
    DataCollection,
    MimeType,
    MosaickingOrder,
    SentinelHubRequest,
)

from ai.config.sentinel_config import config


EVALSCRIPT_TRUE_COLOR = """
//VERSION=3
function setup() {
  return {
    input: ["B02", "B03", "B04", "B08", "B11", "B12"],
    output: { bands: 6, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(sample) {
  return [
    2.5 * sample.B04,
    2.5 * sample.B03,
    2.5 * sample.B02,
    sample.B08,
    sample.B11,
    sample.B12
  ];
}
"""


def _date_range(days: int = 30) -> tuple[str, str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _urlopen_with_tls_fallback(req: urllib.request.Request, timeout: int = 15):
    """
    urllib.open with TLS fallback for macOS/local Python CA issues.
    """
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except Exception as exc:
        cert_error = isinstance(exc, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc)
        if not cert_error:
            raise

    try:
        import certifi  # type: ignore

        ctx = ssl.create_default_context(cafile=certifi.where())
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    except Exception as certifi_exc:
        if os.getenv("SENTINEL_INSECURE_SSL", "0") == "1":
            ctx = ssl._create_unverified_context()
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        raise RuntimeError(
            "Sentinel TLS verification failed. Install certifi (`pip install certifi`) "
            "or set SENTINEL_INSECURE_SSL=1 for local dev only."
        ) from certifi_exc


def preflight_sentinelhub() -> dict:
    """
    Lightweight connectivity check: request an OAuth token.
    """
    if not config.sh_client_id or not config.sh_client_secret:
        return {
            "ok": False,
            "token_url": getattr(config, "sh_token_url", ""),
            "error": "Missing SH_CLIENT_ID/SH_CLIENT_SECRET for Sentinel OAuth.",
            "account_id": getattr(config, "sh_account_id", ""),
            "user_id": getattr(config, "sh_user_id", ""),
        }

    try:
        token_url = config.sh_token_url
        data = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": config.sh_client_id,
                "client_secret": config.sh_client_secret,
            }
        ).encode("utf-8")
        req = urllib.request.Request(token_url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with _urlopen_with_tls_fallback(req, timeout=15) as resp:
            payload = resp.read().decode("utf-8")
        ok = "access_token" in payload
        return {
            "ok": ok,
            "token_url": token_url,
            "account_id": getattr(config, "sh_account_id", ""),
            "user_id": getattr(config, "sh_user_id", ""),
        }
    except Exception as exc:
        return {
            "ok": False,
            "token_url": getattr(config, "sh_token_url", ""),
            "error": str(exc),
            "account_id": getattr(config, "sh_account_id", ""),
            "user_id": getattr(config, "sh_user_id", ""),
        }


def _normalize_unit(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    if arr.max() > 1.0:
        arr = arr / 255.0
    return np.clip(arr, 0.0, 1.0)


def _meters_per_degree(lat_deg: float) -> tuple[float, float]:
    """
    Approximate meters per degree for latitude/longitude at a given latitude.
    Returns (m_per_deg_lat, m_per_deg_lon).
    """
    lat_rad = math.radians(lat_deg)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * max(math.cos(lat_rad), 0.01)
    return m_per_deg_lat, m_per_deg_lon


def fetch_sentinel2_image(
    lat: float,
    lon: float,
    size: int = 256,
    radius_km: Optional[float] = None,
) -> dict:
    """
    Fetch Sentinel-2 L2A true color image for a coordinate.
    Returns normalized float32 array in [0, 1] with shape (H, W, 3).
    """
    if radius_km is not None:
        radius_km = max(float(radius_km), 0.1)
        dlat = radius_km / 111.32
        dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
        bbox_vals = [lon - dlon, lat - dlat, lon + dlon, lat + dlat]
    else:
        bbox_vals = [lon - 0.01, lat - 0.01, lon + 0.01, lat + 0.01]

    bbox = BBox(bbox=bbox_vals, crs=CRS.WGS84)
    start_date, end_date = _date_range(days=30)

    request = SentinelHubRequest(
        evalscript=EVALSCRIPT_TRUE_COLOR,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=(start_date, end_date),
                mosaicking_order=MosaickingOrder.LEAST_CC,
                maxcc=0.30,
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=(size, size),
        config=config,
    )

    try:
        data = request.get_data()
    except Exception as exc:
        raise RuntimeError(f"Sentinel-2 request failed: {exc}") from exc
    if not data or data[0] is None:
        raise RuntimeError("Sentinel-2 request returned no data")

    img = data[0].astype(np.float32)
    if img.ndim != 3 or img.shape[2] < 6:
        raise RuntimeError("Unexpected Sentinel-2 data shape")
    # Guard against empty/nodata tiles that appear all-black in UI.
    if float(np.std(img[:, :, 0:3])) < 1e-6:
        raise RuntimeError("Sentinel-2 tile has near-zero dynamic range")

    rgb = _normalize_unit(img[:, :, 0:3])
    b08 = _normalize_unit(img[:, :, 3])
    b11 = _normalize_unit(img[:, :, 4])
    b12 = _normalize_unit(img[:, :, 5])

    # Estimate pixel area based on bbox size and requested resolution
    m_per_deg_lat, m_per_deg_lon = _meters_per_degree(lat)
    width_m = (bbox_vals[2] - bbox_vals[0]) * m_per_deg_lon
    height_m = (bbox_vals[3] - bbox_vals[1]) * m_per_deg_lat
    pixel_size_x = max(width_m / size, 1.0)
    pixel_size_y = max(height_m / size, 1.0)
    pixel_area_m2 = float(pixel_size_x * pixel_size_y)

    return {
        "rgb": rgb,
        "B08": b08,
        "B11": b11,
        "B12": b12,
        "bbox": bbox_vals,
        "radius_km": radius_km,
        "pixel_area_m2": pixel_area_m2,
        "pixel_size_m": float((pixel_size_x + pixel_size_y) / 2.0),
    }
