from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.models.satellite_adapter import compute_swir_ratio  # noqa: E402


SCENE_TYPES = ("industrial", "desert", "vegetation", "urban", "mixed")


def normalized_noise(rng: np.random.Generator, size: int, scale: int = 32) -> np.ndarray:
    small = rng.random((max(2, size // scale), max(2, size // scale))).astype(np.float32)
    noise = cv2.resize(small, (size, size), interpolation=cv2.INTER_CUBIC)
    noise = cv2.GaussianBlur(noise, (0, 0), scale / 6)
    return np.clip(noise, 0.0, 1.0)


def make_background(rng: np.random.Generator, size: int, scene_type: str) -> Dict[str, np.ndarray]:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    xx /= max(size - 1, 1)
    yy /= max(size - 1, 1)
    texture = normalized_noise(rng, size, scale=int(rng.integers(18, 54)))
    gradient = 0.55 * xx + 0.45 * yy

    presets = {
        "industrial": (0.34, 0.40, 0.36, 0.32),
        "desert": (0.48, 0.35, 0.30, 0.28),
        "vegetation": (0.28, 0.62, 0.26, 0.22),
        "urban": (0.42, 0.38, 0.36, 0.34),
        "mixed": (0.38, 0.46, 0.33, 0.30),
    }
    b04_base, b08_base, b11_base, b12_base = presets[scene_type]

    b04 = b04_base + 0.22 * texture + 0.10 * gradient
    b08 = b08_base + 0.18 * texture + 0.08 * (1.0 - gradient)
    b11 = b11_base + 0.16 * texture + 0.06 * gradient
    b12 = b12_base + 0.15 * texture + 0.05 * gradient

    if scene_type in {"industrial", "urban", "mixed"}:
        for _ in range(int(rng.integers(8, 22))):
            x1 = int(rng.integers(0, max(1, size - 25)))
            y1 = int(rng.integers(0, max(1, size - 25)))
            w = int(rng.integers(size // 22, size // 5))
            h = int(rng.integers(size // 24, size // 6))
            val = float(rng.uniform(0.35, 0.72))
            for band, mult in ((b04, 1.0), (b08, 0.82), (b11, 0.95), (b12, 1.05)):
                band[y1 : y1 + h, x1 : x1 + w] = np.clip(val * mult, 0.0, 1.0)
        for _ in range(int(rng.integers(2, 8))):
            p1 = (int(rng.integers(0, size)), int(rng.integers(0, size)))
            p2 = (int(rng.integers(0, size)), int(rng.integers(0, size)))
            color = float(rng.uniform(0.35, 0.65))
            thickness = int(rng.integers(1, 4))
            for band in (b04, b08, b11, b12):
                cv2.line(band, p1, p2, color, thickness)

    return {
        "B04": np.clip(b04, 0.0, 1.0).astype(np.float32),
        "B08": np.clip(b08, 0.0, 1.0).astype(np.float32),
        "B11": np.clip(b11, 0.0, 1.0).astype(np.float32),
        "B12": np.clip(b12, 0.0, 1.0).astype(np.float32),
    }


def make_plume(rng: np.random.Generator, size: int) -> Tuple[np.ndarray, Dict[str, float]]:
    plume = np.zeros((size, size), dtype=np.float32)
    source_x = float(rng.uniform(size * 0.18, size * 0.82))
    source_y = float(rng.uniform(size * 0.18, size * 0.82))
    angle = float(rng.uniform(0, 2 * math.pi))
    length = float(rng.uniform(size * 0.18, size * 0.58))
    width = float(rng.uniform(size * 0.035, size * 0.12))
    strength = float(rng.uniform(0.18, 0.75))
    segments = int(rng.integers(5, 13))

    for i in range(segments):
        t = i / max(segments - 1, 1)
        cx = int(np.clip(source_x + math.cos(angle) * length * t, 0, size - 1))
        cy = int(np.clip(source_y + math.sin(angle) * length * t, 0, size - 1))
        rx = max(3, int(width * (1.15 + 1.8 * t) * rng.uniform(0.75, 1.2)))
        ry = max(3, int(width * (0.65 + 1.1 * t) * rng.uniform(0.75, 1.2)))
        intensity = strength * (1.0 - 0.70 * t)
        cv2.ellipse(plume, (cx, cy), (rx, ry), math.degrees(angle), 0, 360, intensity, -1)

    plume = cv2.GaussianBlur(plume, (0, 0), max(2.0, width / 2.5))
    plume = np.clip(plume / max(float(plume.max()), 1e-6), 0.0, 1.0) * strength
    metadata = {
        "source_x": round(source_x, 2),
        "source_y": round(source_y, 2),
        "wind_direction_deg": round(math.degrees(angle) % 360.0, 2),
        "relative_strength": round(strength, 4),
    }
    return plume.astype(np.float32), metadata


def add_clouds_and_noise(
    rng: np.random.Generator,
    bands: Dict[str, np.ndarray],
    size: int,
    cloud_probability: float,
) -> None:
    if rng.random() < cloud_probability:
        cloud = np.zeros((size, size), dtype=np.float32)
        for _ in range(int(rng.integers(1, 6))):
            center = (int(rng.integers(0, size)), int(rng.integers(0, size)))
            radius = int(rng.integers(size // 14, size // 4))
            cv2.circle(cloud, center, radius, float(rng.uniform(0.35, 0.9)), -1)
        cloud = cv2.GaussianBlur(cloud, (0, 0), size / 24)
        for key in bands:
            bands[key] = np.clip(bands[key] * (1.0 - 0.38 * cloud) + 0.78 * cloud, 0.0, 1.0)

    haze = float(rng.uniform(0.0, 0.24))
    gain = float(rng.uniform(0.82, 1.18))
    for key in bands:
        noisy = bands[key] * gain + haze
        noisy += rng.normal(0.0, rng.uniform(0.006, 0.025), noisy.shape).astype(np.float32)
        bands[key] = np.clip(noisy, 0.0, 1.0).astype(np.float32)


def render_rgb(bands: Dict[str, np.ndarray]) -> np.ndarray:
    rgb = np.stack([bands["B12"], bands["B11"], bands["B08"]], axis=2)
    rgb = np.clip(np.power(rgb, 0.85), 0.0, 1.0)
    return (rgb * 255).astype(np.uint8)


def write_sample(
    idx: int,
    out_dir: Path,
    size: int,
    rng: np.random.Generator,
    negative_ratio: float,
    save_bands: bool,
) -> Dict[str, object]:
    scene_type = str(rng.choice(SCENE_TYPES))
    bands = make_background(rng, size, scene_type)
    has_plume = bool(rng.random() > negative_ratio)

    plume_meta: Dict[str, float] = {}
    plume = np.zeros((size, size), dtype=np.float32)
    if has_plume:
        plume, plume_meta = make_plume(rng, size)
        # Methane absorption: B11 decreases while B12 increases in the plume.
        bands["B11"] = np.clip(bands["B11"] - plume * rng.uniform(0.16, 0.36), 0.0, 1.0)
        bands["B12"] = np.clip(bands["B12"] + plume * rng.uniform(0.10, 0.28), 0.0, 1.0)

    add_clouds_and_noise(rng, bands, size, cloud_probability=float(rng.uniform(0.05, 0.36)))

    rgb = render_rgb(bands)
    mask = (plume > max(0.08, float(np.percentile(plume[plume > 0], 45)) if np.any(plume > 0) else 1.0))
    mask_u8 = mask.astype(np.uint8) * 255
    stem = f"{idx:07d}"

    cv2.imwrite(str(out_dir / "images" / f"{stem}.png"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(out_dir / "masks" / f"{stem}.png"), mask_u8)

    if save_bands:
        swir_ratio = compute_swir_ratio((bands["B11"] * 255).astype(np.uint8), (bands["B12"] * 255).astype(np.uint8))
        np.savez_compressed(
            out_dir / "bands" / f"{stem}.npz",
            B04=bands["B04"],
            B08=bands["B08"],
            B11=bands["B11"],
            B12=bands["B12"],
            swir_ratio=swir_ratio.astype(np.uint8),
        )

    return {
        "id": stem,
        "scene_type": scene_type,
        "has_plume": has_plume,
        "plume_pixels": int(np.sum(mask)),
        **plume_meta,
    }


def generate(args: argparse.Namespace) -> None:
    out_dir = Path(args.output)
    for sub in ("images", "masks", "metadata"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    if args.save_bands:
        (out_dir / "bands").mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    random.seed(args.seed)
    t0 = time.time()
    metadata_path = out_dir / "metadata" / "samples.csv"

    with metadata_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = [
            "id",
            "scene_type",
            "has_plume",
            "plume_pixels",
            "source_x",
            "source_y",
            "wind_direction_deg",
            "relative_strength",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for idx in range(args.samples):
            row = write_sample(idx, out_dir, args.size, rng, args.negative_ratio, args.save_bands)
            writer.writerow({key: row.get(key, "") for key in fieldnames})
            if (idx + 1) % max(1, args.samples // 20) == 0 or idx + 1 == args.samples:
                elapsed = time.time() - t0
                print(f"{idx + 1:>8}/{args.samples} samples  {elapsed:6.1f}s  {(idx + 1) / max(elapsed, 1e-6):.1f}/s")

    summary = {
        "samples": args.samples,
        "size": args.size,
        "negative_ratio": args.negative_ratio,
        "save_bands": args.save_bands,
        "seed": args.seed,
        "layout": {
            "images": "PNG false-color B12/B11/B08 composites",
            "masks": "PNG binary plume masks",
            "bands": "Optional NPZ B04/B08/B11/B12/swir_ratio arrays",
            "metadata": "CSV with plume/source properties",
        },
    }
    (out_dir / "metadata" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Dataset written to {out_dir.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a large synthetic methane plume segmentation dataset.")
    parser.add_argument("--samples", type=int, default=5000, help="Number of image/mask pairs to generate.")
    parser.add_argument("--output", default="dataset", help="Output dataset directory.")
    parser.add_argument("--size", type=int, default=256, help="Square image size in pixels.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--negative-ratio", type=float, default=0.15, help="Fraction of no-plume images.")
    parser.add_argument("--save-bands", action="store_true", help="Save per-sample B04/B08/B11/B12 NPZ files.")
    return parser.parse_args()


if __name__ == "__main__":
    generate(parse_args())
