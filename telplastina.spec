# hotspot_analyzer.spec - FIXED VERSION FOR PRODUCTION
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

# Get the current directory
current_dir = Path.cwd()

icon_path = current_dir / "assets" / "icon.ico"
if icon_path.exists():
    print(f"[SPEC] Icon found: {icon_path}")
    ICON_FILE = str(icon_path)
else:
    print(f"[SPEC] WARNING: Icon not found at {icon_path}")
    ICON_FILE = None

# Define paths
main_script = 'main.py'
app_name = 'telplastina'

# PyTorch compatibility fixes
block_cipher = None

# Collect all Python files and modules
hiddenimports = [
    # ========== CORE APP MODULES ==========
    'app',
    'app.__main__',
    
    # ========== CORE MODULES ==========
    'core.config.cloud_storage',
    'core.config.paths',
    'core.config.sessions',
    'core.gui.loading_dialog',
    'core.gui.patient_info_bar', 
    'core.gui.searchable_combobox',
    'core.gui.ui_constants',
    'core.utils.image_converter',
    'core.utils.image_transparency',
    'core.utils.pyinstaller_patches',
    'core.logger',
    
    # ========== FEATURES - SPECT VIEWER ==========
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
    
    # ========== DICOM IMPORT ==========
    'features.dicom_import.gui.dicom_import_dialog_v2',
    'features.dicom_import.gui.dicom_view_selector_dialog',
    'features.dicom_import.gui.doctor_selection_dialog',
    'features.dicom_import.logic.dicom_loader',
    'features.dicom_import.logic.directory_scanner',
    'features.dicom_import.logic.input_data',
    'features.dicom_import.logic.pixel_analyzer',
    
    # ========== PET VIEWER (optional) ==========
    'features.pet_viewer.gui.main_window_pet',
    'features.pet_viewer.gui.pet_import_dialog',
    'features.pet_viewer.gui.pet_viewer_widget',
    'features.pet_viewer.logic.pet_directory_scanner',
    'features.pet_viewer.logic.pet_loader',
    
    # ========== SCIENTIFIC LIBRARIES ==========
    'numpy',
    'numpy.core',
    'numpy.core._methods',
    'numpy.lib',
    'numpy.lib.format',
    'numpy.random',
    'numpy.random._pickle',
    'numpy.linalg',
    'numpy.fft',
    
    'scipy',
    'scipy.ndimage',
    'scipy.ndimage._support_alternative_backends', 
    'scipy._lib',
    'scipy._lib._array_api',
    'scipy._lib._docscrape',
    'scipy._lib._util',
    'scipy.sparse',
    'scipy.sparse.linalg',
    'scipy.spatial',
    'scipy.spatial.distance',
    'scipy.optimize',
    'scipy.interpolate',
    'scipy.integrate',
    'scipy.stats',
    'scipy.signal',
    'scipy.special',
    
    'pandas',
    'pandas._libs',
    'pandas._libs.tslibs',
    'pandas.io',
    'pandas.io.formats',
    'pandas._libs.tslibs.timedeltas',
    
    'sklearn',
    'sklearn.utils',
    'sklearn.utils._cython_blas',
    'sklearn.neighbors',
    'sklearn.neighbors._quad_tree',
    'sklearn.tree',
    'sklearn.tree._utils',
    'sklearn.ensemble',
    'sklearn.preprocessing',
    
    'skimage',
    'skimage.filters',
    'skimage.filters.thresholding',
    'skimage.feature',
    'skimage.measure',
    'skimage.morphology',
    'skimage.segmentation',
    'skimage.transform',
    'skimage.util',
    
    'matplotlib',
    'matplotlib.backends',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends._backend_qt',
    'matplotlib.figure',
    'matplotlib.pyplot',
    
    'seaborn',
    
    # ========== PYTORCH - COMPLETE MODULES ==========
    'torch',
    'torch.nn',
    'torch.nn.functional',
    'torch.nn.modules',
    'torch.nn.modules.module',
    'torch.nn.modules.activation',
    'torch.nn.modules.batchnorm',
    'torch.nn.modules.container',
    'torch.nn.modules.conv',
    'torch.nn.modules.linear',
    'torch.nn.modules.loss',
    'torch.nn.modules.normalization',
    'torch.nn.modules.pooling',
    'torch.nn.modules.dropout',
    'torch.nn.parameter',
    'torch.nn.init',
    'torch.optim',
    'torch.utils',
    'torch.utils.data',
    'torch.autograd',
    'torch.autograd.function',
    'torch.cuda',
    'torch.jit',
    'torch.serialization',
    'torch.storage',
    'torch.tensor',
    'torch.testing',
    'torch.types',
    'torch.version',
    'torch.backends',
    'torch.backends.cudnn',
    'torch.backends.mkl',
    'torch.backends.mkldnn',
    
    # Torch FX and nested
    'torch.fx',
    'torch.fx.node',
    'torch.fx.graph',
    'torch.fx.graph_module',
    'torch.fx.experimental',
    'torch.fx.experimental._constant_symnode',
    'torch.nested',
    'torch.nested._internal',
    'torch.nested._internal.nested_tensor',
    'torch.nested._internal.nested_int',

    # ========== TORCH TESTING & INTERNAL MODULES ==========
    'torch.testing',
    'torch.testing._internal',
    'torch.testing._internal.logging_tensor',
    'torch.testing._internal.common_utils',
    'torch.testing._internal.common_dtype',
    'torch.testing._internal.common_device_type',
    'torch.testing._internal.common_methods',
    'torch.testing._internal.common_cuda',
    'torch.testing._internal.autograd_function_db',
    'torch.utils.checkpoint',

    # ========== TORCH COMPILE & JIT ==========
    'torch.compiler',
    'torch._inductor',
    'torch._functorch',
    
    # YOLO/Ultralytics
    'ultralytics',
    'ultralytics.models',
    'ultralytics.models.yolo',
    'ultralytics.utils',
    'ultralytics.engine',
    'ultralytics.nn',
    'ultralytics.data',
    'ultralytics.utils.checks',
    'ultralytics.utils.ops',
    'ultralytics.utils.torch_utils',
    
    # Timm (for model architectures)
    'timm',
    'timm.models',
    'timm.layers',
    
    # TorchVision - MINIMAL SAFE IMPORTS ONLY
    'torchvision',
    'torchvision.extension',  #   INCLUDE extension
    'torchvision._extension', #   INCLUDE private extension
    'torchvision.transforms',
    'torchvision.transforms.functional',
    'torchvision.transforms._transforms_video',
    'torchvision.models',
    'torchvision.utils',
    'torchvision.datasets',
    'torchvision.io',
    'torchvision.ops',
    'torchvision.ops._register_ops',
    
    # ========== NNUNET ==========
    'nnunetv2',
    'nnunetv2.inference',
    'nnunetv2.inference.predict_from_raw_data',
    'nnunetv2.training',
    'nnunetv2.utilities',
    'dynamic_network_architectures',
    'dynamic_network_architectures.architectures',
    'batchgenerators',
    'batchgenerators.utilities',
    'acvl_utils',
    'acvl_utils.cropping_and_padding',
    'acvl_utils.cropping_and_padding.padding',
    
    # ========== XGBOOST ==========
    'xgboost',
    'xgboost.sklearn',
    'xgboost.core',
    
    # ========== IMAGE/MEDICAL PROCESSING ==========
    'pydicom',
    'pydicom.encoders',
    'pydicom.decoders',
    'pydicom.charset',
    'pydicom.sequence',
    'pydicom.dataset',
    'pydicom.filereader',
    'pydicom.filewriter',
    
    'cv2',
    'PIL',
    'PIL._tkinter_finder',
    'PIL.Image',
    'PIL.ImageTk',
    
    'SimpleITK',
    'nibabel',
    'nibabel.orientations',
    'nibabel.affines',
    
    'imageio',
    'imageio.plugins',
    'imageio.core',
    
    # ========== PYSIDE6 ==========
    'PySide6.QtCore',
    'PySide6.QtGui', 
    'PySide6.QtWidgets',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'shiboken6',
    
    # ========== UTILITIES ==========
    'yaml',
    'json',
    'pathlib',
    'pydicom',
    'dotenv',
    'threading',
    'multiprocessing',
    'queue',
    'subprocess',
    'tempfile',
    'shutil',
    'glob',
    'fnmatch',
    're',
    'datetime',
    'time',
    'logging',
    'pickle',
    'gzip',
    'zipfile',
    'tarfile',
    
    # ========== STANDARD LIBRARY MODULES ==========
    'collections',
    'collections.abc',
    'importlib',
    'importlib.util',
    'importlib.metadata',
    'importlib_metadata',
    'importlib_resources',
    'pkg_resources',
    'setuptools',
    'distutils',
    'site',
    'sysconfig',
    'typing',
    'typing_extensions',
    'functools',
    'itertools',
    'operator',
    'math',
    'numbers',
    'warnings',
    'weakref',
    'copy',
    'struct',
    'array',
    'ctypes',
    'ctypes.util',
    'platform',
    'concurrent',
    'concurrent.futures',
    'os.path',
    'urllib',
    'urllib.request',
    'urllib.parse',
    'urllib.error',
    'ssl',
    'socket',
    'http',
    'http.client',
    'inspect',
    'unittest',
    'unittest.mock',
    'unittest.util',
    'pydoc',
    'pydoc_data',
    'pydoc_data.topics',
    'textwrap',
    'linecache',
    'tokenize',
    'keyword',
    'doctest',
]

