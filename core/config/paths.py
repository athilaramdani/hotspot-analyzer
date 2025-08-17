# core/config/paths.py
"""
Configuration file untuk semua path constants dalam Hotspot Analyzer
Updated for PLANAR-only workflow with timestamp-based editing
"""
from pathlib import Path
import sys
from dotenv import load_dotenv
from typing import Optional, Dict, List
import pydicom
from datetime import datetime
from PIL import Image  # ✅ TAMBAHAN
import numpy as np     # ✅ TAMBAHAN

# Load environment variables
load_dotenv()

def get_safe_project_root() -> Path:
    """Get project root with build compatibility for PyInstaller"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent.parent.parent

# Base paths
PROJECT_ROOT = get_safe_project_root()
DATA_ROOT = PROJECT_ROOT / "data"
MODELS_ROOT = PROJECT_ROOT / "models"
TEMP_ROOT = PROJECT_ROOT / "temp"
LOGS_ROOT = PROJECT_ROOT / "logs"

# Data paths - PLANAR only
PLANAR_DATA_PATH = DATA_ROOT / "PLANAR"
DICOM_DATA_PATH = DATA_ROOT / "DICOM"

# Model paths
HOTSPOT_MODEL_PATH = MODELS_ROOT / "hotspot_detection"
SEGMENTATION_MODEL_PATH = MODELS_ROOT / "segmentation_2"
CLASSIFICATION_MODEL_PATH = MODELS_ROOT / "classification"

# Specific model files
YOLO_MODEL_PATH = HOTSPOT_MODEL_PATH / "yolo_hotspot.pt"
UNET_MODEL_PATH = SEGMENTATION_MODEL_PATH / "unet_seg.pth"
CNN_MODEL_PATH = CLASSIFICATION_MODEL_PATH / "cnn_classifier.pth"
CLASSIFICATION_XGBOOST_MODEL = CLASSIFICATION_MODEL_PATH / "model_classification_hs_xgboost_250724.pkl" 
CLASSIFICATION_SCALER_MODEL = CLASSIFICATION_MODEL_PATH / "scaler_classification_32features.pkl"

# Detection Model Path with build compatibility
if getattr(sys, 'frozen', False):
    YOLO_MODEL_PATH = MODELS_ROOT / "hotspot_detection" / "models" / "model_detection_hs_yolov8.pt"
else:
    YOLO_MODEL_PATH = PROJECT_ROOT / "models" / "hotspot_detection" / "models" / "model_detection_hs_yolov8.pt"

# Config files
CONFIG_ROOT = PROJECT_ROOT / "config"
MODEL_CONFIG_PATH = CONFIG_ROOT / "model_config.json"
APP_CONFIG_PATH = CONFIG_ROOT / "app_config.json"

# Asset paths (icons, images, etc)
ASSETS_ROOT = PROJECT_ROOT / "assets"
ICONS_PATH = ASSETS_ROOT / "icons"
IMAGES_PATH = ASSETS_ROOT / "images"

# Default file extensions
NIFTI_EXTENSIONS = [".nii", ".nii.gz"]
DICOM_EXTENSIONS = [".dcm", ".dicom"]
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]
MODEL_EXTENSIONS = [".pt", ".pth", ".onnx", ".h5"]

# Editable files that support timestamp-based editing
EDITABLE_FILES = [
    "ant_segm.png",
    "post_segm.png", 
    "ant_hotspot_classification.png",
    "post_hotspot_classification.png"
]
def get_newest_hotspot_classification_path(patient_folder: Path, view: str) -> Path:
    """
    Get the newest hotspot classification file path by comparing date and timestamp.
    
    Args:
        patient_folder: Patient directory path (e.g., data/PLANAR/ALL/102/20251211 or data/PLANAR/NSY/101)
        view: View name ("ant" or "post" or "anterior" or "posterior")
        
    Returns:
        Path to the newest hotspot classification PNG file
        
    Logic:
        1. If patient folder has date subfolders (YYYYMMDD), search in all of them
        2. Find all hotspot classification files with timestamps
        3. Compare by date first, then by timestamp
        4. If no timestamped files found, return the original file from base folder
    """
    view_short = "ant" if view.lower() in ["anterior", "ant"] else "post"
    base_filename = f"{view_short}_hotspot_classification.png"
    
    newest_file = None
    newest_datetime = None
    
    # Check if this is a study_date folder (8-digit folder name) or patient folder
    if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
        # This is already a study_date folder, search within it and its edit subfolders
        search_folders = [patient_folder]
        
        # Add edit date subfolders (YYYYMMDD format)
        for item in patient_folder.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                search_folders.append(item)
            elif item.is_dir():
                # For ALL user structure: check editor code folders
                for sub_item in item.iterdir():
                    if sub_item.is_dir() and len(sub_item.name) == 8 and sub_item.name.isdigit():
                        search_folders.append(sub_item)
    else:
        # This is a patient folder, search in study_date subfolders
        search_folders = []
        
        for item in patient_folder.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                # Found study_date folder
                study_date_folder = item
                search_folders.append(study_date_folder)
                
                # Also search in edit date subfolders within study_date
                for sub_item in study_date_folder.iterdir():
                    if sub_item.is_dir() and len(sub_item.name) == 8 and sub_item.name.isdigit():
                        search_folders.append(sub_item)
                    elif sub_item.is_dir():
                        # For ALL user structure: check editor code folders
                        for editor_item in sub_item.iterdir():
                            if editor_item.is_dir() and len(editor_item.name) == 8 and editor_item.name.isdigit():
                                search_folders.append(editor_item)
    
    # Search for timestamped files in all candidate folders
    for folder in search_folders:
        if not folder.exists():
            continue
            
        for file_item in folder.iterdir():
            if not file_item.is_file():
                continue
                
            filename = file_item.name
            
            # Check if this is a timestamped version of our target file
            # Format: ant_hotspot_classification_HHMMSS.png
            if filename.startswith(f"{view_short}_hotspot_classification_") and filename.endswith(".png"):
                # Extract timestamp from filename
                parts = filename.rsplit('.', 1)[0].split('_')  # Split by . first, then by _
                if len(parts) >= 4 and len(parts[-1]) == 6 and parts[-1].isdigit():
                    time_str = parts[-1]  # HHMMSS
                    
                    # Get the date from the folder structure
                    # The date could be from the immediate parent folder or ancestor
                    date_str = None
                    current_folder = folder
                    
                    # Walk up the folder hierarchy to find a date folder
                    while current_folder and current_folder != patient_folder.parent:
                        if len(current_folder.name) == 8 and current_folder.name.isdigit():
                            try:
                                datetime.strptime(current_folder.name, "%Y%m%d")  # Validate date
                                date_str = current_folder.name
                                break
                            except ValueError:
                                pass
                        current_folder = current_folder.parent
                    
                    if date_str:
                        try:
                            # Create full datetime for comparison
                            full_datetime_str = f"{date_str}_{time_str}"
                            full_datetime = datetime.strptime(full_datetime_str, "%Y%m%d_%H%M%S")
                            
                            if newest_datetime is None or full_datetime > newest_datetime:
                                newest_datetime = full_datetime
                                newest_file = file_item
                                
                        except ValueError:
                            continue
    
    # If we found a timestamped file, return it
    if newest_file:
        return newest_file
    
    # Fallback: Look for original file in the base locations
    # 1. First check in study_date folder if we're in one
    if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
        original_in_study = patient_folder / base_filename
        if original_in_study.exists():
            return original_in_study
    
    # 2. Check in patient folder (for both study_date subfolders and direct files)
    if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
        # We're in study_date, check parent (patient folder)
        patient_base_folder = patient_folder.parent
    else:
        # We're already in patient folder
        patient_base_folder = patient_folder
    
    # Check for original file in patient base folder
    original_in_patient = patient_base_folder / base_filename
    if original_in_patient.exists():
        return original_in_patient
    
    # 3. Check in any study_date subfolder
    for item in patient_base_folder.iterdir():
        if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
            original_in_study_sub = item / base_filename
            if original_in_study_sub.exists():
                return original_in_study_sub
    
    # Final fallback: return the expected path even if it doesn't exist
    # This maintains consistency with the expected file structure
    if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
        return patient_folder / base_filename
    else:
        return patient_folder / base_filename


def get_newest_segmentation_path(patient_folder: Path, view: str) -> Path:
    """
    Get the newest segmentation file path by comparing date and timestamp.
    Similar logic to hotspot classification but for segmentation files.
    
    Args:
        patient_folder: Patient directory path
        view: View name ("ant" or "post" or "anterior" or "posterior")
        
    Returns:
        Path to the newest segmentation PNG file
    """
    view_short = "ant" if view.lower() in ["anterior", "ant"] else "post"
    base_filename = f"{view_short}_segm.png"
    
    newest_file = None
    newest_datetime = None
    
    # Check if this is a study_date folder or patient folder
    if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
        search_folders = [patient_folder]
        
        # Add edit date subfolders
        for item in patient_folder.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                search_folders.append(item)
            elif item.is_dir():
                # For ALL user structure
                for sub_item in item.iterdir():
                    if sub_item.is_dir() and len(sub_item.name) == 8 and sub_item.name.isdigit():
                        search_folders.append(sub_item)
    else:
        search_folders = []
        
        for item in patient_folder.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                study_date_folder = item
                search_folders.append(study_date_folder)
                
                for sub_item in study_date_folder.iterdir():
                    if sub_item.is_dir() and len(sub_item.name) == 8 and sub_item.name.isdigit():
                        search_folders.append(sub_item)
                    elif sub_item.is_dir():
                        for editor_item in sub_item.iterdir():
                            if editor_item.is_dir() and len(editor_item.name) == 8 and editor_item.name.isdigit():
                                search_folders.append(editor_item)
    
    # Search for timestamped segmentation files
    for folder in search_folders:
        if not folder.exists():
            continue
            
        for file_item in folder.iterdir():
            if not file_item.is_file():
                continue
                
            filename = file_item.name
            
            # Check if this is a timestamped version: ant_segm_HHMMSS.png
            if filename.startswith(f"{view_short}_segm_") and filename.endswith(".png"):
                parts = filename.rsplit('.', 1)[0].split('_')
                if len(parts) >= 3 and len(parts[-1]) == 6 and parts[-1].isdigit():
                    time_str = parts[-1]  # HHMMSS
                    
                    # Get date from folder hierarchy
                    date_str = None
                    current_folder = folder
                    
                    while current_folder and current_folder != patient_folder.parent:
                        if len(current_folder.name) == 8 and current_folder.name.isdigit():
                            try:
                                datetime.strptime(current_folder.name, "%Y%m%d")
                                date_str = current_folder.name
                                break
                            except ValueError:
                                pass
                        current_folder = current_folder.parent
                    
                    if date_str:
                        try:
                            full_datetime_str = f"{date_str}_{time_str}"
                            full_datetime = datetime.strptime(full_datetime_str, "%Y%m%d_%H%M%S")
                            
                            if newest_datetime is None or full_datetime > newest_datetime:
                                newest_datetime = full_datetime
                                newest_file = file_item
                                
                        except ValueError:
                            continue
    
    # Return newest timestamped file if found
    if newest_file:
        return newest_file
    
    # Fallback to original file
    if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
        original_in_study = patient_folder / base_filename
        if original_in_study.exists():
            return original_in_study
        
        # Check parent (patient folder)
        original_in_patient = patient_folder.parent / base_filename
        if original_in_patient.exists():
            return original_in_patient
    else:
        # Check patient folder first
        original_in_patient = patient_folder / base_filename
        if original_in_patient.exists():
            return original_in_patient
        
        # Check study_date subfolders
        for item in patient_folder.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                original_in_study = item / base_filename
                if original_in_study.exists():
                    return original_in_study
    
    # Final fallback
    if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
        return patient_folder / base_filename
    else:
        return patient_folder / base_filename
    
def get_classification_files(patient_folder: Path, filename_stem: str, view: str) -> Dict[str, Path]:
    """Get classification file paths for hotspot detection."""
    view_short = view.lower()[:3]  # "anterior" -> "ant", "posterior" -> "pos"
    
    return {
        'png': patient_folder / f"{filename_stem}_{view_short}_hotspot_classification.png",
        'xml': patient_folder / f"{filename_stem}_{view_short}_hotspot_classification.xml"
    }

def ensure_directories():
    """
    Ensure all necessary directories exist
    """
    directories = [
        DATA_ROOT, PLANAR_DATA_PATH, DICOM_DATA_PATH,
        MODELS_ROOT, HOTSPOT_MODEL_PATH, SEGMENTATION_MODEL_PATH, CLASSIFICATION_MODEL_PATH,
        TEMP_ROOT, LOGS_ROOT, ASSETS_ROOT, ICONS_PATH, IMAGES_PATH, CONFIG_ROOT
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

# ===== DICOM UTILITY FUNCTIONS =====
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
        return datetime.now().strftime("%Y%m%d")
        
    except Exception as e:
        print(f"Warning: Could not extract study date from {dicom_path}: {e}")
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

def generate_edit_timestamp() -> str:
    """
    Generate timestamp for edited files (HHMMSS format only)
    
    Returns:
        Timestamp in HHMMSS format
    """
    return datetime.now().strftime("%H%M%S")

def generate_edit_date() -> str:
    """
    Generate date for edit folders (YYYYMMDD format)
    
    Returns:
        Date in YYYYMMDD format
    """
    return datetime.now().strftime("%Y%m%d")

# ===== PLANAR PATH FUNCTIONS =====
def get_patient_planar_path(session_code: str, patient_id: str, study_date: str = None) -> Path:
    """
    Get patient path for planar data with ALL user support
    Returns the base patient path where main files are stored
    """
    if session_code == "ALL":
        base_path = PLANAR_DATA_PATH / "ALL" / patient_id
    else:
        base_path = PLANAR_DATA_PATH / session_code / patient_id
    
    if study_date:
        return base_path / study_date
    return base_path

def get_study_date_path(session_code: str, patient_id: str, study_date: str) -> Path:
    """
    Get the study date path where main files are stored
    """
    return get_patient_planar_path(session_code, patient_id, study_date)

def get_edit_timestamp_path(session_code: str, patient_id: str, study_date: str, editor_code: str = None, edit_date: str = None) -> Path:
    """
    Get path for timestamp-based edits (both individual and ALL user)
    
    Args:
        session_code: Session code (NSY, ATL, NBL, ALL)
        patient_id: Patient ID
        study_date: Study date in YYYYMMDD format
        editor_code: Doctor code who made the edit (for ALL user only)
        edit_date: Date of edit in YYYYMMDD format
        
    Returns:
        Path for edit folder
    """
    base_path = get_patient_planar_path(session_code, patient_id, study_date)
    
    if session_code == "ALL":
        # ALL user: data/PLANAR/ALL/102/20251211/EMA/20250815/
        if not editor_code:
            raise ValueError("editor_code required for ALL user edits")
        return base_path / editor_code / edit_date
    else:
        # Individual user: data/PLANAR/NSY/101/20250101/20250816/
        if not edit_date:
            edit_date = datetime.now().strftime("%Y%m%d")
        return base_path / edit_date

def get_session_planar_path(session_code: str) -> Path:
    """Get path to session's PLANAR data folder"""
    return PLANAR_DATA_PATH / session_code

