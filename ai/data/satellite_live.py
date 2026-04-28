import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Dict


SIM_BASELINE_PPB = 1800.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _simulate_ch4(lat: float, lon: float) -> Dict[str, object]:
    seed = int((abs(lat) * 1000 + abs(lon) * 1000)) % (2**32)
    # deterministic drift every 5 minutes
    bucket = int(time.time() // 300)
    rng = (seed + bucket) % 1000
    noise = (rng % 61) - 25  # -25..35
    ch4_ppb = max(1700.0, min(1950.0, SIM_BASELINE_PPB + noise))
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ch4_ppb": float(round(ch4_ppb, 1)),
        "timestamp": timestamp,
        "source": "sentinel5p-simulated",
    }


def _get_token(client_id: str, client_secret: str, token_url: str) -> str:
    data = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")

    req = urllib.request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Token response missing access_token")
    return token


def _extract_first_mean(obj):
    if isinstance(obj, dict):
        if "mean" in obj and isinstance(obj["mean"], (int, float)):
            return float(obj["mean"])
        for val in obj.values():
            found = _extract_first_mean(val)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for val in obj:
            found = _extract_first_mean(val)
            if found is not None:
                return found
    return None


def _fetch_ch4_stats(lat: float, lon: float) -> Dict[str, object]:
    client_id = os.getenv("S5P_CLIENT_ID")
    client_secret = os.getenv("S5P_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Missing S5P_CLIENT_ID or S5P_CLIENT_SECRET")

    token_url = os.getenv(
        "S5P_TOKEN_URL",
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
    )
    stats_url = os.getenv(
        "S5P_STATS_URL",
        "https://services.sentinel-hub.com/api/v1/statistics",
    )
    collection_id = os.getenv("S5P_COLLECTION_ID", "S5P_L2__CH4___")

    token = _get_token(client_id, client_secret, token_url)

    bbox_deg = float(os.getenv("S5P_BBOX_DEG", "0.05"))
    bbox = [lon - bbox_deg, lat - bbox_deg, lon + bbox_deg, lat + bbox_deg]

    now = _utc_now()
    start = now - timedelta(days=int(os.getenv("S5P_LOOKBACK_DAYS", "5")))

    evalscript = """//VERSION=3
function setup() {
  return {
    input: [\"CH4\", \"dataMask\"],
    output: [
      { id: \"default\", bands: 1, sampleType: \"FLOAT32\" },
      { id: \"dataMask\", bands: 1 }
    ]
  };
}

function evaluatePixel(sample) {
  return {
    default: [sample.CH4],
    dataMask: [sample.dataMask]
  };
}
"""

    body = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [
                {
                    "type": collection_id,
                    "dataFilter": {
                        "timeRange": {
                            "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
                    },
                }
            ],
        },
        "aggregation": {
            "timeRange": {
                "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "aggregationInterval": {"of": "P1D"},
            "evalscript": evalscript,
            "resx": 7000,
            "resy": 7000,
        },
        "calculations": {
            "default": {
                "statistics": {"default": {"percentiles": {"k": [50]}}}
            }
        },
    }

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(stats_url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    mean_val = _extract_first_mean(payload)
    if mean_val is None:
        raise RuntimeError("Unable to extract mean CH4 value from statistics response")

    return {
        "ch4_ppb": float(round(mean_val, 1)),
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "sentinel5p",
    }


def fetch_sentinel5p_ch4(lat: float, lon: float) -> Dict[str, object]:
    """
    Fetch Sentinel-5P methane data.
    Uses real Sentinel Hub Statistical API when credentials are provided.
    Falls back to simulation when real fetch fails.
    """
    mode = os.getenv("S5P_MODE", "auto").lower()

    if mode in ("real", "auto"):
        try:
            return _fetch_ch4_stats(lat, lon)
        except Exception as exc:
            fallback = _simulate_ch4(lat, lon)
            fallback["note"] = f"real fetch failed: {exc}"
            return fallback

    return _simulate_ch4(lat, lon)


def _sentinel5p_api_placeholder(lat: float, lon: float) -> Dict[str, object]:
    raise NotImplementedError(
        "Real Sentinel-5P API integration not configured. "
        "Set S5P_MODE=real and provide S5P_CLIENT_ID/S5P_CLIENT_SECRET."
    )
