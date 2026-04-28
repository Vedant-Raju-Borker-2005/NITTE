from __future__ import annotations

import math
import os
from typing import Dict

import numpy as np


def estimate_plume_height(plume_area_m2: float, wind_speed_ms: float) -> float:
    """
    Empirical plume height estimate (meters).
    Scales with sqrt(area) and wind speed, clamped for stability.
    """
    base = 40.0
    area_term = 0.002 * math.sqrt(max(plume_area_m2, 1.0))
    wind_term = 6.0 * max(wind_speed_ms, 0.0)
    height = base + area_term + wind_term
    return float(min(max(height, 20.0), 300.0))


def wind_profile(wind_speed_ms: float, height_m: float, z0: float = 0.3, z_ref: float = 10.0) -> float:
    """
    Log wind profile to estimate wind at plume height.
    """
    height_m = max(height_m, 1.0)
    z0 = max(z0, 0.01)
    z_ref = max(z_ref, 1.0)
    return float(wind_speed_ms * math.log(height_m / z0) / math.log(z_ref / z0))


def instrument_response(c_norm: np.ndarray, alpha: float = 2.0) -> np.ndarray:
    """
    Simple instrument response curve: higher absorption -> stronger response.
    """
    return 1.0 - np.exp(-alpha * np.clip(c_norm, 0.0, 1.0))


def radiative_transfer_to_column(c_norm: np.ndarray, height_m: float) -> np.ndarray:
    """
    Convert normalized SWIR proxy to methane column enhancement (mol/m^2).
    This is a simplified radiative-transfer surrogate.
    """
    scale = float(os.getenv("INVERSION_COLUMN_SCALE", "0.02"))
    return np.clip(c_norm, 0.0, 1.0) * height_m * scale


def invert_emission(
    plume_area_m2: float,
    c_norm: np.ndarray,
    plume_mask: np.ndarray,
    wind_speed_ms: float,
) -> Dict[str, float]:
    """
    Inversion-style emission estimate with plume height, wind profile,
    instrument response, and radiative transfer surrogate.
    Returns emission in kg/hr plus diagnostics.
    """
    plume_pixels = int(np.sum(plume_mask > 0))
    if plume_pixels == 0:
        return {
            "emission_kghr": 0.0,
            "plume_height_m": 0.0,
            "wind_eff_ms": 0.0,
            "column_kg_m2": 0.0,
            "column_mol_m2": 0.0,
        }

    height_m = estimate_plume_height(plume_area_m2, wind_speed_ms)
    wind_eff = wind_profile(wind_speed_ms, height_m)

    response = instrument_response(c_norm)
    column_mol_m2 = radiative_transfer_to_column(c_norm * response, height_m)

    # Methane molar mass: 0.016 kg/mol
    column_kg_m2 = column_mol_m2 * 0.016

    # Use mean column within plume
    col_mean = float(np.mean(column_kg_m2[plume_mask > 0]))

    # Characteristic plume length scale
    length_scale = max(math.sqrt(plume_area_m2), 1.0)

    # Mass in plume footprint
    total_mass = col_mean * plume_area_m2

    # Flux approximation (kg/s) -> kg/hr
    emission_kgs = total_mass * wind_eff / length_scale
    emission_kghr = emission_kgs * 3600.0
    scale = float(os.getenv("INVERSION_EMISSION_SCALE", "1.0"))
    emission_kghr *= max(scale, 0.0)

    return {
        "emission_kghr": float(emission_kghr),
        "plume_height_m": float(height_m),
        "wind_eff_ms": float(wind_eff),
        "column_kg_m2": float(col_mean),
        "column_mol_m2": float(np.mean(column_mol_m2[plume_mask > 0])),
        "emission_scale": float(scale),
    }


def ime_emission(
    c_norm: np.ndarray,
    plume_mask: np.ndarray,
    pixel_area_m2: float,
    wind_speed_ms: float,
) -> Dict[str, float]:
    """
    Integrated Mass Enhancement (IME) proxy.
    Q = (U_eff / L) * IME
    IME = sum(ΔΩ * A), where ΔΩ is column enhancement above background.
    """
    plume_pixels = int(np.sum(plume_mask > 0))
    if plume_pixels == 0:
        return {
            "emission_kghr": 0.0,
            "ime_kg": 0.0,
            "plume_area_m2": 0.0,
            "plume_length_m": 0.0,
            "u_eff_ms": 0.0,
            "background": 0.0,
        }

    plume_area_m2 = float(plume_pixels) * float(pixel_area_m2)
    plume_length_m = max(math.sqrt(plume_area_m2), 1.0)

    # Background from outside plume (median)
    outside = c_norm[plume_mask == 0]
    background = float(np.median(outside)) if outside.size > 0 else float(np.median(c_norm))
    enhancement = np.clip(c_norm - background, 0.0, None)

    # Proxy conversion: unitless -> kg/m2
    column_scale = float(os.getenv("IME_COLUMN_SCALE", "0.01"))
    ime_kg = float(np.sum(enhancement * float(pixel_area_m2) * column_scale))

    # Effective wind parameterization (linear, configurable)
    ueff_alpha = float(os.getenv("IME_UEFF_ALPHA", "1.0"))
    ueff_beta = float(os.getenv("IME_UEFF_BETA", "0.0"))
    u_eff = max(ueff_alpha * float(wind_speed_ms) + ueff_beta, 0.1)

    emission_kgs = (u_eff / plume_length_m) * ime_kg
    emission_kghr = emission_kgs * 3600.0

    return {
        "emission_kghr": float(emission_kghr),
        "ime_kg": float(ime_kg),
        "plume_area_m2": float(plume_area_m2),
        "plume_length_m": float(plume_length_m),
        "u_eff_ms": float(u_eff),
        "background": float(background),
        "column_scale": float(column_scale),
    }
