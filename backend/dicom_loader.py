# =====================================================================
# backend/dicom_loader.py
# ---------------------------------------------------------------------
"""
Utility untuk:
1.  Membaca file DICOM (single‑/multi‑frame)
2.  Mengekstrak frame‑frame sebagai ndarray
3.  Menentukan label view (Anterior / Posterior) untuk tiap frame
4.  Menyimpan frame ke PNG (format *_0000.png) agar cocok dg model

API:
    frames, meta = load_frames_and_metadata(path: str)
    png_path     = save_frame_to_png(frame: np.ndarray, view: str, uid: str)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pydicom
import matplotlib.pyplot as plt

# ------------------------------------------------------------------ config
PNG_ROOT = Path(__file__).resolve().parents[1] / "model" / "segmentation" / "nnUNet_raw"
PNG_ROOT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ helpers

def _label_from_meaning(meaning: str) -> str:
    up = meaning.upper()
    if "ANT" in up:
        return "Anterior"
    if "POST" in up:
        return "Posterior"
    return meaning.strip() or None


def _extract_labels(ds) -> list[str]:
    n = int(getattr(ds, "NumberOfFrames", 1))
    labels = [None] * n

    det_seq = getattr(ds, "DetectorInformationSequence", None)
    if det_seq:
        for idx, det in enumerate(det_seq):
            if not hasattr(det, "ViewCodeSequence"):
                continue
            meaning = str(det.ViewCodeSequence[0].CodeMeaning)
            name = _label_from_meaning(meaning)
            if name:
                labels[idx] = name

    # fallback
    for i, lbl in enumerate(labels):
        if not lbl:
            labels[i] = f"Frame {i+1}"
    # dedup
    seen: Dict[str, int] = {}
    for i, lbl in enumerate(labels):
        if lbl in seen:
            seen[lbl] += 1
            labels[i] = f"{lbl} #{seen[lbl]}"
        else:
            seen[lbl] = 1
    return labels

# ------------------------------------------------------------------ public

def load_frames_and_metadata(path: str) -> Tuple[Dict[str, np.ndarray], dict]:
    ds = pydicom.dcmread(Path(path))
    arr = ds.pixel_array
    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]

    labels = _extract_labels(ds)
    frames = {lbl: arr[i] for i, lbl in enumerate(labels)}

    meta = {
        "patient_id":    getattr(ds, "PatientID", ""),
        "patient_name":  str(getattr(ds, "PatientName", "")),
        "patient_birth": getattr(ds, "PatientBirthDate", ""),
        "patient_sex":   getattr(ds, "PatientSex", ""),
        "study_date":    getattr(ds, "StudyDate", ""),
    }
    return frames, meta


def save_frame_to_png(frame: np.ndarray, *, view: str, uid: str) -> Path:
    """Simpan ndarray → PNG dg format <View>_<UID>_0000.png & return path."""
    dataset_id = f"Dataset00{'1' if view == 'Anterior' else '2'}_BoneScan{view}"
    out_dir = PNG_ROOT / dataset_id / "imagesTs"
    out_dir.mkdir(parents=True, exist_ok=True)

    fname = f"{view}_{uid}_0000.png"
    fpath = out_dir / fname

    # normalize uint16 → uint8 kalau perlu
    if frame.dtype != np.uint8:
        frame_norm = (frame.astype(np.float32) - frame.min())
        frame_norm /= max(frame_norm.max(), 1)
        frame = (frame_norm * 255).astype(np.uint8)

    plt.imsave(fpath, frame, cmap="gray")
    return fpath
