import pydicom
import numpy as np
from pathlib import Path
from typing import Dict, Tuple

def _extract_labels(ds) -> list[str]:
    n = int(getattr(ds, "NumberOfFrames", 1))
    labels = [None] * n
    det_seq = getattr(ds, "DetectorInformationSequence", None)
    if det_seq:
        for idx, det in enumerate(det_seq):
            if hasattr(det, "ViewCodeSequence") and det.ViewCodeSequence:
                meaning = str(det.ViewCodeSequence[0].CodeMeaning).upper()
                if "ANT" in meaning: labels[idx] = "Anterior"
                elif "POST" in meaning: labels[idx] = "Posterior"
    for i, lbl in enumerate(labels):
        if not lbl: labels[i] = f"Frame {i+1}"
    seen: Dict[str, int] = {}; final_labels = []
    for lbl in labels:
        if lbl in seen: seen[lbl] += 1; final_labels.append(f"{lbl} #{seen[lbl]}")
        else: seen[lbl] = 1; final_labels.append(lbl)
    return final_labels

def load_frames_and_metadata(path: Path) -> Tuple[Dict[str, np.ndarray], dict]:
    ds = pydicom.dcmread(path)
    arr = ds.pixel_array
    if arr.ndim == 2: arr = arr[np.newaxis, ...]
    labels = _extract_labels(ds)
    frames = {lbl: arr[i] for i, lbl in enumerate(labels)}
    meta = {
        "patient_id": getattr(ds, "PatientID", "N/A"),
        "patient_name": str(getattr(ds, "PatientName", "N/A")),
        "patient_birth_date": getattr(ds, "PatientBirthDate", ""),
        "patient_sex": getattr(ds, "PatientSex", ""),
        "study_date": getattr(ds, "StudyDate", ""),
    }
    return frames, meta