# =====================================================================
# backend/segmenter.py  – DEBUG VERSION (patched with Rifqi preprocessing)
# ---------------------------------------------------------------------
"""
Segmentasi single‑frame ndarray (Bone Scan).

API
---
mask            = segment_image(img, view="Anterior")
mask, rgb_image = segment_image(img, view="Anterior", color=True)
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

# ===== FIXED: Import path configuration from core =====
from core.config.paths import SEGMENTATION_MODEL_PATH

# ------------------------------------------------------------------ try import colorizer
print("[DEBUG] Importing colorizer …")
try:
    from .colorizer import label_mask_to_rgb           # 13‑kelas palette
    COLORIZER_OK = True
    print("[DEBUG] Colorizer import - OK")
except Exception as e:
    COLORIZER_OK = False
    print(f"[DEBUG] Colorizer import failed: {e!r}")

    def label_mask_to_rgb(mask: np.ndarray) -> np.ndarray:   # fallback grayscale→RGB
        g = (mask.astype(np.float32) / max(1, mask.max()) * 255).astype(np.uint8)
        return np.stack([g, g, g], -1)

# ===== FIXED: Use centralized path configuration =====
# OLD CODE (BROKEN):
# ROOT    = Path(__file__).resolve().parents[1]
# SEG_DIR = ROOT / "model" / "segmentation" / "nnUNet_results"

# NEW CODE (FIXED):
SEG_DIR = SEGMENTATION_MODEL_PATH / "nnUNet_results"

# ===== FIXED: Update nnUNet environment paths =====
PROJECT_ROOT = SEGMENTATION_MODEL_PATH.parent.parent  # Go up to project root
os.environ.setdefault("nnUNet_raw",          str(PROJECT_ROOT / "_nn_raw"))
os.environ.setdefault("nnUNet_preprocessed", str(PROJECT_ROOT / "_nn_pre"))
os.environ["nnUNet_results"] = str(SEG_DIR)

print(f"[DEBUG] nnUNet env set:")
print(f"        nnUNet_raw         = {os.environ['nnUNet_raw']}")
print(f"        nnUNet_preprocessed= {os.environ['nnUNet_preprocessed']}")
print(f"        nnUNet_results     = {os.environ['nnUNet_results']}")
print(f"[DEBUG] SEGMENTATION_MODEL_PATH = {SEGMENTATION_MODEL_PATH}")
print(f"[DEBUG] SEG_DIR = {SEG_DIR}")

# ------------------------------------------------------------------ helpers
def _make_predictor() -> nnUNetPredictor:
    use_cuda = torch.cuda.is_available()
    device   = torch.device("cuda:0" if use_cuda else "cpu")
    _log(f"[INFO]  CUDA available: {torch.cuda.is_available()} – using {device}")
    print(f"[SEG] CUDA available={use_cuda}, device={device}")

    params = dict(
        tile_step_size               = 0.5,
        use_gaussian                 = True,
        use_mirroring                = True,
        perform_everything_on_device = use_cuda,
        device                       = device,
        allow_tqdm                   = True,
    )
    if "fp16" in inspect.signature(nnUNetPredictor).parameters:
        params["fp16"] = use_cuda
    return nnUNetPredictor(**params)


def _load_model(view: str) -> nnUNetPredictor:
    """Lazy‑load + cache nnUNet model untuk view tertentu."""
    cache: dict[str, nnUNetPredictor] = getattr(_load_model, "_cache", {})
    v = view.capitalize()
    if v not in ("Anterior", "Posterior"):
        raise ValueError("view must be 'Anterior' or 'Posterior'")


    if v not in cache:
        ds = "Dataset001_BoneRegion"
        ckptdir = SEG_DIR / ds / "nnUNetTrainer_50epochs__nnUNetPlans__2d"

        print(f"[SEG] Loading model for {v} from {ckptdir}")
        
        # ===== ADDED: Verify model path exists =====
        if not ckptdir.exists():
            raise FileNotFoundError(f"Model directory not found: {ckptdir}")
        
        dataset_json = ckptdir / "dataset.json"
        if not dataset_json.exists():
            raise FileNotFoundError(f"dataset.json not found: {dataset_json}")
        
        checkpoint_path = ckptdir / "fold_0" / "checkpoint_best.pth"
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"checkpoint_best.pth not found: {checkpoint_path}")
        
        print(f"[DEBUG] Model files verified:")
        print(f"        dataset.json: {dataset_json}")
        print(f"        checkpoint: {checkpoint_path}")

        pred = _make_predictor()
        _log(f"[INFO]  Loading segmentation model for {v} view…")
        pred.initialize_from_trained_model_folder(
            str(ckptdir), use_folds=(0,), checkpoint_name="checkpoint_best.pth"
        )
        cache[v] = pred
        _load_model._cache = cache           # simpan

    return cache[v]


def _run_inference(img_rs: np.ndarray, model: nnUNetPredictor) -> np.ndarray:
    """img_rs (512×128) → mask 512×128 (uint8)."""
    inp = torch.from_numpy(img_rs.astype(np.float32)[None, None]).to(model.device)
    print(f"[DEBUG]   Input tensor  : {inp.shape}")

    with torch.no_grad():
        logits = model.predict_sliding_window_return_logits(inp)   # (C,H,W) atau (C,1,H,W)
    print(f"[DEBUG]   Logits shape  : {logits.shape}")

    if logits.ndim == 4:                # (C, B=1, H, W)
        logits = logits[:, 0]
    mask = torch.argmax(logits, dim=0).cpu().numpy().astype(np.uint8)   # (H,W)

    print(f"[DEBUG]   Mask (raw)    : {mask.shape}, unique={np.unique(mask)}")
    return mask

# ------------------------------------------------------------------ public
def segment_image(
    img:   np.ndarray,
    *,
    view:  str,
    color: bool = False
) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
    """
    Parameters
    ----------
    img   : ndarray (H,W[,3])
    view  : 'Anterior' | 'Posterior'
    color : True → also return colored RGB segmentation
    """
    _log(f"[INFO]  Segmenting image – view={view}, color={color}")
    print(f"[DEBUG] segment_image(view={view}, color={color})")
    print(f"[DEBUG]   img.shape={img.shape}, dtype={img.dtype}")

    # ------------ ensure 2‑D input
    if img.ndim == 3:
        img = img[..., 0]
        print("[DEBUG]   Using first channel of RGB")
    if img.ndim != 2:
        raise ValueError("img must be 2‑D or 3‑D RGB")

   # ------------ Preprocessing: crop by contour + resize + CLAHE
    _log("[INFO]  Pre-processing: crop by contour → resize → CLAHE")
    if img.dtype != np.uint8:
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    print("[DEBUG]   Normalized image to uint8")

    gray = img
    _, thresh = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        raise ValueError("No contour found in the image.")

    x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
    cropped = gray[y:y+h, x:x+w]
    resized = cv2.resize(cropped, (1024, 256), interpolation=cv2.INTER_AREA)

    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    img_pp = clahe.apply(resized)

    img = img_pp
    print("[DEBUG]   Applied preprocessing: crop→resize(1024×256)→CLAHE")

    H0, W0 = img.shape
    print(f"[DEBUG]   Original size : {H0}×{W0}")

    # ------------ orientasi portrait + resize 512×128
    rotated = False
    if W0 > H0:
        img = np.rot90(img)
        rotated = True
        H0, W0 = img.shape
        print(f"[DEBUG]   Rotated to  : {H0}×{W0}")

    img_rs = img  # Sudah di-resize sebelumnya ke (256,1024)
    print(f"[DEBUG]   img_rs shape : {img_rs.shape}")


    # ------------ inference
    model = _load_model(view)
    t0 = time.time()
    mask = _run_inference(img_rs, model)
    
    print(f"[SEG]   Inference time : {time.time()-t0:.2f}s")
    elapsed = time.time() - t0
    _log(f"[INFO]  Inference finished in {elapsed:.2f}s – unique labels: {np.unique(mask)}")

    # ------------ restore size/orientation
    if (H0, W0) != (512, 128):
        mask = cv2.resize(mask, (W0, H0), interpolation=cv2.INTER_NEAREST)
    if rotated:
        mask = np.rot90(mask, k=-1)

    print(f"[DEBUG]   Final mask    : {mask.shape}, unique={np.unique(mask)}")

    if not color:
        return mask

    rgb = label_mask_to_rgb(mask)
    _log("[INFO]  segment overlay generated")
    print(f"[DEBUG]   RGB shape     : {rgb.shape}")
    return mask, rgb