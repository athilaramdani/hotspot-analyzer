# backend/pet_directory_scanner.py
"""
Scanner untuk direktori PET data.
Mencari folder pasien dan file PET di dalam struktur:
data/PET/[patient_id]/
"""
from pathlib import Path
from typing import Dict, List
import nibabel as nib


def scan_pet_directory(directory: Path) -> Dict[str, List[Path]]:
    """
    Scan direktori PET dan return mapping patient_id -> list of patient folders
    
    Args:
        directory: Path ke direktori PET (biasanya data/PET)
        
    Returns:
        Dict mapping patient_id ke list folder patient yang berisi data PET
    """
    patient_map: Dict[str, List[Path]] = {}
    
    if not directory.exists():
        print(f"PET directory tidak ditemukan: {directory}")
        return patient_map
    
    # Scan semua subfolder dalam direktori PET
    for patient_folder in directory.iterdir():
        if not patient_folder.is_dir():
            continue
            
        patient_id = patient_folder.name
        
        # Cek apakah folder mengandung file PET yang valid
        if _has_valid_pet_data(patient_folder):
            patient_map.setdefault(patient_id, []).append(patient_folder)
            print(f"Found PET data for patient {patient_id} in {patient_folder}")
    
    total_patients = len(patient_map)
    print(f"Found {total_patients} patients with PET data")
    
    return patient_map


def _has_valid_pet_data(folder: Path) -> bool:
    """
    Cek apakah folder mengandung file PET yang valid
    Minimal harus ada file PET.nii.gz atau file .nii yang mengandung 'pet'
    """
    # Cek file PET utama
    pet_files = [
        "PET.nii.gz", "PET.nii", 
        "pet.nii.gz", "pet.nii",
        "8_pet_corr.nii"  # sesuai contoh data
    ]
    
    for pet_file in pet_files:
        if (folder / pet_file).exists():
            return True
    
    # Cek file .nii/.nii.gz lainnya yang mengandung 'pet'
    for nii_file in folder.glob("*.nii*"):
        if "pet" in nii_file.name.lower():
            return True
    
    return False


def get_pet_files(patient_folder: Path) -> Dict[str, Path]:
    """
    Dapatkan file-file PET yang tersedia dalam folder pasien
    
    Returns:
        Dict dengan key sebagai nama file dan value sebagai Path
    """
    pet_files = {}
    
    # File-file standar yang dicari
    standard_files = {
        "PET": ["PET.nii.gz", "PET.nii", "pet.nii.gz", "pet.nii"],
        "CT": ["CT.nii.gz", "CT.nii", "ct.nii.gz", "ct.nii"],
        "SEG": ["SEG.nii.gz", "SEG.nii", "seg.nii.gz", "seg.nii"],
        "SUV": ["SUV.nii.gz", "SUV.nii", "suv.nii.gz", "suv.nii"],
        "CTres": ["CTres.nii.gz", "CTres.nii"],
        "PET_CORR": ["8_pet_corr.nii"]
    }
    
    for file_type, possible_names in standard_files.items():
        for name in possible_names:
            file_path = patient_folder / name
            if file_path.exists():
                pet_files[file_type] = file_path
                break
    
    return pet_files


def validate_pet_file(file_path: Path) -> bool:
    """
    Validasi apakah file PET dapat dibaca dengan benar
    """
    try:
        img = nib.load(str(file_path))
        data = img.get_fdata()
        
        # Cek dimensi minimal (harus 3D atau 4D)
        if len(data.shape) < 3:
            return False
            
        # Cek apakah ada data (tidak semua nol)
        if data.max() == 0:
            return False
            
        return True
        
    except Exception as e:
        print(f"Error validating PET file {file_path}: {e}")
        return False


def get_pet_metadata(file_path: Path) -> Dict:
    """
    Extract metadata dari file PET
    """
    try:
        img = nib.load(str(file_path))
        header = img.header
        
        metadata = {
            "shape": img.shape,
            "affine": img.affine.tolist(),
            "voxel_size": header.get_zooms(),
            "data_type": str(img.get_data_dtype()),
            "file_size": file_path.stat().st_size,
            "file_path": str(file_path)
        }
        
        return metadata
        
    except Exception as e:
        print(f"Error extracting metadata from {file_path}: {e}")
        return {}