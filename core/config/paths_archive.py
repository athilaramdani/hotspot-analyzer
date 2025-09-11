# core/config/paths_archive.py
"""
Archived path functions for PET, SPECT and Cloud Storage
These functions are no longer used in the main application but kept for reference
"""
from pathlib import Path
import os
from typing import Optional
import logging
# ===== ARCHIVED PET FUNCTIONS =====
def get_patient_pet_path(patient_id: str, session_code: str = None) -> Path:
    """ARCHIVED: Get path to patient's PET data folder"""
    from .paths import DATA_ROOT
    PET_DATA_PATH = DATA_ROOT / "PET"
    
    if session_code:
        return PET_DATA_PATH / session_code / patient_id
    return PET_DATA_PATH / patient_id

def get_cloud_pet_path(patient_id: str, session_code: str = None) -> str:
    """ARCHIVED: Get cloud path for PET data"""
    if session_code:
        return f"data/PET/{session_code}/{patient_id}"
    return f"data/PET/{patient_id}"

# ===== ARCHIVED SPECT FUNCTIONS =====
def get_patient_spect_path(patient_id: str, session_code: str) -> Path:
    """ARCHIVED: Get path to patient's SPECT data folder"""
    from .paths import DATA_ROOT
    SPECT_DATA_PATH = DATA_ROOT / "SPECT"
    return SPECT_DATA_PATH / session_code / patient_id

def get_session_spect_path(session_code: str) -> Path:
    """ARCHIVED: Get path to session's SPECT data folder"""
    from .paths import DATA_ROOT
    SPECT_DATA_PATH = DATA_ROOT / "SPECT"
    return SPECT_DATA_PATH / session_code

def get_segmentation_files(patient_folder: Path, filename_stem: str, view: str):
    """ARCHIVED: Get segmentation file paths for a specific view with study date support"""
    vtag = view.lower()
    
    return {
        'png_mask': patient_folder / f"{filename_stem}_{vtag}_mask.png",
        'png_colored': patient_folder / f"{filename_stem}_{vtag}_colored.png",
        'dcm_mask': patient_folder / f"{filename_stem}_{vtag}_mask.dcm",
        'dcm_colored': patient_folder / f"{filename_stem}_{vtag}_colored.dcm"
    }

def get_segmentation_files_with_edited(patient_folder: Path, filename_stem: str, view: str):
    """ARCHIVED: Get segmentation file paths including edited versions"""
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

def get_hotspot_files(patient_id: str, session_code: str, view: str, study_date: str):
    """ARCHIVED: Get hotspot file paths with proper edited file prioritization"""
    from .paths import DATA_ROOT, generate_filename_stem
    SPECT_DATA_PATH = DATA_ROOT / "SPECT"
    patient_folder = SPECT_DATA_PATH / session_code / patient_id
    filename_stem = generate_filename_stem(patient_id, study_date)
    
    # Normalize view names
    view_normalized = view.lower()
    if "ant" in view_normalized:
        view_full = "anterior"
        view_short = "ant"
    else:
        view_full = "posterior" 
        view_short = "post"
    
    # XML file prioritization logic
    xml_edited_path = patient_folder / f"{filename_stem}_{view_short}_edited.xml"
    xml_original_path = patient_folder / f"{filename_stem}_{view_short}.xml"
    final_xml_path = xml_edited_path if xml_edited_path.exists() else xml_original_path
    
    return {
        'colored_png_edited': patient_folder / f"{filename_stem}_{view_full}_hotspot_edited_colored.png",
        'mask_file_edited': patient_folder / f"{filename_stem}_{view_full}_hotspot_edited_mask.png",
        'colored_png': patient_folder / f"{filename_stem}_{view_full}_hotspot_colored.png",
        'mask_file': patient_folder / f"{filename_stem}_{view_full}_hotspot_mask.png",
        'xml_file': final_xml_path,
        'xml_file_original': xml_original_path,
        'xml_file_edited': xml_edited_path,
        'colored_png_legacy': patient_folder / f"{filename_stem}_{view_short}_hotspot_colored.png",
        'mask_file_legacy': patient_folder / f"{filename_stem}_{view_short}_hotspot_mask.png",
    }

