# backend/input_data.py  (VERBOSE DEBUG EDITION)
from __future__ import annotations
from pathlib import Path
from shutil   import copy2
from typing   import Callable, Sequence, List

import numpy as np
import pydicom
from pydicom.dataset import Dataset, Tag
from pydicom.uid      import ExplicitVRLittleEndian

from .dicom_loader import load_frames_and_metadata
from .segmenter     import segment_image


# ----------------------------------------------------------------- konfigurasi
_DATA_DIR  = Path(__file__).resolve().parents[1] / "data"
_VERBOSE   = True          # ← set False kalau sudah stabil
_LOG_FILE  = None          # isi Path("debug.log") bila mau log ke file


def _log(msg: str) -> None:
    if not _VERBOSE:
        return
    print(msg)
    if _LOG_FILE:
        with open(_LOG_FILE, "a", encoding="utf‑8") as fh:
            fh.write(msg + "\n")


# ----------------------------------------------------------------- overlay util
def _insert_overlay(ds: Dataset, mask: np.ndarray, *, group: int,
                    desc: str) -> None:

    mask  = (mask > 0).astype(np.uint8)
    rows, cols = mask.shape
    packed     = np.packbits(mask.reshape(-1, 8)[:, ::-1]).tobytes()

    ds.add_new(Tag(group, 0x0010), "US", rows)
    ds.add_new(Tag(group, 0x0011), "US", cols)
    ds.add_new(Tag(group, 0x0022), "LO", desc)
    ds.add_new(Tag(group, 0x0040), "CS", "G")
    ds.add_new(Tag(group, 0x0050), "SS", [1, 1])
    ds.add_new(Tag(group, 0x0100), "US", 1)
    ds.add_new(Tag(group, 0x0102), "US", 0)
    ds.add_new(Tag(group, 0x3000), "OW", packed)


# ----------------------------------------------------------------- proses 1 file
def _process_one(src: Path, dest_root: Path) -> Path:
    _log(f"\n=== Processing {src} ===")

    # --- tentukan folder pasien ------------------------------------------------
    try:
        pid = str(pydicom.dcmread(src, stop_before_pixels=True).PatientID)
    except Exception as e:
        _log(f"[ERROR] read meta failed: {e}")
        raise

    dest_dir  = dest_root / pid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / src.name

    if src.resolve() != dest_path.resolve():
        copy2(src, dest_path)
        _log(f"  Copied → {dest_path}")
    else:
        _log("  Source already inside data folder – skip copy")

    # --- baca pixel ------------------------------------------------------------
    ds = pydicom.dcmread(dest_path)
    frames, _ = load_frames_and_metadata(dest_path)
    _log(f"  Frames detected: {list(frames.keys())}")

    overlay_group = 0x6000
    saved_masks   = []

    for view, img in frames.items():
        _log(f"  >> Segmentation view={view} img.shape={img.shape}")
        try:
            mask = segment_image(img, view=view)
        except ValueError as e:
            _log(f"     [WARN] model for '{view}' unavailable: {e}")
            continue
        except Exception as e:
            _log(f"     [ERROR] segmentation crash: {e}")
            continue

        unique, counts = np.unique(mask, return_counts=True)
        _log(f"     Mask stats: {dict(zip(unique.tolist(), counts.tolist()))}")

        # overlay
        _insert_overlay(ds, mask, group=overlay_group, desc=f"Seg {view}")
        _log(f"     Overlay written to group {overlay_group:#04x}")
        overlay_group += 0x2

        # simpan .npy
        mask_fname = f"{dest_path.stem}_{view.lower()}_mask.npy"
        try:
            np.save(dest_dir / mask_fname, mask.astype(np.uint8))
            saved_masks.append(mask_fname)
            _log(f"     Mask file saved: {mask_fname}")
        except Exception as e:
            _log(f"     [ERROR] np.save failed: {e}")

    # tulis balik DICOM
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR   = False
    ds.save_as(dest_path, write_like_original=False)
    _log(f"  DICOM updated – overlays: {', '.join(saved_masks) or 'None'}\n")
    return dest_path


# ----------------------------------------------------------------- batch
def process_files(paths: Sequence[Path], *,
                  data_root: str | Path | None = None,
                  progress_cb: Callable[[int,int,str], None] | None = None
                 ) -> List[Path]:

    dest_root = Path(data_root) if data_root else _DATA_DIR
    dest_root.mkdir(parents=True, exist_ok=True)

    out   : List[Path] = []
    total = len(paths)

    _log(f"## Starting batch: {total} file(s)")
    for i, p in enumerate(paths, 1):
        try:
            out.append(_process_one(Path(p), dest_root))
        finally:
            if progress_cb:
                progress_cb(i, total, str(p))
    _log("## Batch finished\n")
    return out
