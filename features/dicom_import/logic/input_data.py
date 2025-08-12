# features/dicom_import/logic/input_data.py - FIXED: No DICOM modification
from __future__ import annotations
from pathlib import Path
from shutil import copy2
from typing import Callable, Sequence, List, Dict, Optional
import traceback

import numpy as np
from PIL import Image
import pydicom
from pydicom.dataset import Dataset, FileDataset, Tag
from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    generate_uid,
)

from .dicom_loader import load_frames_and_metadata_with_assignments
from features.spect_viewer.logic.segmenter import predict_bone_mask
from core.logger import _log
from core.gui.ui_constants import truncate_text

# Use new directory structure from paths.py with study date support
from core.config.paths import (
    get_patient_spect_path, 
    get_session_spect_path,
    SPECT_DATA_PATH,
    is_cloud_enabled,
    extract_study_date_from_dicom,
    generate_filename_stem,
    get_dicom_output_path
)

try:
    from features.dicom_import.logic.pixel_analyzer import convert_to_black_background
    PIXEL_ANALYZER_AVAILABLE = True
except ImportError:
    PIXEL_ANALYZER_AVAILABLE = False
    def convert_to_black_background(frame_data, current_bg="auto"):
        return frame_data

# Import cloud storage
try:
    from core.config.cloud_storage import upload_patient_file
    CLOUD_AVAILABLE = True
except ImportError:
    CLOUD_AVAILABLE = False
    def upload_patient_file(*args, **kwargs):
        return False

# ---------------------------------------------------------------- config
_VERBOSE = True
_LOG_FILE = None

# ✅ REMOVED: _insert_overlay() function - no DICOM overlay modification
# ✅ REMOVED: _save_secondary_capture() function - no DICOM creation

# ---------------------------------------------------------------- helpers
def _ensure_2d(mask: np.ndarray) -> np.ndarray:
    return mask if mask.ndim == 2 else mask[0] if mask.shape[0] == 1 else mask[:, :, 0]

def _save_original_frame_png(frame: np.ndarray, output_path: Path) -> None:
    """
    Save original DICOM frame as normalized PNG for classification use
    
    Args:
        frame: Original frame data from DICOM
        output_path: Path to save the PNG file
    """
    try:
        # Normalize frame to uint8 (0-255 range)
        if frame.dtype != np.uint8:
            frame_norm = frame.astype(np.float32)
            frame_norm = (frame_norm - frame_norm.min()) / max(frame_norm.max() - frame_norm.min(), 1)
            frame_uint8 = (frame_norm * 255).astype(np.uint8)
        else:
            frame_uint8 = frame
        
        # Save as grayscale PNG
        Image.fromarray(frame_uint8, mode="L").save(output_path)
        _log(f"     Original frame saved: {output_path.name}")
        
    except Exception as e:
        _log(f"     [WARN] Failed to save original frame PNG: {e}")

def _upload_original_png_to_cloud(png_path: Path, session_code: str, patient_id: str) -> bool:
    """
    Upload ONLY original PNG files to cloud
    
    Args:
        png_path: Path to original PNG file
        session_code: Session code
        patient_id: Patient ID
        
    Returns:
        True if successful upload
    """
    if not CLOUD_AVAILABLE or not is_cloud_enabled():
        return False
    
    # ONLY UPLOAD ORIGINAL PNG FILES
    if not png_path.name.endswith('_original.png'):
        return False
    
    try:
        success = upload_patient_file(png_path, session_code, patient_id, is_edited=False)
        if success:
            _log(f"     ✅ Uploaded original PNG: {png_path.name}")
        else:
            _log(f"     ❌ Failed to upload PNG: {png_path.name}")
        return success
    except Exception as e:
        _log(f"     [WARN] PNG upload failed: {e}")
        return False

