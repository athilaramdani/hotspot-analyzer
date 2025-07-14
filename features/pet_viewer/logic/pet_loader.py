# features/pet_viewer/logic/pet_loader.py
"""
Loader untuk data PET menggunakan nibabel dan monai
"""
from pathlib import Path
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass
import numpy as np
import nibabel as nib

from .pet_directory_scanner import get_pet_files, validate_pet_file, get_pet_metadata


@dataclass
class PETData:
    """Data class untuk menyimpan data PET"""
    patient_id: str
    pet_image: Optional[np.ndarray] = None
    ct_image: Optional[np.ndarray] = None
    seg_image: Optional[np.ndarray] = None
    suv_image: Optional[np.ndarray] = None
    pet_corr_image: Optional[np.ndarray] = None
    
    # Metadata
    pet_metadata: Dict = None
    ct_metadata: Dict = None
    seg_metadata: Dict = None
    suv_metadata: Dict = None
    
    # Affine transforms
    pet_affine: Optional[np.ndarray] = None
    ct_affine: Optional[np.ndarray] = None
    seg_affine: Optional[np.ndarray] = None
    suv_affine: Optional[np.ndarray] = None
    
    def __post_init__(self):
        if self.pet_metadata is None:
            self.pet_metadata = {}
        if self.ct_metadata is None:
            self.ct_metadata = {}
        if self.seg_metadata is None:
            self.seg_metadata = {}
        if self.suv_metadata is None:
            self.suv_metadata = {}


def load_pet_data(patient_folder: Path, progress_callback: Optional[Callable[[str, int], None]] = None) -> Optional[PETData]:
    """
    Load PET data dari folder pasien
    
    Args:
        patient_folder: Path ke folder pasien yang berisi file PET
        progress_callback: Optional callback function(message, progress_percent)
        
    Returns:
        PETData object atau None jika gagal
    """
    def report_progress(message: str, progress: int):
        if progress_callback:
            progress_callback(message, progress)
    
    try:
        patient_id = patient_folder.name
        print(f"Loading PET data for patient {patient_id} from {patient_folder}")
        
        report_progress("Scanning folder for PET files...", 10)
        
        # Dapatkan file-file PET yang tersedia
        pet_files = get_pet_files(patient_folder)
        
        if not pet_files:
            print(f"No PET files found in {patient_folder}")
            return None
        
        report_progress("Initializing data structure...", 20)
        
        # Inisialisasi PETData
        pet_data = PETData(patient_id=patient_id)
        
        total_files = len(pet_files)
        current_file = 0
        
        # Load PET image (prioritas utama)
        if "PET" in pet_files:
            current_file += 1
            report_progress(f"Loading PET image ({current_file}/{total_files})...", 30 + (current_file * 10))
            pet_data.pet_image, pet_data.pet_affine, pet_data.pet_metadata = _load_nii_file(pet_files["PET"])
        elif "PET_CORR" in pet_files:
            current_file += 1
            report_progress(f"Loading PET corrected image ({current_file}/{total_files})...", 30 + (current_file * 10))
            pet_data.pet_corr_image, pet_data.pet_affine, pet_data.pet_metadata = _load_nii_file(pet_files["PET_CORR"])
        
        # Load CT image (opsional)
        if "CT" in pet_files:
            current_file += 1
            report_progress(f"Loading CT image ({current_file}/{total_files})...", 30 + (current_file * 10))
            pet_data.ct_image, pet_data.ct_affine, pet_data.ct_metadata = _load_nii_file(pet_files["CT"])
        
        # Load segmentation (opsional)
        if "SEG" in pet_files:
            current_file += 1
            report_progress(f"Loading segmentation ({current_file}/{total_files})...", 30 + (current_file * 10))
            pet_data.seg_image, pet_data.seg_affine, pet_data.seg_metadata = _load_nii_file(pet_files["SEG"])
        
        # Load SUV (opsional)
        if "SUV" in pet_files:
            current_file += 1
            report_progress(f"Loading SUV image ({current_file}/{total_files})...", 30 + (current_file * 10))
            pet_data.suv_image, pet_data.suv_affine, pet_data.suv_metadata = _load_nii_file(pet_files["SUV"])
        
        report_progress("Validating loaded data...", 90)
        
        # Validasi minimal ada satu image yang berhasil dimuat
        if (pet_data.pet_image is None and 
            pet_data.pet_corr_image is None and 
            pet_data.ct_image is None):
            print(f"No valid images loaded for patient {patient_id}")
            return None
        
        report_progress("Loading completed successfully!", 100)
        
        print(f"Successfully loaded PET data for patient {patient_id}")
        return pet_data
        
    except Exception as e:
        print(f"Error loading PET data from {patient_folder}: {e}")
        if progress_callback:
            progress_callback(f"Error: {str(e)}", 0)
        return None


