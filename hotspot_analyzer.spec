# hotspot_analyzer.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Get the current directory
current_dir = Path.cwd()

# Define paths
main_script = 'app/__main__.py'  # Updated to match your structure
app_name = 'hotspotAnalyzer'

# Collect all Python files and modules
hiddenimports = [
    # App module
    'app',
    'app.__main__',
    
    # Missing modules for scientific stack
    'pydoc',
    'pydoc_data',
    'pydoc_data.topics',
    'doctest',
    'inspect',
    
    # Core modules
    'core.config.cloud_storage',
    'core.config.paths',
    'core.config.sessions',
    'core.gui.loading_dialog',
    'core.gui.patient_info_bar', 
    'core.gui.searchable_combobox',
    'core.gui.ui_constants',
    'core.utils.image_converter',
    'core.utils.image_transparency',
    'core.logger',
    
    # Features
    'features.dicom_import.gui.dicom_import_dialog_v2',
    'features.dicom_import.gui.dicom_view_selector_dialog',
    'features.dicom_import.gui.doctor_selection_dialog',
    'features.dicom_import.logic.dicom_loader',
    'features.dicom_import.logic.directory_scanner',
    'features.dicom_import.logic.input_data',
    'features.dicom_import.logic.pixel_analyzer',
    
    'features.spect_viewer.gui.main_window_spect',
    'features.spect_viewer.gui.bsi_canvas',
    'features.spect_viewer.gui.frame_selector',
    'features.spect_viewer.gui.hotspot_editor_dialog',
    'features.spect_viewer.gui.mode_selector',
    'features.spect_viewer.gui.scan_grid',
    'features.spect_viewer.gui.scan_timeline',
    'features.spect_viewer.gui.segmentation_editor_dialog',
    'features.spect_viewer.gui.side_panel',
    'features.spect_viewer.gui.timeline_cards',
    'features.spect_viewer.gui.view_selector',
    'features.spect_viewer.gui.editor_components.base_components',
    'features.spect_viewer.gui.editor_components.hotspot_components',
    'features.spect_viewer.gui.editor_components.segmentation_components',
    'features.spect_viewer.gui.editor_components.xml_utils',
    
    'features.spect_viewer.logic.adjust_contrast',
    'features.spect_viewer.logic.algorithm_quantification',
    'features.spect_viewer.logic.bounding_box_renderer',
    'features.spect_viewer.logic.box_detection',
    'features.spect_viewer.logic.bsi_timeline_integration',
    'features.spect_viewer.logic.classification_wrapper',
    'features.spect_viewer.logic.classification_xml_converter',
    'features.spect_viewer.logic.colorizer',
    'features.spect_viewer.logic.hotspot_processor',
    'features.spect_viewer.logic.image_inverter',
    'features.spect_viewer.logic.inference_classification_hs',
    'features.spect_viewer.logic.integrated_workflow',
    'features.spect_viewer.logic.layer_processor',
    'features.spect_viewer.logic.processing_wrapper',
    'features.spect_viewer.logic.quantification_integration',
    'features.spect_viewer.logic.quantification_wrapper',
    'features.spect_viewer.logic.segmenter',
    
    'features.pet_viewer.gui.main_window_pet',
    'features.pet_viewer.gui.pet_import_dialog',
    'features.pet_viewer.gui.pet_viewer_widget',
    'features.pet_viewer.logic.pet_directory_scanner',
    'features.pet_viewer.logic.pet_loader',
    
    # Scientific/ML libraries
    'numpy',
    'scipy',
    'scipy.ndimage',
    'scipy.ndimage._support_alternative_backends', 
    'scipy._lib',
    'scipy._lib._array_api',
    'scipy._lib._docscrape',
    'pandas',
    'sklearn',
    'skimage',
    'skimage.filters',
    'skimage.filters.thresholding',
    'matplotlib',
    'seaborn',
    'torch',
    'torchvision',
    'timm',
    'ultralytics',
    'pydicom',
    'cv2',
    'PIL',
    'SimpleITK',
    'nibabel',
    'imageio',
    
    # PySide6 modules
    'PySide6.QtCore',
    'PySide6.QtGui', 
    'PySide6.QtWidgets',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'shiboken6',
    
    # Other utilities
    'yaml',
    'json',
    'pathlib',
    'dotenv',
]

# Collect data files
datas = [
    # Configuration files
    ('config', 'config'),
    # Assets
    ('assets', 'assets'),
    # Models (include all subdirectories)
    ('models', 'models'),
    # Segmentation data
    ('segmentation', 'segmentation'),
    # Environment file
    ('.env', '.'),
    # Data directory structure (empty folders will be created later)
    ('data', 'data'),
]

# Binaries to exclude (will be included automatically if needed)
excludes = [
    'tkinter',
    'test',
    'unittest',
    'pydoc',
    'doctest',
]

# Analysis
a = Analysis(
    [main_script],
    pathex=[str(current_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# Remove duplicates
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to True for debugging, False for windowed app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add path to .ico file if you have one
)

# Collect everything into dist folder
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles, 
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name,
)