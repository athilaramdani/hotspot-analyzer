# build.py - Build script for Hotspot Analyzer
"""
Enhanced build script for creating the Hotspot Analyzer executable
Handles PyTorch compatibility and optimization
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import tempfile

def setup_environment():
    """Setup environment variables for PyTorch compatibility"""
    # Disable PyTorch JIT to avoid source inspection issues
    os.environ['TORCH_JIT'] = '0'
    os.environ['TORCH_JIT_LOG_LEVEL'] = 'ERROR'
    
    # ✅ CRITICAL: Disable triton completely
    os.environ['TRITON_DISABLE'] = '1'
    os.environ['TORCH_TRITON_DISABLE'] = '1'
    os.environ['USE_TRITON'] = '0'
    
    # ✅ NEW: Completely disable triton to prevent library registration conflicts
    os.environ['TORCH_DISABLE_TRITON_OPS'] = '1'
    os.environ['TORCH_DISABLE_TRITON_LIBRARY'] = '1'
    os.environ['TORCH_DISABLE_TRITON_REGISTRATION'] = '1'
    
    # Optimize for production
    os.environ['PYTHONOPTIMIZE'] = '1'
    
    # Reduce verbosity
    os.environ['PYINSTALLER_COMPILE_BOOTLOADER'] = '0'
    
    # NEW: Disable torch dynamo completely
    os.environ['TORCHDYNAMO_DISABLE'] = '1'
    os.environ['TORCH_COMPILE_DISABLE'] = '1'
    os.environ['TORCH_DYNAMO_DISABLE'] = '1'
    
    # ✅ ADD: Additional environment variables for nnUNet compatibility
    os.environ['TORCH_FX_DISABLE'] = '1'
    os.environ['NNUNET_DISABLE_COMPILE'] = '1'
    
    print("✅ Environment configured with torch._dynamo disabled")

def create_torch_hooks():
    """Create comprehensive torch hooks for PyInstaller"""
    hooks_dir = Path("hooks")
    hooks_dir.mkdir(exist_ok=True)
    
    # Create comprehensive torch hook
    torch_hook = hooks_dir / "hook-torch.py"
    torch_hook_content = '''
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all torch modules
datas, binaries, hiddenimports = collect_all('torch')

# Add specific torch modules that might be missing
hiddenimports += [
    'torch._dynamo',
    'torch._dynamo.config',
    'torch._dynamo.convert_frame',
    'torch._dynamo.eval_frame',
    'torch._dynamo.resume_execution', 
    'torch._dynamo.symbolic_convert',
    'torch._dynamo.trace_rules',
    'torch._dynamo.variables',
    'torch._dynamo.variables.base',
    'torch._dynamo.guards',
    'torch._dynamo.polyfills',
    'torch._dynamo.polyfills.fx',
    'torch._dynamo.polyfills.loader',
    'torch._functorch',
    'torch._inductor',
    'torch._C._nn',
    'torch._C._autograd',
    'torch._C._te',
    'torch._C._fft',
    'torch._C._linalg',
    'torch._C._sparse',
    'torch._C._special',
    'torch._ops',
    'torch._ops.ops',
    'torch.utils.checkpoint',
    'torch.testing._internal',
    'torch.testing._internal.logging_tensor',
    'torch.testing._internal.common_utils',
    'torch.testing._internal.common_dtype',
    'torch.testing._internal.common_device_type',
]

# Exclude triton completely
excludedimports = ['triton', 'triton.*']

# Add nnUNet related modules  
hiddenimports += [
    'nnunetv2',
    'dynamic_network_architectures',
    'batchgenerators',
    'acvl_utils',
]

# Add ultralytics modules
hiddenimports += [
    'ultralytics',
    'ultralytics.models',
    'ultralytics.models.yolo',
    'ultralytics.utils',
    'ultralytics.engine',
    'ultralytics.nn',
]

# Exclude tests and development files
excludedimports += [
    'torch.test', 
    'torch.testing',
    'nnunetv2.tests',
    'ultralytics.tests',
]

print(f"Torch hook: collected {len(hiddenimports)} hidden imports")
'''
    torch_hook.write_text(torch_hook_content)
    print("✅ Comprehensive torch hook created")

def clean_previous_builds():
    """Clean previous build artifacts"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"🧹 Cleaned {dir_name}/")
    
    # Clean .pyc files
    for pyc_file in Path('.').rglob('*.pyc'):
        pyc_file.unlink()
    
    print("✅ Previous builds cleaned")

