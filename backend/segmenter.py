# backend/segmenter.py
"""
Lazy‑loaded nnUNet v2 segmenter **dengan logging rinci**.
Gunakan:  `mask = segment_image(img, view="Anterior")`
"""
from __future__ import annotations

from pathlib import Path
import inspect
import os
import sys
import cv2
import numpy as np
import torch
from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

# ------------------------------------------------------------------ env paths
ROOT = Path(__file__).resolve().parents[1]  # /hotspot‑analyzer
SEG_DIR = ROOT / "model" / "segmentation"  # anterior/ posterior

# Biarkan nnUNet "merasa" path sudah ter‑set.  
# Untuk inference kita hanya butuh nnUNet_results → lokasi model.
os.environ["nnUNet_raw"] = str(ROOT / "_nn_raw")              # dummy
os.environ["nnUNet_preprocessed"] = str(ROOT / "_nn_pre")      # dummy
os.environ["nnUNet_results"] = str(SEG_DIR)                    # **penting**

# ------------------------------------------------------------------ helper

def _make_predictor() -> nnUNetPredictor:
    """Buat nnUNetPredictor dengan kwargs yg kompatibel dgn versi runtime."""
    base = dict(
        tile_step_size=0.5,
        use_mirroring=True,
        perform_everything_on_device=torch.cuda.is_available(),
        device=torch.device("cuda:0" if torch.cuda.is_available() else "cpu"),
    )
    if "fp16" in inspect.signature(nnUNetPredictor).parameters:
        base["fp16"] = torch.cuda.is_available()
    return nnUNetPredictor(**base)


def _good_model_folder(view_folder: Path) -> Path:
    """Autodeteksi sub‑folder trainer/config jika ada (newer nnUNet layout)."""
    if (view_folder / "fold_0").is_dir():
        return view_folder  # old layout (our simplified copy)
    # newer layout: Dataset*/nnUNetTrainer__nnUNetPlans__2d/
    cands = list(view_folder.glob("**/fold_0"))
    if cands:
        return cands[0].parent
    raise FileNotFoundError(f"fold_0 not found inside {view_folder}")


def _load_predictor(view_folder: Path) -> nnUNetPredictor:
    view_folder = _good_model_folder(view_folder)
    print(f"[SEG] Loading model from '{view_folder}'", file=sys.stderr)

    pred = _make_predictor()

    # --- siapkan kwargs yg didukung -------------------------------------------------
    init_sig = inspect.signature(pred.initialize_from_trained_model_folder)
    init_kwargs: dict = {}

    if "use_folds" in init_sig.parameters:
        init_kwargs["use_folds"] = (0,)
    if "checkpoint_name" in init_sig.parameters:
        init_kwargs["checkpoint_name"] = "checkpoint_best.pth"
    if "configuration" in init_sig.parameters:
        init_kwargs["configuration"] = "2d"

    pred.initialize_from_trained_model_folder(str(view_folder), **init_kwargs)
    return pred


# ------------------------------------------------------------------ singleton cache
class _SegPool:
    _cache: dict[str, nnUNetPredictor] = {}

    def __getitem__(self, view: str) -> nnUNetPredictor:
        key = view.lower()
        if key not in ("anterior", "posterior"):
            raise ValueError("view must be 'Anterior' or 'Posterior'")
        if key not in self._cache:
            self._cache[key] = _load_predictor(SEG_DIR / key)
        return self._cache[key]


_SEG = _SegPool()

# ------------------------------------------------------------------ public API

def segment_image(img: np.ndarray, *, view: str) -> np.ndarray:
    """
    img  : ndarray H×W (uint8/uint16/RGB) – single frame
    view : 'Anterior' | 'Posterior'
    return : binary mask uint8, ukuran sama dgn input
    """

    # ---------------------------------------------------------------- 1. ambil 1‑channel
    if img.ndim == 3:
        img_c1 = img[..., 0]  # ambil channel 0
    elif img.ndim == 2:
        img_c1 = img
    else:
        raise ValueError(f"unexpected shape {img.shape}")

    H0, W0 = img_c1.shape  # simpan ukuran asli

    # ---------------------------------------------------------------- 2. pastikan portrait (H > W)
    rotated = False
    if W0 > H0:  # contoh: 1024×256 (landscape)
        img_c1 = np.rot90(img_c1)  # ke 256×1024
        rotated = True
        H0, W0 = img_c1.shape

    # ---------------------------------------------------------------- 3. resize persis 512×128
    if (H0, W0) != (512, 128):
        img_rs = cv2.resize(img_c1, (128, 512), interpolation=cv2.INTER_AREA)
    else:
        img_rs = img_c1

    img_rs = img_rs.astype(np.float32)[None, None, ...]  # (1,1,512,128)
    print(
        f"[SEG] view={view}  input={img_rs.shape}  model_dir={SEG_DIR / view.lower()}",
        file=sys.stderr,
    )

    # ---------------------------------------------------------------- 4. inference
    pred = _SEG[view]

    try:
        out = pred.predict_single_npy_array(img_rs, None, None)
    except Exception as e:
        # Propagasi dgn info tambahan supaya gampang dilacak
        raise RuntimeError(f"nnUNet inference failed: {e}") from e

    # ------ handle berbagai format return -----------------------------------------
    if out is None:
        raise RuntimeError(
            "predict_single_npy_array returned None → kemungkinan path model salah "
            "atau checkpoint rusak. Cek log di atas & struktur folder nnUNet_results."
        )
    if isinstance(out, tuple):
        mask = out[0]
    else:
        mask = out

    mask = (mask > 0).astype(np.uint8)  # (512,128)

    # ---------------------------------------------------------------- 5. kembalikan ukuran/orientasi
    if (H0, W0) != (512, 128):
        mask = cv2.resize(mask, (W0, H0), interpolation=cv2.INTER_NEAREST)
    if rotated:
        mask = np.rot90(mask, k=-1)  # rotate balik

    return mask