def get_planar_original_files(patient_folder: Path, original_dicom_name: str = None):
    """
    Get original image file paths for planar data with new simplified naming
    
    Args:
        patient_folder: Patient directory path
        original_dicom_name: Original DICOM filename (keeps original name)
        
    Returns:
        Dictionary with original file paths using new naming convention
    """
    files = {
        # Original images - simplified naming
        'ant_original': patient_folder / "ant_original.png",
        'post_original': patient_folder / "post_original.png"
    }
    
    # Add DICOM file with original name if provided
    if original_dicom_name:
        files['dicom_file'] = patient_folder / original_dicom_name
    
    return files

def get_planar_segmentation_files(patient_folder: Path, view: str, with_priority: bool = True, session_code: str = None):
    """
    Get segmentation file paths with priority system for edited files
    
    Args:
        patient_folder: Patient directory path (study_date folder)
        view: View name (ant/post or anterior/posterior)
        with_priority: Whether to use priority system (edited > original)
        session_code: Session code for ALL user context
        
    Returns:
        Dictionary with segmentation file paths using priority system
    """
    vtag = "ant" if view.lower() in ["anterior", "ant"] else "post"
    segm_filename = f"{vtag}_segm.png"
    mask_filename = f"{vtag}_mask.png"
    
    if with_priority:
        # Use priority system
        segm_file = get_file_with_priority(patient_folder, segm_filename, session_code)
        mask_file = get_file_with_priority(patient_folder, mask_filename, session_code)
        
        return {
            'segmentation_png': segm_file or (patient_folder / segm_filename),
            'mask_png': mask_file or (patient_folder / mask_filename)
        }
    else:
        # Original behavior
        return {
            'segmentation_png': patient_folder / segm_filename,
            'mask_png': patient_folder / mask_filename
        }
