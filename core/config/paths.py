# core/config/paths.py
"""
Configuration file untuk semua path constants dalam Hotspot Analyzer
Updated to support study date in filenames
"""
from pathlib import Path
import os
from dotenv import load_dotenv
from typing import Optional
import pydicom
from ultralytics import YOLO
import cv2
import matplotlib.pyplot as plt

# Load environment variables
load_dotenv()

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent.parent  # hotspot-analyzer/
DATA_ROOT = PROJECT_ROOT / "data"
MODELS_ROOT = PROJECT_ROOT / "models"
TEMP_ROOT = PROJECT_ROOT / "temp"
LOGS_ROOT = PROJECT_ROOT / "logs"

# Data paths
PET_DATA_PATH = DATA_ROOT / "PET"
SPECT_DATA_PATH = DATA_ROOT / "SPECT"
DICOM_DATA_PATH = DATA_ROOT / "DICOM"

# Model paths
HOTSPOT_MODEL_PATH = MODELS_ROOT / "hotspot_detection"
SEGMENTATION_MODEL_PATH = MODELS_ROOT / "segmentation_2"
CLASSIFICATION_MODEL_PATH = MODELS_ROOT / "classification"

# Specific model files
YOLO_MODEL_PATH = HOTSPOT_MODEL_PATH / "yolo_hotspot.pt"
UNET_MODEL_PATH = SEGMENTATION_MODEL_PATH / "unet_seg.pth"
CNN_MODEL_PATH = CLASSIFICATION_MODEL_PATH / "cnn_classifier.pth"

# Config files
CONFIG_ROOT = PROJECT_ROOT / "config"
MODEL_CONFIG_PATH = CONFIG_ROOT / "model_config.json"
APP_CONFIG_PATH = CONFIG_ROOT / "app_config.json"

# Output paths
OUTPUT_ROOT = PROJECT_ROOT / "output"
RESULTS_PATH = OUTPUT_ROOT / "results"
EXPORTS_PATH = OUTPUT_ROOT / "exports"
REPORTS_PATH = OUTPUT_ROOT / "reports"

# Cache paths
CACHE_ROOT = PROJECT_ROOT / ".cache"
IMAGE_CACHE_PATH = CACHE_ROOT / "images"
MODEL_CACHE_PATH = CACHE_ROOT / "models"

# Temp paths
TEMP_IMAGES_PATH = TEMP_ROOT / "images"
TEMP_PROCESSING_PATH = TEMP_ROOT / "processing"

# Log paths
APP_LOG_PATH = LOGS_ROOT / "app.log"
ERROR_LOG_PATH = LOGS_ROOT / "error.log"
DEBUG_LOG_PATH = LOGS_ROOT / "debug.log"

# Asset paths (icons, images, etc)
ASSETS_ROOT = PROJECT_ROOT / "assets"
ICONS_PATH = ASSETS_ROOT / "icons"
IMAGES_PATH = ASSETS_ROOT / "images"

# Detection Model Path
YOLO_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "hotspot_detection" / "models" / "model_detection_hs_yolov8.pt"


# ===== CLOUD STORAGE CONFIGURATION =====
# BackBlaze B2 Configuration
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY") 
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "hotspot-analyzer-data")
B2_ENDPOINT = os.getenv("B2_ENDPOINT", "https://s3.us-west-004.backblazeb2.com")

# Cloud sync settings
CLOUD_SYNC_ENABLED = os.getenv("CLOUD_SYNC_ENABLED", "false").lower() == "true"
AUTO_BACKUP = os.getenv("AUTO_BACKUP", "false").lower() == "true"
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))

# Cloud paths mapping
CLOUD_DATA_PREFIX = "data/"
CLOUD_MODELS_PREFIX = "models/"
CLOUD_LOGS_PREFIX = "logs/"
CLOUD_BACKUP_PREFIX = "backups/"

# Default file extensions
NIFTI_EXTENSIONS = [".nii", ".nii.gz"]
DICOM_EXTENSIONS = [".dcm", ".dicom"]
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]
MODEL_EXTENSIONS = [".pt", ".pth", ".onnx", ".h5"]

