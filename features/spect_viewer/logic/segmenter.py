# =====================================================================
# backend/segmenter.py  –  MODERN VERSION
# ---------------------------------------------------------------------
"""
Segmentasi single-frame ndarray (Bone Scan).

API
---
mask            = predict_bone_mask(image)
mask, rgb_image = predict_bone_mask(image, to_rgb=True)
"""
from __future__ import annotations

import inspect
import os
import time
from pathlib import Path
from typing import Tuple, Union

import cv2
import numpy as np
import torch
from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor
from core.logger import _log

# ===== Import path configuration from core =====
from core.config.paths import SEGMENTATION_MODEL_PATH

# ------------------------------------------------------------------ try import colorizer
# (Bagian ini tidak diubah, tetap diperlukan untuk fallback)
try:
    from .colorizer import label_mask_to_rgb      # 13-kelas palette
    COLORIZER_OK = True
except Exception:
    COLORIZER_OK = False
    def label_mask_to_rgb(mask: np.ndarray) -> np.ndarray:  # fallback grayscale→RGB
        g = (mask.astype(np.float32) / max(1, mask.max()) * 255).astype(np.uint8)
        return np.stack([g, g, g], -1)

# ===== Use centralized path configuration =====
SEG_DIR = SEGMENTATION_MODEL_PATH / "nnUNet_results"

# ===== Update nnUNet environment paths =====
PROJECT_ROOT = SEGMENTATION_MODEL_PATH.parent.parent
os.environ.setdefault("nnUNet_raw",          str(PROJECT_ROOT / "_nn_raw"))
os.environ.setdefault("nnUNet_preprocessed", str(PROJECT_ROOT / "_nn_pre"))
os.environ["nnUNet_results"] = str(SEG_DIR)


# ------------------------------------------------------------------ HELPERS (ADAPTED FROM NEW LOGIC)
def create_predictor() -> nnUNetPredictor:
    """Creates the nnUNet predictor with standardized settings."""
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda:0" if use_cuda else "cpu")
    _log(f"[INFO]  CUDA available: {use_cuda} – using {device}")

    settings = dict(
        tile_step_size=0.5,
        use_gaussian=True,
        use_mirroring=True,
        perform_everything_on_device=use_cuda,
        device=device,
        allow_tqdm=True
    )
    if "fp16" in inspect.signature(nnUNetPredictor).parameters:
        settings["fp16"] = use_cuda
    return nnUNetPredictor(**settings)


def load_bone_model() -> nnUNetPredictor:
    """Lazy-load + cache the bone segmentation model."""
    # <-- RENAMED & SIMPLIFIED: from _load_model(view) to load_bone_model()
    if not hasattr(load_bone_model, "_cache"):
        load_bone_model._cache = {}
    cache = load_bone_model._cache

    if "bone" not in cache:
        dataset = "Dataset001_BoneRegion"
        model_path = SEG_DIR / dataset / "nnUNetTrainer_50epochs__nnUNetPlans__2d"
        _log(f"[INFO]  Loading bone segmentation model from {model_path}")

        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")

        predictor = create_predictor()
        predictor.initialize_from_trained_model_folder(
            str(model_path), use_folds=(0,), checkpoint_name="checkpoint_best.pth"
        )
        cache["bone"] = predictor
    return cache["bone"]


def run_prediction(image: np.ndarray, model: nnUNetPredictor) -> np.ndarray:
    """Runs sliding window inference on a pre-processed image."""
    # <-- RENAMED: from _run_inference to run_prediction
    tensor = torch.from_numpy(image.astype(np.float32)[None, None]).to(model.device)
    with torch.no_grad():
        logits = model.predict_sliding_window_return_logits(tensor)
    if logits.ndim == 4:
        logits = logits[:, 0]
    return torch.argmax(logits, dim=0).cpu().numpy().astype(np.uint8)


# ------------------------------------------------------------------ PUBLIC API (COMPLETELY REPLACED)
def predict_bone_mask(
    image: np.ndarray, *, to_rgb: bool = False
) -> np.ndarray: # Sekarang selalu mengembalikan satu nilai: np.ndarray
    """
    Performs bone segmentation on an input image using simple resize preprocessing.
    ... (docstring tidak berubah) ...
    Returns
    -------
    np.ndarray
        - `mask` (1024, 256) jika `to_rgb=False`.
        - `rgb_image` (1024, 256, 3) jika `to_rgb=True`.
    """
    _log(f"[INFO]  Segmenting bone mask (simple preprocessing)...")
    t_start = time.time()

    # --- Ensure 2-D input ---
    if image.ndim == 3:
        image = image[..., 0] # Use first channel if RGB
    if image.ndim != 2:
        raise ValueError("image must be 2-D or 3-D")

    # --- Preprocessing: Simple resize to model's input size ---
    resized = cv2.resize(image, (256, 1024), interpolation=cv2.INTER_AREA)

    # --- Inference ---
    model = load_bone_model()
    mask = run_prediction(resized, model) # Output shape is (1024, 256)

    # --- Return results ---
    elapsed = time.time() - t_start
    _log(f"[INFO]  Prediction finished in {elapsed:.2f}s. Mask shape: {mask.shape}")

    # ✅ PERBAIKAN LOGIKA RETURN
    if to_rgb:
        # Jika to_rgb=True, buat gambar berwarna dan kembalikan HANYA itu.
        return label_mask_to_rgb(mask)
    else:
        # Jika to_rgb=False, kembalikan mask mentah seperti biasa.
        return mask