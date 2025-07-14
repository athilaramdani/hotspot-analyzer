# core/config/paths.py
"""
Configuration file untuk semua path constants dalam Hotspot Analyzer
"""
from pathlib import Path
import os

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
SEGMENTATION_MODEL_PATH = MODELS_ROOT / "segmentation"
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

def get_patient_spect_path(patient_id: str, session_code: str = None) -> Path:
    """Get path to patient's SPECT data folder"""
    if session_code:
        return SPECT_DATA_PATH / f"{patient_id}_{session_code}"
    return SPECT_DATA_PATH / patient_id

def get_patient_pet_path(patient_id: str) -> Path:
    """Get path to patient's PET data folder"""
    return PET_DATA_PATH / patient_id

def get_segmentation_files(patient_folder: Path, filename_stem: str, view: str):
    """Get segmentation file paths for a specific view"""
    base = patient_folder / filename_stem
    vtag = view.lower()
    
    return {
        'png_mask': base.with_name(f"{filename_stem}_{vtag}_mask.png"),
        'png_colored': base.with_name(f"{filename_stem}_{vtag}_colored.png"),
        'dcm_mask': base.with_name(f"{filename_stem}_{vtag}_mask.dcm"),
        'dcm_colored': base.with_name(f"{filename_stem}_{vtag}_colored.dcm")
    }

def get_hotspot_files(patient_id: str, session_code: str, view: str):
    """Get hotspot file paths for a specific patient and view"""
    patient_folder = get_patient_spect_path(patient_id, session_code)
    view_suffix = "ant" if "ant" in view.lower() else "post"
    
    return {
        'colored_png': patient_folder / f"{patient_id}_{view_suffix}_hotspot_colored.png",
        'xml_file': patient_folder / f"{patient_id}_{view_suffix}.xml",
        'mask_file': patient_folder / f"{patient_id}_{view_suffix}_hotspot_mask.png"
    }

def get_output_path(patient_id: str, analysis_type: str = "hotspot") -> Path:
    """Get output path for patient analysis results"""
    return RESULTS_PATH / analysis_type / patient_id

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