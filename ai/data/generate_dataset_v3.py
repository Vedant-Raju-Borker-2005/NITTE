"""
EN02 v3 — Scalable Synthetic Dataset Generator
New vs v2:
  - CLI --scale flag: small (60) / medium (500) / large (2000)
  - Three atmospheric condition modes: clear, haze, bright
  - Sensor noise simulation
  - Deterministic seed option for reproducibility
Run:
  python generate_dataset_v3.py                  # default: 60 samples, clear
  python generate_dataset_v3.py --scale medium   # 500 samples
  python generate_dataset_v3.py --scale large    # 2000 samples
  python generate_dataset_v3.py --scale small --seed 42
"""

import cv2
import numpy as np
import os
import random
import argparse
import time

# ── Defaults ─────────────────────────────────────────────────────────────────
SCALE_MAP = {"small": 60, "medium": 500, "large": 2000}
IMG_SIZE  = 256

OUTPUT_IMAGES = "dataset/images"
OUTPUT_MASKS  = "dataset/masks"

# ── Atmospheric condition presets ─────────────────────────────────────────────
ATMOS_CONDITIONS = {
    "clear": {
        "cloud_prob":      0.45,
        "haze_alpha":      0.0,
        "brightness_var":  0.0,
        "sensor_noise_std": 5,
    },
    "haze": {
        "cloud_prob":      0.2,
        "haze_alpha":      random.uniform(0.25, 0.55),   # haze intensity
        "brightness_var":  0.15,
        "sensor_noise_std": 12,
    },
    "bright": {
        "cloud_prob":      0.3,
        "haze_alpha":      0.0,
        "brightness_var":  0.35,   # overexposure / high-sun angle
        "sensor_noise_std": 8,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# IMAGE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_industrial_background(size: int = IMG_SIZE) -> np.ndarray:
    base = np.random.randint(30, 80, (size, size, 3), dtype=np.uint8)
    for _ in range(random.randint(4, 12)):
        x1, y1 = random.randint(0, size - 40), random.randint(0, size - 40)
        x2 = x1 + random.randint(10, 60)
        y2 = y1 + random.randint(10, 60)
        color = tuple(random.randint(60, 140) for _ in range(3))
        cv2.rectangle(base, (x1, y1), (x2, y2), color, -1)
    for _ in range(random.randint(2, 5)):
        pt1 = (random.randint(0, size), random.randint(0, size))
        pt2 = (random.randint(0, size), random.randint(0, size))
        cv2.line(base, pt1, pt2, (90, 90, 90), random.randint(1, 3))
    noise = np.random.randint(-20, 20, base.shape, dtype=np.int16)
    return np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def add_cloud_artifacts(img: np.ndarray, size: int = IMG_SIZE) -> np.ndarray:
    cloud = np.zeros_like(img, dtype=np.uint8)
    for _ in range(random.randint(2, 5)):
        x = random.randint(0, size)
        y = random.randint(0, size)
        r = random.randint(20, 80)
        cv2.circle(cloud, (x, y), r, (255, 255, 255), -1)
    cloud = cv2.GaussianBlur(cloud, (51, 51), 0)
    alpha = random.uniform(0.2, 0.45)
    return cv2.addWeighted(img, 1 - alpha, cloud, alpha, 0)


def apply_haze(img: np.ndarray, alpha: float) -> np.ndarray:
    """Simulate atmospheric haze — blend toward a bright grey layer."""
    haze = np.full_like(img, 200, dtype=np.uint8)
    return cv2.addWeighted(img, 1 - alpha, haze, alpha, 0)


def apply_brightness_variation(img: np.ndarray, factor: float) -> np.ndarray:
    """Simulate high sun angle / sensor gain variation."""
    scale = 1.0 + random.uniform(-factor, factor)
    return np.clip(img.astype(np.float32) * scale, 0, 255).astype(np.uint8)


def apply_sensor_noise(img: np.ndarray, std: int) -> np.ndarray:
    """Simulate CCD/CMOS sensor read noise."""
    noise = np.random.normal(0, std, img.shape).astype(np.int16)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def generate_wind_drift_plume(size: int = IMG_SIZE) -> np.ndarray:
    """Directional wind-drift plume with Gaussian morphology."""
    mask = np.zeros((size, size), dtype=np.float32)
    sx = random.randint(size // 4, 3 * size // 4)
    sy = random.randint(size // 4, 3 * size // 4)
    cv2.circle(mask, (sx, sy), random.randint(18, 35), 1.0, -1)

    wind_angle   = random.uniform(0, 360)
    wind_strength = random.uniform(1.5, 4.0)
    n_seg        = random.randint(3, 7)
    dx = int(np.cos(np.radians(wind_angle)) * 18 * wind_strength / n_seg)
    dy = int(np.sin(np.radians(wind_angle)) * 18 * wind_strength / n_seg)

    for i in range(1, n_seg + 1):
        cx  = int(np.clip(sx + dx * i, 5, size - 5))
        cy  = int(np.clip(sy + dy * i, 5, size - 5))
        rx  = max(5, random.randint(20, 50) - i * 3)
        ry  = max(4, random.randint(12, 30) - i * 2)
        intensity = max(0.2, 0.9 - i * 0.12)
        cv2.ellipse(mask, (cx, cy), (rx, ry), wind_angle, 0, 360, intensity, -1)

    blur_k = random.choice([31, 41])
    mask   = cv2.GaussianBlur(mask, (blur_k, blur_k), 0)
    return np.clip(mask, 0, 1)


def simulate_ch4_band(img: np.ndarray, mask_float: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    band = gray - (mask_float * 65.0)
    return np.clip(band, 0, 255).astype(np.uint8)


def pick_condition() -> str:
    return random.choices(
        list(ATMOS_CONDITIONS.keys()),
        weights=[0.50, 0.30, 0.20],    # clear most common
    )[0]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def generate(n_samples: int, seed: int | None = None) -> None:
    os.makedirs(OUTPUT_IMAGES, exist_ok=True)
    os.makedirs(OUTPUT_MASKS,  exist_ok=True)

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
        print(f"[EN02] Seed set to {seed} (reproducible run)")

    t0 = time.time()
    condition_counts: dict[str, int] = {k: 0 for k in ATMOS_CONDITIONS}

    for i in range(n_samples):
        condition_name = pick_condition()
        cond           = ATMOS_CONDITIONS[condition_name]
        condition_counts[condition_name] += 1

        img    = generate_industrial_background()
        mask_f = generate_wind_drift_plume()

        # Atmospheric pipeline (order matters)
        if cond["haze_alpha"] > 0:
            img = apply_haze(img, cond["haze_alpha"])
        if random.random() < cond["cloud_prob"]:
            img = add_cloud_artifacts(img)
        if cond["brightness_var"] > 0:
            img = apply_brightness_variation(img, cond["brightness_var"])
        img = apply_sensor_noise(img, cond["sensor_noise_std"])

        mask_b = (mask_f > 0.25).astype(np.uint8) * 255

        cv2.imwrite(f"{OUTPUT_IMAGES}/{i:05d}.png", img)
        cv2.imwrite(f"{OUTPUT_MASKS}/{i:05d}.png",  mask_b)

        if (i + 1) % max(1, n_samples // 10) == 0 or i == n_samples - 1:
            elapsed = time.time() - t0
            rate    = (i + 1) / elapsed
            print(f"  [{i+1:>5}/{n_samples}] {elapsed:.1f}s  ({rate:.0f} img/s)")

    print(f"\nDataset generation complete ✓")
    print(f"  Total:      {n_samples} samples")
    print(f"  Conditions: {condition_counts}")
    print(f"  Images  →   {OUTPUT_IMAGES}/")
    print(f"  Masks   →   {OUTPUT_MASKS}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="EN02 Dataset Generator v3")
    parser.add_argument(
        "--scale", choices=["small", "medium", "large"], default="small",
        help="small=60, medium=500, large=2000 samples (default: small)",
    )
    parser.add_argument(
        "--n", type=int, default=None,
        help="Override exact sample count (ignores --scale)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility",
    )
    args   = parser.parse_args()
    n      = args.n if args.n is not None else SCALE_MAP[args.scale]
    print(f"[EN02] Generating {n} samples (scale={args.scale}) …")
    generate(n, seed=args.seed)


if __name__ == "__main__":
    main()
