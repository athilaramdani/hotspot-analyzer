# =====================================================================
# backend/input_data.py   --  SEGMENT → PNG → OVERLAY → SECONDARY DICOM
# ---------------------------------------------------------------------
"""
Alur:
1.  Salin file asli → ./data/SPECT/[session_code]/[patient_id]/[patient_id].dcm
2.  Segmentasi setiap frame (Anterior/Posterior)
3.  Simpan:
      • Overlay biner ke DICOM NM asli  (group 0x6000,0x3000)
      • PNG   : *_mask.png, *_colored.png
      • SC-DICOM (OT) : *_mask.dcm, *_colored.dcm   ← agar viewer lain bisa buka
4.  Upload ke cloud storage
"""

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

# Use new directory structure from paths.py
from core.config.paths import (
    get_patient_spect_path, 
    get_session_spect_path,
    SPECT_DATA_PATH,
    is_cloud_enabled
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
    """Upload file to cloud storage if enabled"""
    if not CLOUD_AVAILABLE or not is_cloud_enabled():
        return False
    
    try:
        return upload_patient_file(file_path, session_code, patient_id, is_edited)
    except Exception as e:
        _log(f"     [WARN] Cloud upload failed: {e}")
        return False

# ---------------------------------------------------------------- core
def _process_one(src: Path, session_code: str) -> Path:
    _log(f"\n=== Processing {src} ===")

    pid = str(pydicom.dcmread(src, stop_before_pixels=True).PatientID)
    dest_dir = get_patient_spect_path(pid, session_code)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = dest_dir / src.name
    if src.resolve() != dest_path.resolve():
        copy2(src, dest_path)
    _log(f"  Copied → {dest_path}")

    _upload_to_cloud(dest_path, session_code, pid)

    ds = pydicom.dcmread(dest_path)
    
    if session_code not in str(ds.PatientID):
        ds.PatientID = f"{pid}_{session_code}"

    frames, _ = load_frames_and_metadata(dest_path)
    _log(f"  Frames detected: {list(frames.keys())}")

    overlay_group = 0x6000
    saved: List[str] = []

    # ✅ PERBAIKAN: Unpack 'view' dan 'img' dari frames.items()
    for view, img in frames.items():
        _log(f"  >> Segmenting {view}")
        try:
            # ✅ PERBAIKAN: Gunakan parameter 'to_rgb=True'
            mask = predict_bone_mask(img, to_rgb=False) # Get raw mask for overlay & binary files
            rgb = predict_bone_mask(img, to_rgb=True)   # Get colored image for saving

        except Exception as e:
            _log(f"    [ERROR] Segmentation failed: {e}")
            continue

        _insert_overlay(ds, mask, group=overlay_group, desc=f"Seg {view}")
        overlay_group += 0x2

        base = f"{dest_path.stem}_{view.lower()}"
        
        # --- PNG files
        mask_png_path = dest_dir / f"{base}_mask.png"
        colored_png_path = dest_dir / f"{base}_colored.png"
        
        Image.fromarray((mask > 0).astype(np.uint8) * 255, mode="L").save(mask_png_path)
        Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(colored_png_path)
        
        saved += [f"{base}_mask.png", f"{base}_colored.png"]
        
        _upload_to_cloud(mask_png_path, session_code, pid)
        _upload_to_cloud(colored_png_path, session_code, pid)

        # --- SC-DICOM files
        try:
            mask_dcm_path = dest_dir / f"{base}_mask.dcm"
            colored_dcm_path = dest_dir / f"{base}_colored.dcm"
            
            _save_secondary_capture(ds, (mask > 0).astype(np.uint8) * 255,
                                    mask_dcm_path, descr=f"{view} Mask")
            _save_secondary_capture(ds, rgb, colored_dcm_path, descr=f"{view} RGB")
            
            saved += [f"{base}_mask.dcm", f"{base}_colored.dcm"]
            
            _upload_to_cloud(mask_dcm_path, session_code, pid)
            _upload_to_cloud(colored_dcm_path, session_code, pid)
            
        except Exception as e:
            _log(f"    [WARN] SC-DICOM save failed: {e}")

    # Save updated DICOM with overlays
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.save_as(dest_path, write_like_original=False)
    
    _upload_to_cloud(dest_path, session_code, pid)
    
    _log(f"  DICOM updated – files saved: {', '.join(saved)}")
    
    if is_cloud_enabled():
        _log(f"  Cloud sync: {'✅ Enabled' if CLOUD_AVAILABLE else '❌ Not available'}")
    
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
    Process multiple DICOM files with new directory structure
    
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
            log_cb(msg)        # kirim ke frontend jika callback ada
    globals()["_log"] = _proxy
    # --------------------------------------------------------------

    out: List[Path] = []
    total = len(paths)
    _log(f"## Starting batch: {total} file(s)")
    _log(f"## Session code: {session_code}")
    _log(f"## New directory structure: data/SPECT/{session_code}/[patient_id]/")

    for i, p in enumerate(paths, 1):
        try:
            result = _process_one(Path(p), session_code)
            out.append(result)
        except Exception as e:
            _log(f"[ERROR] {p} failed: {e}\n{traceback.format_exc()}")
        finally:
            if progress_cb:
                progress_cb(i, total, str(p))

    _log("## Batch finished")
    
    # Final cloud sync summary
    if is_cloud_enabled() and CLOUD_AVAILABLE:
        try:
            from core.config.cloud_storage import sync_spect_data
            uploaded, downloaded = sync_spect_data(session_code)
            _log(f"## Cloud sync completed: {uploaded} uploaded, {downloaded} downloaded")
        except Exception as e:
            _log(f"## Cloud sync failed: {e}")
    
    globals()["_log"] = orig_log      # kembalikan logger asli
    return out

# ---------------------------------------------------------------- migration helper
def migrate_old_structure():
    """
    Migrate from old structure to new structure
    OLD: data/SPECT/[patient_id]_[session_code]/
    NEW: data/SPECT/[session_code]/[patient_id]/
    """
    from core.config.paths import migrate_old_to_new_structure
    migrate_old_to_new_structure()