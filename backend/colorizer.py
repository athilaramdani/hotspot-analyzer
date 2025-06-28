# =====================================================================
# backend/colorizer.py – FIXED LABEL↔PALETTE ORDER
# ---------------------------------------------------------------------
"""Konversi label mask 0‑12 → RGB ndarray sesuai palette.

Label ID ⇄ warna sudah disamakan dengan mapping yang dipakai Rifqi saat
membuat ground‑truth (background = label 0, skull = 1, dst.).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
from PIL import Image

# fmt: off
_PALETTE: List[List[int]] = [
    [0,   0,   0],   # 0  – background  (hitam)
    [176, 230,  13], # 1  – skull
    [0,   151, 219], # 2  – cervical vertebrae
    [126, 230, 225], # 3  – thoracic vertebrae
    [166,  55, 167], # 4  – rib
    [230, 157, 180], # 5  – sternum
    [167, 110,  77], # 6  – collarbone
    [121,   0,  24], # 7  – scapula
    [56,   65, 184], # 8  – humerus
    [230, 218,   0], # 9  – lumbar vertebrae
    [230, 114,  35], # 10 – sacrum
    [12,  187,  62], # 11 – pelvis
    [230, 182,  22], # 12 – femur
]
# fmt: on

_LABELS = list(range(len(_PALETTE)))  # [0, 1, ..., 12]
_MAP = {l: _PALETTE[l] for l in _LABELS}  # label → RGB triple


def label_mask_to_rgb(mask: np.ndarray) -> np.ndarray:
    """mask uint8 (H×W) → RGB ndarray (H×W×3)."""
    h, w = mask.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for l in _LABELS:
        rgb[mask == l] = _MAP[l]
    return rgb


def save_colored(mask: np.ndarray, save_path: Path) -> None:
    Image.fromarray(label_mask_to_rgb(mask)).save(save_path)
