"""
Patch pipeline_manager_v2.py so that SentinelHubUnavailableError
(package not installed) always triggers synthetic fallback,
even when require_live_satellite=True (strict mode).
"""
import re, os

path = os.path.join(os.path.dirname(__file__), "ai", "pipelines", "pipeline_manager_v2.py")
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

# 1. Ensure the import exists
if "SentinelHubUnavailableError" not in src:
    src = src.replace(
        "from ai.data.sentinel2_fetcher import fetch_sentinel2_image",
        "from ai.data.sentinel2_fetcher import fetch_sentinel2_image, SentinelHubUnavailableError",
        1
    )
    print("Added SentinelHubUnavailableError import.")
else:
    print("SentinelHubUnavailableError already imported.")

# 2. Patch the satellite fetch loop to catch SentinelHubUnavailableError separately
OLD_FETCH_LOOP = """        # Fetch real Sentinel-2 L2A bands if EMIT unavailable
        if bands is None:
            base_radius = float(radius_km) if radius_km is not None else 5.0
            radius_candidates = [base_radius, base_radius * 2.0, base_radius * 3.0]
            for rk in radius_candidates:
                try:
                    bands = fetch_sentinel2_image(lat, lon, size=IMG_SIZE, radius_km=rk)
                    image_source = \"Sentinel-2 L2A\"
                    break
                except Exception as exc:
                    last_exc = exc
        if bands is None:
            if bool(require_live_satellite):
                total_ms = round((time.perf_counter() - t_start) * 1000, 1)
                return {
                    \"error\": \"Live satellite data unavailable\",
                    \"details\": str(last_exc) if last_exc else \"No Sentinel-2 tiles returned.\",
                    \"plume_detected\": False,
                    \"image_source\": \"none\",
                    \"processing_time_ms\": total_ms,
                    \"pipeline_errors\": ctx.errors,
                }

            # Fallback to deterministic synthetic bands so UI can still visualize output.
            bands = _fallback_live_bands(lat, lon, size=IMG_SIZE, radius_km=radius_km)
            image_source = \"Synthetic fallback\"
            if last_exc is not None:
                ctx.errors.append(f\"LiveDataFallback: {last_exc}\")"""

NEW_FETCH_LOOP = """        # Fetch real Sentinel-2 L2A bands if EMIT unavailable
        _package_missing = False
        if bands is None:
            base_radius = float(radius_km) if radius_km is not None else 5.0
            radius_candidates = [base_radius, base_radius * 2.0, base_radius * 3.0]
            for rk in radius_candidates:
                try:
                    bands = fetch_sentinel2_image(lat, lon, size=IMG_SIZE, radius_km=rk)
                    image_source = \"Sentinel-2 L2A\"
                    break
                except SentinelHubUnavailableError as exc:
                    # Package not installed — no point retrying all radii
                    last_exc = exc
                    _package_missing = True
                    break
                except Exception as exc:
                    last_exc = exc
        if bands is None:
            # Only hard-fail in strict mode when sentinelhub IS installed but
            # satellite data is genuinely unreachable (auth/timeout/network error).
            # If the package simply isn't installed, always use synthetic fallback.
            if bool(require_live_satellite) and not _package_missing:
                total_ms = round((time.perf_counter() - t_start) * 1000, 1)
                return {
                    \"error\": \"Live satellite data unavailable\",
                    \"details\": str(last_exc) if last_exc else \"No Sentinel-2 tiles returned.\",
                    \"plume_detected\": False,
                    \"image_source\": \"none\",
                    \"processing_time_ms\": total_ms,
                    \"pipeline_errors\": ctx.errors,
                }

            # Fallback to deterministic synthetic bands so UI can still visualize output.
            bands = _fallback_live_bands(lat, lon, size=IMG_SIZE, radius_km=radius_km)
            image_source = \"Synthetic fallback\"
            if last_exc is not None:
                ctx.errors.append(f\"LiveDataFallback: {last_exc}\")"""

if OLD_FETCH_LOOP in src:
    src = src.replace(OLD_FETCH_LOOP, NEW_FETCH_LOOP, 1)
    print("Patched satellite fetch loop successfully.")
else:
    print("ERROR: Could not find old fetch loop block to patch!")
    # Show what is there
    idx = src.find("Fetch real Sentinel-2 L2A bands")
    print("Context around target:", repr(src[max(0,idx-50):idx+500]))

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("Done. Run syntax check...")
import ast
ast.parse(src)
print("Syntax OK.")
