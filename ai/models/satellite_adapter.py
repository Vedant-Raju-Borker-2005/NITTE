"""
EN02 v3 — Satellite Data Adapter (Integration Stub)
====================================================
This module provides the interface between EN02 and real satellite data sources.

CURRENT STATE: Simulation stub — generates realistic pseudo-imagery.
PRODUCTION:    Replace `load_sentinel2_stub` body with ESA Sentinel Hub API calls.
               See migration guide at the bottom of this file.

Supported (stub) bands:
  B04  — Red        (665 nm)
  B08  — NIR        (842 nm)  — vegetation / cloud discrimination
  B11  — SWIR-1     (1610 nm) — methane proxy
  B12  — SWIR-2     (2190 nm) — hydrocarbon detection

Real CH₄ retrieval uses the ratio B12/B11 (SWIR ratio technique),
which correlates with XCH₄ column concentration as measured by TROPOMI.
"""

from __future__ import annotations

from typing import Dict

import cv2
import numpy as np

from ai.config import IMG_SIZE, MODEL_THRESHOLD


# ── Public API ────────────────────────────────────────────────────────────────

def load_sentinel2_stub(lat: float, lon: float,
                        scene_size: int = 256) -> Dict[str, np.ndarray]:
    """
    Simulate a Sentinel-2 multi-band acquisition over a given coordinate.

    Parameters
    ----------
    lat, lon   : geographic centre of the tile (decimal degrees)
    scene_size : output pixel dimensions (default 256 — matches model input)

    Returns
    -------
    dict with keys: "B04", "B08", "B11", "B12", "rgb", "swir_ratio"
      All values are uint8 ndarray of shape (scene_size, scene_size).
      "rgb"        — false-colour composite (B08/B04/B03 style)
      "swir_ratio" — B12/B11 ratio normalised to 0-255 (methane proxy)

    ─────────────────────────────────────────────────────────────────────────────
    PRODUCTION MIGRATION — replace this function body with:

        from sentinelhub import SHConfig, BBox, CRS, SentinelHubRequest, DataCollection, MimeType
        config = SHConfig()
        config.sh_client_id     = os.environ["SH_CLIENT_ID"]
        config.sh_client_secret = os.environ["SH_CLIENT_SECRET"]

        bbox = BBox(bbox=[lon-0.05, lat-0.05, lon+0.05, lat+0.05], crs=CRS.WGS84)
        request = SentinelHubRequest(
            evalscript=EVALSCRIPT_SWIR,   # see evalscripts/ folder
            input_data=[SentinelHubRequest.input_data(DataCollection.SENTINEL2_L2A)],
            responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
            bbox=bbox, size=[scene_size, scene_size], config=config,
        )
        bands = request.get_data()[0]           # shape: (H, W, n_bands)
        return _unpack_bands(bands, scene_size)
    ─────────────────────────────────────────────────────────────────────────────
    """
    # Seed RNG deterministically from lat/lon so same coordinate → same image
    seed = int((abs(lat) * 1000 + abs(lon) * 1000)) % (2**32)
    rng  = np.random.default_rng(seed)

    s = scene_size

    # ── Generate realistic-looking band values ────────────────────────────────
    # B04 Red: mostly soil / vegetation brightness
    B04 = _make_band(rng, s, base_mean=90,  noise=25, urban_patches=True)

    # B08 NIR: vegetation reflects strongly, urban low
    B08 = _make_band(rng, s, base_mean=110, noise=30, urban_patches=False)

    # B11 SWIR-1: methane absorption at 1610nm — plume depresses this band
    B11 = _make_band(rng, s, base_mean=80,  noise=20, urban_patches=True)

    # B12 SWIR-2: hydrocarbon signal — elevated in plume region
    B12 = _make_band(rng, s, base_mean=70,  noise=18, urban_patches=True)

    # Inject a synthetic plume: B11 dips, B12 rises
    plume_mask = _synthetic_plume(rng, s)
    B11 = np.clip(B11.astype(np.int16) - (plume_mask * 60).astype(np.int16), 0, 255).astype(np.uint8)
    B12 = np.clip(B12.astype(np.int16) + (plume_mask * 50).astype(np.int16), 0, 255).astype(np.uint8)

    # ── SWIR ratio (methane proxy) ─────────────────────────────────────────────
    b11f = B11.astype(np.float32) + 1.0     # avoid /0
    b12f = B12.astype(np.float32)
    ratio = np.clip((b12f / b11f) * 128, 0, 255).astype(np.uint8)

    # ── False-colour composite ─────────────────────────────────────────────────
    rgb = cv2.merge([B04, B08, B12])        # NIR-Red-SWIR false colour

    return {
        "B04":        B04,
        "B08":        B08,
        "B11":        B11,
        "B12":        B12,
        "rgb":        rgb,
        "swir_ratio": ratio,
    }


def bands_to_model_input(bands: Dict[str, np.ndarray]) -> np.ndarray:
    """
    Convert multi-band dict to single-channel model input.
    Uses the SWIR ratio as the primary detection channel
    (this is what the U-Net expects: a normalised 256×256 float32 array).
    """
    ratio = bands["swir_ratio"].astype(np.float32) / 255.0
    return ratio   # shape (256, 256), range [0, 1]