def get_planar_hotspot_files(patient_folder: Path, view: str, with_priority: bool = True, session_code: str = None):
    """
    ✅ UPDATED: Get hotspot file paths with priority system for edited files
    
    Args:
        patient_folder: Patient directory path (study_date folder)
        view: View name (ant/post or anterior/posterior)
        with_priority: Whether to use priority system (edited > original)
        session_code: Session code for ALL user context (NSY, ATL, etc.)
        
    Returns:
        Dictionary with hotspot file paths using priority system
    """
    vtag = "ant" if view.lower() in ["anterior", "ant"] else "post"
    
    # ✅ Base files (non-editable) - always from study_date folder
    base_files = {
        # YOLO detection files (non-editable)
        'yolo_xml': patient_folder / f"{vtag}_hotspot_yolo.xml",
        
        # Otsu processing files (non-editable)
        'otsu_colored': patient_folder / f"{vtag}_hotspot_otsu_colored.png",
        'otsu_colored_blend': patient_folder / f"{vtag}_hotspot_otsu_colored_blend.png",
        'otsu_grayscale': patient_folder / f"{vtag}_hotspot_otsu_grayscale.png",
        
        # Classification files (editable) - will be updated with priority
        'classification_xml': patient_folder / f"{vtag}_hotspot_classification.xml",
        'classification_png': patient_folder / f"{vtag}_hotspot_classification.png"
    }
    
    # ✅ FALLBACK: Check if files exist in study_date folder, otherwise try parent
    if not base_files['classification_png'].exists():
        # Try parent directory (patient level) as fallback
        parent_dir = patient_folder.parent if len(patient_folder.name) == 8 and patient_folder.name.isdigit() else patient_folder
        
        fallback_files = {
            'yolo_xml': parent_dir / f"{vtag}_hotspot_yolo.xml",
            'otsu_colored': parent_dir / f"{vtag}_hotspot_otsu_colored.png",
            'otsu_colored_blend': parent_dir / f"{vtag}_hotspot_otsu_colored_blend.png",
            'otsu_grayscale': parent_dir / f"{vtag}_hotspot_otsu_grayscale.png",
            'classification_xml': parent_dir / f"{vtag}_hotspot_classification.xml",
            'classification_png': parent_dir / f"{vtag}_hotspot_classification.png"
        }
        
        # Use fallback files if they exist
        for key, fallback_path in fallback_files.items():
            if fallback_path.exists():
                base_files[key] = fallback_path
    
    if with_priority:
        # ✅ Use priority system for editable files only
        classification_png_filename = f"{vtag}_hotspot_classification.png"
        classification_xml_filename = f"{vtag}_hotspot_classification.xml"
        
        # Check if these are editable files
        if classification_png_filename in EDITABLE_FILES:
            priority_png = get_file_with_priority(
                patient_folder, classification_png_filename, session_code
            )
            if priority_png and priority_png.exists():
                base_files['classification_png'] = priority_png
                print(f"[PRIORITY] Using edited PNG: {priority_png}")
            else:
                print(f"[PRIORITY] Using original PNG: {base_files['classification_png']}")
        
        if classification_xml_filename in EDITABLE_FILES:
            priority_xml = get_file_with_priority(
                patient_folder, classification_xml_filename, session_code
            )
            if priority_xml and priority_xml.exists():
                base_files['classification_xml'] = priority_xml
                print(f"[PRIORITY] Using edited XML: {priority_xml}")
            else:
                print(f"[PRIORITY] Using original XML: {base_files['classification_xml']}")
    
    # ✅ DEBUG: Print final file selection
    print(f"[HOTSPOT FILES] Final selection for {vtag}:")
    for key, path in base_files.items():
        exists = path.exists() if path else False
        is_edited = "edited" if (path and "_20" in str(path) and len(path.stem.split('_')[-1]) == 6) else "original"
        print(f"[HOTSPOT FILES]   {key}: {path} (exists: {exists}, type: {is_edited})")
    
    return base_files

def load_original_image_from_path(dicom_path: Path, view_name: str, frame_map: dict = None) -> Optional[Image.Image]:
    """
    Load original PNG image for the specified view using NEW structure with study_date support
    
    Args:
        dicom_path: Path to DICOM file
        view_name: View name (Anterior/Posterior or ant/post)
        frame_map: Dictionary containing frame data as fallback
        
    Returns:
        PIL Image object or None if not found
    """
    try:
        from PIL import Image
        import numpy as np
        
        view_short = "ant" if view_name.lower() in ["anterior", "ant"] else "post"
        png_filename = f"{view_short}_original.png"
        
        # ✅ PERBAIKAN: Cari di direktori study_date dulu (dimana DICOM berada)
        study_date_dir = dicom_path.parent
        png_path = study_date_dir / png_filename
        
        print(f"[DEBUG] Looking for original PNG in study_date dir: {png_path}")
        
        if png_path.exists():
            # Found in study_date directory
            original_image = Image.open(png_path)
            if original_image.mode != 'L':
                original_image = original_image.convert('L')
            print(f"[DEBUG] Loaded original PNG from study_date dir: {original_image.size}")
            return original_image
        
        # ✅ FALLBACK: Cari di parent direktori (patient level)
        patient_dir = study_date_dir.parent
        png_path_fallback = patient_dir / png_filename
        print(f"[DEBUG] Fallback: Looking in patient dir: {png_path_fallback}")
        
        if png_path_fallback.exists():
            original_image = Image.open(png_path_fallback)
            if original_image.mode != 'L':
                original_image = original_image.convert('L')
            print(f"[DEBUG] Loaded original PNG from patient dir: {original_image.size}")
            return original_image
        
        # ✅ FALLBACK: Load from DICOM frames if PNG not available
        if frame_map and view_name in frame_map:
            frame_data = frame_map[view_name]
            if isinstance(frame_data, np.ndarray):
                # Normalize to uint8
                if frame_data.dtype != np.uint8:
                    frame_norm = (frame_data - frame_data.min()) / max(frame_data.max() - frame_data.min(), 1)
                    frame_uint8 = (frame_norm * 255).astype(np.uint8)
                else:
                    frame_uint8 = frame_data.copy()
                
                # Convert to PIL Image
                original_image = Image.fromarray(frame_uint8, 'L')
                print(f"[DEBUG] Fallback: Loaded from DICOM frame: {original_image.size}")
                return original_image
        
        print(f"[DEBUG] No image source available for {view_name}")
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to load original image: {e}")
        return None

