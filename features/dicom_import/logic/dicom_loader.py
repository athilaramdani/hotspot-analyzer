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

# Use centralized path configuration
from core.config.paths import SEGMENTATION_MODEL_PATH

# ------------------------------------------------------------------ config
PNG_ROOT = SEGMENTATION_MODEL_PATH / "nnUNet_raw"
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
    """
    Load DICOM frames and metadata
    
    Args:
        path: Path to DICOM file
        
    Returns:
        Tuple of (frames_dict, metadata_dict)
        frames_dict: {view_name: numpy_array}
        metadata_dict: Patient and study information
    """
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
        "modality":      getattr(ds, "Modality", ""),
        "series_description": getattr(ds, "SeriesDescription", ""),
    }
    return frames, meta


def save_frame_to_png(frame: np.ndarray, *, view: str, uid: str) -> Path:
    """
    Simpan ndarray → PNG dg format <View>_<UID>_0000.png & return path.
    
    Args:
        frame: Numpy array of the frame
        view: View name (Anterior/Posterior)
        uid: Unique identifier
        
    Returns:
        Path to saved PNG file
    """
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

def get_png_output_dir(view: str) -> Path:
    """
    Get output directory for PNG files based on view
    
    Args:
        view: View name (Anterior/Posterior)
        
    Returns:
        Path to output directory
    """
    dataset_id = f"Dataset00{'1' if view == 'Anterior' else '2'}_BoneScan{view}"
    return PNG_ROOT / dataset_id / "imagesTs"

def cleanup_temp_png_files(uid: str = None):
    """
    Clean up temporary PNG files
    
    Args:
        uid: Specific UID to clean up (optional, cleans all if None)
    """
    try:
        pattern = f"*_{uid}_*.png" if uid else "*.png"
        
        for view in ["Anterior", "Posterior"]:
            output_dir = get_png_output_dir(view)
            if output_dir.exists():
                for png_file in output_dir.glob(pattern):
                    try:
                        png_file.unlink()
                    except Exception as e:
                        print(f"Warning: Could not delete {png_file}: {e}")
                        
    except Exception as e:
        print(f"Warning: PNG cleanup failed: {e}")

def extract_patient_info_from_path(dicom_path: Path) -> Tuple[str, str]:
    """
    Extract patient ID and session code from DICOM file path
    Based on new directory structure: data/SPECT/[session_code]/[patient_id]/file.dcm
    
    Args:
        dicom_path: Path to DICOM file
        
    Returns:
        Tuple of (patient_id, session_code)
    """
    try:
        # Navigate up the path to find structure
        parts = dicom_path.parts
        
        # Look for SPECT in path
        spect_index = None
        for i, part in enumerate(parts):
            if part == "SPECT":
                spect_index = i
                break
        
        if spect_index is not None and len(parts) > spect_index + 2:
            # Structure: .../SPECT/[session_code]/[patient_id]/file.dcm
            session_code = parts[spect_index + 1]
            patient_id = parts[spect_index + 2]
            return patient_id, session_code
        
        # Fallback: try to extract from filename or parent directory
        parent_name = dicom_path.parent.name
        if "_" in parent_name:
            # Old structure compatibility
            parts = parent_name.split("_")
            if len(parts) >= 2:
                return parts[0], "_".join(parts[1:])
        
        return parent_name, "UNKNOWN"
        
    except Exception:
        return "UNKNOWN", "UNKNOWN"