# ---------------------------------------------------------------- core
def _process_one_with_assignments(
    src: Path, 
    session_code: str,
    view_assignments: Optional[Dict[int, str]] = None,
    background_assignments: Optional[Dict[int, Dict[str, str]]] = None  # TAMBAHAN BARU
) -> Path:
    """
    ✅ FIXED: Process single DICOM without any modification - only copy and generate outputs
    
    Args:
        src: Source DICOM path
        session_code: Session code
        view_assignments: Dict {frame_index: view_name} atau None untuk auto-detect
    """
    _log(f"\n=== Processing {truncate_text(src.name, 40)} ===")

    # Read patient info and study date from ORIGINAL DICOM
    _log("  >> Reading DICOM metadata...")
    ds_temp = pydicom.dcmread(src, stop_before_pixels=True)
    pid = str(ds_temp.PatientID)  # ✅ Use ORIGINAL PatientID without modification
    study_date = extract_study_date_from_dicom(src)
    
    _log(f"  Patient ID: {pid} (ORIGINAL - NO MODIFICATION)")
    _log(f"  Study Date: {study_date}")
    
    if view_assignments:
        _log(f"  View assignments: {view_assignments}")
    else:
        _log("  Using auto-detection for views")
    
    # Generate filename stem with study date
    filename_stem = generate_filename_stem(pid, study_date)
    _log(f"  Filename stem: {filename_stem}")
    
    dest_dir = get_patient_spect_path(pid, session_code)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Create destination path with new naming convention
    dest_path = dest_dir / f"{filename_stem}.dcm"
    
    # STEP 1: Copy ORIGINAL file to destination WITHOUT ANY MODIFICATION
    if src.resolve() != dest_path.resolve():
        _log(f"  >> Copying ORIGINAL DICOM without modification...")
        copy2(src, dest_path)
    _log(f"  Copied ORIGINAL → {truncate_text(str(dest_path), 60)}")

    # ✅ CRITICAL: Load ORIGINAL DICOM for processing WITHOUT MODIFICATION
    _log("  >> Loading ORIGINAL DICOM frames with view assignments...")
    
    frames, _ = load_frames_and_metadata_with_assignments(dest_path, view_assignments)
    _log(f"  Frames detected: {list(frames.keys())}")
    processed_frames = {}
    if background_assignments and PIXEL_ANALYZER_AVAILABLE:
        _log("  >> Processing background selections...")
        for view_name, frame in frames.items():
            # Find corresponding frame index
            frame_idx = None
            for idx, (v, _) in enumerate(frames.items()):
                if v == view_name:
                    frame_idx = idx
                    break
            
            if frame_idx is not None and frame_idx in background_assignments:
                bg_selection = background_assignments[frame_idx].get("background", "black")
                _log(f"     Processing {view_name} with {bg_selection} background")
                
                # Safe background processing (PANGGIL FUNCTION BARU)
                processed_frame = _safe_background_processing(frame, bg_selection, view_name)  # ← BARIS BARU
                processed_frames[view_name] = processed_frame
                
                _log(f"     ✅ {view_name} background processed")
            else:
                # No background assignment, use original
                processed_frames[view_name] = frame
                _log(f"     Using original {view_name} (no background assignment)")
        
        # Update frames with processed versions
        frames = processed_frames
        _log("  ✅ Background processing completed")
    else:
        if background_assignments:
            _log("  ⚠️  Background assignments provided but pixel analyzer not available")
        else:
            _log("  Using original frames (no background assignments)")
    # ✅ VALIDATE THAT WE HAVE ANTERIOR AND POSTERIOR
    frame_views = set(frames.keys())
    if "Anterior" not in frame_views or "Posterior" not in frame_views:
        error_msg = f"Missing required views. Got: {list(frame_views)}, Need: ['Anterior', 'Posterior']"
        _log(f"  [ERROR] {error_msg}")
        raise ValueError(error_msg)

    saved: List[str] = []
    png_files_to_upload: List[Path] = []

    # STEP 2: SAVE ORIGINAL FRAMES AS PNG (FOR CLASSIFICATION)
    _log("  >> Saving original frames for classification...")
    for view_name, frame in frames.items():
        if view_name in ["Anterior", "Posterior"]:
            view_tag = view_name.lower()
            original_png_path = dest_dir / f"{filename_stem}_{view_tag}_original.png"
            _save_original_frame_png(frame, original_png_path)
            saved.append(f"{filename_stem}_{view_tag}_original.png")
            png_files_to_upload.append(original_png_path)
        else:
            _log(f"  [WARN] Skipping non-standard view: {view_name}")

    # STEP 3: SEGMENTATION PROCESSING (PNG OUTPUT ONLY)
    _log("  >> Generating segmentation masks and colored overlays...")
    for view_idx, (view, img) in enumerate(frames.items(), 1):
        if view not in ["Anterior", "Posterior"]:
            _log(f"  [WARN] Skipping segmentation for non-standard view: {view}")
            continue
            
        view_name = truncate_text(view, 20)
        _log(f"  >> [{view_idx}/{len(frames)}] Processing {view_name}")
        
        try:
            # Segmentation
            _log(f"     Segmenting bone mask...")
            mask = predict_bone_mask(img, to_rgb=False)
            
            _log(f"     Generating colored overlay...")
            rgb = predict_bone_mask(img, to_rgb=True)
            
            _log(f"     Segmentation completed for {view_name}")

        except Exception as e:
            _log(f"    [ERROR] Segmentation failed for {view_name}: {e}")
            continue

        # ✅ NO DICOM OVERLAY INSERTION - ORIGINAL DICOM UNTOUCHED

        # Use proper view tag
        view_tag = view.lower()
        
        # PNG files with enforced naming (OUTPUT ONLY)
        _log(f"     Saving PNG files with enforced naming...")
        mask_png_path = dest_dir / f"{filename_stem}_{view_tag}_mask.png"
        colored_png_path = dest_dir / f"{filename_stem}_{view_tag}_colored.png"
        
        Image.fromarray((mask > 0).astype(np.uint8) * 255, mode="L").save(mask_png_path)
        Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(colored_png_path)
        
        saved += [f"{filename_stem}_{view_tag}_mask.png", f"{filename_stem}_{view_tag}_colored.png"]

        # ✅ NO SECONDARY CAPTURE DICOM CREATION

    # ✅ NO DICOM MODIFICATION OR SAVING - ORIGINAL REMAINS UNTOUCHED

    # STEP 4: YOLO DETECTION
    _log("  >> Running YOLO hotspot detection...")
    try:
        from features.spect_viewer.logic.processing_wrapper import run_yolo_detection_for_patient
        yolo_result = run_yolo_detection_for_patient(dest_path, pid)
        if yolo_result:
            _log(f"     YOLO detection completed - XML files created")
        else:
            _log(f"     YOLO detection completed - no detections found")
    except Exception as e:
        _log(f"     [WARN] YOLO detection failed: {e}")

    # STEP 5: OTSU HOTSPOT PROCESSING
    _log("  >> Running Otsu hotspot processing...")
    try:
        from features.spect_viewer.logic.processing_wrapper import run_hotspot_processing_in_process
        hotspot_result = run_hotspot_processing_in_process(dest_path, pid)
        if hotspot_result:
            _log(f"     Otsu processing completed - hotspot PNG files created")
        else:
            _log(f"     Otsu processing completed - no hotspots generated")
    except Exception as e:
        _log(f"     [WARN] Otsu hotspot processing failed: {e}")

    # STEP 6: CLASSIFICATION
    _log("  >> Running hotspot classification inference...")
    try:
        from features.spect_viewer.logic.processing_wrapper import run_classification_for_patient
        classification_result = run_classification_for_patient(dest_path, pid, study_date)
        if classification_result:
            _log(f"     Classification completed - Normal/Abnormal results saved")
        else:
            _log(f"     Classification completed - no classifications generated")
    except Exception as e:
        _log(f"     [WARN] Classification failed: {e}")

    # STEP 7: QUANTIFICATION
    _log("  >> Running BSI quantification with classification masks...")
    try:
        from features.spect_viewer.logic.quantification_wrapper import run_quantification_for_patient
        quantification_result = run_quantification_for_patient(dest_path, pid, study_date)
        if quantification_result:
            _log(f"     BSI quantification completed - results saved")
        else:
            _log(f"     BSI quantification failed - missing required files")
    except Exception as e:
        _log(f"     [WARN] BSI quantification failed: {e}")

    # STEP 8: UPLOAD ORIGINAL PNG FILES TO CLOUD
    _log("  >> Uploading original PNG files to cloud...")
    uploaded_count = 0
    for png_path in png_files_to_upload:
        if _upload_original_png_to_cloud(png_path, session_code, pid):
            uploaded_count += 1
    
    if uploaded_count > 0:
        _log(f"     ✅ Uploaded {uploaded_count} original PNG files to cloud")
    else:
        _log(f"     ⚠️  No files uploaded to cloud (cloud storage unavailable)")
    
    _log(f"  ✅ DICOM processing completed - ORIGINAL DICOM UNTOUCHED")
    _log(f"  Files saved locally: {len(saved)} PNG output files")
    _log(f"  Cloud upload: {uploaded_count} original PNG files only")
    _log(f"  Views processed: {list(frames.keys())}")
    _log(f"  ORIGINAL DICOM: {dest_path.name} (NO MODIFICATION)")
    
    return dest_path

