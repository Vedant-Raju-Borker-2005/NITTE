"""
EN02 v3 — False Positive Reduction Layer
Applied AFTER U-Net segmentation, BEFORE emission calculation.

Strategy (in order):
  1. Remove small blobs below area threshold  → kills noise specks
  2. Remove low-intensity regions             → kills reflectance artefacts
  3. Morphological opening                   → smooths ragged edges

All parameters are tunable via config.py — no magic numbers here.
"""

from __future__ import annotations
import numpy as np
import cv2
from typing import Tuple

from ai.config import FP_MIN_BLOB_AREA, FP_MIN_INTENSITY


def filter_false_positives(
    mask: np.ndarray,
    band: np.ndarray,
    min_blob_area: int   = FP_MIN_BLOB_AREA,
    min_intensity:  float = FP_MIN_INTENSITY,
    apply_morph:    bool  = True,
) -> Tuple[np.ndarray, dict]:
    """
    Remove likely false-positive plume regions from a binary mask.

    Parameters
    ----------
    mask          : uint8 ndarray (256×256), values 0 or 255
    band          : uint8 ndarray (256×256) — simulated CH₄ absorption band
    min_blob_area : minimum connected-component area in pixels to keep
    min_intensity : minimum mean band absorption depth to keep a region
    apply_morph   : if True, apply morphological opening after filtering

    Returns
    -------
    (filtered_mask, report) where report is a dict describing what was removed
    """
    assert mask.ndim == 2, "mask must be 2-D"
    assert band.ndim == 2, "band must be 2-D (grayscale)"

    working  = mask.copy()
    removed  = {"small_blobs": 0, "low_intensity": 0, "morph_cleaned": False}

    # ── Step 1: Remove small blobs ────────────────────────────────────────────
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        working, connectivity=8
    )
    for lbl in range(1, n_labels):          # label 0 = background
        area = stats[lbl, cv2.CC_STAT_AREA]
        if area < min_blob_area:
            working[labels == lbl] = 0
            removed["small_blobs"] += 1

    # ── Step 2: Remove low-intensity regions ──────────────────────────────────
    # Recompute components after step 1
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        working, connectivity=8
    )
    # Band: lower pixel value = more absorption = more likely real methane
    absorption = 255.0 - band.astype(np.float32)  # invert so high = strong

    for lbl in range(1, n_labels):
        region_mask   = (labels == lbl)
        mean_abs      = float(np.mean(absorption[region_mask]))
        if mean_abs < min_intensity:
            working[region_mask] = 0
            removed["low_intensity"] += 1

    # ── Step 3: Morphological opening (remove thin noise bridges) ────────────
    if apply_morph and np.any(working > 0):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        working = cv2.morphologyEx(working, cv2.MORPH_OPEN, kernel)
        removed["morph_cleaned"] = True

    total_removed = removed["small_blobs"] + removed["low_intensity"]
    removed["total_components_removed"] = total_removed
    removed["plume_pixels_remaining"]   = int(np.sum(working > 0))

    return working, removed


# ── Quick self-test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    # Synthetic test: large real plume + several noise specks
    mask = np.zeros((256, 256), dtype=np.uint8)
    band = np.full((256, 256), 180, dtype=np.uint8)   # moderate absorption

    # Real plume — large, high absorption
    cv2.ellipse(mask, (128, 128), (60, 40), 0, 0, 360, 255, -1)
    band[80:170, 70:190] = 80    # strong absorption in plume region

    # Fake specks — tiny, low absorption
    for x, y in [(20, 20), (240, 10), (10, 240), (230, 230)]:
        cv2.circle(mask, (x, y), 3, 255, -1)

    filtered, report = filter_false_positives(mask, band)
    print("Filter report:", json.dumps(report, indent=2))
    print(f"Original  plume pixels: {int(np.sum(mask > 0))}")
    print(f"Filtered  plume pixels: {report['plume_pixels_remaining']}")
    assert report["small_blobs"] == 4, "Should remove 4 noise specks"
    print("✓ All assertions passed")
