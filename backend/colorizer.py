# =====================================================================
# backend/colorizer.py
# ---------------------------------------------------------------------
"""Konversi label mask (0‑12) menjadi gambar RGB sesuai palette."""
from __future__ import annotations

import numpy as np
from PIL import Image
from pathlib import Path

_PALETTE = [
    [176, 230, 13], [0, 151, 219], [126, 230, 225],
    [166, 55, 167], [230, 157, 180], [167, 110, 77],
    [121, 0, 24], [56, 65, 184], [230, 218, 0],
    [230, 114, 35], [12, 187, 62], [230, 182, 22],
    [0, 0, 0]
]
_LABELS = list(range(len(_PALETTE)))
_MAP = {l: _PALETTE[i] for i, l in enumerate(_LABELS)}


def label_mask_to_rgb(mask: np.ndarray) -> np.ndarray:
    """mask uint8 H×W → RGB ndarray H×W×3."""
    h, w = mask.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for l in _LABELS:
        rgb[mask == l] = _MAP[l]
    return rgb


def save_colored(mask: np.ndarray, save_path: Path) -> None:
    Image.fromarray(label_mask_to_rgb(mask)).save(save_path)