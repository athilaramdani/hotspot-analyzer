from backend.segmenter import segment_image

"""
Utility: load DICOM, kembalikan
    frames_dict : {label(str): ndarray}
    meta        : {patient_id, patient_name, …}
Label diturunkan dari tag ViewCodeSequence:
    * "ANT"  → "Anterior"
    * "POST" → "Posterior"
Jika tag tak ada, pakai CodeMeaning apa adanya;
kalau blank → "Frame <n>".
"""

import re
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pydicom


def _label_from_meaning(meaning: str) -> str:
    """Normalisasi nama frame."""
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

    # fallback: beri nama default
    for i, lbl in enumerate(labels):
        if not lbl:
            labels[i] = f"Frame {i+1}"
    # hindari duplikat label
    seen: Dict[str, int] = {}
    for i, lbl in enumerate(labels):
        if lbl in seen:
            seen[lbl] += 1
            labels[i] = f"{lbl} #{seen[lbl]}"
        else:
            seen[lbl] = 1
    return labels


def load_frames_and_metadata(path: str) -> Tuple[Dict[str, np.ndarray], dict]:
    ds = pydicom.dcmread(Path(path))
    arr = ds.pixel_array
    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]          # (1, H, W)

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