# Collect data files - FIXED PATHS but not used
datas = []



# Binaries to exclude (reduce size)
excludes = [
    'tkinter',
    '_tkinter',
    'matplotlib.tests',
    'numpy.tests',
    'scipy.tests',
    'sklearn.tests',
    'torch.test',
    'test',
    'tests',
    'pytest',
    'unittest2',
    'IPython',
    'jupyter',
    'notebook',
    # Block triton completely
    'triton',
    'triton.language',
    'triton.compiler',
    'triton.runtime',
    'triton.ops',
    # Exclude problematic torch modules
    'torch._dynamo',  #   BARU: Exclude dynamo untuk stability
    'torch._inductor',  #   BARU: Exclude inductor
]

# Runtime hooks - EMPTY to let PyInstaller handle torch normally
runtime_hooks = [
    'hooks/runtime_hook.py',
    'hooks/runtime_hook_nnunet.py',
    'hooks/runtime_hook_torchvision.py',
    'hooks/runtime_hook_xgboost.py'  #   ADD THIS
]

# Analysis with improved settings
a = Analysis(
    [main_script],
    pathex=[str(current_dir)],
    binaries=[
        #   ADD: XGBoost library binaries
        (str(current_dir / '.venv' / 'Lib' / 'site-packages' / 'xgboost' / 'lib' / 'xgboost.dll'), 'xgboost/lib'),
        (str(current_dir / '.venv' / 'Lib' / 'site-packages' / 'xgboost' / 'lib' / 'xgboost.dll'), 'lib'),
    ],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['hooks'],
    hooksconfig={
        # Disable PyTorch JIT and other problematic features
        'torch': {
            'enable_jit': False,
            'optimize': False,
        }
    },
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    noarchive=False,
    optimize=1, 
    debug='all', # Changed to 1 for better compatibility
    # Ensure torch is treated as a package
    module_collection_mode={
        'torch': 'pyz+py',
        'torch.nn': 'pyz+py',
        'torch._C': 'pyz+py',
        'torch._ops': 'pyz+py',
        'torch.fx': 'pyz+py',
        'torch.nested': 'pyz+py',
        'torch.autograd': 'pyz+py',
        'torch.utils': 'pyz+py',
        'torch.backends': 'pyz+py',
    }
)

# Filter out duplicates and problematic entries
unique_pure = []
seen = set()
for item in a.pure:
    if item[0] not in seen:
        seen.add(item[0])
        unique_pure.append(item)
a.pure = unique_pure

# Create PYZ archive
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,  # Set to True for debugging
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging, False for production
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,  #   FIXED: Add icon path
)

# Collect everything into dist folder
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles, 
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        'torch*.dll',
        'cuda*.dll', 
        '*.pyd',
        'qt*.dll',
    ],
    name=app_name,
)