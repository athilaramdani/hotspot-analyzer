# features/dicom_import/logic/input_data.py - UPDATED with view assignment support
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

# ---------------------------------------------------------------- overlay util
def _insert_overlay(ds: Dataset, mask: np.ndarray, *, group: int, desc: str) -> None:
    if mask.ndim != 2:
        mask = mask[0] if mask.shape[0] == 1 else mask[:, :, 0]

    rows, cols = mask.shape
    packed = np.packbits((mask > 0).astype(np.uint8).reshape(-1, 8)[:, ::-1]).tobytes()

    ds.add_new(Tag(group, 0x0010), "US", rows)
    ds.add_new(Tag(group, 0x0011), "US", cols)
    ds.add_new(Tag(group, 0x0022), "LO", desc)
    ds.add_new(Tag(group, 0x0040), "CS", "G")
    ds.add_new(Tag(group, 0x0050), "SS", [1, 1])
    ds.add_new(Tag(group, 0x0100), "US", 1)
    ds.add_new(Tag(group, 0x0102), "US", 0)
    ds.add_new(Tag(group, 0x3000), "OW", packed)

# ---------------------------------------------------------------- SC-DICOM helper
def _save_secondary_capture(ref: Dataset, img: np.ndarray, out_path: Path, descr: str) -> None:
    """Buat SC-DICOM sederhana (Modality=OT) dari ndarray uint8."""
    rgb = img.ndim == 3
    rows, cols = img.shape[:2]

    meta = pydicom.Dataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(str(out_path), {}, file_meta=meta, preamble=b"\0" * 128)

    # inherit pasien & study utama
    for tag in [
        "PatientID", "PatientName", "PatientBirthDate", "PatientSex",
        "StudyInstanceUID", "StudyDate", "StudyTime", "AccessionNumber"
    ]:
        if hasattr(ref, tag):
            setattr(ds, tag, getattr(ref, tag))

    ds.Modality = "OT"
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = 999
    ds.InstanceNumber = 1
    ds.SeriesDescription = descr

    ds.SamplesPerPixel = 3 if rgb else 1
    ds.PhotometricInterpretation = "RGB" if rgb else "MONOCHROME2"
    ds.Rows, ds.Columns = rows, cols
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    if rgb:
        ds.PlanarConfiguration = 0

    ds.PixelData = img.astype(np.uint8).tobytes()

    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.save_as(out_path, write_like_original=False)
    _log(f"     SC-DICOM saved: {out_path.name}")

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
    view_assignments: Optional[Dict[int, str]] = None
) -> Path:
    """
    Process single DICOM with view assignments
    
    Args:
        src: Source DICOM path
        session_code: Session code
        view_assignments: Dict {frame_index: view_name} atau None untuk auto-detect
    """
    _log(f"\n=== Processing {truncate_text(src.name, 40)} ===")

    # Read patient info and study date
    _log("  >> Reading DICOM metadata...")
    ds_temp = pydicom.dcmread(src, stop_before_pixels=True)
    pid = str(ds_temp.PatientID)
    study_date = extract_study_date_from_dicom(src)
    
    _log(f"  Patient ID: {pid}")
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
    dest_path = get_dicom_output_path(pid, session_code, study_date)
    
    # STEP 1: Copy file to destination with new name (LOCAL ONLY)
    if src.resolve() != dest_path.resolve():
        _log(f"  >> Copying to patient directory with new name...")
        copy2(src, dest_path)
    _log(f"  Copied → {truncate_text(str(dest_path), 60)}")

    # Load DICOM for processing with view assignments
    _log("  >> Loading DICOM frames with view assignments...")
    ds = pydicom.dcmread(dest_path)
    
    if session_code not in str(ds.PatientID):
        ds.PatientID = f"{pid}_{session_code}"

    frames, _ = load_frames_and_metadata_with_assignments(dest_path, view_assignments)
    _log(f"  Frames detected: {list(frames.keys())}")

    # ✅ VALIDATE THAT WE HAVE ANTERIOR AND POSTERIOR
    frame_views = set(frames.keys())
    if "Anterior" not in frame_views or "Posterior" not in frame_views:
        error_msg = f"Missing required views. Got: {list(frame_views)}, Need: ['Anterior', 'Posterior']"
        _log(f"  [ERROR] {error_msg}")
        raise ValueError(error_msg)

    overlay_group = 0x6000
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

    # STEP 3: SEGMENTATION PROCESSING
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

        # Insert overlay into DICOM
        _log(f"     Inserting overlay into DICOM...")
        _insert_overlay(ds, mask, group=overlay_group, desc=f"Seg {view}")
        overlay_group += 0x2

        # Use proper view tag
        view_tag = view.lower()
        
        # PNG files with enforced naming
        _log(f"     Saving PNG files with enforced naming...")
        mask_png_path = dest_dir / f"{filename_stem}_{view_tag}_mask.png"
        colored_png_path = dest_dir / f"{filename_stem}_{view_tag}_colored.png"
        
        Image.fromarray((mask > 0).astype(np.uint8) * 255, mode="L").save(mask_png_path)
        Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(colored_png_path)
        
        saved += [f"{filename_stem}_{view_tag}_mask.png", f"{filename_stem}_{view_tag}_colored.png"]

        # SC-DICOM files with enforced naming
        try:
            _log(f"     Creating secondary capture DICOM...")
            mask_dcm_path = dest_dir / f"{filename_stem}_{view_tag}_mask.dcm"
            colored_dcm_path = dest_dir / f"{filename_stem}_{view_tag}_colored.dcm"
            
            _save_secondary_capture(ds, (mask > 0).astype(np.uint8) * 255,
                                    mask_dcm_path, descr=f"{view} Mask")
            _save_secondary_capture(ds, rgb, colored_dcm_path, descr=f"{view} RGB")
            
            saved += [f"{filename_stem}_{view_tag}_mask.dcm", f"{filename_stem}_{view_tag}_colored.dcm"]
            
        except Exception as e:
            _log(f"    [WARN] SC-DICOM save failed for {view_name}: {e}")

    # Save updated DICOM with overlays
    _log("  >> Finalizing DICOM with overlays...")
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.save_as(dest_path, write_like_original=False)

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
    
    _log(f"  DICOM processing completed")
    _log(f"  Files saved locally: {len(saved)} items")
    _log(f"  Cloud upload: {uploaded_count} original PNG files only")
    _log(f"  Views processed: {list(frames.keys())}")
    _log(f"  Enforced naming: ANTERIOR/POSTERIOR only")
    
    return dest_path