def get_cloud_spect_path(session_code: str, patient_id: str = None) -> str:
    """ARCHIVED: Get cloud path for SPECT data"""
    if patient_id:
        return f"data/SPECT/{session_code}/{patient_id}"
    return f"data/SPECT/{session_code}"

# ===== ARCHIVED CLOUD STORAGE CONFIGURATION =====
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY") 
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "hotspot-analyzer-data")
B2_ENDPOINT = os.getenv("B2_ENDPOINT", "https://s3.us-west-004.backblazeb2.com")

CLOUD_SYNC_ENABLED = os.getenv("CLOUD_SYNC_ENABLED", "false").lower() == "true"
AUTO_BACKUP = os.getenv("AUTO_BACKUP", "false").lower() == "true"
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))

CLOUD_DATA_PREFIX = "data/"
CLOUD_MODELS_PREFIX = "models/"
CLOUD_LOGS_PREFIX = "logs/"
CLOUD_BACKUP_PREFIX = "backups/"

def get_cloud_path(local_path: Path) -> str:
    """ARCHIVED: Convert local path to cloud storage path"""
    try:
        from .paths import PROJECT_ROOT
        rel_path = local_path.relative_to(PROJECT_ROOT)
        cloud_path = str(rel_path).replace("\\", "/")
        return cloud_path
    except ValueError:
        return str(local_path).replace("\\", "/")

def get_local_path_from_cloud(cloud_path: str) -> Path:
    """ARCHIVED: Convert cloud storage path to local path"""
    from .paths import PROJECT_ROOT
    return PROJECT_ROOT / cloud_path.replace("/", os.sep)

def is_cloud_enabled() -> bool:
    """ARCHIVED: Check if cloud storage is properly configured and enabled"""
    return (CLOUD_SYNC_ENABLED and 
            B2_KEY_ID and 
            B2_APPLICATION_KEY and 
            B2_BUCKET_NAME and 
            B2_ENDPOINT)

def validate_cloud_config():
    """ARCHIVED: Validate cloud storage configuration"""
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

# ===== ARCHIVED OUTPUT/CACHE/TEMP PATHS =====
def get_archived_output_paths():
    """ARCHIVED: Get output paths that are no longer used"""
    from .paths import PROJECT_ROOT
    
    return {
        'OUTPUT_ROOT': PROJECT_ROOT / "output",
        'RESULTS_PATH': PROJECT_ROOT / "output" / "results",
        'EXPORTS_PATH': PROJECT_ROOT / "output" / "exports",
        'REPORTS_PATH': PROJECT_ROOT / "output" / "reports",
        'CACHE_ROOT': PROJECT_ROOT / ".cache",
        'IMAGE_CACHE_PATH': PROJECT_ROOT / ".cache" / "images",
        'MODEL_CACHE_PATH': PROJECT_ROOT / ".cache" / "models",
        'TEMP_IMAGES_PATH': PROJECT_ROOT / "temp" / "images",
        'TEMP_PROCESSING_PATH': PROJECT_ROOT / "temp" / "processing",
        'APP_LOG_PATH': PROJECT_ROOT / "logs" / "app.log",
        'ERROR_LOG_PATH': PROJECT_ROOT / "logs" / "error.log",
        'DEBUG_LOG_PATH': PROJECT_ROOT / "logs" / "debug.log"
    }

def get_output_path(patient_id: str, session_code: str, analysis_type: str = "hotspot") -> Path:
    """ARCHIVED: Get output path for patient analysis results"""
    paths = get_archived_output_paths()
    return paths['RESULTS_PATH'] / analysis_type / session_code / patient_id

# ===== ARCHIVED MIGRATION FUNCTIONS =====
def get_old_patient_spect_path(patient_id: str, session_code: str) -> Path:
    """ARCHIVED: Get OLD path structure for migration purposes"""
    from .paths import DATA_ROOT
    SPECT_DATA_PATH = DATA_ROOT / "SPECT"
    return SPECT_DATA_PATH / f"{patient_id}_{session_code}"

