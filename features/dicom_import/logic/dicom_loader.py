# features/dicom_import/logic/dicom_loader.py - Enhanced with view assignment support
"""
Enhanced DICOM loader yang mendukung:
1. Multiple detection methods untuk Anterior/Posterior 
2. User-assigned view labels
3. Fallback ke root ViewCodeSequence 
4. Proper naming convention dengan study date
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple, Optional

import numpy as np
import pydicom
import matplotlib.pyplot as plt

# Use centralized path configuration
from core.config.paths import SEGMENTATION_MODEL_PATH

# ------------------------------------------------------------------ config
PNG_ROOT = SEGMENTATION_MODEL_PATH / "nnUNet_raw"
PNG_ROOT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ helpers

def _label_from_meaning(meaning: str) -> Optional[str]:
    """Enhanced label detection dari meaning string"""
    if not meaning:
        return None
        
    up = meaning.upper()
    if "ANT" in up:
        return "Anterior"
    if "POST" in up:
        return "Posterior"
    return meaning.strip() or None


def _extract_labels_enhanced(ds) -> list[str]:
    """
    Enhanced label extraction dengan multiple fallback methods
    """
    n = int(getattr(ds, "NumberOfFrames", 1))
    labels = [None] * n

    # ✅ METHOD 1: DetectorInformationSequence (standard method)
    det_seq = getattr(ds, "DetectorInformationSequence", None)
    if det_seq:
        for idx, det in enumerate(det_seq):
            if not hasattr(det, "ViewCodeSequence"):
                continue
            meaning = str(det.ViewCodeSequence[0].CodeMeaning)
            name = _label_from_meaning(meaning)
            if name and idx < n:
                labels[idx] = name

    # ✅ METHOD 2: Root ViewCodeSequence (untuk DICOM kedua)
    elif hasattr(ds, "ViewCodeSequence"):
        view_seq = ds.ViewCodeSequence
        for idx, view_item in enumerate(view_seq):
            if idx >= n:
                break
            if hasattr(view_item, "CodeMeaning"):
                meaning = str(view_item.CodeMeaning)
                name = _label_from_meaning(meaning)
                if name:
                    labels[idx] = name

    # ✅ METHOD 3: ViewPosition tag
    elif hasattr(ds, "ViewPosition"):
        view_pos = str(ds.ViewPosition)
        if "\\" in view_pos:  # Multiple views separated by backslash
            positions = view_pos.split("\\")
            for idx, pos in enumerate(positions):
                if idx >= n:
                    break
                name = _label_from_meaning(pos)
                if name:
                    labels[idx] = name

    # ✅ METHOD 4: Smart fallback untuk bone scan
    all_none = all(lbl is None for lbl in labels)
    if all_none and n == 2:
        # Standard bone scan assumption: frame 0 = anterior, frame 1 = posterior
        labels = ["Anterior", "Posterior"]
        print(f"   🎯 Using bone scan assumption: [Anterior, Posterior]")
    elif all_none:
        # Generic fallback with frame numbers
        labels = [f"Frame {i+1}" for i in range(n)]
        print(f"   ⚠️  Generic fallback: {labels}")
    
    # ✅ DEDUPLICATION: Handle duplicate names
    seen: Dict[str, int] = {}
    for i, lbl in enumerate(labels):
        if lbl in seen:
            seen[lbl] += 1
            labels[i] = f"{lbl} #{seen[lbl]}"
        else:
            seen[lbl] = 1
    
    return labels

# Backward compatibility
_extract_labels = _extract_labels_enhanced

# ------------------------------------------------------------------ public

def load_frames_and_metadata_with_assignments(
    path: str, 
    view_assignments: Optional[Dict[int, str]] = None
) -> Tuple[Dict[str, np.ndarray], dict]:
    """
    Load DICOM frames with user-assigned view labels
    
    Args:
        path: Path to DICOM file
        view_assignments: Optional dict {frame_index: view_name}
        
    Returns:
        Tuple of (frames_dict, metadata_dict)
        frames_dict: {view_name: numpy_array}
        metadata_dict: Patient and study information
    """
    ds = pydicom.dcmread(Path(path))
    arr = ds.pixel_array
    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]

    # Use user assignments if provided, otherwise auto-detect
    if view_assignments:
        labels = []
        for i in range(arr.shape[0]):
            if i in view_assignments:
                labels.append(view_assignments[i])
            else:
                labels.append(f"Frame {i+1}")
    else:
        labels = _extract_labels_enhanced(ds)

    # ✅ ENFORCE ANTERIOR/POSTERIOR NAMING
    # Convert any Frame X to proper view names if possible
    normalized_labels = []
    for i, label in enumerate(labels):
        if label in ["Anterior", "Posterior"]:
            normalized_labels.append(label)
        elif "Frame" in label and len(labels) == 2:
            # For 2-frame case, assume Frame 1=Anterior, Frame 2=Posterior
            if i == 0:
                normalized_labels.append("Anterior")
            else:
                normalized_labels.append("Posterior")
        else:
            # Keep original but warn
            normalized_labels.append(label)
            print(f"   ⚠️  Non-standard view name: {label}")
    
    frames = {lbl: arr[i] for i, lbl in enumerate(normalized_labels)}

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


def load_frames_and_metadata(path: str) -> Tuple[Dict[str, np.ndarray], dict]:
    """
    Backward compatibility function - load frames with auto-detection only
    """
    return load_frames_and_metadata_with_assignments(path, None)


def validate_view_assignments(view_assignments: Dict[int, str]) -> Tuple[bool, List[str]]:
    """
    Validate view assignments untuk memastikan ada Anterior dan Posterior
    
    Args:
        view_assignments: Dict {frame_index: view_name}
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    views = set(view_assignments.values())
    
    if "Anterior" not in views:
        errors.append("Missing Anterior view assignment")
    
    if "Posterior" not in views:
        errors.append("Missing Posterior view assignment")
    
    # Check for duplicate assignments
    view_counts = {}
    for view in view_assignments.values():
        view_counts[view] = view_counts.get(view, 0) + 1
    
    for view, count in view_counts.items():
        if count > 1 and view in ["Anterior", "Posterior"]:
            errors.append(f"Multiple frames assigned to {view} view")
    
    return len(errors) == 0, errors


def save_frame_to_png(frame: np.ndarray, *, view: str, uid: str, study_date: str = None) -> Path:
    """
    Simpan ndarray → PNG dg format <View>_<UID>_<StudyDate>_0000.png & return path.
    
    Args:
        frame: Numpy array of the frame
        view: View name (MUST be "Anterior" or "Posterior")
        uid: Unique identifier
        study_date: Study date in YYYYMMDD format (optional)
        
    Returns:
        Path to saved PNG file
    """
    # ✅ ENFORCE proper view names
    if view not in ["Anterior", "Posterior"]:
        raise ValueError(f"View must be 'Anterior' or 'Posterior', got: {view}")
    
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
        view: View name (MUST be "Anterior" or "Posterior")
        
    Returns:
        Path to output directory
    """
    if view not in ["Anterior", "Posterior"]:
        raise ValueError(f"View must be 'Anterior' or 'Posterior', got: {view}")
        
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
        from datetime import datetime
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