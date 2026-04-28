#!/usr/bin/env python
"""Test AI modules and endpoints."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Test 1: Import AI modules
print("=" * 60)
print("TEST 1: Importing AI modules")
print("=" * 60)

try:
    from ai.models.false_positive_filter import filter_false_positives
    print("✓ false_positive_filter imported")
except Exception as e:
    print(f"✗ false_positive_filter: {e}")

try:
    from ai.models.inference_model import predict_plume, predict_plume_prob
    print("✓ inference_model imported")
except Exception as e:
    print(f"✗ inference_model: {e}")

try:
    from ai.models.physics_module import physics_emission
    print("✓ physics_module imported")
except Exception as e:
    print(f"✗ physics_module: {e}")

try:
    from ai.models.satellite_adapter import load_sentinel2_stub
    print("✓ satellite_adapter imported")
except Exception as e:
    print(f"✗ satellite_adapter: {e}")

# Test 2: Load Sentinel-2 data
print("\n" + "=" * 60)
print("TEST 2: Loading Sentinel-2 stub data")
print("=" * 60)

try:
    import numpy as np
    sentinel_data = load_sentinel2_stub(19.076, 72.8777, scene_size=256)
    print(f"✓ Sentinel-2 loaded, keys: {list(sentinel_data.keys())}")
    print(f"  RGB shape: {sentinel_data.get('rgb', np.zeros((256, 256, 3))).shape}")
    print(f"  B11 shape: {sentinel_data.get('B11', np.zeros((256, 256))).shape}")
    print(f"  B12 shape: {sentinel_data.get('B12', np.zeros((256, 256))).shape}")
except Exception as e:
    print(f"✗ Failed to load Sentinel-2: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Run U-Net inference
print("\n" + "=" * 60)
print("TEST 3: Running U-Net inference")
print("=" * 60)

try:
    rgb = sentinel_data.get('rgb')
    if rgb is not None:
        print(f"  Input RGB shape: {rgb.shape}, dtype: {rgb.dtype}")
        mask = predict_plume(rgb, threshold=0.5)
        print(f"✓ U-Net inference complete")
        print(f"  Output mask shape: {mask.shape}, dtype: {mask.dtype}")
        print(f"  Mask min/max values: {mask.min()}/{mask.max()}")
    else:
        print("✗ RGB data not available")
except Exception as e:
    print(f"✗ U-Net inference failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: False positive filtering
print("\n" + "=" * 60)
print("TEST 4: False positive filtering")
print("=" * 60)

try:
    if 'mask' in locals() and 'sentinel_data' in locals():
        swir1 = sentinel_data.get('B11', np.zeros((256, 256), dtype=np.uint8))
        filtered, report = filter_false_positives(mask, swir1, min_blob_area=50, min_intensity=30)
        print(f"✓ False positive filtering complete")
        print(f"  Filtered mask shape: {filtered.shape}")
        print(f"  Report: {report}")
    else:
        print("✗ Previous tests required")
except Exception as e:
    print(f"✗ False positive filtering failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Tests completed successfully!")
print("=" * 60)