def _load_nii_file(file_path: Path) -> tuple[Optional[np.ndarray], Optional[np.ndarray], Dict]:
    """
    Load file NIfTI dan return image data, affine, dan metadata
    
    Returns:
        tuple: (image_data, affine_matrix, metadata)
    """
    try:
        print(f"Loading NIfTI file: {file_path}")
        
        # Validasi file
        if not validate_pet_file(file_path):
            print(f"Invalid PET file: {file_path}")
            return None, None, {}
        
        # Load dengan nibabel
        img = nib.load(str(file_path))
        image_data = img.get_fdata()
        affine = img.affine
        
        # Get metadata
        metadata = get_pet_metadata(file_path)
        
        # Normalisasi data jika diperlukan
        if image_data.max() > 0:
            # Clip outliers (optional)
            p99 = np.percentile(image_data[image_data > 0], 99)
            image_data = np.clip(image_data, 0, p99)
        
        print(f"Loaded image shape: {image_data.shape}, dtype: {image_data.dtype}")
        
        return image_data, affine, metadata
        
    except Exception as e:
        print(f"Error loading NIfTI file {file_path}: {e}")
        return None, None, {}


def get_slice_data(image_data: np.ndarray, axis: int, slice_idx: int) -> np.ndarray:
    """
    Dapatkan slice dari image data pada axis dan index tertentu
    
    Args:
        image_data: 3D atau 4D numpy array
        axis: axis untuk slice (0=sagittal, 1=coronal, 2=axial)
        slice_idx: index slice
        
    Returns:
        2D numpy array dari slice
    """
    if image_data is None:
        return None
    
    # Handle 4D data (ambil volume pertama)
    if len(image_data.shape) == 4:
        image_data = image_data[:, :, :, 0]
    
    # Pastikan 3D
    if len(image_data.shape) != 3:
        return None
    
    # Clip slice index
    slice_idx = max(0, min(slice_idx, image_data.shape[axis] - 1))
    
    # Extract slice
    if axis == 0:  # Sagittal
        slice_data = image_data[slice_idx, :, :]
    elif axis == 1:  # Coronal
        slice_data = image_data[:, slice_idx, :]
    elif axis == 2:  # Axial
        slice_data = image_data[:, :, slice_idx]
    else:
        return None
    
    return slice_data


def normalize_image_for_display(image_data: np.ndarray) -> np.ndarray:
    """
    Normalisasi image data untuk display (0-255)
    """
    if image_data is None:
        return None
    
    # Handle NaN dan infinite values
    image_data = np.nan_to_num(image_data)
    
    # Normalisasi ke range 0-255
    if image_data.max() > image_data.min():
        normalized = (image_data - image_data.min()) / (image_data.max() - image_data.min())
        normalized = (normalized * 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(image_data, dtype=np.uint8)
    
    return normalized


def extract_patient_info(pet_data: PETData) -> Dict[str, Any]:
    """
    Extract informasi pasien dari PET data untuk display
    """
    info = {
        "patient_id": pet_data.patient_id,
        "has_pet": pet_data.pet_image is not None or pet_data.pet_corr_image is not None,
        "has_ct": pet_data.ct_image is not None,
        "has_seg": pet_data.seg_image is not None,
        "has_suv": pet_data.suv_image is not None,
    }
    
    # Tambahkan info dari metadata
    if pet_data.pet_metadata:
        info.update({
            "pet_shape": pet_data.pet_metadata.get("shape", "Unknown"),
            "pet_voxel_size": pet_data.pet_metadata.get("voxel_size", "Unknown"),
            "pet_data_type": pet_data.pet_metadata.get("data_type", "Unknown"),
        })
    
    return info