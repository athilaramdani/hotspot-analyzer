import pydicom
import numpy as np


def load_frames_and_metadata_matrix(path: str):
    """
    Baca file DICOM dan kembalikan:
    - frames : np.ndarray  (shape = [N, H, W] , minimal 2 frame)
    - meta   : dict        (patient / study metadata)
    """
    ds = pydicom.dcmread(path)

    # pixel_array bisa 2-D (single-frame) atau 3-D (multi-frame)
    frames = ds.pixel_array
    if frames.ndim == 2:                        # jika cuma satu frame
        frames = np.expand_dims(frames, 0)

    meta = {
        "patient_id":   getattr(ds, "PatientID",   ""),
        "patient_name": str(getattr(ds, "PatientName", "")),
        "patient_birth": getattr(ds, "PatientBirthDate", ""),
        "patient_sex":  getattr(ds, "PatientSex",  ""),
        "study_date":   getattr(ds, "StudyDate",   ""),
    }

    return frames, meta
