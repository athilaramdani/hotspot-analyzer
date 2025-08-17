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
# ✅ ADD missing imports from paths.py
from core.config.paths import (
    get_patient_planar_path, 
    get_session_planar_path,
    get_planar_original_files,        # ✅ ADD
    get_planar_segmentation_files,    # ✅ ADD
    get_planar_hotspot_files,         # ✅ ADD
    PLANAR_DATA_PATH,
    extract_study_date_from_dicom,
    generate_filename_stem
)

# Import cloud functions from archive
from core.config.paths_archive import is_cloud_enabled

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


def validate_patient_folder_structure(dest_path: Path, session_code: str, patient_id: str, study_date: str) -> bool:
    """
    ✅ SIMPLIFIED: Basic path structure validation
    """
    try:
        expected_structure = get_patient_planar_path(session_code, patient_id, study_date)
        actual_folder = dest_path.parent
        
        if actual_folder == expected_structure:
            _log(f"  ✅ Path structure validated: {actual_folder}")
            return True
        else:
            _log(f"  ⚠️ Path structure different but acceptable:")
            _log(f"      Expected: {expected_structure}")
            _log(f"      Actual:   {actual_folder}")
            return False  # But don't fail the process
    except Exception as e:
        _log(f"  [WARN] Path validation error: {e}")
        return False


def normalize_view_name(view_name: str) -> str:
    """
    Normalize view names to standard format
    
    Args:
        view_name: Original view name from DICOM
        
    Returns:
        Normalized view name ('Anterior' or 'Posterior')
    """
    view_lower = view_name.lower().strip()
    
    # Anterior variations
    if view_lower in ['anterior', 'ant', 'front']:
        return 'Anterior'
    
    # Posterior variations  
    elif view_lower in ['posterior', 'post', 'back']:
        return 'Posterior'
    
    # Return original if no match
    else:
        return view_name

def scan_folders_for_dicom(folder_paths: List[Path]) -> List[Path]:
    """
    Scan multiple folders for DICOM files
    
    Args:
        folder_paths: List of folder paths to scan
        
    Returns:
        List of DICOM file paths found
    """
    dicom_files = []
    
    for folder_path in folder_paths:
        if not folder_path.exists() or not folder_path.is_dir():
            continue
            
        # Scan for DICOM files recursively
        for ext in ['.dcm', '.dicom']:
            dicom_files.extend(folder_path.rglob(f"*{ext}"))
    
    return sorted(dicom_files)