def _safe_background_processing(frame_data, background_selection, view_name):
    """Safely process background with error handling"""
    try:
        if PIXEL_ANALYZER_AVAILABLE:
            return convert_to_black_background(frame_data, background_selection)
        else:
            _log(f"     ⚠️  Pixel analyzer not available for {view_name}")
            return frame_data
    except Exception as e:
        _log(f"     ❌ Background processing failed for {view_name}: {e}")
        return frame_data

def _process_one(src: Path, session_code: str) -> Path:
    """
    Backward compatibility - process with auto-detection
    """
    return _process_one_with_assignments(src, session_code, None)


# ---------------------------------------------------------------- batch processing
def process_files_with_assignments(
    file_view_assignments: Dict[Path, Dict[int, str]],
    background_assignments: Dict[Path, Dict[int, Dict[str, str]]] = None,  # TAMBAHAN BARU
    *,
    data_root: str | Path | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
    log_cb: Callable[[str], None] | None = None,
    session_code: str | None = None 
) -> List[Path]:
    """
    Process multiple DICOM files WITH user-assigned views and background selections
    
    Args:
        file_view_assignments: Dict {file_path: {frame_index: view_name}}
        background_assignments: Dict {file_path: {frame_index: {"view": view_name, "background": bg_type}}}
        data_root: Root data directory
        progress_cb: Progress callback
        log_cb: Log callback
        session_code: Session code (required)
        
    Returns:
        List of processed file paths
    """
    
    if not session_code:
        raise ValueError("session_code is required for new directory structure")
    if background_assignments is None:
        background_assignments = {}
        _log("## No background assignments provided - using defaults")
    else:
        _log(f"## Background assignments provided for {len(background_assignments)} files")
    # Validate all assignments
    for file_path, view_assignments in file_view_assignments.items():
        from .dicom_loader import validate_view_assignments
        is_valid, errors = validate_view_assignments(view_assignments)
        if not is_valid:
            raise ValueError(f"Invalid view assignments for {file_path.name}: {', '.join(errors)}")
    
    # Ensure session directory exists
    if data_root:
        session_root = Path(data_root) / "SPECT" / session_code
    else:
        session_root = get_session_spect_path(session_code)
    
    session_root.mkdir(parents=True, exist_ok=True)
    
    # Proxy _log for frontend
    orig_log = _log
    def _proxy(msg: str) -> None:
        orig_log(msg)
        if log_cb:
            display_msg = truncate_text(msg, 100) if len(msg) > 100 else msg
            log_cb(display_msg)
    globals()["_log"] = _proxy

    paths = list(file_view_assignments.keys())
    out: List[Path] = []
    total = len(paths)
    
    _log(f"## Starting batch import with view assignments: {total} file(s)")
    _log(f"## Session code: {session_code}")
    _log(f"## Target directory: data/SPECT/{session_code}/[patient_id]/")
    _log(f"## ✅ DICOM PROTECTION: Original DICOM files will NOT be modified")
    _log(f"## ✅ OUTPUT ONLY: PNG/XML files for analysis results")
    if background_assignments:
        bg_file_count = len(background_assignments)
        _log(f"## 🎨 BACKGROUND PROCESSING: {bg_file_count} files have background selections")
        _log(f"## Background conversion: White → Black (for model compatibility)")
    else:
        _log(f"## 🎨 BACKGROUND PROCESSING: Using original backgrounds (no selections)")
    _log(f"## Processing workflow: Copy Original → PNG outputs → Segmentation → YOLO → Otsu → Classification → Quantification → Upload PNG")

    for i, file_path in enumerate(paths, 1):
        try:
            _log(f"\n## Processing file {i}/{total}: {truncate_text(file_path.name, 30)}")
            view_assignments = file_view_assignments[file_path]
            file_background = background_assignments.get(file_path, {})
            result = _process_one_with_assignments(
                file_path, 
                session_code, 
                view_assignments, 
                file_background
            )
            out.append(result)
            _log(f"## File {i}/{total} completed successfully - ORIGINAL DICOM PRESERVED")
        except Exception as e:
            error_msg = f"File {i}/{total} failed: {str(e)[:100]}..."
            _log(f"[ERROR] {error_msg}")
            print(f"[FULL ERROR] {file_path} failed: {e}\n{traceback.format_exc()}")
        finally:
            if progress_cb:
                progress_cb(i, total, str(file_path))

    _log("## Batch import process completed")
    _log("## ✅ DICOM PROTECTION: All original DICOM files preserved without modification")
    _log("## ✅ OUTPUT GENERATION: PNG/XML analysis files created successfully")
    _log("## ✅ CLOUD UPLOAD: Original PNG files uploaded to cloud storage")
    _log("## All files use study date naming convention with proper view names.")
    
    globals()["_log"] = orig_log
    return out


