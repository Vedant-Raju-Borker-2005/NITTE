from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import torch
except Exception:  # pragma: no cover - optional runtime dependency
    torch = None


if torch is not None:
    class SimpleUNet(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.conv1 = torch.nn.Conv2d(3, 16, 3, padding=1)
            self.conv2 = torch.nn.Conv2d(16, 32, 3, padding=1)
            self.conv3 = torch.nn.Conv2d(32, 1, 1)

        def forward(self, x):
            x = torch.relu(self.conv1(x))
            x = torch.relu(self.conv2(x))
            x = torch.sigmoid(self.conv3(x))
            return x
else:
    class SimpleUNet:  # pragma: no cover - fallback stub
        pass


_MODEL: Optional[SimpleUNet] = None


def torch_available() -> bool:
    return torch is not None


def model_path() -> str:
    return str(Path(__file__).resolve().parent / "methane_model.pth")


def model_available() -> bool:
    return os.path.exists(model_path())


def _load_model() -> Optional[SimpleUNet]:
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    if torch is None:
        return None

    model = SimpleUNet()
    try:
        state = torch.load(model_path(), map_location="cpu")
        model.load_state_dict(state)
        model.eval()
        _MODEL = model
    except Exception:
        _MODEL = None
    return _MODEL


def predict_plume_prob(rgb: np.ndarray) -> np.ndarray:
    """
    Run SimpleUNet inference and return a probability map (H, W) in [0, 1].
    """
    if rgb is None or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("predict_plume expects an (H, W, 3) RGB array")

    if torch is None:
        raise RuntimeError("torch not available for model inference")

    model = _load_model()
    if model is None:
        raise RuntimeError("model weights not available at ai/models/methane_model.pth")

    img = rgb.astype(np.float32)
    if img.max() > 1.5:
        img = img / 255.0

    tensor = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0)
    with torch.no_grad():
        pred = model(tensor).squeeze().cpu().numpy()

    return np.clip(pred.astype(np.float32), 0.0, 1.0)


def predict_plume(rgb: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """
    Run SimpleUNet inference and return a binary mask (H, W).
    Output is uint8 with values {0, 255}.
    """
    pred = predict_plume_prob(rgb)
    thr = float(np.clip(threshold, 0.05, 0.95))
    mask = (pred >= thr).astype(np.uint8) * 255
    return mask