def debug_quantification_paths(patient_folder: Path, patient_id: str = None) -> None:
    """Debug helper untuk check quantification file paths"""
    
    print(f"\n📁 [DEBUG PATHS GANTENG] ===================")
    print(f"📁 [DEBUG PATHS] Patient folder: {patient_folder}")
    print(f"📁 [DEBUG PATHS] Patient ID: {patient_id}")
    print(f"📁 [DEBUG PATHS] Folder exists: {patient_folder.exists()}")
    
    if not patient_folder.exists():
        print(f"📁 [DEBUG PATHS] ❌ Folder does not exist!")
        return
    
    print(f"📁 [DEBUG PATHS] Folder structure:")
    
    # Check main folder contents
    for item in patient_folder.iterdir():
        if item.is_file():
            size = item.stat().st_size
            print(f"📁 [DEBUG PATHS]   FILE: {item.name} ({size} bytes)")
        elif item.is_dir():
            print(f"📁 [DEBUG PATHS]   DIR:  {item.name}/")
            # Check subdirectory contents (for study_date folders)
            if len(item.name) == 8 and item.name.isdigit():
                print(f"📁 [DEBUG PATHS]     Study date folder contents:")
                for subitem in item.iterdir():
                    if subitem.is_file():
                        sub_size = subitem.stat().st_size
                        print(f"📁 [DEBUG PATHS]       FILE: {subitem.name} ({sub_size} bytes)")
                    elif subitem.is_dir():
                        print(f"📁 [DEBUG PATHS]       DIR:  {subitem.name}/")
    
    # Test new quantification paths
    try:
        quant_files = get_planar_quantification_files(patient_folder)
        print(f"📁 [DEBUG PATHS] New quantification paths:")
        for key, path in quant_files.items():
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            print(f"📁 [DEBUG PATHS]   {key}: {path} (exists: {exists}, size: {size} bytes)")
            
            if exists:
                # Try to read file content
                try:
                    with open(path, 'r') as f:
                        content = f.read()
                        print(f"📁 [DEBUG PATHS]     Content preview: {content[:100]}...")
                except Exception as e:
                    print(f"📁 [DEBUG PATHS]     Error reading file: {e}")
                    
    except Exception as e:
        print(f"📁 [DEBUG PATHS] Error with new paths: {e}")
        import traceback
        traceback.print_exc()
    
    # Test old pattern if patient_id provided
    if patient_id:
        print(f"📁 [DEBUG PATHS] Old pattern search:")
        old_ant = list(patient_folder.glob(f"{patient_id}_*_bsi_quantification_anterior.json"))
        old_post = list(patient_folder.glob(f"{patient_id}_*_bsi_quantification_posterior.json"))
        print(f"📁 [DEBUG PATHS]   Old anterior: {[f.name for f in old_ant]}")
        print(f"📁 [DEBUG PATHS]   Old posterior: {[f.name for f in old_post]}")
        
        # Also check study_date subfolders
        for item in patient_folder.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                study_old_ant = list(item.glob(f"{patient_id}_*_bsi_quantification_anterior.json"))
                study_old_post = list(item.glob(f"{patient_id}_*_bsi_quantification_posterior.json"))
                study_new_ant = list(item.glob("bsi_quantification_anterior.json"))
                study_new_post = list(item.glob("bsi_quantification_posterior.json"))
                
                if study_old_ant or study_old_post or study_new_ant or study_new_post:
                    print(f"📁 [DEBUG PATHS]   In study_date folder {item.name}:")
                    print(f"📁 [DEBUG PATHS]     Old anterior: {[f.name for f in study_old_ant]}")
                    print(f"📁 [DEBUG PATHS]     Old posterior: {[f.name for f in study_old_post]}")
                    print(f"📁 [DEBUG PATHS]     New anterior: {[f.name for f in study_new_ant]}")
                    print(f"📁 [DEBUG PATHS]     New posterior: {[f.name for f in study_new_post]}")


def get_planar_quantification_files(patient_folder: Path):
    """
    ✅ AUTO-DETECT: Get BSI quantification file paths with study_date structure detection
    """
    print(f"📁 [DEBUG QUANT FILES] Getting quantification files for: {patient_folder}")
    
    # ✅ AUTO-DETECT: Check if this is study_date folder or patient folder
    folder_name = patient_folder.name
    is_study_date_folder = len(folder_name) == 8 and folder_name.isdigit()
    
    if is_study_date_folder:
        # Files are in study_date folder
        search_folder = patient_folder
        print(f"📁 [DEBUG QUANT FILES] Detected study_date folder: {search_folder}")
    else:
        # Look for study_date subfolders
        study_date_folders = [d for d in patient_folder.iterdir() 
                            if d.is_dir() and len(d.name) == 8 and d.name.isdigit()]
        
        if study_date_folders:
            # Use the latest study_date folder
            latest_study_date = sorted(study_date_folders, key=lambda x: x.name)[-1]
            search_folder = latest_study_date
            print(f"📁 [DEBUG QUANT FILES] Using latest study_date folder: {search_folder}")
        else:
            # No study_date folders, use patient folder directly
            search_folder = patient_folder
            print(f"📁 [DEBUG QUANT FILES] Using patient folder: {search_folder}")
    
    files = {
        'bsi_json_ant': search_folder / "bsi_quantification_ant.json",
        'bsi_json_post': search_folder / "bsi_quantification_post.json"
    }
    
    print(f"📁 [DEBUG QUANT FILES] Generated paths:")
    for key, path in files.items():
        exists = path.exists()
        print(f"📁 [DEBUG QUANT FILES]   {key}: {path} (exists: {exists})")
    
    return files

def get_current_session_code() -> str:
    """
    Get current session code from sessions.json config
    
    Returns:
        Current session code or 'unknown' if not found
    """
    try:
        import json
        
        # Get config path
        project_root = get_safe_project_root()
        sessions_config_path = project_root / "config" / "sessions.json"
        
        if sessions_config_path.exists():
            with open(sessions_config_path, 'r') as f:
                config = json.load(f)
            
            session_code = config.get("last_session", {}).get("session_code")
            if session_code:
                print(f"[SESSION] Found session code from config: {session_code}")
                return session_code
        
        print(f"[SESSION] No session found in config, using 'unknown'")
        return "unknown"
        
    except Exception as e:
        print(f"[SESSION] Error reading session config: {e}")
        return "unknown"

def get_planar_files_complete(patient_folder: Path, view: str, original_dicom_name: str = None, with_priority: bool = True):
    """
    Get complete set of planar files for a specific view with timestamp priority
    
    Args:
        patient_folder: Patient directory path
        view: View name (ant/post)
        original_dicom_name: Original DICOM filename
        with_priority: Whether to use latest timestamp versions
        
    Returns:
        Dictionary with all file paths for the view
    """
    vtag = "ant" if view.lower() in ["anterior", "ant"] else "post"
    
    # Get all file types
    original_files = get_planar_original_files(patient_folder, original_dicom_name)
    segmentation_files = get_planar_segmentation_files(patient_folder, view, with_priority)
    hotspot_files = get_planar_hotspot_files(patient_folder, view, with_priority)
    quantification_files = get_planar_quantification_files(patient_folder)
    
    result = {
        # Original files
        'original_png': original_files[f'{vtag}_original'],
        
        # Segmentation files
        'segmentation_png': segmentation_files['segmentation_png'],
        'mask_png': segmentation_files['mask_png'],
        
        # Hotspot files - YOLO
        'yolo_xml': hotspot_files['yolo_xml'],
        
        # Hotspot files - Otsu
        'otsu_colored': hotspot_files['otsu_colored'],
        'otsu_colored_blend': hotspot_files['otsu_colored_blend'],
        'otsu_grayscale': hotspot_files['otsu_grayscale'],
        
        # Hotspot files - Classification (main UI files with priority)
        'classification_xml': hotspot_files['classification_xml'],
        'classification_png': hotspot_files['classification_png'],
        
        # Quantification files
        'bsi_json': quantification_files[f'bsi_json_{vtag}']
    }
    
    # Add DICOM file if provided
    if original_dicom_name:
        result['dicom_file'] = original_files['dicom_file']
    
    return result

# AFTER
def get_planar_workflow_files(patient_folder: Path, original_dicom_name: str = None, with_priority: bool = True, session_code: str = None):
    """
    Get all workflow-related files for both views with timestamp priority
    
    Args:
        patient_folder: Patient directory path
        original_dicom_name: Original DICOM filename
        with_priority: Whether to use latest timestamp versions
        session_code: Session code for ALL user context
        
    Returns:
        Dictionary with workflow files organized by step and view
    """
    workflow_files = {
        'original': {
            'ant': patient_folder / "ant_original.png",
            'post': patient_folder / "post_original.png"
        },
        
        'segmentation': {
            'ant': patient_folder / "ant_segm.png",
            'post': patient_folder / "post_segm.png"
        },
        
        'yolo_detection': {
            'ant': patient_folder / "ant_hotspot_yolo.xml",
            'post': patient_folder / "post_hotspot_yolo.xml"
        },
        
        'otsu_processing': {
            'ant': {
                'colored': patient_folder / "ant_hotspot_otsu_colored.png",
                'colored_blend': patient_folder / "ant_hotspot_otsu_colored_blend.png",
                'grayscale': patient_folder / "ant_hotspot_otsu_grayscale.png"
            },
            'post': {
                'colored': patient_folder / "post_hotspot_otsu_colored.png",
                'colored_blend': patient_folder / "post_hotspot_otsu_colored_blend.png",
                'grayscale': patient_folder / "post_hotspot_otsu_grayscale.png"
            }
        },
        
        'classification': {
            'ant': {
                'xml': patient_folder / "ant_hotspot_classification.xml",
                'png': patient_folder / "ant_hotspot_classification.png"
            },
            'post': {
                'xml': patient_folder / "post_hotspot_classification.xml",
                'png': patient_folder / "post_hotspot_classification.png"
            }
        },
        
        'quantification': {
            'ant_json': patient_folder / "bsi_quantification_ant.json",
            'post_json': patient_folder / "bsi_quantification_post.json"
        }
    }
    
    if with_priority:
        # ✅ TAMBAH: Update with latest timestamp versions for editable files
        for view in ['ant', 'post']:
            # Segmentation
            latest_segm = get_latest_timestamp_file(patient_folder, f"{view}_segm.png", session_code)
            if latest_segm:
                workflow_files['segmentation'][view] = latest_segm
            
            # Classification
            latest_class_png = get_latest_timestamp_file(patient_folder, f"{view}_hotspot_classification.png", session_code)
            latest_class_xml = get_latest_timestamp_file(patient_folder, f"{view}_hotspot_classification.xml", session_code)
            if latest_class_png:
                workflow_files['classification'][view]['png'] = latest_class_png
            if latest_class_xml:
                workflow_files['classification'][view]['xml'] = latest_class_xml
    
    # Add DICOM file if provided
    if original_dicom_name:
        workflow_files['dicom_file'] = patient_folder / original_dicom_name
    
    return workflow_files