def _process_one(src: Path, session_code: str) -> Path:
    """
    Backward compatibility - process with auto-detection
    """
    return _process_one_with_assignments(src, session_code, None)


# ---------------------------------------------------------------- batch processing
def process_files_with_assignments(
    file_view_assignments: Dict[Path, Dict[int, str]],
    *,
    data_root: str | Path | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
    log_cb: Callable[[str], None] | None = None,
    session_code: str | None = None 
) -> List[Path]:
    """
    Process multiple DICOM files WITH user-assigned views
    
    Args:
        file_view_assignments: Dict {file_path: {frame_index: view_name}}
        data_root: Root data directory
        progress_cb: Progress callback
        log_cb: Log callback
        session_code: Session code (required)
        
    Returns:
        List of processed file paths
    """
    
    if not session_code:
        raise ValueError("session_code is required for new directory structure")
    
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
    _log(f"## ENFORCED NAMING: Anterior/Posterior views only")
    _log(f"## Processing workflow: Copy → Original PNG → Segmentation → YOLO → Otsu → Classification → Quantification → Upload PNG")

    for i, file_path in enumerate(paths, 1):
        try:
            _log(f"\n## Processing file {i}/{total}: {truncate_text(file_path.name, 30)}")
            view_assignments = file_view_assignments[file_path]
            result = _process_one_with_assignments(file_path, session_code, view_assignments)
            out.append(result)
            _log(f"## File {i}/{total} completed successfully")
        except Exception as e:
            error_msg = f"File {i}/{total} failed: {str(e)[:100]}..."
            _log(f"[ERROR] {error_msg}")
            print(f"[FULL ERROR] {file_path} failed: {e}\n{traceback.format_exc()}")
        finally:
            if progress_cb:
                progress_cb(i, total, str(file_path))

    _log("## Batch import process completed")
    _log("## ENFORCED VIEW NAMING: All files processed with Anterior/Posterior views")
    _log("## Local processing completed. Original PNG files uploaded to cloud.")
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
    _log(f"## AUTO-DETECTION: System will detect Anterior/Posterior views")
    _log(f"## Processing workflow: Copy → Original PNG → Segmentation → YOLO → Otsu → Classification → Quantification → Upload PNG")

    for i, p in enumerate(paths, 1):
        try:
            _log(f"\n## Processing file {i}/{total}: {truncate_text(p.name, 30)}")
            result = _process_one_with_assignments(Path(p), session_code, None)
            out.append(result)
            _log(f"## File {i}/{total} completed successfully")
        except Exception as e:
            error_msg = f"File {i}/{total} failed: {str(e)[:100]}..."
            _log(f"[ERROR] {error_msg}")
            print(f"[FULL ERROR] {p} failed: {e}\n{traceback.format_exc()}")
        finally:
            if progress_cb:
                progress_cb(i, total, str(p))

    _log("## Batch import process completed")
    _log("## AUTO-DETECTION completed. Check logs for any view assignment issues.")
    _log("## Local processing completed. Original PNG files uploaded to cloud.")
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