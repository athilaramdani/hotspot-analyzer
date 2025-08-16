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
    
    Args:
        session_code: Session code (NSY, ATL, NBL, ALL)
        patient_id: Patient ID
        study_date: Study date in YYYYMMDD format (optional)
        
    Returns:
        Path for patient data
    """
    if session_code == "ALL":
        base_path = PLANAR_DATA_PATH / "ALL" / patient_id
    else:
        base_path = PLANAR_DATA_PATH / session_code / patient_id
    
    if study_date:
        return base_path / study_date
    return base_path

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

def get_planar_segmentation_files(patient_folder: Path, view: str, with_priority: bool = True):
    """
    Get segmentation file paths for planar data with timestamp priority
    
    Args:
        patient_folder: Patient directory path
        view: View name (ant/post)
        with_priority: Whether to check for latest timestamp version
        
    Returns:
        Dictionary with file paths using new naming convention
    """
    vtag = "ant" if view.lower() in ["anterior", "ant"] else "post"
    
    base_files = {
        'segmentation_png': patient_folder / f"{vtag}_segm.png",
        'mask_png': patient_folder / f"{vtag}_mask.png"
    }
    
    if with_priority:
        # Check for latest timestamp version
        latest_segm = get_latest_timestamp_file(patient_folder, f"{vtag}_segm.png")
        if latest_segm:
            base_files['segmentation_png'] = latest_segm
    
    return base_files

def get_planar_hotspot_files(patient_folder: Path, view: str, with_priority: bool = True):
    """
    Get hotspot file paths for planar data with timestamp priority
    
    Args:
        patient_folder: Patient directory path
        view: View name (ant/post)
        with_priority: Whether to check for latest timestamp version
        
    Returns:
        Dictionary with hotspot file paths using new naming convention
    """
    vtag = "ant" if view.lower() in ["anterior", "ant"] else "post"
    
    base_files = {
        # YOLO detection files
        'yolo_xml': patient_folder / f"{vtag}_hotspot_yolo.xml",
        
        # Otsu processing files
        'otsu_colored': patient_folder / f"{vtag}_hotspot_otsu_colored.png",         # 100% hotspot
        'otsu_colored_blend': patient_folder / f"{vtag}_hotspot_otsu_colored_blend.png",  # 50/50 blend
        'otsu_grayscale': patient_folder / f"{vtag}_hotspot_otsu_grayscale.png",    # Used for classification input
        
        # Classification files (main ones used in UI)
        'classification_xml': patient_folder / f"{vtag}_hotspot_classification.xml",
        'classification_png': patient_folder / f"{vtag}_hotspot_classification.png"
    }
    
    if with_priority:
        # Check for latest timestamp versions of editable files
        latest_classification_png = get_latest_timestamp_file(patient_folder, f"{vtag}_hotspot_classification.png")
        if latest_classification_png:
            base_files['classification_png'] = latest_classification_png
            
            # Also update XML if PNG is from timestamp (they go together)
            latest_classification_xml = get_latest_timestamp_file(patient_folder, f"{vtag}_hotspot_classification.xml")
            if latest_classification_xml:
                base_files['classification_xml'] = latest_classification_xml
    
    return base_files

def get_planar_quantification_files(patient_folder: Path):
    """
    Get BSI quantification file paths with new simplified naming
    
    Args:
        patient_folder: Patient directory path
        
    Returns:
        Dictionary with quantification file paths using new naming convention
    """
    return {
        'bsi_json_ant': patient_folder / "bsi_quantification_ant.json",
        'bsi_json_post': patient_folder / "bsi_quantification_post.json"
    }

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

def get_planar_workflow_files(patient_folder: Path, original_dicom_name: str = None, with_priority: bool = True):
    """
    Get all workflow-related files for both views with timestamp priority
    
    Args:
        patient_folder: Patient directory path
        original_dicom_name: Original DICOM filename
        with_priority: Whether to use latest timestamp versions
        
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
        # Update with latest timestamp versions for editable files
        for view in ['ant', 'post']:
            # Segmentation
            latest_segm = get_latest_timestamp_file(patient_folder, f"{view}_segm.png")
            if latest_segm:
                workflow_files['segmentation'][view] = latest_segm
            
            # Classification
            latest_class_png = get_latest_timestamp_file(patient_folder, f"{view}_hotspot_classification.png")
            latest_class_xml = get_latest_timestamp_file(patient_folder, f"{view}_hotspot_classification.xml")
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
def get_latest_timestamp_file(patient_folder: Path, filename: str) -> Optional[Path]:
    """
    Get the latest timestamp version of a file if it exists
    
    Args:
        patient_folder: Patient directory path
        filename: Base filename to search for
        
    Returns:
        Path to latest timestamp version or None if not found
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