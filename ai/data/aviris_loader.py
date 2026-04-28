import os

import cv2

try:
    from spectral import open_image
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise ImportError(
        "Missing dependency: spectral. Install with `pip install spectral` to read AVIRIS .hdr files."
    ) from exc

TARGET_SIZE = 256  # keep small for speed

def load_aviris_folder(folder, max_samples=None):
    samples = []

    files = [f for f in os.listdir(folder) if f.endswith(".hdr")]

    for hdr_file in files:
        base = hdr_file.replace(".hdr", "")

        hdr_path = os.path.join(folder, hdr_file)
        mask_path = os.path.join(folder, base + "_mask.png")

        if not os.path.exists(mask_path):
            continue

        img = open_image(hdr_path)
        data = img.load()

        rgb = data[:, :, :3]

        # Normalize
        rgb = (rgb - rgb.min()) / (rgb.max() - rgb.min() + 1e-6)

        # Load mask
        mask = cv2.imread(mask_path, 0)
        mask = (mask > 0).astype("float32")

        # 🔥 RESIZE BOTH
        rgb = cv2.resize(rgb, (TARGET_SIZE, TARGET_SIZE))
        mask = cv2.resize(mask, (TARGET_SIZE, TARGET_SIZE))

        samples.append((rgb, mask))
        if max_samples is not None and len(samples) >= max_samples:
            break

    print("Loaded samples:", len(samples))
    return samples
