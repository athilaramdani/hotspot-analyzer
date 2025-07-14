# core/config/__init__.py
"""
Configuration module untuk Hotspot Analyzer
"""

from .paths import (
    # Base paths
    PROJECT_ROOT, DATA_ROOT, MODELS_ROOT, OUTPUT_ROOT,
    SPECT_DATA_PATH, PET_DATA_PATH, DICOM_DATA_PATH,
    
    # Model paths
    YOLO_MODEL_PATH, UNET_MODEL_PATH, CNN_MODEL_PATH,
    
    # Utility functions
    ensure_directories, validate_paths,
    get_patient_spect_path, get_patient_pet_path,
    get_segmentation_files, get_hotspot_files,
    get_output_path, get_model_path, get_temp_path
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
    # Paths
    'PROJECT_ROOT', 'DATA_ROOT', 'MODELS_ROOT', 'OUTPUT_ROOT',
    'SPECT_DATA_PATH', 'PET_DATA_PATH', 'DICOM_DATA_PATH',
    'YOLO_MODEL_PATH', 'UNET_MODEL_PATH', 'CNN_MODEL_PATH',
    'ensure_directories', 'validate_paths',
    'get_patient_spect_path', 'get_patient_pet_path',
    'get_segmentation_files', 'get_hotspot_files',
    'get_output_path', 'get_model_path', 'get_temp_path',
    
    # Sessions
    'AVAILABLE_SESSION_CODES', 'AVAILABLE_MODALITIES',
    'SESSION_CODE_DESCRIPTIONS',
    'get_session_manager', 'create_session', 'end_session',
    'get_current_session', 'get_available_session_codes',
    'get_available_modalities', 'validate_session_code',
    'validate_modality', 'get_session_description'
]