# Default file names
DEFAULT_PET_FILENAME = "PET.nii.gz"
DEFAULT_CT_FILENAME = "CT.nii.gz"
DEFAULT_SEG_FILENAME = "SEG.nii.gz"
DEFAULT_SUV_FILENAME = "SUV.nii.gz"

def ensure_directories():
    """
    Ensure all necessary directories exist
    """
    directories = [
        DATA_ROOT, PET_DATA_PATH, SPECT_DATA_PATH, DICOM_DATA_PATH,
        MODELS_ROOT, HOTSPOT_MODEL_PATH, SEGMENTATION_MODEL_PATH, CLASSIFICATION_MODEL_PATH,
        OUTPUT_ROOT, RESULTS_PATH, EXPORTS_PATH, REPORTS_PATH,
        CACHE_ROOT, IMAGE_CACHE_PATH, MODEL_CACHE_PATH,
        TEMP_ROOT, TEMP_IMAGES_PATH, TEMP_PROCESSING_PATH,
        LOGS_ROOT, ASSETS_ROOT, ICONS_PATH, IMAGES_PATH
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

# ===== NEW DIRECTORY STRUCTURE FUNCTIONS WITH STUDY DATE =====
def extract_study_date_from_dicom(dicom_path: Path) -> str:
    """
    Extract study date from DICOM file
    
    Args:
        dicom_path: Path to DICOM file
        
    Returns:
        Study date in YYYYMMDD format, or current date if not found
    """
    try:
        ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
        study_date = getattr(ds, 'StudyDate', None)
        
        if study_date:
            # Ensure it's in YYYYMMDD format
            study_date = str(study_date).replace('-', '').replace('/', '')
            if len(study_date) == 8 and study_date.isdigit():
                return study_date
        
        # Fallback: use SeriesDate
        series_date = getattr(ds, 'SeriesDate', None)
        if series_date:
            series_date = str(series_date).replace('-', '').replace('/', '')
            if len(series_date) == 8 and series_date.isdigit():
                return series_date
        
        # Final fallback: current date
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d")
        
    except Exception as e:
        print(f"Warning: Could not extract study date from {dicom_path}: {e}")
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d")

def generate_filename_stem(patient_id: str, study_date: str) -> str:
    """
    Generate filename stem with patient ID and study date
    
    Args:
        patient_id: Patient ID
        study_date: Study date in YYYYMMDD format
        
    Returns:
        Filename stem: [patient_id]_[study_date]
    """
    return f"{patient_id}_{study_date}"

def get_patient_spect_path(patient_id: str, session_code: str) -> Path:
    """
    Get path to patient's SPECT data folder with NEW structure
    NEW: data/SPECT/[session_code]/[patient_id]/
    OLD: data/SPECT/[patient_id]_[session_code]/
    """
    return SPECT_DATA_PATH / session_code / patient_id

def get_session_spect_path(session_code: str) -> Path:
    """Get path to session's SPECT data folder"""
    return SPECT_DATA_PATH / session_code

def get_patient_pet_path(patient_id: str, session_code: str = None) -> Path:
    """Get path to patient's PET data folder"""
    if session_code:
        return PET_DATA_PATH / session_code / patient_id
    return PET_DATA_PATH / patient_id

def get_segmentation_files(patient_folder: Path, filename_stem: str, view: str):
    """
    Get segmentation file paths for a specific view with study date support
    
    Args:
        patient_folder: Patient directory path
        filename_stem: Filename stem ([patient_id]_[study_date])
        view: View name (anterior/posterior)
        
    Returns:
        Dictionary with file paths
    """
    vtag = view.lower()
    
    return {
        'png_mask': patient_folder / f"{filename_stem}_{vtag}_mask.png",
        'png_colored': patient_folder / f"{filename_stem}_{vtag}_colored.png",
        'dcm_mask': patient_folder / f"{filename_stem}_{vtag}_mask.dcm",
        'dcm_colored': patient_folder / f"{filename_stem}_{vtag}_colored.dcm"
    }

def get_segmentation_files_with_edited(patient_folder: Path, filename_stem: str, view: str):
    """
    Get segmentation file paths including edited versions with study date support
    
    Args:
        patient_folder: Patient directory path
        filename_stem: Filename stem ([patient_id]_[study_date])
        view: View name (anterior/posterior)
        
    Returns:
        Dictionary with original and edited file paths
    """
    vtag = view.lower()
    
    return {
        # Original files
        'png_mask': patient_folder / f"{filename_stem}_{vtag}_mask.png",
        'png_colored': patient_folder / f"{filename_stem}_{vtag}_colored.png",
        'dcm_mask': patient_folder / f"{filename_stem}_{vtag}_mask.dcm",
        'dcm_colored': patient_folder / f"{filename_stem}_{vtag}_colored.dcm",
        
        # Edited files
        'png_mask_edited': patient_folder / f"{filename_stem}_{vtag}_edited_mask.png",
        'png_colored_edited': patient_folder / f"{filename_stem}_{vtag}_edited_colored.png",
        'dcm_mask_edited': patient_folder / f"{filename_stem}_{vtag}_edited_mask.dcm",
        'dcm_colored_edited': patient_folder / f"{filename_stem}_{vtag}_edited_colored.dcm",
    }

# UPDATE get_hotspot_files function in paths.py

def get_hotspot_files(patient_id: str, session_code: str, view: str, study_date: str):
    """
    Get hotspot file paths for a specific patient and view with study date
    Updated to include PURE colored versions
    
    Args:
        patient_id: Patient ID
        session_code: Session code
        view: View name
        study_date: Study date in YYYYMMDD format
        
    Returns:
        Dictionary with hotspot file paths including pure versions
    """
    patient_folder = get_patient_spect_path(patient_id, session_code)
    filename_stem = generate_filename_stem(patient_id, study_date)
    view_suffix = "ant" if "ant" in view.lower() else "post"
    view_full = "anterior" if "ant" in view.lower() else "posterior"
    
    return {
        # ✅ BLENDED VERSIONS (with original DICOM background)
        'colored_png': patient_folder / f"{filename_stem}_{view_suffix}_hotspot_colored.png",
        'xml_file': patient_folder / f"{filename_stem}_{view_suffix}.xml",
        'mask_file': patient_folder / f"{filename_stem}_{view_suffix}_hotspot_mask.png",
        
        # ✅ PURE VERSIONS (palette colors only, no background)
        'pure_colored_png': patient_folder / f"{filename_stem}_{view_full}_hotspot_colored.png",
        
        # Edited versions (blended)
        'colored_png_edited': patient_folder / f"{filename_stem}_{view_suffix}_hotspot_edited_colored.png",
        'xml_file_edited': patient_folder / f"{filename_stem}_{view_suffix}_edited.xml",
        'mask_file_edited': patient_folder / f"{filename_stem}_{view_suffix}_hotspot_edited_mask.png",
        
        # ✅ Edited versions (pure)
        'pure_colored_png_edited': patient_folder / f"{filename_stem}_{view_full}_hotspot_edited_colored.png",
    }

def get_dicom_output_path(patient_id: str, session_code: str, study_date: str) -> Path:
    """
    Get output path for processed DICOM file with study date
    
    Args:
        patient_id: Patient ID
        session_code: Session code
        study_date: Study date in YYYYMMDD format
        
    Returns:
        Path for output DICOM file
    """
    patient_folder = get_patient_spect_path(patient_id, session_code)
    filename_stem = generate_filename_stem(patient_id, study_date)
    return patient_folder / f"{filename_stem}.dcm"

def get_output_path(patient_id: str, session_code: str, analysis_type: str = "hotspot") -> Path:
    """Get output path for patient analysis results"""
    return RESULTS_PATH / analysis_type / session_code / patient_id

def get_temp_path(session_id: str = None) -> Path:
    """Get temporary processing path"""
    if session_id:
        return TEMP_PROCESSING_PATH / session_id
    return TEMP_PROCESSING_PATH

def get_model_path(model_name: str) -> Path:
    """Get path for specific model"""
    model_paths = {
        "yolo": YOLO_MODEL_PATH,
        "unet": UNET_MODEL_PATH,
        "cnn": CNN_MODEL_PATH
    }
    return model_paths.get(model_name.lower(), MODELS_ROOT / f"{model_name}.pt")

def find_files_by_pattern(patient_folder: Path, patient_id: str, pattern: str = "*") -> list[Path]:
    """
    Find files matching pattern with any study date
    
    Args:
        patient_folder: Patient directory
        patient_id: Patient ID
        pattern: File pattern (e.g., "*_anterior_*.png")
        
    Returns:
        List of matching files
    """
    search_pattern = f"{patient_id}_*{pattern}"
    return list(patient_folder.glob(search_pattern))

def parse_filename_components(filename: str) -> dict:
    """
    Parse filename to extract components
    
    Args:
        filename: Filename to parse
        
    Returns:
        Dictionary with parsed components
    """
    try:
        parts = filename.split('_')
        if len(parts) >= 2:
            patient_id = parts[0]
            study_date = parts[1]
            
            # Extract other components
            remaining = '_'.join(parts[2:])
            
            result = {
                'patient_id': patient_id,
                'study_date': study_date,
                'remaining': remaining,
                'is_edited': 'edited' in remaining,
                'view': None,
                'file_type': None
            }
            
            # Detect view
            if 'anterior' in remaining:
                result['view'] = 'anterior'
            elif 'posterior' in remaining:
                result['view'] = 'posterior'
            
            # Detect file type
            if 'mask' in remaining:
                result['file_type'] = 'mask'
            elif 'colored' in remaining:
                result['file_type'] = 'colored'
            elif 'hotspot' in remaining:
                result['file_type'] = 'hotspot'
            
            return result
            
    except Exception as e:
        print(f"Error parsing filename {filename}: {e}")
    
    return {
        'patient_id': None,
        'study_date': None,
        'remaining': filename,
        'is_edited': False,
        'view': None,
        'file_type': None
    }

# ===== CLOUD PATH HELPERS =====
def get_cloud_path(local_path: Path) -> str:
    """Convert local path to cloud storage path"""
    try:
        # Get relative path from project root
        rel_path = local_path.relative_to(PROJECT_ROOT)
        
        # Convert to cloud path format (use forward slashes)
        cloud_path = str(rel_path).replace("\\", "/")
        
        return cloud_path
    except ValueError:
        # Path is not relative to project root
        return str(local_path).replace("\\", "/")

def get_local_path_from_cloud(cloud_path: str) -> Path:
    """Convert cloud storage path to local path"""
    return PROJECT_ROOT / cloud_path.replace("/", os.sep)

def get_cloud_spect_path(session_code: str, patient_id: str = None) -> str:
    """Get cloud path for SPECT data"""
    if patient_id:
        return f"data/SPECT/{session_code}/{patient_id}"
    return f"data/SPECT/{session_code}"

def get_cloud_pet_path(patient_id: str, session_code: str = None) -> str:
    """Get cloud path for PET data"""
    if session_code:
        return f"data/PET/{session_code}/{patient_id}"
    return f"data/PET/{patient_id}"

def is_cloud_enabled() -> bool:
    """Check if cloud storage is properly configured and enabled"""
    return (CLOUD_SYNC_ENABLED and 
            B2_KEY_ID and 
            B2_APPLICATION_KEY and 
            B2_BUCKET_NAME and 
            B2_ENDPOINT)

# ===== MIGRATION HELPERS =====
def get_old_patient_spect_path(patient_id: str, session_code: str) -> Path:
    """Get OLD path structure for migration purposes"""
    return SPECT_DATA_PATH / f"{patient_id}_{session_code}"

def migrate_old_to_new_structure():
    """
    Migrate old directory structure to new structure
    OLD: data/SPECT/[patient_id]_[session_code]/
    NEW: data/SPECT/[session_code]/[patient_id]/
    """
    if not SPECT_DATA_PATH.exists():
        return
    
    print("🔄 Migrating SPECT directory structure...")
    
    # Find all old-style directories
    old_directories = []
    for item in SPECT_DATA_PATH.iterdir():
        if item.is_dir() and "_" in item.name:
            # Check if it's old format (patient_id_session_code)
            parts = item.name.split("_")
            if len(parts) >= 2:
                old_directories.append(item)
    
    migrated_count = 0
    for old_dir in old_directories:
        try:
            # Parse old directory name
            parts = old_dir.name.split("_")
            patient_id = parts[0]
            session_code = "_".join(parts[1:])  # Handle multi-part session codes
            
            # Create new path
            new_path = get_patient_spect_path(patient_id, session_code)
            
            if not new_path.exists():
                # Create parent directory
                new_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Move directory
                old_dir.rename(new_path)
                print(f"✅ Migrated: {old_dir} → {new_path}")
                migrated_count += 1
            else:
                print(f"⚠️  Target already exists: {new_path}")
                
        except Exception as e:
            print(f"❌ Failed to migrate {old_dir}: {e}")
    
    print(f"📁 Migration completed: {migrated_count} directories migrated")

def migrate_filenames_to_study_date():
    """
    Migrate existing files to include study date in filenames
    This will scan all patient folders and rename files to include study date
    """
    if not SPECT_DATA_PATH.exists():
        return
    
    print("🔄 Migrating filenames to include study date...")
    
    migrated_count = 0
    for session_dir in SPECT_DATA_PATH.iterdir():
        if not session_dir.is_dir():
            continue
            
        for patient_dir in session_dir.iterdir():
            if not patient_dir.is_dir():
                continue
                
            patient_id = patient_dir.name
            session_code = session_dir.name
            
            # Find primary DICOM file to extract study date
            dicom_files = list(patient_dir.glob("*.dcm"))
            primary_dicom = None
            
            for dcm_file in dicom_files:
                # Skip secondary capture files
                if any(skip in dcm_file.name.lower() for skip in ['mask', 'colored', 'edited']):
                    continue
                primary_dicom = dcm_file
                break
            
            if not primary_dicom:
                print(f"⚠️  No primary DICOM found in {patient_dir}")
                continue
            
            try:
                # Extract study date
                study_date = extract_study_date_from_dicom(primary_dicom)
                new_filename_stem = generate_filename_stem(patient_id, study_date)
                
                # Rename all files in the directory
                for file_path in patient_dir.iterdir():
                    if not file_path.is_file():
                        continue
                    
                    old_name = file_path.name
                    
                    # Skip if already has study date pattern
                    if len(old_name.split('_')) >= 2 and old_name.split('_')[1].isdigit() and len(old_name.split('_')[1]) == 8:
                        continue
                    
                    # Generate new name
                    if old_name.startswith(patient_id):
                        # Replace patient_id with patient_id_studydate
                        new_name = old_name.replace(patient_id, new_filename_stem, 1)
                        new_path = patient_dir / new_name
                        
                        if new_path != file_path:
                            file_path.rename(new_path)
                            print(f"✅ Renamed: {old_name} → {new_name}")
                            migrated_count += 1
                    
            except Exception as e:
                print(f"❌ Failed to migrate files in {patient_dir}: {e}")
    
    print(f"📁 Filename migration completed: {migrated_count} files renamed")

# Environment-specific overrides
if os.getenv("DEVELOPMENT"):
    # Development environment paths
    DATA_ROOT = PROJECT_ROOT / "dev_data"
    MODELS_ROOT = PROJECT_ROOT / "dev_models"

if os.getenv("PRODUCTION"):
    # Production environment paths
    DATA_ROOT = Path("/opt/hotspot-analyzer/data")
    MODELS_ROOT = Path("/opt/hotspot-analyzer/models")
    LOGS_ROOT = Path("/var/log/hotspot-analyzer")

# Validate critical paths exist
def validate_paths():
    """Validate that critical paths exist and are accessible"""
    critical_paths = [PROJECT_ROOT, DATA_ROOT]
    
    for path in critical_paths:
        if not path.exists():
            raise FileNotFoundError(f"Critical path does not exist: {path}")
        if not os.access(path, os.R_OK):
            raise PermissionError(f"No read access to critical path: {path}")
    
    return True

def validate_cloud_config():
    """Validate cloud storage configuration"""
    if not is_cloud_enabled():
        missing = []
        if not B2_KEY_ID:
            missing.append("B2_KEY_ID")
        if not B2_APPLICATION_KEY:
            missing.append("B2_APPLICATION_KEY")
        if not B2_BUCKET_NAME:
            missing.append("B2_BUCKET_NAME")
        if not B2_ENDPOINT:
            missing.append("B2_ENDPOINT")
        
        return False, f"Missing cloud configuration: {', '.join(missing)}"
    
    return True, "Cloud configuration is valid"