def verify_dependencies():
    """Verify that all required dependencies are available"""
    required_modules = [
        'torch',
        'torchvision', 
        'ultralytics',
        'nnunetv2',
        'xgboost',
        'pydicom',
        'PySide6',
        'numpy',
        'scipy',
        'sklearn',
        'cv2',
        'PIL',
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            missing_modules.append(module)
            print(f"❌ {module} - MISSING")
    
    if missing_modules:
        print(f"\n⚠️  Missing modules: {', '.join(missing_modules)}")
        print("Please install missing dependencies before building")
        return False
    
    print("✅ All dependencies verified")
    return True

def check_model_files():
    """Check if model files exist"""
    model_files = [
        "models/segmentation_2/nnUNet_results/Dataset001_BoneRegion/nnUNetTrainer_50epochs__nnUNetPlans__2d/fold_0/checkpoint_best.pth",
        "models/hotspot_detection/models/model_detection_hs_yolov8.pt",
        "models/classification/model_classification_hs_xgboost_250724.pkl",
        "models/classification/scaler_classification_32features.pkl"
    ]
    
    missing_models = []
    total_size = 0
    
    for model_path in model_files:
        path = Path(model_path)
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            total_size += size_mb
            print(f"✅ {model_path} ({size_mb:.1f} MB)")
        else:
            missing_models.append(model_path)
            print(f"❌ {model_path} - MISSING")
    
    if missing_models:
        print(f"\n⚠️  Missing model files: {len(missing_models)}")
        print("The application may not work properly without these models")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    print(f"✅ Total model size: {total_size:.1f} MB")
    return True

def copy_models_explicitly():
    """Explicitly copy model files to ensure they're included"""
    # ✅ FIXED: Define model_files list in this function
    model_files = [
        "models/hotspot_detection/models/model_detection_hs_yolov8.pt",
        "models/classification/model_classification_hs_xgboost_250724.pkl",
        "models/classification/scaler_classification_32features.pkl", 
        "models/segmentation_2/nnUNet_results/Dataset001_BoneRegion/nnUNetTrainer_50epochs__nnUNetPlans__2d/fold_0/checkpoint_best.pth"
    ]
    
    # Create models directory INSIDE HotspotAnalyzer folder
    dist_models = Path("dist/HotspotAnalyzer/models")
    dist_models.mkdir(parents=True, exist_ok=True)
    
    for model_file in model_files:
        src_path = Path(model_file)
        if src_path.exists():
            # Create destination directory structure INSIDE HotspotAnalyzer
            dest_path = Path("dist/HotspotAnalyzer") / model_file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(src_path, dest_path)
            print(f"✅ Copied model: {model_file}")
        else:
            print(f"❌ Model not found: {model_file}")
    
    print("✅ Model files explicitly copied")

def run_pyinstaller():
    """Run PyInstaller with the spec file"""
    spec_file = "hotspot_analyzer.spec"
    
    if not Path(spec_file).exists():
        print(f"❌ Spec file not found: {spec_file}")
        return False
    
    print(f"🚀 Starting PyInstaller build with {spec_file}")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",           # Clean cache and temporary files
        "--noconfirm",       # Don't ask for confirmation
        "--log-level", "INFO",  # Set log level
        spec_file
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ PyInstaller build completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller build failed with exit code {e.returncode}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        return False

def post_build_cleanup():
    """Cleanup and optimization after build"""
    dist_dir = Path("dist/HotspotAnalyzer")
    
    if not dist_dir.exists():
        print("❌ Build directory not found")
        return False
    
    # Calculate build size
    total_size = 0
    file_count = 0
    
    for file_path in dist_dir.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size
            file_count += 1
    
    size_mb = total_size / (1024 * 1024)
    print(f"📦 Build size: {size_mb:.1f} MB ({file_count:,} files)")
    
    # Optional: Remove debug files for smaller distribution
    debug_patterns = ['*.pdb', '*.debug', '*.map']
    removed_files = 0
    
    for pattern in debug_patterns:
        for debug_file in dist_dir.rglob(pattern):
            debug_file.unlink()
            removed_files = 1
    
    if removed_files > 0:
        print(f"🧹 Removed {removed_files} debug files")
    
    return True

def create_installer_script():
    """Create a simple installer script"""
    installer_content = """
@echo off
echo Installing Hotspot Analyzer...
echo.
echo This will install Hotspot Analyzer to: %PROGRAMFILES%\\HotspotAnalyzer
echo.
pause

if not exist "%PROGRAMFILES%\\HotspotAnalyzer" mkdir "%PROGRAMFILES%\\HotspotAnalyzer"

echo Copying files...
xcopy /E /I /Y "HotspotAnalyzer\\*" "%PROGRAMFILES%\\HotspotAnalyzer\\"

echo Creating desktop shortcut...
powershell "$s=(New-Object -COM WScript.Shell).CreateShortcut('%userprofile%\\Desktop\\Hotspot Analyzer.lnk');$s.TargetPath='%PROGRAMFILES%\\HotspotAnalyzer\\HotspotAnalyzer.exe';$s.Save"

echo.
echo Installation completed!
echo You can run Hotspot Analyzer from the desktop shortcut or from:
echo %PROGRAMFILES%\\HotspotAnalyzer\\HotspotAnalyzer.exe
echo.
pause
"""
    
    installer_path = Path("dist/install.bat")
    with open(installer_path, 'w') as f:
        f.write(installer_content)
    
    print(f"✅ Created installer script: {installer_path}")

def main():
    """Main build process"""
    print("🏗️  Hotspot Analyzer Build Script")
    print("=" * 50)
    
    # Step 1: Setup environment
    setup_environment()
    
    # Step 2: Clean previous builds
    clean_previous_builds()
    create_torch_hooks()
    
    # Step 3: Verify dependencies
    if not verify_dependencies():
        sys.exit(1)
    
    # Step 4: Check model files
    if not check_model_files():
        sys.exit(1)
    # Step 4.5: Create runtime hooks if they don't exist
    hooks_dir = Path("hooks")
    hooks_dir.mkdir(exist_ok=True)

    # Create the early torch hook
    torch_early_hook = hooks_dir / "hook-torch_early.py"
    if not torch_early_hook.exists():
        print("Creating early torch hook...")
        hook_content = '''"""
    Early hook to patch torch BEFORE it loads to prevent triton registration
    """
    import sys
    import types
    import os

    os.environ['TRITON_DISABLE'] = '1'
    os.environ['TORCH_DISABLE_TRITON_LIBRARY'] = '1'

    class MockLibrary:
        def __init__(self, name, kind):
            if name == "triton":
                self.m = None
            else:
                try:
                    import torch._C
                    self.m = torch._C._dispatch_library(name, kind)
                except:
                    self.m = None

    mock_torch = types.ModuleType('torch')
    mock_torch.library = types.ModuleType('torch.library')
    mock_torch.library.Library = MockLibrary
    sys.modules['torch.library'] = mock_torch.library
    '''
        torch_early_hook.write_text(hook_content)
        print("✅ Early torch hook created")

    # Step 5: Run PyInstaller
    if not run_pyinstaller():
        sys.exit(1)
    
    # Step 6: Post-build cleanup
    if not post_build_cleanup():
        sys.exit(1)
    
    # Step 6.5: Copy models explicitly
    copy_models_explicitly()
    
    # Step 7: Create installer
    create_installer_script()
    
    print("\n" + "=" * 50)
    print("🎉 Build completed successfully!")
    print("\nNext steps:")
    print("1. Test the executable: dist/HotspotAnalyzer/HotspotAnalyzer.exe")
    print("2. Run the installer: dist/install.bat")
    print("3. Distribute the dist/HotspotAnalyzer folder")

if __name__ == "__main__":
    main()