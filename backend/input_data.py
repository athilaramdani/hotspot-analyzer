# =====================================================================
# backend/input_data.py   --  SEGMENT → PNG → OVERLAY → SECONDARY DICOM
# ---------------------------------------------------------------------
"""
Alur:
1.  Salin file asli → ./data/<PatientID>/1.dcm
2.  Segmentasi setiap frame (Anterior/Posterior)
3.  Simpan:
      • Overlay biner ke DICOM NM asli  (group 0x6000,0x3000)
      • PNG   : *_mask.png, *_colored.png
      • SC-DICOM (OT) : *_mask.dcm, *_colored.dcm   ← agar viewer lain bisa buka
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
from .segmenter    import segment_image

# ---------------------------------------------------------------- config
_DATA_DIR  = Path(__file__).resolve().parents[1] / "data"
_VERBOSE   = True
_LOG_FILE  = None            # bisa diisi Path("debug.log")

def _log(msg: str) -> None:
    if _VERBOSE:
        print(msg)
        if _LOG_FILE:
            _LOG_FILE.write_text(msg + "\n")

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

# ---------------------------------------------------------------- core
def _process_one(src: Path, dest_root: Path) -> Path:
    _log(f"\n=== Processing {src} ===")

    pid = str(pydicom.dcmread(src, stop_before_pixels=True).PatientID)
    dest_dir = dest_root / pid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / src.name
    if src.resolve() != dest_path.resolve():
        copy2(src, dest_path)
    _log(f"  Copied → {dest_path}")

    ds = pydicom.dcmread(dest_path)
    frames, _ = load_frames_and_metadata(dest_path)
    _log(f"  Frames detected: {list(frames.keys())}")

    overlay_group = 0x6000
    saved: List[str] = []

    for view, img in frames.items():
        _log(f"  >> Segmenting {view}")
        try:
            mask, rgb = segment_image(img, view=view, color=True)
        except Exception as e:
            _log(f"     [ERROR] Segmentation failed: {e}")
            continue

        mask = _ensure_2d(mask)
        _insert_overlay(ds, mask, group=overlay_group, desc=f"Seg {view}")
        overlay_group += 0x2

        base = f"{dest_path.stem}_{view.lower()}"
        # --- PNG
        Image.fromarray((mask > 0).astype(np.uint8) * 255, mode="L").save(dest_dir / f"{base}_mask.png")
        Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(dest_dir / f"{base}_colored.png")
        saved += [f"{base}_mask.png", f"{base}_colored.png"]

        # --- SC-DICOM
        try:
            _save_secondary_capture(ds, (mask > 0).astype(np.uint8) * 255,
                                    dest_dir / f"{base}_mask.dcm", descr=f"{view} Mask")
            _save_secondary_capture(ds, rgb, dest_dir / f"{base}_colored.dcm", descr=f"{view} RGB")
            saved += [f"{base}_mask.dcm", f"{base}_colored.dcm"]
        except Exception as e:
            _log(f"     [WARN] SC-DICOM save failed: {e}")

    # tulis balik NM-DICOM
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR   = False
    ds.save_as(dest_path, write_like_original=False)
    _log(f"  DICOM updated – files saved: {', '.join(saved)}\n")
    return dest_path


# ---------------------------------------------------------------- batch
def process_files(
    paths: Sequence[Path],
    *,
    data_root: str | Path | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> List[Path]:

    dest_root = Path(data_root) if data_root else _DATA_DIR
    dest_root.mkdir(parents=True, exist_ok=True)

    out: List[Path] = []
    total = len(paths)
    _log(f"## Starting batch: {total} file(s)")

    for i, p in enumerate(paths, 1):
        try:
            out.append(_process_one(Path(p), dest_root))
        except Exception as e:
            _log(f"[ERROR] {p} failed: {e}\n{traceback.format_exc()}")
        finally:
            if progress_cb:
                progress_cb(i, total, str(p))

    _log("## Batch finished\n")
    return out
