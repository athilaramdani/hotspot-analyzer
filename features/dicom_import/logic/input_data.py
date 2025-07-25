# features/dicom_import/logic/input_data.py - Enhanced with study date in filenames
from __future__ import annotations
from pathlib import Path
from shutil  import copy2
from typing  import Callable, Sequence, List
import traceback

import numpy as np
from PIL import Image
import pydicom
from pydicom.dataset import Dataset, FileDataset, Tag
from pydicom.uid     import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    generate_uid,
)

from .dicom_loader import load_frames_and_metadata
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
_VERBOSE   = True
_LOG_FILE  = None            # bisa diisi Path("debug.log")

# ---------------------------------------------------------------- overlay util
def _insert_overlay(ds: Dataset, mask: np.ndarray, *, group: int, desc: str) -> None:
    if mask.ndim != 2:                      # pastikan 2-D
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
    meta.MediaStorageSOPClassUID    = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID          = ExplicitVRLittleEndian
    meta.ImplementationClassUID     = generate_uid()

    ds = FileDataset(str(out_path), {}, file_meta=meta, preamble=b"\0" * 128)

    # --- inherit pasien & study utama
    for tag in [
        "PatientID", "PatientName", "PatientBirthDate", "PatientSex",
        "StudyInstanceUID", "StudyDate", "StudyTime", "AccessionNumber"
    ]:
        if hasattr(ref, tag):
            setattr(ds, tag, getattr(ref, tag))

    ds.Modality          = "OT"
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber      = 999
    ds.InstanceNumber    = 1
    ds.SeriesDescription = descr

    ds.SamplesPerPixel          = 3 if rgb else 1
    ds.PhotometricInterpretation = "RGB" if rgb else "MONOCHROME2"
    ds.Rows, ds.Columns         = rows, cols
    ds.BitsAllocated            = 8
    ds.BitsStored               = 8
    ds.HighBit                  = 7
    ds.PixelRepresentation      = 0
    if rgb:
        ds.PlanarConfiguration = 0

    ds.PixelData = img.astype(np.uint8).tobytes()

    ds.is_little_endian = True
    ds.is_implicit_VR   = False
    ds.save_as(out_path, write_like_original=False)
    _log(f"     SC-DICOM saved: {out_path.name}")

# ---------------------------------------------------------------- helpers
def _ensure_2d(mask: np.ndarray) -> np.ndarray:
    return mask if mask.ndim == 2 else mask[0] if mask.shape[0] == 1 else mask[:, :, 0]

def _upload_to_cloud(file_path: Path, session_code: str, patient_id: str, is_edited: bool = False) -> bool:
    """Upload file to cloud storage if enabled - ONLY for input DICOM files"""
    if not CLOUD_AVAILABLE or not is_cloud_enabled():
        return False
    
    # ✅ ONLY UPLOAD ORIGINAL INPUT DICOM FILES
    # Skip processed files (mask, colored, etc.)
    if any(pattern in file_path.name.lower() for pattern in ['mask', 'colored', '_ant_', '_post_']):
        _log(f"     Skipping processed file upload: {file_path.name}")
        return False
    
    # ✅ ONLY UPLOAD .dcm files that are input files
    if file_path.suffix.lower() not in {'.dcm', '.dicom'}:
        _log(f"     Skipping non-DICOM file upload: {file_path.name}")
        return False
    
    try:
        success = upload_patient_file(file_path, session_code, patient_id, is_edited)
        if success:
            _log(f"     ✅ Uploaded input DICOM: {file_path.name}")
        else:
            _log(f"     ❌ Failed to upload: {file_path.name}")
        return success
    except Exception as e:
        _log(f"     [WARN] Cloud upload failed: {e}")
        return False

