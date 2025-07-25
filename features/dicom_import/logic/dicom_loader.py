# =====================================================================
# backend/dicom_loader.py - Updated with study date support
# ---------------------------------------------------------------------
"""
Utility untuk:
1.  Membaca file DICOM (single‑/multi‑frame)
2.  Mengekstrak frame‑frame sebagai ndarray
3.  Menentukan label view (Anterior / Posterior) untuk tiap frame
4.  Menyimpan frame ke PNG (format *_0000.png) agar cocok dg model
5.  Extract study date dan patient info dengan naming convention baru

API:
    frames, meta = load_frames_and_metadata(path: str)
    png_path     = save_frame_to_png(frame: np.ndarray, view: str, uid: str)
    patient_id, session_code = extract_patient_info_from_path(path: Path)
    study_date = extract_study_date_from_dicom(path: Path)
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
    Load DICOM frames and metadata with enhanced study date extraction
    
    Args:
        path: Path to DICOM file
        
    Returns:
        Tuple of (frames_dict, metadata_dict)
        frames_dict: {view_name: numpy_array}
        metadata_dict: Patient and study information including study_date
    """
    ds = pydicom.dcmread(Path(path))
    arr = ds.pixel_array
    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]

    labels = _extract_labels(ds)
    frames = {lbl: arr[i] for i, lbl in enumerate(labels)}

    # Enhanced metadata extraction with study date
    meta = {
        "patient_id":    getattr(ds, "PatientID", ""),
        "patient_name":  str(getattr(ds, "PatientName", "")),
        "patient_birth": getattr(ds, "PatientBirthDate", ""),
        "patient_sex":   getattr(ds, "PatientSex", ""),
        "study_date":    getattr(ds, "StudyDate", ""),
        "series_date":   getattr(ds, "SeriesDate", ""),
        "study_time":    getattr(ds, "StudyTime", ""),
        "modality":      getattr(ds, "Modality", ""),
        "series_description": getattr(ds, "SeriesDescription", ""),
        "study_instance_uid": getattr(ds, "StudyInstanceUID", ""),
        "series_instance_uid": getattr(ds, "SeriesInstanceUID", ""),
    }
    
    # Ensure study_date is in proper format
    if meta["study_date"]:
        # Clean up study date format
        study_date = str(meta["study_date"]).replace('-', '').replace('/', '')
        if len(study_date) == 8 and study_date.isdigit():
            meta["study_date"] = study_date
        else:
            # Fallback to series date
            if meta["series_date"]:
                series_date = str(meta["series_date"]).replace('-', '').replace('/', '')
                if len(series_date) == 8 and series_date.isdigit():
                    meta["study_date"] = series_date
    
    # Final fallback: current date
    if not meta["study_date"] or len(meta["study_date"]) != 8:
        from datetime import datetime
        meta["study_date"] = datetime.now().strftime("%Y%m%d")
    
    return frames, meta


def save_frame_to_png(frame: np.ndarray, *, view: str, uid: str, study_date: str = None) -> Path:
    """
    Simpan ndarray → PNG dg format <View>_<UID>_<StudyDate>_0000.png & return path.
    
    Args:
        frame: Numpy array of the frame
        view: View name (Anterior/Posterior)
        uid: Unique identifier
        study_date: Study date in YYYYMMDD format (optional)
        
    Returns:
        Path to saved PNG file
    """
    dataset_id = f"Dataset00{'1' if view == 'Anterior' else '2'}_BoneScan{view}"
    out_dir = PNG_ROOT / dataset_id / "imagesTs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Include study date in filename if provided
    if study_date:
        fname = f"{view}_{uid}_{study_date}_0000.png"
    else:
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

def cleanup_temp_png_files(uid: str = None, study_date: str = None):
    """
    Clean up temporary PNG files
    
    Args:
        uid: Specific UID to clean up (optional, cleans all if None)
        study_date: Specific study date to clean up (optional)
    """
    try:
        if uid and study_date:
            pattern = f"*_{uid}_{study_date}_*.png"
        elif uid:
            pattern = f"*_{uid}_*.png"
        elif study_date:
            pattern = f"*_{study_date}_*.png"
        else:
            pattern = "*.png"
        
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

def extract_study_date_from_dicom(dicom_path: Path) -> str:
    """
    Extract study date from DICOM file
    
    Args:
        dicom_path: Path to DICOM file
        
    Returns:
        Study date in YYYYMMDD format, or current date if not found
    """
    try:
        ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
        study_date = getattr(ds, 'StudyDate', None)
        
        if study_date:
            # Ensure it's in YYYYMMDD format
            study_date = str(study_date).replace('-', '').replace('/', '')
            if len(study_date) == 8 and study_date.isdigit():
                return study_date
        
        # Fallback: use SeriesDate
        series_date = getattr(ds, 'SeriesDate', None)
        if series_date:
            series_date = str(series_date).replace('-', '').replace('/', '')
            if len(series_date) == 8 and series_date.isdigit():
                return series_date
        
        # Final fallback: current date
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d")
        
    except Exception as e:
        print(f"Warning: Could not extract study date from {dicom_path}: {e}")
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d")