def check_planar_workflow_completion(patient_folder: Path, original_dicom_name: str = None, with_priority: bool = True):
    """
    Check completion status of workflow steps with timestamp priority
    
    Args:
        patient_folder: Patient directory path
        original_dicom_name: Original DICOM filename
        with_priority: Whether to use latest timestamp versions
        
    Returns:
        Dictionary with completion status for each workflow step
    """
    files = get_planar_workflow_files(patient_folder, original_dicom_name, with_priority)
    
    completion = {
        'original_extraction': (
            files['original']['ant'].exists() and 
            files['original']['post'].exists()
        ),
        'segmentation': (
            files['segmentation']['ant'].exists() and 
            files['segmentation']['post'].exists()
        ),
        'yolo_detection': (
            files['yolo_detection']['ant'].exists() and 
            files['yolo_detection']['post'].exists()
        ),
        'otsu_processing': (
            files['otsu_processing']['ant']['grayscale'].exists() and 
            files['otsu_processing']['post']['grayscale'].exists()
        ),
        'classification': (
            files['classification']['ant']['xml'].exists() and 
            files['classification']['post']['xml'].exists() and
            files['classification']['ant']['png'].exists() and 
            files['classification']['post']['png'].exists()
        ),
        'quantification': (
            files['quantification']['ant_json'].exists() and 
            files['quantification']['post_json'].exists()
        )
    }
    
    # Check DICOM import if filename provided
    if original_dicom_name and 'dicom_file' in files:
        completion['dicom_import'] = files['dicom_file'].exists()
    else:
        completion['dicom_import'] = True  # Assume imported if no filename provided
    
    # Overall completion
    completion['overall_complete'] = all(completion.values())
    
    # Next step determination
    if not completion['dicom_import']:
        completion['next_step'] = 'dicom_import'
    elif not completion['original_extraction']:
        completion['next_step'] = 'original_extraction'
    elif not completion['segmentation']:
        completion['next_step'] = 'segmentation'
    elif not completion['yolo_detection']:
        completion['next_step'] = 'yolo_detection'
    elif not completion['otsu_processing']:
        completion['next_step'] = 'otsu_processing'
    elif not completion['classification']:
        completion['next_step'] = 'classification'
    elif not completion['quantification']:
        completion['next_step'] = 'quantification'
    else:
        completion['next_step'] = 'complete'
    
    return completion

def get_workflow_step_files(patient_folder: Path, step: str, view: str = None, with_priority: bool = True):
    """
    Get files for a specific workflow step with timestamp priority
    
    Args:
        patient_folder: Patient directory path
        step: Workflow step name
        view: View (ant/post), optional for steps that affect both views
        with_priority: Whether to use latest timestamp versions
        
    Returns:
        List of file paths for the step
    """
    step_files = {
        'original_extraction': ['ant_original.png', 'post_original.png'],
        'segmentation': ['ant_segm.png', 'post_segm.png'],
        'yolo_detection': ['ant_hotspot_yolo.xml', 'post_hotspot_yolo.xml'],
        'otsu_processing': [
            'ant_hotspot_otsu_colored.png', 'ant_hotspot_otsu_colored_blend.png', 'ant_hotspot_otsu_grayscale.png',
            'post_hotspot_otsu_colored.png', 'post_hotspot_otsu_colored_blend.png', 'post_hotspot_otsu_grayscale.png'
        ],
        'classification': [
            'ant_hotspot_classification.xml', 'ant_hotspot_classification.png',
            'post_hotspot_classification.xml', 'post_hotspot_classification.png'
        ],
        'quantification': ['bsi_quantification_ant.json', 'bsi_quantification_post.json']
    }
    
    if step in step_files:
        files_to_check = step_files[step]
        
        if view:
            # Filter by view if specified
            vtag = "ant" if view.lower() in ["anterior", "ant"] else "post"
            files_to_check = [f for f in files_to_check if f.startswith(vtag)]
        
        result_files = []
        for filename in files_to_check:
            if with_priority and filename in EDITABLE_FILES:
                # Check for latest timestamp version
                latest_file = get_latest_timestamp_file(patient_folder, filename)
                if latest_file:
                    result_files.append(latest_file)
                else:
                    result_files.append(patient_folder / filename)
            else:
                result_files.append(patient_folder / filename)
        
        return result_files
    
    return []

# ===== TIMESTAMP EDIT FUNCTIONS =====
def get_latest_timestamp_file(patient_folder: Path, filename: str, session_code: str = None) -> Optional[Path]:
    """
    Get the latest timestamp version of a file if it exists
    Supports both individual and ALL user structures
    """
    if filename not in EDITABLE_FILES:
        return None
    
    latest_file = None
    latest_datetime = None
    
    # Look for date directories in patient folder (YYYYMMDD format)
    for item in patient_folder.iterdir():
        if item.is_dir() and len(item.name) == 8 and item.name.isdigit():  # YYYYMMDD format
            try:
                # Validate date format
                edit_date = datetime.strptime(item.name, "%Y%m%d")
                
                # Look for files with timestamp suffix in this date folder
                for file_item in item.iterdir():
                    if file_item.is_file():
                        file_name = file_item.name
                        # Check if it's our target file with HHMMSS suffix
                        # Format: ant_segm_104711.png
                        if file_name.startswith(filename.rsplit('.', 1)[0] + '_') and file_name.endswith('.' + filename.split('.')[-1]):
                            # Extract timestamp from filename
                            parts = file_name.rsplit('.', 1)[0].split('_')
                            if len(parts) >= 3 and len(parts[-1]) == 6 and parts[-1].isdigit():
                                time_str = parts[-1]  # HHMMSS
                                try:
                                    # Create full datetime
                                    full_datetime_str = f"{item.name}_{time_str}"
                                    full_datetime = datetime.strptime(full_datetime_str, "%Y%m%d_%H%M%S")
                                    
                                    if latest_datetime is None or full_datetime > latest_datetime:
                                        latest_datetime = full_datetime
                                        latest_file = file_item
                                except ValueError:
                                    continue
            except ValueError:
                continue
    
    return latest_file

def get_file_with_priority(base_path: Path, filename: str, session_code: str = None) -> Optional[Path]:
    """
    Get file with priority: edited timestamp > original file
    """
    # ✅ USE DEBUG VERSION
    return debug_file_with_priority(base_path, filename, session_code)