def migrate_old_to_new_structure():
    """ARCHIVED: Migrate old directory structure to new structure"""
    from .paths import DATA_ROOT
    SPECT_DATA_PATH = DATA_ROOT / "SPECT"
    
    if not SPECT_DATA_PATH.exists():
        return
    
    logging.info("🔄 Migrating SPECT directory structure...")
    
    old_directories = []
    for item in SPECT_DATA_PATH.iterdir():
        if item.is_dir() and "_" in item.name:
            parts = item.name.split("_")
            if len(parts) >= 2:
                old_directories.append(item)
    
    migrated_count = 0
    for old_dir in old_directories:
        try:
            parts = old_dir.name.split("_")
            patient_id = parts[0]
            session_code = "_".join(parts[1:])
            
            new_path = SPECT_DATA_PATH / session_code / patient_id
            
            if not new_path.exists():
                new_path.parent.mkdir(parents=True, exist_ok=True)
                old_dir.rename(new_path)
                logging.info(f"  Migrated: {old_dir} → {new_path}")
                migrated_count += 1
            else:
                logging.info(f"⚠️  Target already exists: {new_path}")
                
        except Exception as e:
            logging.info(f" Failed to migrate {old_dir}: {e}")
    
    logging.info(f"  Migration completed: {migrated_count} directories migrated")

def migrate_filenames_to_study_date():
    """ARCHIVED: Migrate existing files to include study date in filenames"""
    from .paths import DATA_ROOT, extract_study_date_from_dicom, generate_filename_stem
    SPECT_DATA_PATH = DATA_ROOT / "SPECT"
    
    if not SPECT_DATA_PATH.exists():
        return
    
    logging.info("🔄 Migrating filenames to include study date...")
    
    migrated_count = 0
    for session_dir in SPECT_DATA_PATH.iterdir():
        if not session_dir.is_dir():
            continue
            
        for patient_dir in session_dir.iterdir():
            if not patient_dir.is_dir():
                continue
                
            patient_id = patient_dir.name
            
            dicom_files = list(patient_dir.glob("*.dcm"))
            primary_dicom = None
            
            for dcm_file in dicom_files:
                if any(skip in dcm_file.name.lower() for skip in ['mask', 'colored', 'edited']):
                    continue
                primary_dicom = dcm_file
                break
            
            if not primary_dicom:
                logging.info(f"⚠️  No primary DICOM found in {patient_dir}")
                continue
            
            try:
                study_date = extract_study_date_from_dicom(primary_dicom)
                new_filename_stem = generate_filename_stem(patient_id, study_date)
                
                for file_path in patient_dir.iterdir():
                    if not file_path.is_file():
                        continue
                    
                    old_name = file_path.name
                    
                    if len(old_name.split('_')) >= 2 and old_name.split('_')[1].isdigit() and len(old_name.split('_')[1]) == 8:
                        continue
                    
                    if old_name.startswith(patient_id):
                        new_name = old_name.replace(patient_id, new_filename_stem, 1)
                        new_path = patient_dir / new_name
                        
                        if new_path != file_path:
                            file_path.rename(new_path)
                            logging.info(f"  Renamed: {old_name} → {new_name}")
                            migrated_count += 1
                    
            except Exception as e:
                logging.info(f" Failed to migrate files in {patient_dir}: {e}")
    
    logging.info(f"  Filename migration completed: {migrated_count} files renamed")

