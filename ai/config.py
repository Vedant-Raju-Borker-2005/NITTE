"""Central configuration for the IGNISIA AI pipeline."""

from __future__ import annotations

import os


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# Core model/runtime settings
IMG_SIZE = _get_int("EN02_IMG_SIZE", 256)
MODEL_THRESHOLD = _get_float("EN02_MODEL_THRESH", 0.45)

# Emission physics/scalars
WIND_SPEED = _get_float("EN02_WIND_SPEED", 5.0)
PIXEL_AREA = _get_float("EN02_PIXEL_AREA", 900.0)  # 30m x 30m
METHANE_GWP = _get_float("EN02_METHANE_GWP", 80.0)
GAS_PRICE_USD_PER_KG = _get_float("EN02_GAS_PRICE_USD_PER_KG", 0.85)

# Severity thresholds (kg/hr)
SEV_LOW = _get_float("EN02_SEV_LOW", 50.0)
SEV_MODERATE = _get_float("EN02_SEV_MODERATE", 200.0)
SEV_HIGH = _get_float("EN02_SEV_HIGH", 500.0)

# Attribution weighting
WIND_ALIGN_WEIGHT = _get_float("EN02_WIND_ALIGN_WEIGHT", 0.4)
DIST_WEIGHT = _get_float("EN02_DIST_WEIGHT", 0.6)

# False positive filter settings
FP_MIN_BLOB_AREA = _get_int("EN02_FP_MIN_AREA", 80)
FP_MIN_INTENSITY = _get_float("EN02_FP_MIN_INTENSITY", 22.0)

# Logging
LOG_LEVEL = os.getenv("EN02_LOG_LEVEL", "INFO")