def extract_all_dicom_metadata(dicom_path: Path) -> dict:
    """
    Extract comprehensive metadata from DICOM file including study date
    
    Args:
        dicom_path: Path to DICOM file
        
    Returns:
        Dictionary with comprehensive metadata
    """
    try:
        ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
        
        metadata = {
            # Patient information
            "patient_id": getattr(ds, "PatientID", ""),
            "patient_name": str(getattr(ds, "PatientName", "")),
            "patient_birth_date": getattr(ds, "PatientBirthDate", ""),
            "patient_sex": getattr(ds, "PatientSex", ""),
            "patient_age": getattr(ds, "PatientAge", ""),
            
            # Study information
            "study_date": getattr(ds, "StudyDate", ""),
            "study_time": getattr(ds, "StudyTime", ""),
            "study_instance_uid": getattr(ds, "StudyInstanceUID", ""),
            "study_description": getattr(ds, "StudyDescription", ""),
            "accession_number": getattr(ds, "AccessionNumber", ""),
            
            # Series information
            "series_date": getattr(ds, "SeriesDate", ""),
            "series_time": getattr(ds, "SeriesTime", ""),
            "series_instance_uid": getattr(ds, "SeriesInstanceUID", ""),
            "series_description": getattr(ds, "SeriesDescription", ""),
            "series_number": getattr(ds, "SeriesNumber", ""),
            
            # Image information
            "modality": getattr(ds, "Modality", ""),
            "manufacturer": getattr(ds, "Manufacturer", ""),
            "manufacturer_model": getattr(ds, "ManufacturerModelName", ""),
            "institution_name": getattr(ds, "InstitutionName", ""),
            "referring_physician": str(getattr(ds, "ReferringPhysicianName", "")),
            
            # Image characteristics
            "rows": getattr(ds, "Rows", 0),
            "columns": getattr(ds, "Columns", 0),
            "number_of_frames": getattr(ds, "NumberOfFrames", 1),
            "bits_allocated": getattr(ds, "BitsAllocated", 0),
            "bits_stored": getattr(ds, "BitsStored", 0),
            
            # Path information
            "file_path": str(dicom_path),
            "file_size": dicom_path.stat().st_size if dicom_path.exists() else 0,
        }
        
        # Clean up and validate study date
        if metadata["study_date"]:
            study_date = str(metadata["study_date"]).replace('-', '').replace('/', '')
            if len(study_date) == 8 and study_date.isdigit():
                metadata["study_date"] = study_date
            else:
                metadata["study_date"] = ""
        
        # If no study date, try series date
        if not metadata["study_date"] and metadata["series_date"]:
            series_date = str(metadata["series_date"]).replace('-', '').replace('/', '')
            if len(series_date) == 8 and series_date.isdigit():
                metadata["study_date"] = series_date
        
        # Final fallback for study date
        if not metadata["study_date"]:
            from datetime import datetime
            metadata["study_date"] = datetime.now().strftime("%Y%m%d")
        
        return metadata
        
    except Exception as e:
        print(f"Error extracting metadata from {dicom_path}: {e}")
        return {
            "patient_id": "UNKNOWN",
            "study_date": datetime.now().strftime("%Y%m%d"),
            "error": str(e)
        }

def validate_dicom_file(dicom_path: Path) -> bool:
    """
    Validate if file is a proper DICOM file
    
    Args:
        dicom_path: Path to file to validate
        
    Returns:
        True if valid DICOM, False otherwise
    """
    try:
        ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
        # Basic validation
        return hasattr(ds, 'PatientID') and hasattr(ds, 'Modality')
    except Exception:
        return False

def get_dicom_preview_info(dicom_path: Path) -> dict:
    """
    Get basic preview information from DICOM file for UI display
    
    Args:
        dicom_path: Path to DICOM file
        
    Returns:
        Dictionary with preview information
    """
    try:
        metadata = extract_all_dicom_metadata(dicom_path)
        
        # Format for display
        preview = {
            "patient_id": metadata.get("patient_id", "Unknown"),
            "patient_name": metadata.get("patient_name", "Unknown"),
            "study_date": metadata.get("study_date", "Unknown"),
            "modality": metadata.get("modality", "Unknown"),
            "series_description": metadata.get("series_description", "Unknown"),
            "image_size": f"{metadata.get('rows', 0)}x{metadata.get('columns', 0)}",
            "number_of_frames": metadata.get("number_of_frames", 1),
            "file_size_mb": round(metadata.get("file_size", 0) / (1024 * 1024), 2),
        }
        
        # Format study date for display
        if preview["study_date"] and len(preview["study_date"]) == 8:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(preview["study_date"], "%Y%m%d")
                preview["study_date_formatted"] = date_obj.strftime("%Y-%m-%d")
            except:
                preview["study_date_formatted"] = preview["study_date"]
        else:
            preview["study_date_formatted"] = "Unknown"
        
        return preview
        
    except Exception as e:
        return {
            "patient_id": "Error",
            "patient_name": "Error reading file",
            "study_date": "Unknown",
            "modality": "Unknown",
            "error": str(e)
        }