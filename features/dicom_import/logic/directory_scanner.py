# =====================================================================
# backend/directory_scanner.py
# ---------------------------------------------------------------------
"""
Pindai folder `data/…` dan kembalikan mapping:
    {PatientID: [daftar-file scan primer (*.dcm)]}

‣  Hanya file DICOM “primer” (NM / bukan Secondary-Capture) yang dihitung
   agar overlay & SC-DICOM buatan kita (Modality=OT atau
   SOP Class UID = SecondaryCapture) tidak dianggap sebagai scan baru.
"""
from pathlib import Path
from typing  import Dict, List

import pydicom

_UID_SC = "1.2.840.10008.5.1.4.1.1.7"          # Secondary Capture Image Storage

# ---------------------------------------------------------------- helpers
def _is_primary(ds) -> bool:
    """True jika berkas adalah scan NM primer, False jika turunan (mask/RGB)."""
    modality = (ds.get("Modality", "") or "").upper()
    if modality == "OT":                # SC-DICOM yang kita buat
        return False

    if ds.get("SOPClassUID") == _UID_SC:
        return False                    # generic Secondary-Capture

    image_type = "\\".join(ds.get("ImageType", [])).upper()
    if "DERIVED" in image_type:
        return False                    # turunan yang ditandai DERIVED

    # Tambahan filter (opsional): SeriesNumber, SeriesDescription, ds.Rows==
    return True


# ---------------------------------------------------------------- main
def scan_dicom_directory(directory: Path) -> Dict[str, List[Path]]:
    patient_map: Dict[str, List[Path]] = {}

    dicoms = list(directory.glob("**/*.dcm"))
    print(f"Ditemukan {len(dicoms)} file DICOM di '{directory}'")

    for p in dicoms:
        try:
            ds = pydicom.dcmread(p, stop_before_pixels=True)
        except Exception as e:
            print(f"[WARN] Tidak bisa baca {p}: {e}")
            continue

        if not _is_primary(ds):
            continue

        pid = ds.get("PatientID")
        if not pid:
            continue

        patient_map.setdefault(pid, []).append(p)

    total_scans = sum(len(v) for v in patient_map.values())
    print(f"Ditemukan {len(patient_map)} ID pasien (total {total_scans} scan primer).")
    return patient_map