def debug_timestamp_file_detection(patient_folder: Path, filename: str, session_code: str = None):
    """
    Debug function to trace timestamp file detection
    """
    print(f"\n🔍 [DEBUG TIMESTAMP GANTENG] ===================")
    print(f"🔍 [DEBUG TIMESTAMP] Looking for: {filename}")
    print(f"🔍 [DEBUG TIMESTAMP] In folder: {patient_folder}")
    print(f"🔍 [DEBUG TIMESTAMP] Session code: {session_code}")
    print(f"🔍 [DEBUG TIMESTAMP] Is editable: {filename in EDITABLE_FILES}")
    
    if filename not in EDITABLE_FILES:
        print(f"🔍 [DEBUG TIMESTAMP] ❌ File not in EDITABLE_FILES: {EDITABLE_FILES}")
        return None
    
    # Check folder structure
    print(f"🔍 [DEBUG TIMESTAMP] Folder contents:")
    if patient_folder.exists():
        for item in patient_folder.iterdir():
            if item.is_dir():
                print(f"🔍 [DEBUG TIMESTAMP]   DIR:  {item.name}")
                # Check if it's a date directory
                if len(item.name) == 8 and item.name.isdigit():
                    print(f"🔍 [DEBUG TIMESTAMP]     This is a date directory!")
                    # Check contents of date directory
                    for sub_item in item.iterdir():
                        if sub_item.is_file():
                            print(f"🔍 [DEBUG TIMESTAMP]       FILE: {sub_item.name}")
                            # Check if it matches our pattern
                            base_name = filename.rsplit('.', 1)[0]  # ant_hotspot_classification
                            extension = filename.split('.')[-1]     # png
                            
                            if sub_item.name.startswith(base_name + '_') and sub_item.name.endswith('.' + extension):
                                print(f"🔍 [DEBUG TIMESTAMP]       ✅ MATCHES PATTERN!")
                                
                                # Extract timestamp
                                parts = sub_item.name.rsplit('.', 1)[0].split('_')
                                print(f"🔍 [DEBUG TIMESTAMP]       File parts: {parts}")
                                
                                if len(parts) >= 3:
                                    potential_timestamp = parts[-1]
                                    print(f"🔍 [DEBUG TIMESTAMP]       Potential timestamp: {potential_timestamp}")
                                    
                                    if len(potential_timestamp) == 6 and potential_timestamp.isdigit():
                                        print(f"🔍 [DEBUG TIMESTAMP]       ✅ VALID TIMESTAMP!")
                                        
                                        # Try to parse datetime
                                        try:
                                            full_datetime_str = f"{item.name}_{potential_timestamp}"
                                            full_datetime = datetime.strptime(full_datetime_str, "%Y%m%d_%H%M%S")
                                            print(f"🔍 [DEBUG TIMESTAMP]       ✅ VALID DATETIME: {full_datetime}")
                                        except ValueError as e:
                                            print(f"🔍 [DEBUG TIMESTAMP]       ❌ INVALID DATETIME: {e}")
                                    else:
                                        print(f"🔍 [DEBUG TIMESTAMP]       ❌ Invalid timestamp format")
                                else:
                                    print(f"🔍 [DEBUG TIMESTAMP]       ❌ Not enough parts")
                            else:
                                print(f"🔍 [DEBUG TIMESTAMP]       ❌ Doesn't match pattern")
            else:
                print(f"🔍 [DEBUG TIMESTAMP]   FILE: {item.name}")
    else:
        print(f"🔍 [DEBUG TIMESTAMP] ❌ Folder doesn't exist!")
    
    # Now run the actual function
    print(f"🔍 [DEBUG TIMESTAMP] Running get_latest_timestamp_file...")
    result = get_latest_timestamp_file(patient_folder, filename, session_code)
    print(f"🔍 [DEBUG TIMESTAMP] Result: {result}")
    
    return result

def debug_file_with_priority(base_path: Path, filename: str, session_code: str = None):
    """
    Debug function to trace file priority selection
    """
    print(f"\n🎯 [DEBUG PRIORITY GANTENG] ===================")
    print(f"🎯 [DEBUG PRIORITY] Looking for: {filename}")
    print(f"🎯 [DEBUG PRIORITY] In path: {base_path}")
    print(f"🎯 [DEBUG PRIORITY] Session code: {session_code}")
    
    # Check original file first
    original_file = base_path / filename
    print(f"🎯 [DEBUG PRIORITY] Original file: {original_file}")
    print(f"🎯 [DEBUG PRIORITY] Original exists: {original_file.exists()}")
    
    # Check for edited version
    if filename in EDITABLE_FILES:
        print(f"🎯 [DEBUG PRIORITY] File is editable, checking for timestamp version...")
        
        # Debug the timestamp detection
        latest_edited = debug_timestamp_file_detection(base_path, filename, session_code)
        
        if latest_edited and latest_edited.exists():
            print(f"🎯 [DEBUG PRIORITY] ✅ Found edited version: {latest_edited}")
            return latest_edited
        else:
            print(f"🎯 [DEBUG PRIORITY] ❌ No edited version found")
    else:
        print(f"🎯 [DEBUG PRIORITY] File is not editable")
    
    if original_file.exists():
        print(f"🎯 [DEBUG PRIORITY] ✅ Using original file: {original_file}")
        return original_file
    else:
        print(f"🎯 [DEBUG PRIORITY] ❌ No file found at all")
        return None
def get_all_possible_paths_for_file(study_date_path: Path, filename: str, session_code: str = None) -> List[Path]:
    """
    Get all possible paths where a file might exist, ordered by priority
    
    Returns:
        List of paths ordered by priority (edited timestamp > original)
    """
    paths = []
    
    if filename in EDITABLE_FILES:
        # Get all timestamp versions (already sorted by newest first)
        timestamp_versions = get_all_timestamp_versions(study_date_path, filename)
        paths.extend(timestamp_versions)
    
    # Add original file path
    original_path = study_date_path / filename
    if original_path not in paths:
        paths.append(original_path)
    
    return paths

def get_all_timestamp_versions(patient_folder: Path, filename: str) -> List[Path]:
    """
    Get all timestamp versions of a file
    
    Args:
        patient_folder: Patient directory path
        filename: Base filename to search for
        
    Returns:
        List of paths to all timestamp versions, sorted by timestamp (newest first)
    """
    if filename not in EDITABLE_FILES:
        return []
    
    versions = []
    
    # Look for date directories in patient folder (YYYYMMDD format)
    for item in patient_folder.iterdir():
        if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
            try:
                # Validate date format
                edit_date = datetime.strptime(item.name, "%Y%m%d")
                
                # Look for files with timestamp suffix in this date folder
                for file_item in item.iterdir():
                    if file_item.is_file():
                        file_name = file_item.name
                        # Check if it's our target file with HHMMSS suffix
                        if file_name.startswith(filename.rsplit('.', 1)[0] + '_') and file_name.endswith('.' + filename.split('.')[-1]):
                            parts = file_name.rsplit('.', 1)[0].split('_')
                            if len(parts) >= 3 and len(parts[-1]) == 6 and parts[-1].isdigit():
                                time_str = parts[-1]  # HHMMSS
                                try:
                                    # Create full datetime for sorting
                                    full_datetime_str = f"{item.name}_{time_str}"
                                    full_datetime = datetime.strptime(full_datetime_str, "%Y%m%d_%H%M%S")
                                    versions.append((full_datetime, file_item))
                                except ValueError:
                                    continue
            except ValueError:
                continue
    
    # Sort by timestamp (newest first) and return just the paths
    versions.sort(key=lambda x: x[0], reverse=True)
    return [path for _, path in versions]

def save_edit_timestamp_file(patient_folder: Path, session_code: str, filename: str, file_data, editor_code: str = None) -> Path:
    """
    Save an edited file with timestamp
    
    Args:
        patient_folder: Patient directory path
        session_code: Session code
        filename: Filename to save
        file_data: File data to save
        editor_code: Editor code (for ALL user, optional for individual)
        
    Returns:
        Path where file was saved
    """
    if filename not in EDITABLE_FILES:
        raise ValueError(f"File {filename} is not editable")
    
    # Generate timestamp components
    edit_date = generate_edit_date()  # YYYYMMDD
    edit_time = generate_edit_timestamp()  # HHMMSS
    
    # Determine edit directory structure
    if session_code == "ALL":
        if not editor_code:
            raise ValueError("editor_code required for ALL user edits")
        # Structure: data/PLANAR/ALL/102/20251211/EMA/20250815/
        edit_dir = patient_folder / editor_code / edit_date
    else:
        # Structure: data/PLANAR/NSY/101/20250101/20250816/
        edit_dir = patient_folder / edit_date
    
    # Create timestamped filename: ant_hotspot_classification_193522.png
    base_name = filename.rsplit('.', 1)[0]  # ant_hotspot_classification
    extension = filename.split('.')[-1]     # png
    timestamped_filename = f"{base_name}_{edit_time}.{extension}"
    
    # Create edit directory
    edit_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file with timestamp in filename
    file_path = edit_dir / timestamped_filename
    
    # Handle different file types
    if filename.endswith('.png'):
        # For PNG files, assume file_data is PIL Image or numpy array
        if hasattr(file_data, 'save'):
            file_data.save(file_path)
        else:
            import cv2
            cv2.imwrite(str(file_path), file_data)
    elif filename.endswith('.xml'):
        # For XML files, assume file_data is string or bytes
        if isinstance(file_data, str):
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file_data)
        else:
            with open(file_path, 'wb') as f:
                f.write(file_data)
    
    # For classification files, also handle the corresponding XML/PNG pair
    if "hotspot_classification" in filename:
        view = "ant" if filename.startswith("ant") else "post"
        if filename.endswith('.png'):
            # When PNG is saved, create corresponding XML with same timestamp
            xml_filename = f"{view}_hotspot_classification.xml"
            xml_base_name = xml_filename.rsplit('.', 1)[0]  # ant_hotspot_classification
            xml_extension = xml_filename.split('.')[-1]     # xml
            xml_timestamped_filename = f"{xml_base_name}_{edit_time}.{xml_extension}"
            xml_path = edit_dir / xml_timestamped_filename
            
            if not xml_path.exists():
                # Copy XML from base folder or create minimal XML
                base_xml = patient_folder / xml_filename
                if base_xml.exists():
                    import shutil
                    shutil.copy2(base_xml, xml_path)
        elif filename.endswith('.xml'):
            # When XML is saved, create corresponding PNG with same timestamp
            png_filename = f"{view}_hotspot_classification.png"
            png_base_name = png_filename.rsplit('.', 1)[0]  # ant_hotspot_classification
            png_extension = png_filename.split('.')[-1]     # png
            png_timestamped_filename = f"{png_base_name}_{edit_time}.{png_extension}"
            png_path = edit_dir / png_timestamped_filename
            
            if not png_path.exists():
                # Copy PNG from base folder
                base_png = patient_folder / png_filename
                if base_png.exists():
                    import shutil
                    shutil.copy2(base_png, png_path)
    
    return file_path