def fetch_sentinel_data(lat: float, lon: float) -> Dict[str, np.ndarray]:
    """Public data fetcher used by the pipeline manager."""
    return load_sentinel2_stub(lat=lat, lon=lon, scene_size=IMG_SIZE)


def compute_swir_ratio(b11: np.ndarray, b12: np.ndarray) -> np.ndarray:
    """Compute B12/B11 methane proxy ratio and normalize to uint8."""
    b11f = b11.astype(np.float32) + 1.0
    b12f = b12.astype(np.float32)
    ratio = np.clip((b12f / b11f) * 128.0, 0, 255)
    return ratio.astype(np.uint8)


def preprocess_bands(bands: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Apply denoise + contrast normalization to each numeric band."""
    cleaned: Dict[str, np.ndarray] = {}
    for key in ("B04", "B08", "B11", "B12", "swir_ratio"):
        arr = bands[key]
        arr = np.nan_to_num(arr, nan=float(np.nanmean(arr)) if np.isnan(arr).any() else 0.0)
        arr = arr.astype(np.uint8)
        arr = cv2.GaussianBlur(arr, (3, 3), 0)
        arr = _normalize_band(arr)
        cleaned[key] = arr

    rgb = bands.get("rgb")
    if rgb is None:
        rgb = cv2.merge([cleaned["B04"], cleaned["B08"], cleaned["B12"]])
    else:
        rgb = cv2.resize(rgb, (IMG_SIZE, IMG_SIZE))
    cleaned["rgb"] = rgb
    return cleaned


def generate_pseudo_labels(prob_map: np.ndarray, threshold: float = MODEL_THRESHOLD) -> np.ndarray:
    """Convert probability map to binary segmentation mask."""
    probs = prob_map.astype(np.float32)
    return (probs > float(threshold)).astype(np.uint8) * 255


def hybrid_detection(prob_map: np.ndarray, swir_ratio: np.ndarray) -> np.ndarray:
    """
    Merge ML prediction and SWIR thresholding for improved recall.
    Accepts either float probs [0,1] or pre-thresholded uint8 mask.
    """
    if prob_map.dtype == np.uint8 and set(np.unique(prob_map)).issubset({0, 255}):
        ml_mask = prob_map
    else:
        ml_mask = generate_pseudo_labels(prob_map, threshold=MODEL_THRESHOLD)

    swir_mask = (swir_ratio.astype(np.uint8) > 140).astype(np.uint8) * 255
    union = cv2.bitwise_or(ml_mask, swir_mask)

    # Smooth jagged boundaries and remove tiny bridge noise.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    union = cv2.morphologyEx(union, cv2.MORPH_CLOSE, kernel)
    union = cv2.morphologyEx(union, cv2.MORPH_OPEN, kernel)
    return union.astype(np.uint8)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _make_band(rng: np.random.Generator, size: int,
               base_mean: int, noise: int,
               urban_patches: bool) -> np.ndarray:
    """Generate a single realistic-looking satellite band."""
    base = rng.integers(
        max(0, base_mean - noise), min(255, base_mean + noise),
        size=(size, size), dtype=np.uint8,
    )
    if urban_patches:
        n = rng.integers(3, 8)
        for _ in range(n):
            x1 = int(rng.integers(0, size - 30))
            y1 = int(rng.integers(0, size - 30))
            w  = int(rng.integers(10, 50))
            h  = int(rng.integers(10, 50))
            val = int(rng.integers(60, 160))
            base[y1:y1+h, x1:x1+w] = val
    # Smooth slightly to remove salt-and-pepper look
    return cv2.GaussianBlur(base, (3, 3), 0)


def _normalize_band(arr: np.ndarray) -> np.ndarray:
    p2, p98 = np.percentile(arr, (2, 98))
    if p98 - p2 < 1e-6:
        return arr
    norm = np.clip((arr.astype(np.float32) - p2) * (255.0 / (p98 - p2)), 0, 255)
    return norm.astype(np.uint8)


def _synthetic_plume(rng: np.random.Generator, size: int) -> np.ndarray:
    """Return a float mask [0,1] for plume injection."""
    mask = np.zeros((size, size), dtype=np.float32)
    cx   = int(rng.integers(size // 3, 2 * size // 3))
    cy   = int(rng.integers(size // 3, 2 * size // 3))
    rx   = int(rng.integers(20, 55))
    ry   = int(rng.integers(15, 40))
    cv2.ellipse(mask, (cx, cy), (rx, ry), float(rng.integers(0, 180)), 0, 360, 1.0, -1)
    return cv2.GaussianBlur(mask, (31, 31), 0)


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    bands = load_sentinel2_stub(lat=19.076, lon=72.877)
    print("Bands returned:", list(bands.keys()))
    for k, v in bands.items():
        print(f"  {k}: shape={v.shape}, dtype={v.dtype}, "
              f"min={v.min()}, max={v.max()}, mean={v.mean():.1f}")
    model_in = bands_to_model_input(bands)
    print(f"\nModel input: shape={model_in.shape}, range=[{model_in.min():.3f}, {model_in.max():.3f}]")
    print("✓ Sentinel-2 stub working correctly")