# ---------------------------------------------------------------- core
def _process_one(src: Path, session_code: str) -> Path:
    _log(f"\n=== Processing {truncate_text(src.name, 40)} ===")

    # Read patient info and study date
    _log("  >> Reading DICOM metadata...")
    ds_temp = pydicom.dcmread(src, stop_before_pixels=True)
    pid = str(ds_temp.PatientID)
    study_date = extract_study_date_from_dicom(src)
    
    _log(f"  Patient ID: {pid}")
    _log(f"  Study Date: {study_date}")
    
    # Generate filename stem with study date
    filename_stem = generate_filename_stem(pid, study_date)
    _log(f"  Filename stem: {filename_stem}")
    
    dest_dir = get_patient_spect_path(pid, session_code)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Create destination path with new naming convention
    dest_path = get_dicom_output_path(pid, session_code, study_date)
    
    # Copy file to destination with new name
    if src.resolve() != dest_path.resolve():
        _log(f"  >> Copying to patient directory with new name...")
        copy2(src, dest_path)
    _log(f"  Copied → {truncate_text(str(dest_path), 60)}")

    # ✅ UPLOAD HANYA INPUT DICOM SAJA
    _upload_to_cloud(dest_path, session_code, pid)

    # Load DICOM for processing
    _log("  >> Loading DICOM frames...")
    ds = pydicom.dcmread(dest_path)
    
    if session_code not in str(ds.PatientID):
        ds.PatientID = f"{pid}_{session_code}"

    frames, _ = load_frames_and_metadata(dest_path)
    _log(f"  Frames detected: {list(frames.keys())}")

    overlay_group = 0x6000
    saved: List[str] = []

    # Process each frame/view
    for view_idx, (view, img) in enumerate(frames.items(), 1):
        view_name = truncate_text(view, 20)
        _log(f"  >> [{view_idx}/{len(frames)}] Processing {view_name}")
        
        try:
            # Enhanced segmentation progress messages
            _log(f"     Segmenting bone mask (simple preprocessing)...")
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

        # Use new filename stem for all generated files
        view_tag = view.lower()
        
        # --- PNG files (SAVE LOCALLY ONLY) with new naming
        _log(f"     Saving PNG files locally with study date...")
        mask_png_path = dest_dir / f"{filename_stem}_{view_tag}_mask.png"
        colored_png_path = dest_dir / f"{filename_stem}_{view_tag}_colored.png"
        
        Image.fromarray((mask > 0).astype(np.uint8) * 255, mode="L").save(mask_png_path)
        Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(colored_png_path)
        
        saved += [f"{filename_stem}_{view_tag}_mask.png", f"{filename_stem}_{view_tag}_colored.png"]
        
        # ❌ REMOVE THESE UPLOADS
        # _upload_to_cloud(mask_png_path, session_code, pid)
        # _upload_to_cloud(colored_png_path, session_code, pid)

        # --- SC-DICOM files (SAVE LOCALLY ONLY) with new naming
        try:
            _log(f"     Creating secondary capture DICOM with study date...")
            mask_dcm_path = dest_dir / f"{filename_stem}_{view_tag}_mask.dcm"
            colored_dcm_path = dest_dir / f"{filename_stem}_{view_tag}_colored.dcm"
            
            _save_secondary_capture(ds, (mask > 0).astype(np.uint8) * 255,
                                    mask_dcm_path, descr=f"{view} Mask")
            _save_secondary_capture(ds, rgb, colored_dcm_path, descr=f"{view} RGB")
            
            saved += [f"{filename_stem}_{view_tag}_mask.dcm", f"{filename_stem}_{view_tag}_colored.dcm"]
            
            # ❌ REMOVE THESE UPLOADS
            # _upload_to_cloud(mask_dcm_path, session_code, pid)
            # _upload_to_cloud(colored_dcm_path, session_code, pid)
            
        except Exception as e:
            _log(f"    [WARN] SC-DICOM save failed for {view_name}: {e}")

    # Save updated DICOM with overlays (LOCAL ONLY)
    _log("  >> Finalizing DICOM with overlays...")
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.save_as(dest_path, write_like_original=False)
    
    # ❌ REMOVE THIS DUPLICATE UPLOAD
    # _upload_to_cloud(dest_path, session_code, pid)
    
    _log(f"  DICOM processing completed")
    _log(f"  Files saved locally: {len(saved)} items")
    _log(f"  Cloud upload: Input DICOM only")
    _log(f"  New filename pattern: {filename_stem}_[view]_[type]")
    
    return dest_path

# ---------------------------------------------------------------- batch
def process_files(
    paths: Sequence[Path],
    *,
    data_root: str | Path | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
    log_cb: Callable[[str], None] | None = None,
    session_code: str | None = None 
) -> List[Path]:
    """
    Process multiple DICOM files with new directory structure and study date in filenames
    
    Args:
        paths: List of DICOM file paths to process
        data_root: Root data directory (optional, uses SPECT_DATA_PATH if None)
        progress_cb: Progress callback function
        log_cb: Log callback function  
        session_code: Session/doctor code (NSY, ATL, NBL, etc.)
        
    Returns:
        List of processed file paths
    """
    
    if not session_code:
        raise ValueError("session_code is required for new directory structure")
    
    # Ensure session directory exists
    if data_root:
        session_root = Path(data_root) / "SPECT" / session_code
    else:
        session_root = get_session_spect_path(session_code)
    
    session_root.mkdir(parents=True, exist_ok=True)
    
    # ---------- proxy _log agar bisa dikirim ke frontend ----------
    orig_log = _log
    def _proxy(msg: str) -> None:
        orig_log(msg)          # tetap tulis ke console/file
        if log_cb:
            # Truncate very long messages for UI display
            display_msg = truncate_text(msg, 100) if len(msg) > 100 else msg
            log_cb(display_msg)        # kirim ke frontend jika callback ada
    globals()["_log"] = _proxy
    # --------------------------------------------------------------

    out: List[Path] = []
    total = len(paths)
    _log(f"## Starting batch import: {total} file(s)")
    _log(f"## Session code: {session_code}")
    _log(f"## Target directory: data/SPECT/{session_code}/[patient_id]/")
    _log(f"## New naming: [patient_id]_[study_date]_[view]_[type]")

    for i, p in enumerate(paths, 1):
        try:
            _log(f"\n## Processing file {i}/{total}: {truncate_text(p.name, 30)}")
            result = _process_one(Path(p), session_code)
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
    
    # ❌ REMOVE FINAL CLOUD SYNC COMPLETELY
    # Final cloud sync summary
    # if is_cloud_enabled() and CLOUD_AVAILABLE:
    #     try:
    #         from core.config.cloud_storage import sync_spect_data
    #         _log("## Performing final cloud synchronization...")
    #         uploaded, downloaded = sync_spect_data(session_code)
    #         _log(f"## Cloud sync completed: {uploaded} up, {downloaded} down")
    #     except Exception as e:
    #         _log(f"## Cloud sync failed: {truncate_text(str(e), 50)}")
    
    # ✅ REPLACE WITH THIS MESSAGE
    _log("## Local processing completed. Only input DICOM files uploaded to cloud.")
    _log("## All files now use study date naming convention.")
    
    globals()["_log"] = orig_log      # kembalikan logger asli
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