def get_edit_history(patient_folder: Path, filename: str) -> List[Dict]:
    """
    Get edit history for a file
    
    Args:
        patient_folder: Patient directory path
        filename: Base filename
        
    Returns:
        List of edit history entries with timestamp and path info
    """
    if filename not in EDITABLE_FILES:
        return []
    
    history = []
    
    # Look for date directories (YYYYMMDD format)
    for item in patient_folder.iterdir():
        if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
            try:
                # Validate date format
                edit_date = datetime.strptime(item.name, "%Y%m%d")
                
                # Look for files with timestamp suffix in this date folder
                for file_item in item.iterdir():
                    if file_item.is_file():
                        file_name = file_item.name
                        # Check if it's our target file with HHMMSS suffix
                        if file_name.startswith(filename.rsplit('.', 1)[0] + '_') and file_name.endswith('.' + filename.split('.')[-1]):
                            parts = file_name.rsplit('.', 1)[0].split('_')
                            if len(parts) >= 3 and len(parts[-1]) == 6 and parts[-1].isdigit():
                                time_str = parts[-1]  # HHMMSS
                                try:
                                    # Create full datetime
                                    full_datetime_str = f"{item.name}_{time_str}"
                                    full_datetime = datetime.strptime(full_datetime_str, "%Y%m%d_%H%M%S")
                                    
                                    history.append({
                                        'date': item.name,
                                        'time': time_str,
                                        'datetime': full_datetime,
                                        'path': file_item,
                                        'filename': file_name,
                                        'size': file_item.stat().st_size,
                                        'modified': datetime.fromtimestamp(file_item.stat().st_mtime)
                                    })
                                except ValueError:
                                    continue
            except ValueError:
                continue
    
    # Sort by datetime (newest first)
    history.sort(key=lambda x: x['datetime'], reverse=True)
    return history

# ===== UTILITY FUNCTIONS =====
def find_files_by_pattern(patient_folder: Path, pattern: str = "*") -> List[Path]:
    """
    Find files matching pattern in patient folder
    
    Args:
        patient_folder: Patient directory
        pattern: File pattern (e.g., "*_ant_*.png")
        
    Returns:
        List of matching files
    """
    return list(patient_folder.glob(pattern))

def get_model_path(model_name: str) -> Path:
    """Get path for specific model"""
    model_paths = {
        "yolo": YOLO_MODEL_PATH,
        "unet": UNET_MODEL_PATH,
        "cnn": CNN_MODEL_PATH,
        "xgboost": CLASSIFICATION_XGBOOST_MODEL,
        "scaler": CLASSIFICATION_SCALER_MODEL
    }
    return model_paths.get(model_name.lower(), MODELS_ROOT / f"{model_name}.pt")

def get_temp_path(session_id: str = None) -> Path:
    """Get temporary processing path"""
    if session_id:
        temp_path = TEMP_ROOT / session_id
        temp_path.mkdir(parents=True, exist_ok=True)
        return temp_path
    return TEMP_ROOT

def validate_paths():
    """Validate that critical paths exist and are accessible"""
    critical_paths = [PROJECT_ROOT, DATA_ROOT, MODELS_ROOT]
    
    for path in critical_paths:
        if not path.exists():
            raise FileNotFoundError(f"Critical path does not exist: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")
    
    return True

def get_dicom_files_in_folder(folder_path: Path) -> List[Path]:
    """
    Get all DICOM files in a folder
    
    Args:
        folder_path: Folder to search
        
    Returns:
        List of DICOM file paths
    """
    dicom_files = []
    for ext in DICOM_EXTENSIONS:
        dicom_files.extend(folder_path.glob(f"*{ext}"))
    return sorted(dicom_files)

def parse_planar_filename(filename: str) -> Dict[str, str]:
    """
    Parse planar filename to extract components
    
    Args:
        filename: Filename to parse
        
    Returns:
        Dictionary with parsed components
    """
    # Handle new naming convention
    if filename.startswith(('ant_', 'post_')):
        parts = filename.split('_')
        view = parts[0]  # ant or post
        
        if len(parts) >= 2:
            file_type = '_'.join(parts[1:]).replace('.png', '').replace('.xml', '').replace('.json', '')
        else:
            file_type = 'unknown'
        
        return {
            'view': view,
            'file_type': file_type,
            'naming_convention': 'new',
            'is_hotspot': 'hotspot' in file_type,
            'is_segmentation': 'segm' in file_type or 'mask' in file_type,
            'is_original': 'original' in file_type,
            'is_quantification': 'bsi' in file_type,
            'is_editable': filename in EDITABLE_FILES
        }
    
    # Handle old naming convention
    elif '_' in filename:
        parts = filename.split('_')
        if len(parts) >= 3:
            patient_id = parts[0]
            study_date = parts[1]
            remaining = '_'.join(parts[2:])
            
            return {
                'patient_id': patient_id,
                'study_date': study_date,
                'remaining': remaining,
                'naming_convention': 'old',
                'needs_migration': True
            }
    
    return {
        'filename': filename,
        'naming_convention': 'unknown',
        'needs_migration': False
    }

def validate_planar_naming_convention(patient_folder: Path):
    """
    Validate that files follow the new naming convention
    
    Args:
        patient_folder: Patient directory path
        
    Returns:
        Dictionary with validation results
    """
    expected_files = [
        # Original files
        'ant_original.png', 'post_original.png',
        
        # Segmentation files
        'ant_segm.png', 'post_segm.png',
        
        # YOLO files
        'ant_hotspot_yolo.xml', 'post_hotspot_yolo.xml',
        
        # Otsu files
        'ant_hotspot_otsu_colored.png', 'ant_hotspot_otsu_colored_blend.png', 'ant_hotspot_otsu_grayscale.png',
        'post_hotspot_otsu_colored.png', 'post_hotspot_otsu_colored_blend.png', 'post_hotspot_otsu_grayscale.png',
        
        # Classification files
        'ant_hotspot_classification.xml', 'ant_hotspot_classification.png',
        'post_hotspot_classification.xml', 'post_hotspot_classification.png',
        
        # Quantification files
        'bsi_quantification_ant.json', 'bsi_quantification_post.json'
    ]
    
    validation = {
        'follows_convention': True,
        'existing_files': [],
        'missing_files': [],
        'unexpected_files': [],
        'old_naming_detected': [],
        'edit_date_dirs': [],
        'editable_files_with_timestamps': []
    }
    
    # Check existing files
    for file_path in patient_folder.iterdir():
        if file_path.is_file():
            filename = file_path.name
            
            if filename in expected_files:
                validation['existing_files'].append(filename)
            elif filename.endswith('.dcm'):
                validation['existing_files'].append(filename)  # DICOM files are expected
            elif any(old_pattern in filename for old_pattern in ['anterior', 'posterior', '_classification_mask']):
                validation['old_naming_detected'].append(filename)
                validation['follows_convention'] = False
            else:
                validation['unexpected_files'].append(filename)
        elif file_path.is_dir():
            # Check for edit date directories (YYYYMMDD format)
            if len(file_path.name) == 8 and file_path.name.isdigit():
                try:
                    datetime.strptime(file_path.name, "%Y%m%d")
                    validation['edit_date_dirs'].append(file_path.name)
                    
                    # Check what editable files are in this date dir
                    for edit_file in file_path.iterdir():
                        if edit_file.is_file():
                            edit_filename = edit_file.name
                            # Check if it's a timestamped editable file
                            for editable_file in EDITABLE_FILES:
                                base_name = editable_file.rsplit('.', 1)[0]
                                extension = editable_file.split('.')[-1]
                                if edit_filename.startswith(base_name + '_') and edit_filename.endswith('.' + extension):
                                    # Extract timestamp from filename
                                    parts = edit_filename.rsplit('.', 1)[0].split('_')
                                    if len(parts) >= 3 and len(parts[-1]) == 6 and parts[-1].isdigit():
                                        validation['editable_files_with_timestamps'].append(f"{file_path.name}/{edit_filename}")
                except ValueError:
                    pass
    
    # Check missing files (optional - only check if we have some files)
    if validation['existing_files']:
        for expected_file in expected_files:
            if expected_file not in validation['existing_files']:
                validation['missing_files'].append(expected_file)
    
    return validation

