from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import os
import tempfile
from typing import Dict, Optional, Tuple

import numpy as np

try:  # optional dependency
    import earthaccess  # type: ignore
except Exception:  # pragma: no cover
    earthaccess = None

try:  # optional dependency
    import xarray as xr  # type: ignore
except Exception:  # pragma: no cover
    xr = None


DEFAULT_PRODUCT = os.getenv("EMIT_PRODUCT", "EMITL2ARFL")
DEFAULT_DAYS = int(os.getenv("EMIT_LOOKBACK_DAYS", "60"))


def _date_range(days: int) -> Tuple[str, str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _bbox_from_radius(lat: float, lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    radius_km = max(float(radius_km), 1.0)
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def _login() -> None:
    if earthaccess is None:
        raise RuntimeError("earthaccess not installed")
    strategy = "environment" if os.getenv("EARTHDATA_USERNAME") or os.getenv("EARTHDATA_TOKEN") else "netrc"
    earthaccess.login(strategy=strategy)


def emit_availability(
    lat: float,
    lon: float,
    days: int = DEFAULT_DAYS,
    radius_km: float = 5.0,
    short_name: str = DEFAULT_PRODUCT,
) -> Dict[str, object]:
    """
    Check if EMIT granules are available for a location and recent date window.
    """
    if earthaccess is None:
        return {"available": False, "error": "earthaccess not installed"}
    _login()
    start, end = _date_range(days)
    bbox = _bbox_from_radius(lat, lon, radius_km)
    granules = earthaccess.search_data(short_name=short_name, temporal=(start, end), bounding_box=bbox)
    if not granules:
        return {"available": False, "short_name": short_name, "days": days}

    first = granules[0]
    granule_id = getattr(first, "data", {}).get("title") if hasattr(first, "data") else None
    if not granule_id and hasattr(first, "get"):
        granule_id = first.get("title")

    return {
        "available": True,
        "short_name": short_name,
        "days": days,
        "granule_id": granule_id,
    }


def _find_var(ds: "xr.Dataset", candidates: Tuple[str, ...]) -> Optional[str]:
    for name in candidates:
        if name in ds.variables:
            return name
    for name in ds.variables:
        lname = name.lower()
        for cand in candidates:
            if cand.lower() in lname:
                return name
    return None


def _get_wavelengths(ds: "xr.Dataset") -> Optional[np.ndarray]:
    name = _find_var(ds, ("wavelength", "wavelengths", "wave", "bands"))
    if name is None:
        return None
    arr = ds[name].values
    if arr.ndim > 1:
        arr = arr.flatten()
    return np.asarray(arr, dtype=np.float32)


def _band_index_from_wavelength(wavelengths: np.ndarray, target_nm: float) -> int:
    wl = np.asarray(wavelengths, dtype=np.float32)
    if np.nanmax(wl) < 20.0:  # microns
        wl = wl * 1000.0
    idx = int(np.nanargmin(np.abs(wl - target_nm)))
    return int(max(min(idx, len(wl) - 1), 0))


def _extract_window(
    cube: np.ndarray, center_row: int, center_col: int, size: int
) -> np.ndarray:
    half = size // 2
    r0 = max(center_row - half, 0)
    r1 = min(center_row + half, cube.shape[0])
    c0 = max(center_col - half, 0)
    c1 = min(center_col + half, cube.shape[1])
    window = cube[r0:r1, c0:c1, :]
    if window.shape[0] != size or window.shape[1] != size:
        pad_r = size - window.shape[0]
        pad_c = size - window.shape[1]
        window = np.pad(window, ((0, pad_r), (0, pad_c), (0, 0)), mode="edge")
    return window


def fetch_emit_hyperspectral(
    lat: float,
    lon: float,
    size: int = 256,
    days: int = DEFAULT_DAYS,
    radius_km: float = 5.0,
    short_name: str = DEFAULT_PRODUCT,
) -> Dict[str, object]:
    """
    Download EMIT NetCDF (L2A reflectance by default) and extract a local window.
    Returns:
      rgb, B08, B11, B12 (pseudo bands), pixel_size_m, pixel_area_m2, wavelengths, cube
    """
    if earthaccess is None or xr is None:
        raise RuntimeError("earthaccess/xarray not installed")

    _login()
    start, end = _date_range(days)
    bbox = _bbox_from_radius(lat, lon, radius_km)
    granules = earthaccess.search_data(short_name=short_name, temporal=(start, end), bounding_box=bbox)
    if not granules:
        raise RuntimeError("No EMIT granules available for location/date window")

    with tempfile.TemporaryDirectory() as tmpdir:
        files = earthaccess.download(granules[0], local_path=tmpdir)
        nc_files = [f for f in files if str(f).lower().endswith(".nc")]
        if not nc_files:
            raise RuntimeError("No NetCDF file in EMIT granule")
        nc_path = str(nc_files[0])

        try:
            ds = xr.open_dataset(nc_path, engine="netcdf4")
        except Exception:
            ds = xr.open_dataset(nc_path, engine="h5netcdf")

        var_name = _find_var(ds, ("reflectance", "rfl", "radiance", "rad"))
        if var_name is None:
            raise RuntimeError("No reflectance/radiance variable found in EMIT file")

        cube = ds[var_name].values
        if cube.ndim != 3:
            raise RuntimeError("Unexpected EMIT data shape")

        # Try to locate geolocation arrays for nearest pixel
        lat_name = _find_var(ds, ("latitude", "lat"))
        lon_name = _find_var(ds, ("longitude", "lon"))
        if lat_name and lon_name:
            lat_arr = ds[lat_name].values
            lon_arr = ds[lon_name].values
            if lat_arr.shape == cube.shape[:2] and lon_arr.shape == cube.shape[:2]:
                dist = (lat_arr - lat) ** 2 + (lon_arr - lon) ** 2
                center_row, center_col = np.unravel_index(int(np.argmin(dist)), dist.shape)
            else:
                center_row, center_col = cube.shape[0] // 2, cube.shape[1] // 2
        else:
            center_row, center_col = cube.shape[0] // 2, cube.shape[1] // 2

        window = _extract_window(cube, center_row, center_col, size)
        window = np.nan_to_num(window.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)

        wavelengths = _get_wavelengths(ds)
        if wavelengths is not None and len(wavelengths) >= 3:
            idx_1600 = _band_index_from_wavelength(wavelengths, 1600.0)
            idx_2200 = _band_index_from_wavelength(wavelengths, 2200.0)
            idx_2300 = _band_index_from_wavelength(wavelengths, 2300.0)
        else:
            # fallback to approximate indices if wavelength metadata missing
            bands = window.shape[2]
            idx_1600 = max(min(int(bands * 0.45), bands - 1), 0)
            idx_2200 = max(min(int(bands * 0.62), bands - 1), 0)
            idx_2300 = max(min(int(bands * 0.66), bands - 1), 0)

        b08 = window[:, :, idx_1600]
        b11 = window[:, :, idx_2200]
        b12 = window[:, :, idx_2300]

        def _norm(arr: np.ndarray) -> np.ndarray:
            arr = arr.astype(np.float32)
            mn = float(np.min(arr))
            mx = float(np.max(arr))
            if mx - mn < 1e-6:
                return np.zeros_like(arr, dtype=np.float32)
            return np.clip((arr - mn) / (mx - mn), 0.0, 1.0)

        rgb = np.stack([_norm(b12), _norm(b11), _norm(b08)], axis=2)

        pixel_size_m = float(ds.attrs.get("spatial_resolution", 60.0))
        pixel_area_m2 = float(pixel_size_m * pixel_size_m)

        return {
            "rgb": rgb,
            "B08": _norm(b08),
            "B11": _norm(b11),
            "B12": _norm(b12),
            "cube": window,
            "wavelengths": wavelengths,
            "pixel_size_m": pixel_size_m,
            "pixel_area_m2": pixel_area_m2,
            "short_name": short_name,
        }