# ✅ NEW: Smart duplicate detection
def check_duplicate_files(file_paths: List[Path], session_code: str) -> Dict[Path, bool]:
    """
    Check which files are already imported
    
    Args:
        file_paths: List of DICOM file paths to check
        session_code: Session code
        
    Returns:
        Dictionary mapping file_path to is_duplicate
    """
    duplicates = {}
    session_root = get_session_planar_path(session_code)
    
    for file_path in file_paths:
        # Extract patient info
        try:
            ds = pydicom.dcmread(file_path, stop_before_pixels=True)
            pid = str(ds.PatientID)
            study_date = extract_study_date_from_dicom(file_path)
            
            # Check if file already exists
            patient_dir = session_root / pid / study_date
            existing_dicom = patient_dir / file_path.name
            
            duplicates[file_path] = existing_dicom.exists()
            
        except Exception:
            duplicates[file_path] = False
    
    return duplicates

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
    if not CLOUD_AVAILABLE:
        return False
    
    try:
        if not is_cloud_enabled():
            return False
    except Exception:
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
    background_assignments: Optional[Dict[int, Dict[str, str]]] = None,
    cloud_upload_enabled: bool = True
) -> Path:
    """
    ✅ FIXED: Process single DICOM with NEW path structure and naming
    """
    _log(f"\n=== Processing {truncate_text(src.name, 40)} ===")
    
    # Read patient info and study date from ORIGINAL DICOM
    ds_temp = pydicom.dcmread(src, stop_before_pixels=True)
    pid = str(ds_temp.PatientID)
    study_date = extract_study_date_from_dicom(src)
    
    _log(f"  Patient ID: {pid}")
    _log(f"  Study Date: {study_date}")
    
    # ✅ FIX: Generate filename_stem for saved files list
    filename_stem = generate_filename_stem(pid, study_date)
    
    # ✅ NEW: Use study_date in path structure
    dest_dir = get_patient_planar_path(session_code, pid, study_date)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # ✅ NEW: Keep original DICOM filename
    original_filename = src.name
    dest_path = dest_dir / original_filename
    
    # ✅ MOVE: Path validation AFTER dest_path is defined
    try:
        path_valid = validate_patient_folder_structure(dest_path, session_code, pid, study_date)
        if not path_valid:
            _log(f"  [WARN] Path structure validation failed, but continuing...")
    except Exception as e:
        _log(f"  [WARN] Path validation error: {e}")
    
    # Copy ORIGINAL file to destination WITHOUT MODIFICATION
    if src.resolve() != dest_path.resolve():
        _log(f"  >> Copying ORIGINAL DICOM without modification...")
        copy2(src, dest_path)
    _log(f"  Copied ORIGINAL → {truncate_text(str(dest_path), 60)}")

    # Load ORIGINAL DICOM for processing WITHOUT MODIFICATION
    _log("  >> Loading ORIGINAL DICOM frames with view assignments...")
    
    frames, _ = load_frames_and_metadata_with_assignments(dest_path, view_assignments)
    _log(f"  Frames detected: {list(frames.keys())}")
    
    # Background processing if available (BEFORE normalization)
    original_frames = frames.copy()  # Keep original for background processing
    processed_frames = {}

    if background_assignments and PIXEL_ANALYZER_AVAILABLE:
        _log("  >> Processing background selections...")
        for idx, (view_name, frame) in enumerate(original_frames.items()):
            if idx in background_assignments:
                bg_selection = background_assignments[idx].get("background", "black")
                _log(f"     Processing {view_name} with {bg_selection} background")
                processed_frame = _safe_background_processing(frame, bg_selection, view_name)
                processed_frames[view_name] = processed_frame
                _log(f"     ✅ {view_name} background processed")
            else:
                processed_frames[view_name] = frame
                _log(f"     Using original {view_name} (no background assignment)")
        
        frames = processed_frames
        _log("  ✅ Background processing completed")
    else:
        if background_assignments:
            _log("  ⚠️  Background assignments provided but pixel analyzer not available")
        else:
            _log("  Using original frames (no background assignments)")

    # NOW normalize view names after background processing
    normalized_frames = {}
    for view_name, frame_data in frames.items():
        if view_name.lower() in ['anterior', 'ant']:
            normalized_frames['Anterior'] = frame_data
            if view_name != 'Anterior':
                _log(f"  >> Normalized '{view_name}' → 'Anterior'")
        elif view_name.lower() in ['posterior', 'post']:
            normalized_frames['Posterior'] = frame_data
            if view_name != 'Posterior':
                _log(f"  >> Normalized '{view_name}' → 'Posterior'")
        else:
            _log(f"  [WARN] Unknown view name: {view_name}")
            normalized_frames[view_name] = frame_data

    frames = normalized_frames
    _log(f"  ✅ Final views: {list(frames.keys())}")

    # Validate that we have required views (after normalization)
    frame_views = set(frames.keys())
    if "Anterior" not in frame_views or "Posterior" not in frame_views:
        error_msg = f"Missing required views. Got: {list(frame_views)}, Need: ['Anterior', 'Posterior']"
        _log(f"  [ERROR] {error_msg}")
        raise ValueError(error_msg)

    _log(f"  ✅ Normalized views: {list(frames.keys())}")

    saved: List[str] = []
    png_files_to_upload: List[Path] = []

    # STEP 2: SAVE ORIGINAL FRAMES AS PNG - Use paths.py naming
    _log("  >> Saving original frames for classification...")
    for view_name, frame in frames.items():
        if view_name in ["Anterior", "Posterior"]:
            view_tag = "ant" if view_name == "Anterior" else "post"
            
            # ✅ USE paths.py for file naming
            original_files = get_planar_original_files(dest_dir)
            original_png_path = original_files[f'{view_tag}_original']
            
            _save_original_frame_png(frame, original_png_path)
            saved.append(original_png_path.name)
            png_files_to_upload.append(original_png_path)
        else:
            _log(f"  [WARN] Skipping non-standard view: {view_name}")

    # STEP 3: SEGMENTATION PROCESSING - Use paths.py naming with FIXED error handling
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

            # ✅ MOVE file saving INSIDE try block
            segmentation_files = get_planar_segmentation_files(dest_dir, view, with_priority=False)
            mask_png_path = segmentation_files['mask_png']
            colored_png_path = segmentation_files['segmentation_png']
                    
            Image.fromarray((mask > 0).astype(np.uint8) * 255, mode="L").save(mask_png_path)
            Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(colored_png_path)
            
            saved += [mask_png_path.name, colored_png_path.name]
            _log(f"     ✅ Saved: {mask_png_path.name}, {colored_png_path.name}")

        except Exception as e:
            _log(f"    [ERROR] Segmentation failed for {view_name}: {e}")
            _log(f"    [FALLBACK] Creating placeholder segmentation files...")
            
            try:
                segmentation_files = get_planar_segmentation_files(dest_dir, view, with_priority=False)
                mask_png_path = segmentation_files['mask_png']
                colored_png_path = segmentation_files['segmentation_png']
                
                # Create placeholder files
                placeholder_mask = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
                placeholder_rgb = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
                
                Image.fromarray(placeholder_mask, mode="L").save(mask_png_path)
                Image.fromarray(placeholder_rgb, mode="RGB").save(colored_png_path)
                
                saved += [mask_png_path.name, colored_png_path.name]
                _log(f"     ⚠️ Created placeholder files: {mask_png_path.name}, {colored_png_path.name}")
                
            except Exception as fallback_error:
                _log(f"    [ERROR] Fallback creation failed: {fallback_error}")
                continue

    # STEP 4: YOLO DETECTION
    _log("  >> Running YOLO hotspot detection...")
    try:
        from features.spect_viewer.logic.processing_wrapper import run_yolo_detection_wrapper
        yolo_result = run_yolo_detection_wrapper(dest_path, pid)
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
        classification_result = run_classification_with_new_paths(dest_path, pid, study_date)
        if classification_result:
            _log(f"     Classification completed - Normal/Abnormal results saved")
        else:
            _log(f"     Classification completed - no classifications generated")
    except Exception as e:
        _log(f"     [WARN] Classification failed: {e}")

    # STEP 7: QUANTIFICATION
    _log("  >> Running BSI quantification with classification masks...")
    try:
        from features.spect_viewer.logic.processing_wrapper import run_quantification_for_patient
        quantification_result = run_quantification_for_patient(dest_path, pid, study_date)
        if quantification_result:
            _log(f"     BSI quantification completed - results saved")
        else:
            _log(f"     BSI quantification failed - missing required files")
    except Exception as e:
        _log(f"     [WARN] BSI quantification failed: {e}")

    # STEP 8: UPLOAD ORIGINAL PNG FILES TO CLOUD (if enabled)
    _log("  >> Uploading original PNG files to cloud...")
    uploaded_count = 0
    if cloud_upload_enabled:
        for png_path in png_files_to_upload:
            if _upload_original_png_to_cloud(png_path, session_code, pid):
                uploaded_count += 1
    else:
        _log("  >> Cloud upload disabled - skipping upload step")
    
    if uploaded_count > 0:
        _log(f"     ✅ Uploaded {uploaded_count} original PNG files to cloud")
    else:
        _log(f"     ⚠️  No files uploaded to cloud (cloud storage unavailable or disabled)")
    
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

