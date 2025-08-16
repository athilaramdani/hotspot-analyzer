# core/config/__init__.py
"""
Configuration module untuk Hotspot Analyzer
Updated for PLANAR-only workflow with timestamp-based editing
"""

from .paths import (
    # Base paths
    PROJECT_ROOT, DATA_ROOT, MODELS_ROOT,
    PLANAR_DATA_PATH, DICOM_DATA_PATH,
    
    # Model paths
    YOLO_MODEL_PATH, UNET_MODEL_PATH, CNN_MODEL_PATH,
    CLASSIFICATION_XGBOOST_MODEL, CLASSIFICATION_SCALER_MODEL,
    
    # Config paths
    CONFIG_ROOT, MODEL_CONFIG_PATH, APP_CONFIG_PATH,
    
    # Asset paths
    ASSETS_ROOT, ICONS_PATH, IMAGES_PATH,
    
    # PLANAR-specific functions
    get_patient_planar_path, 
    get_edit_timestamp_path,
    get_session_planar_path,
    get_planar_original_files,
    get_planar_segmentation_files,
    get_planar_hotspot_files,
    get_planar_quantification_files,
    get_planar_files_complete,
    get_planar_workflow_files,
    check_planar_workflow_completion,
    get_workflow_step_files,
    
    # Timestamp editing functions
    generate_edit_timestamp,
    generate_edit_date,
    get_latest_timestamp_file,
    get_all_timestamp_versions,
    save_edit_timestamp_file,
    get_edit_history,
    get_editable_files_info,
    get_active_file_path,
    is_file_editable,
    
    # Constants
    EDITABLE_FILES,
    
    # Utility functions
    ensure_directories, validate_paths,
    extract_study_date_from_dicom,
    generate_filename_stem,
    get_model_path, get_temp_path,
    find_files_by_pattern,
    get_dicom_files_in_folder,
    parse_planar_filename,
    
    # Migration and validation functions
    migrate_old_naming_to_new,
    validate_planar_naming_convention,
    cleanup_old_edited_files
)

from .sessions import (
    # Session constants
    AVAILABLE_SESSION_CODES, AVAILABLE_MODALITIES,
    SESSION_CODE_DESCRIPTIONS,
    
    # Session management
    get_session_manager, create_session, end_session,
    get_current_session, get_available_session_codes,
    get_available_modalities, validate_session_code,
    validate_modality, get_session_description
)

# Initialize directories on import
ensure_directories()

__all__ = [
    # Base paths
    'PROJECT_ROOT', 'DATA_ROOT', 'MODELS_ROOT',
    'PLANAR_DATA_PATH', 'DICOM_DATA_PATH',
    
    # Model paths
    'YOLO_MODEL_PATH', 'UNET_MODEL_PATH', 'CNN_MODEL_PATH',
    'CLASSIFICATION_XGBOOST_MODEL', 'CLASSIFICATION_SCALER_MODEL',
    
    # Config paths
    'CONFIG_ROOT', 'MODEL_CONFIG_PATH', 'APP_CONFIG_PATH',
    
    # Asset paths
    'ASSETS_ROOT', 'ICONS_PATH', 'IMAGES_PATH',
    
    # PLANAR path functions
    'get_patient_planar_path', 
    'get_edit_timestamp_path',
    'get_session_planar_path',
    'get_planar_original_files',
    'get_planar_segmentation_files',
    'get_planar_hotspot_files',
    'get_planar_quantification_files',
    'get_planar_files_complete',
    'get_planar_workflow_files',
    'check_planar_workflow_completion',
    'get_workflow_step_files',
    
    # Timestamp editing functions
    'generate_edit_timestamp',
    'generate_edit_date',
    'get_latest_timestamp_file',
    'get_all_timestamp_versions',
    'save_edit_timestamp_file',
    'get_edit_history',
    'get_editable_files_info',
    'get_active_file_path',
    'is_file_editable',
    
    # Constants
    'EDITABLE_FILES',
    
    # Utility functions
    'ensure_directories', 'validate_paths',
    'extract_study_date_from_dicom',
    'generate_filename_stem',
    'get_model_path', 'get_temp_path',
    'find_files_by_pattern',
    'get_dicom_files_in_folder',
    'parse_planar_filename',
    
    # Migration and validation functions
    'migrate_old_naming_to_new',
    'validate_planar_naming_convention',
    'cleanup_old_edited_files',
    
    # Session management
    'AVAILABLE_SESSION_CODES', 'AVAILABLE_MODALITIES',
    'SESSION_CODE_DESCRIPTIONS',
    'get_session_manager', 'create_session', 'end_session',
    'get_current_session', 'get_available_session_codes',
    'get_available_modalities', 'validate_session_code',
    'validate_modality', 'get_session_description'
]