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

# ------------------------------------------------------------------ env paths
ROOT    = Path(__file__).resolve().parents[1]
SEG_DIR = ROOT / "model" / "segmentation" / "nnUNet_results"

os.environ.setdefault("nnUNet_raw",          str(ROOT / "_nn_raw"))
os.environ.setdefault("nnUNet_preprocessed", str(ROOT / "_nn_pre"))
os.environ["nnUNet_results"] = str(SEG_DIR)

print(f"[DEBUG] nnUNet env set:")
print(f"        nnUNet_raw         = {os.environ['nnUNet_raw']}")
print(f"        nnUNet_preprocessed= {os.environ['nnUNet_preprocessed']}")
print(f"        nnUNet_results     = {os.environ['nnUNet_results']}")

# ------------------------------------------------------------------ helpers
def _make_predictor() -> nnUNetPredictor:
    use_cuda = torch.cuda.is_available()
    device   = torch.device("cuda:0" if use_cuda else "cpu")
    print(f"[SEG] CUDA available={use_cuda}, device={device}")

    params = dict(
        tile_step_size               = 0.5,
        use_gaussian                 = True,
        use_mirroring                = True,
        perform_everything_on_device = use_cuda,
        device                       = device,
        allow_tqdm                   = False,
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
        ds      = f"Dataset00{'1' if v=='Anterior' else '2'}_BoneScan{v}"
        ckptdir = SEG_DIR / ds / "nnUNetTrainer__nnUNetPlans__2d"
        print(f"[SEG] Loading model for {v} from {ckptdir}")

        pred = _make_predictor()
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
    print(f"[DEBUG] segment_image(view={view}, color={color})")
    print(f"[DEBUG]   img.shape={img.shape}, dtype={img.dtype}")

    # ------------ ensure 2‑D input
    if img.ndim == 3:
        img = img[..., 0]
        print("[DEBUG]   Using first channel of RGB")
    if img.ndim != 2:
        raise ValueError("img must be 2‑D or 3‑D RGB")

    # ------------ Rifqi preprocessing (normalize → invert → +13% contrast)
    img_norm = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    img_inv  = cv2.bitwise_not(img_norm)
    img_pp   = cv2.convertScaleAbs(img_inv, alpha=1.13, beta=0)
    img      = img_pp
    print("[DEBUG]   Applied Rifqi preprocessing: normalize→invert→contrast+13%")

    H0, W0 = img.shape
    print(f"[DEBUG]   Original size : {H0}×{W0}")

    # ------------ orientasi portrait + resize 512×128
    rotated = False
    if W0 > H0:
        img = np.rot90(img)
        rotated = True
        H0, W0 = img.shape
        print(f"[DEBUG]   Rotated to  : {H0}×{W0}")

    if (H0, W0) != (512, 128):
        img_rs = cv2.resize(img, (128, 512), interpolation=cv2.INTER_AREA)
    else:
        img_rs = img
    print(f"[DEBUG]   Resized to    : {img_rs.shape}")

    # ------------ inference
    model = _load_model(view)
    t0 = time.time()
    mask = _run_inference(img_rs, model)
    print(f"[SEG]   Inference time : {time.time()-t0:.2f}s")

    # ------------ restore size/orientation
    if (H0, W0) != (512, 128):
        mask = cv2.resize(mask, (W0, H0), interpolation=cv2.INTER_NEAREST)
    if rotated:
        mask = np.rot90(mask, k=-1)

    print(f"[DEBUG]   Final mask    : {mask.shape}, unique={np.unique(mask)}")

    if not color:
        return mask

    rgb = label_mask_to_rgb(mask)
    print(f"[DEBUG]   RGB shape     : {rgb.shape}")
    return mask, rgb