# ===== MIGRATION FUNCTIONS =====
def migrate_old_naming_to_new(patient_folder: Path, filename_stem: str):
    """
    Migrate files from old naming convention to new simplified naming
    
    Args:
        patient_folder: Patient directory path
        filename_stem: Filename stem ([patient_id]_[study_date])
        
    Returns:
        Dictionary with migration results
    """
    migration_map = {
        # Original files
        f"{filename_stem}_anterior_original.png": "ant_original.png",
        f"{filename_stem}_posterior_original.png": "post_original.png",
        
        # Segmentation files
        f"{filename_stem}_anterior_colored.png": "ant_segm.png",
        f"{filename_stem}_posterior_colored.png": "post_segm.png",
        
        # YOLO files
        f"{filename_stem}_ant.xml": "ant_hotspot_yolo.xml",
        f"{filename_stem}_post.xml": "post_hotspot_yolo.xml",
        
        # Otsu files (keep the useful ones, rename the ambiguous ones)
        f"{filename_stem}_anterior_hotspot_colored.png": "ant_hotspot_otsu_colored.png",
        f"{filename_stem}_ant_hotspot_colored.png": "ant_hotspot_otsu_colored_blend.png",
        f"{filename_stem}_ant_hotspot_mask.png": "ant_hotspot_otsu_grayscale.png",
        f"{filename_stem}_posterior_hotspot_colored.png": "post_hotspot_otsu_colored.png",
        f"{filename_stem}_post_hotspot_colored.png": "post_hotspot_otsu_colored_blend.png",
        f"{filename_stem}_post_hotspot_mask.png": "post_hotspot_otsu_grayscale.png",
        
        # Classification files
        f"{filename_stem}_ant_classification.xml": "ant_hotspot_classification.xml",
        f"{filename_stem}_anterior_classification_mask.png": "ant_hotspot_classification.png",
        f"{filename_stem}_post_classification.xml": "post_hotspot_classification.xml",
        f"{filename_stem}_posterior_classification_mask.png": "post_hotspot_classification.png",
        
        # Quantification files
        f"{filename_stem}_bsi_quantification_anterior.json": "bsi_quantification_ant.json",
        f"{filename_stem}_bsi_quantification_posterior.json": "bsi_quantification_post.json"
    }
    
    migration_results = {
        'migrated': [],
        'skipped': [],
        'errors': []
    }
    
    for old_name, new_name in migration_map.items():
        old_path = patient_folder / old_name
        new_path = patient_folder / new_name
        
        try:
            if old_path.exists():
                if not new_path.exists():
                    import shutil
                    shutil.move(str(old_path), str(new_path))
                    migration_results['migrated'].append(f"{old_name} → {new_name}")
                else:
                    migration_results['skipped'].append(f"{new_name} already exists")
            else:
                migration_results['skipped'].append(f"{old_name} not found")
                
        except Exception as e:
            migration_results['errors'].append(f"Error migrating {old_name}: {e}")
    
    return migration_results

def cleanup_old_edited_files(patient_folder: Path):
    """
    Clean up old _edited files that are no longer used
    
    Args:
        patient_folder: Patient directory path
        
    Returns:
        Dictionary with cleanup results
    """
    cleanup_results = {
        'removed': [],
        'errors': []
    }
    
    # Look for old _edited files
    old_edited_patterns = [
        "*_edited.png",
        "*_edited.xml", 
        "*_edited.json",
        "*_edited_*.png",
        "*_edited_*.xml"
    ]
    
    for pattern in old_edited_patterns:
        for old_file in patient_folder.glob(pattern):
            try:
                old_file.unlink()
                cleanup_results['removed'].append(old_file.name)
            except Exception as e:
                cleanup_results['errors'].append(f"Error removing {old_file.name}: {e}")
    
    return cleanup_results

# ===== EDITOR-SPECIFIC FUNCTIONS =====
def get_editable_files_info(patient_folder: Path) -> Dict:
    """
    Get information about editable files and their versions
    
    Args:
        patient_folder: Patient directory path
        
    Returns:
        Dictionary with editable files info
    """
    info = {}
    
    for filename in EDITABLE_FILES:
        file_info = {
            'base_file': patient_folder / filename,
            'base_exists': (patient_folder / filename).exists(),
            'latest_timestamp': None,
            'latest_file': None,
            'all_versions': [],
            'edit_history': []
        }
        
        # Get latest timestamp version
        latest = get_latest_timestamp_file(patient_folder, filename)
        if latest:
            file_info['latest_timestamp'] = latest.parent.name
            file_info['latest_file'] = latest
        
        # Get all versions
        file_info['all_versions'] = get_all_timestamp_versions(patient_folder, filename)
        
        # Get edit history
        file_info['edit_history'] = get_edit_history(patient_folder, filename)
        
        info[filename] = file_info
    
    return info

def get_active_file_path(patient_folder: Path, filename: str) -> Path:
    """
    Get the active file path (latest timestamp or base file)
    
    Args:
        patient_folder: Patient directory path
        filename: Base filename
        
    Returns:
        Path to the active file
    """
    if filename in EDITABLE_FILES:
        latest = get_latest_timestamp_file(patient_folder, filename)
        if latest:
            return latest
    
    return patient_folder / filename

def is_file_editable(filename: str) -> bool:
    """
    Check if a file is editable (supports timestamp versioning)
    
    Args:
        filename: Filename to check
        
    Returns:
        True if file is editable
    """
    return filename in EDITABLE_FILES

def get_quantification_files(patient_folder: Path, filename_stem: str = None) -> dict:
    """
    ✅ NEW: Get quantification file paths with new simplified naming
    
    Args:
        patient_folder: Patient directory path  
        filename_stem: Filename stem (optional, for backward compatibility)
        
    Returns:
        Dictionary with quantification file paths using new naming convention
    """
    return {
        'bsi_json_ant': patient_folder / "bsi_quantification_anterior.json",
        'bsi_json_post': patient_folder / "bsi_quantification_posterior.json",
        # For backward compatibility with old naming
        'bsi_json_ant_old': patient_folder / f"{filename_stem}_bsi_quantification_anterior.json" if filename_stem else None,
        'bsi_json_post_old': patient_folder / f"{filename_stem}_bsi_quantification_posterior.json" if filename_stem else None
    }

def get_segmentation_files_with_edited(patient_folder: Path, filename_stem: str, view: str) -> dict:
    """
    ✅ NEW: Get segmentation files with priority for edited versions
    """
    vtag = "ant" if view.lower() in ["anterior", "ant"] else "post"
    
    base_files = {
        'png_colored': patient_folder / f"{vtag}_segm.png",
        'png_colored_edited': get_latest_timestamp_file(patient_folder, f"{vtag}_segm.png"),
    }
    
    return base_files

def get_classification_files(patient_folder: Path, filename_stem: str, view: str) -> dict:
    """
    ✅ NEW: Get classification files with priority for edited versions
    """
    vtag = "ant" if view.lower() in ["anterior", "ant"] else "post"
    
    base_files = {
        'mask_original': patient_folder / f"{vtag}_hotspot_classification.png", 
        'mask_edited': get_latest_timestamp_file(patient_folder, f"{vtag}_hotspot_classification.png"),
        'xml_original': patient_folder / f"{vtag}_hotspot_classification.xml",
        'xml_edited': get_latest_timestamp_file(patient_folder, f"{vtag}_hotspot_classification.xml")
    }
    
    return base_files