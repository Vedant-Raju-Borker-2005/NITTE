"""Time-series helpers for per-plant emission history."""

from __future__ import annotations

from typing import Iterable

import numpy as np

from ai.config import SEV_LOW


def append_emission(history: Iterable[float], value: float, max_points: int = 100) -> list[float]:
    """Append one reading and keep only the most recent `max_points` values."""
    out = [float(v) for v in history]
    out.append(max(0.0, float(value)))
    if len(out) > max_points:
        out = out[-max_points:]
    return out


def analyze_time_series(history: Iterable[float]) -> dict:
    """Return trend, anomaly, and persistence metrics for a history series."""
    vals = [max(0.0, float(v)) for v in history]
    if not vals:
        return {
            "trend": "stable",
            "trend_slope": 0.0,
            "persistence_score": 0.0,
            "anomaly_flag": False,
            "anomaly_zscore": 0.0,
            "window_mean": 0.0,
            "summary": "No historical emission readings yet.",
        }

    arr = np.asarray(vals, dtype=np.float32)
    mean = float(np.mean(arr))
    std = float(np.std(arr))

    if len(arr) >= 2:
        x = np.arange(len(arr), dtype=np.float32)
        slope = float(np.polyfit(x, arr, 1)[0])
    else:
        slope = 0.0

    if slope > 2.0:
        trend = "increasing"
    elif slope < -2.0:
        trend = "decreasing"
    else:
        trend = "stable"

    last = float(arr[-1])
    z = (last - mean) / std if std > 1e-9 else 0.0
    anomaly = bool(abs(z) >= 2.0)

    persistence = float(np.mean(arr >= float(SEV_LOW)) * 100.0)

    if trend == "increasing":
        summary = f"Emission rising (+{slope:.1f} kg/hr per pass). Active {persistence:.0f}% of monitored period."
    elif trend == "decreasing":
        summary = f"Emission falling ({slope:.1f} kg/hr per pass). Active {persistence:.0f}% of monitored period."
    else:
        summary = f"Emission stable around {mean:.1f} kg/hr. Active {persistence:.0f}% of monitored period."

    return {
        "trend": trend,
        "trend_slope": round(slope, 2),
        "persistence_score": round(persistence, 1),
        "anomaly_flag": anomaly,
        "anomaly_zscore": round(float(z), 2),
        "window_mean": round(mean, 2),
        "summary": summary,
    }