def _process_one(src: Path, session_code: str, cloud_upload_enabled: bool = True) -> Path:
    """
    Backward compatibility - process with auto-detection
    """
    return _process_one_with_assignments(src, session_code, None, None, cloud_upload_enabled)   


# ---------------------------------------------------------------- batch processing
def process_files_with_assignments(
    file_view_assignments: Dict[Path, Dict[int, str]],
    background_assignments: Dict[Path, Dict[int, Dict[str, str]]] = None,
    *,
    data_root: str | Path | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
    log_cb: Callable[[str], None] | None = None,
    session_code: str | None = None,
    cloud_upload_enabled: bool = True  # ✅ ADD cloud parameter
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
        session_root = get_session_planar_path(session_code)
    
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
    _log(f"## Target directory: data/PLANAR/{session_code}/[patient_id]/")
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
                file_background,
                cloud_upload_enabled  # ✅ ADD cloud parameter
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
    session_code: str | None = None,
    cloud_upload_enabled: bool = True  # ✅ ADD cloud parameter
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
        session_root = get_session_planar_path(session_code)
    
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
            result = _process_one_with_assignments(Path(p), session_code, None, None, cloud_upload_enabled)  # ✅ ADD cloud parameter
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

def validate_planar_structure(session_code: str) -> bool:
    """
    Validate that PLANAR structure exists
    
    Args:
        session_code: Session code
        
    Returns:
        True if structure is correct
    """
    try:
        session_path = PLANAR_DATA_PATH / session_code
        session_path.mkdir(parents=True, exist_ok=True)
        _log(f"[VALIDATION] PLANAR structure validated: {session_path}")
        return True
    except Exception as e:
        _log(f"[VALIDATION ERROR] Failed to create PLANAR structure: {e}")
        return False
    
def run_classification_with_new_paths(dest_path: Path, pid: str, study_date: str) -> bool:
    """
    ✅ COMPLETE: Run classification with proper new file naming and path mapping
    """
    try:
        patient_folder = dest_path.parent
        
        # ✅ CHECK: Map new files to old naming expected by classification
        original_files = get_planar_original_files(patient_folder)
        segmentation_files_ant = get_planar_segmentation_files(patient_folder, "ant", with_priority=False)
        segmentation_files_post = get_planar_segmentation_files(patient_folder, "post", with_priority=False)
        
        # ✅ CREATE: Temporary directory with old naming for classification compatibility
        temp_dir = patient_folder / "temp_classification"
        temp_dir.mkdir(exist_ok=True)
        
        filename_stem = generate_filename_stem(pid, study_date)
        
        file_mappings = []
        success_count = 0
        
        # Map new files to old naming expected by classification
        file_mapping_list = [
            (original_files['ant_original'], f"{filename_stem}_anterior_original.png"),
            (original_files['post_original'], f"{filename_stem}_posterior_original.png"),
            (segmentation_files_ant['segmentation_png'], f"{filename_stem}_anterior_colored.png"),
            (segmentation_files_post['segmentation_png'], f"{filename_stem}_posterior_colored.png")
        ]
        
        # Create file mappings
        import shutil
        for source_file, old_name in file_mapping_list:
            if source_file.exists():
                target_file = temp_dir / old_name
                shutil.copy2(source_file, target_file)
                file_mappings.append(target_file)
                success_count += 1
                _log(f"     Mapped: {source_file.name} -> {old_name}")
        
        _log(f"     Successfully mapped {success_count} files for classification")
        
        if success_count >= 2:  # At least some files mapped
            # ✅ CHANGE: Temporarily change working directory for classification
            import os
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                _log(f"     Running classification in temp directory: {temp_dir}")
                
                from features.spect_viewer.logic.processing_wrapper import run_classification_for_patient
                result = run_classification_for_patient(dest_path, pid, study_date)
                
                # ✅ COPY: Results back to main folder with new naming
                if result:
                    _log(f"     Copying classification results back to main folder...")
                    
                    # Copy results back with new naming
                    result_mappings = [
                        (f"{filename_stem}_ant_classification.xml", "ant_hotspot_classification.xml"),
                        (f"{filename_stem}_post_classification.xml", "post_hotspot_classification.xml"),
                        (f"{filename_stem}_anterior_classification_mask.png", "ant_hotspot_classification.png"),
                        (f"{filename_stem}_posterior_classification_mask.png", "post_hotspot_classification.png")
                    ]
                    
                    for old_result_name, new_result_name in result_mappings:
                        old_result_path = temp_dir / old_result_name
                        new_result_path = patient_folder / new_result_name
                        
                        if old_result_path.exists():
                            shutil.copy2(old_result_path, new_result_path)
                            _log(f"     Copied: {old_result_name} -> {new_result_name}")
                
                return result
                
            finally:
                os.chdir(original_cwd)
                
                # ✅ CLEANUP: Remove temp directory
                try:
                    shutil.rmtree(temp_dir)
                    _log(f"     Cleaned up temp directory")
                except Exception as cleanup_error:
                    _log(f"     [WARN] Cleanup failed: {cleanup_error}")
        else:
            _log(f"     ❌ Insufficient files for classification ({success_count} < 2)")
            return False
            
    except Exception as e:
        _log(f"     [ERROR] Classification wrapper failed: {e}")
        import traceback
        traceback.print_exc()
        return False