def migrate_spect_to_planar():
    """ARCHIVED: Migrate SPECT directory structure to PLANAR structure"""
    from .paths import DATA_ROOT, extract_study_date_from_dicom
    SPECT_DATA_PATH = DATA_ROOT / "SPECT"
    PLANAR_DATA_PATH = DATA_ROOT / "PLANAR"
    
    if not SPECT_DATA_PATH.exists():
        return
    
    logging.info("🔄 Migrating SPECT to PLANAR structure...")
    
    migrated_count = 0
    for session_dir in SPECT_DATA_PATH.iterdir():
        if not session_dir.is_dir():
            continue
            
        session_code = session_dir.name
        new_session_dir = PLANAR_DATA_PATH / session_code
        new_session_dir.mkdir(parents=True, exist_ok=True)
        
        for patient_dir in session_dir.iterdir():
            if not patient_dir.is_dir():
                continue
                
            patient_id = patient_dir.name
            new_patient_dir = new_session_dir / patient_id
            
            dicom_files = list(patient_dir.glob("*.dcm"))
            if dicom_files:
                try:
                    study_date = extract_study_date_from_dicom(dicom_files[0])
                    final_patient_dir = new_patient_dir / study_date
                    final_patient_dir.mkdir(parents=True, exist_ok=True)
                    
                    for file_path in patient_dir.iterdir():
                        if file_path.is_file():
                            old_name = file_path.name
                            new_name = old_name.replace("anterior", "ant").replace("posterior", "post")
                            
                            new_file_path = final_patient_dir / new_name
                            if not new_file_path.exists():
                                import shutil
                                shutil.copy2(file_path, new_file_path)
                                logging.info(f"  Migrated: {file_path} → {new_file_path}")
                                migrated_count += 1
                    
                except Exception as e:
                    logging.info(f" Failed to migrate {patient_dir}: {e}")
    
    logging.info(f"  SPECT to PLANAR migration completed: {migrated_count} files migrated")

# ===== ARCHIVED FILE FUNCTIONS =====
def get_original_image_files(patient_folder: Path, filename_stem: str) -> dict:
    """ARCHIVED: Get original PNG image file paths for both views"""
    return {
        'anterior_png': patient_folder / f"{filename_stem}_anterior_original.png",
        'posterior_png': patient_folder / f"{filename_stem}_posterior_original.png",
    }

def get_view_original_png(patient_folder: Path, filename_stem: str, view: str) -> Path:
    """ARCHIVED: Get original PNG file path for specific view"""
    view_normalized = view.lower()
    return patient_folder / f"{filename_stem}_{view_normalized}_original.png"

def get_segmentation_files_for_quantification(patient_folder: Path, filename_stem: str, view: str):
    """ARCHIVED: Get segmentation files with edited priority for quantification"""
    view_normalized = view.lower()
    
    edited_colored = patient_folder / f"{filename_stem}_{view_normalized}_edited_colored.png"
    original_colored = patient_folder / f"{filename_stem}_{view_normalized}_colored.png"
    
    return {
        'colored_edited': edited_colored,
        'colored_original': original_colored,
        'colored_to_use': edited_colored if edited_colored.exists() else original_colored
    }

def get_classification_files(patient_folder: Path, filename_stem: str, view: str) -> dict:
    """ARCHIVED: Get classification file paths"""
    vtag = view.lower()
    return {
        "json_original": patient_folder / f"{filename_stem}_{vtag}_classification.json",
        "json_edited": patient_folder / f"{filename_stem}_{vtag}_classification_edited.json",
        "mask_original": patient_folder / f"{filename_stem}_{vtag}_classification_mask.png",
        "mask_edited": patient_folder / f"{filename_stem}_{vtag}_classification_mask_edited.png",
    }

def get_quantification_files(patient_folder: Path, filename_stem: str) -> dict:
    """ARCHIVED: Get quantification files"""
    return {
        "bsi_json_anterior": patient_folder / f"{filename_stem}_bsi_quantification_anterior.json",
        "bsi_json_posterior": patient_folder / f"{filename_stem}_bsi_quantification_posterior.json",
    }

def get_dicom_output_path(patient_id: str, session_code: str, study_date: str) -> Path:
    """ARCHIVED: Get output path for processed DICOM file with study date"""
    from .paths import DATA_ROOT, generate_filename_stem
    SPECT_DATA_PATH = DATA_ROOT / "SPECT"
    patient_folder = SPECT_DATA_PATH / session_code / patient_id
    filename_stem = generate_filename_stem(patient_id, study_date)
    return patient_folder / f"{filename_stem}.dcm"