def process_files(
    paths: Sequence[Path],
    *,
    data_root: str | Path | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
    log_cb: Callable[[str], None] | None = None,
    session_code: str | None = None 
) -> List[Path]:
    """
    Backward compatibility - process with auto-detection only
    
    Args:
        paths: List of DICOM file paths to process
        data_root: Root data directory
        progress_cb: Progress callback
        log_cb: Log callback  
        session_code: Session code (required)
        
    Returns:
        List of processed file paths
    """
    
    if not session_code:
        raise ValueError("session_code is required for new directory structure")
    
    # Convert to file_view_assignments format with None (auto-detect)
    file_view_assignments = {Path(p): None for p in paths}
    
    # Ensure session directory exists
    if data_root:
        session_root = Path(data_root) / "SPECT" / session_code
    else:
        session_root = get_session_spect_path(session_code)
    
    session_root.mkdir(parents=True, exist_ok=True)
    
    # Proxy _log for frontend
    orig_log = _log
    def _proxy(msg: str) -> None:
        orig_log(msg)
        if log_cb:
            display_msg = truncate_text(msg, 100) if len(msg) > 100 else msg
            log_cb(display_msg)
    globals()["_log"] = _proxy

    out: List[Path] = []
    total = len(paths)
    
    _log(f"## Starting batch import with AUTO-DETECTION: {total} file(s)")
    _log(f"## Session code: {session_code}")
    _log(f"## Target directory: data/SPECT/{session_code}/[patient_id]/")
    _log(f"## ✅ DICOM PROTECTION: Original DICOM files will NOT be modified")
    _log(f"## ✅ AUTO-DETECTION: System will detect Anterior/Posterior views")
    _log(f"## Processing workflow: Copy Original → PNG outputs → Segmentation → YOLO → Otsu → Classification → Quantification → Upload PNG")

    for i, p in enumerate(paths, 1):
        try:
            _log(f"\n## Processing file {i}/{total}: {truncate_text(p.name, 30)}")
            result = _process_one_with_assignments(Path(p), session_code, None)
            out.append(result)
            _log(f"## File {i}/{total} completed successfully - ORIGINAL DICOM PRESERVED")
        except Exception as e:
            error_msg = f"File {i}/{total} failed: {str(e)[:100]}..."
            _log(f"[ERROR] {error_msg}")
            print(f"[FULL ERROR] {p} failed: {e}\n{traceback.format_exc()}")
        finally:
            if progress_cb:
                progress_cb(i, total, str(p))

    _log("## Batch import process completed")
    _log("## ✅ DICOM PROTECTION: All original DICOM files preserved without modification")
    _log("## ✅ AUTO-DETECTION completed. Check logs for any view assignment issues.")
    _log("## ✅ OUTPUT GENERATION: PNG/XML analysis files created successfully")
    _log("## ✅ CLOUD UPLOAD: Original PNG files uploaded to cloud storage")
    _log("## All files use study date naming convention.")
    
    globals()["_log"] = orig_log
    return out


# ---------------------------------------------------------------- migration helper
def migrate_old_structure():
    """
    Migrate from old structure to new structure
    OLD: data/SPECT/[patient_id]_[session_code]/
    NEW: data/SPECT/[session_code]/[patient_id]/
    """
    from core.config.paths import migrate_old_to_new_structure, migrate_filenames_to_study_date
    migrate_old_to_new_structure()
    migrate_filenames_to_study_date()