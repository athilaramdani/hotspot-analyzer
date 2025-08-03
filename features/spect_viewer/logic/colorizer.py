# =====================================================================
# features\spect_viewer\logic\colorizer.py – FIXED LABEL↔PALETTE ORDER
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
_HOTSPOT_PALLETTE: List[List[int]] = [
    [0,   0,   0],   # 0  – background  (hitam)
    [255, 0,  0], # 1  – Abnormal
    [255,   241, 188], # 2  – Normal
]
# fmt: on


_LABELS = list(range(len(_PALETTE)))  # [0, 1, ..., 12]
_HOTSPOT_LABELS = list(range(len(_HOTSPOT_PALLETTE)))  # [0, 1, 2]
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

def label_mask_to_hotspot_rgb(mask: np.ndarray) -> np.ndarray:
    """mask uint8 (H×W) → RGB ndarray (H×W×3) untuk hotspot."""
    h, w = mask.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for l in _HOTSPOT_LABELS:
        rgb[mask == l] = _HOTSPOT_PALLETTE[l]
    return rgb

def label_new_mask_to_hotspot_rgb(mask: np.ndarray) -> np.ndarray:
    """
    Convert a label mask to RGB colors for hotspot visualization.
    
    Args:
        mask: Input mask - can be either:
              - 2D grayscale array with values (0, 64, 128, 255)
              - 3D RGB array (will be converted to grayscale first)
    
    Returns:
        np.ndarray: RGB array with shape (H, W, 3)
    """
    # Check if mask is already 3D (RGB)
    if len(mask.shape) == 3:
        # If it's already RGB, check if it's already properly colored
        if mask.shape[2] == 3:
            # Convert RGB to grayscale to get the label values
            # Using standard RGB to grayscale conversion
            grayscale_mask = np.dot(mask[...,:3], [0.299, 0.587, 0.114])
            
            # Round to nearest expected label values
            unique_vals = np.unique(grayscale_mask)
            
            # If the unique values suggest it's already a colored mask, return as is
            if len(unique_vals) > 4:  # More than 4 unique values suggests it's colored
                return mask.astype(np.uint8)
            
            # Otherwise, treat the first channel as the label mask
            mask = mask[:, :, 0]
    
    # Now we have a 2D mask
    h, w = mask.shape
    
    # Create RGB output array
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    
    # Define colors
    background_color = np.array([0, 0, 0])        # Black for background (0)
    unknown_color = np.array([255, 241, 188])     # Light cream for unknown (64)
    normal_color = np.array([255, 241, 188])      # Light cream for normal (128)
    hotspot_color = np.array([255, 0, 0])         # Red for hotspot (255)
    
    # Apply colors based on mask values
    rgb[mask == 0] = background_color    # Background
    rgb[mask == 64] = unknown_color      # Unknown
    rgb[mask == 128] = normal_color      # Normal
    rgb[mask == 255] = hotspot_color     # Hotspot/Abnormal
    
    return rgb

def save_hotspot_colored(mask: np.ndarray, save_path: Path) -> None:
    """Simpan mask hotspot sebagai gambar berwarna."""
    Image.fromarray(label_mask_to_hotspot_rgb(mask)).save(save_path)

