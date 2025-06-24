import pydicom
from pathlib import Path
from typing import Dict, List

def scan_dicom_directory(directory: Path) -> Dict[str, List[Path]]:
    """
    Memindai direktori untuk file DICOM dan mengelompokkan path file berdasarkan PatientID.
    Membaca hanya metadata untuk efisiensi.
    """
    patient_map: Dict[str, List[Path]] = {}
    
    dicom_files = list(directory.glob('**/*.dcm'))
    print(f"Ditemukan {len(dicom_files)} file .dcm di '{directory}'")

    for file_path in dicom_files:
        try:
            ds = pydicom.dcmread(file_path, stop_before_pixels=True)
            patient_id = ds.get("PatientID", None)

            if patient_id:
                if patient_id not in patient_map:
                    patient_map[patient_id] = []
                patient_map[patient_id].append(file_path)

        except Exception as e:
            print(f"Gagal membaca metadata dari {file_path}: {e}")

    print(f"Ditemukan {len(patient_map)} ID pasien unik.")
    return patient_map