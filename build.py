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
    
    # CRITICAL: Disable triton completely
    os.environ['TRITON_DISABLE'] = '1'
    os.environ['TORCH_TRITON_DISABLE'] = '1'
    os.environ['USE_TRITON'] = '0'
    
    # NEW: Completely disable triton to prevent library registration conflicts
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
    
    # ADD: Additional environment variables for nnUNet compatibility
    os.environ['TORCH_FX_DISABLE'] = '1'
    os.environ['NNUNET_DISABLE_COMPILE'] = '1'
    
    logging.info("Environment configured with torch._dynamo disabled")

def create_torch_hooks():
    """Create comprehensive torch hooks for PyInstaller"""
    hooks_dir = Path("hooks")
    hooks_dir.mkdir(exist_ok=True)
    
    # Create comprehensive torch hook
    torch_hook = hooks_dir / "hook-torch.py"
    torch_hook_content = '''
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Kumpulkan semua resource utama dari torch
datas, binaries, hiddenimports = collect_all('torch')

# Pastikan torch.testing (termasuk _comparison) ikut ter-bundle
try:
    hiddenimports += collect_submodules('torch.testing')
except Exception:
    pass

# (opsional) functorch kadang lazy-load; aman untuk ikutkan submodules-nya
try:
    hiddenimports += collect_submodules('torch._functorch')
except Exception:
    pass

# Exclude triton sepenuhnya
excludedimports = ['triton', 'triton.*']

# Tambahan modul terkait nnUNet
hiddenimports += [
    'nnunetv2',
    'dynamic_network_architectures',
    'batchgenerators',
    'acvl_utils',
]

# Tambahan modul ultralytics/YOLO
hiddenimports += [
    'ultralytics',
    'ultralytics.models',
    'ultralytics.models.yolo',
    'ultralytics.utils',
    'ultralytics.engine',
    'ultralytics.nn',
]

# Exclude paket test (JANGAN exclude torch.testing)
excludedimports += [
    'torch.test',
    'nnunetv2.tests',
    'ultralytics.tests',
]

logging.info(f"Torch hook: collected {len(hiddenimports)} hidden imports, {len(datas)} datas, {len(binaries)} binaries")
'''
    torch_hook.write_text(torch_hook_content)
    logging.info("  Comprehensive torch hook created")

def clean_previous_builds():
    """Clean previous build artifacts"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            logging.info(f"🧹 Cleaned {dir_name}/")
    
    # Clean .pyc files
    for pyc_file in Path('.').rglob('*.pyc'):
        pyc_file.unlink()
    
    logging.info("  Previous builds cleaned")

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
            logging.info(f" {module}")
        except ImportError:
            missing_modules.append(module)
            logging.info(f" {module} - MISSING")
    
    if missing_modules:
        logging.info(f"\n  Missing modules: {', '.join(missing_modules)}")
        logging.info("Please install missing dependencies before building")
        return False
    
    logging.info("All dependencies verified")
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
            logging.info(f"  {model_path} ({size_mb:.1f} MB)")
        else:
            missing_models.append(model_path)
            logging.info(f" {model_path} - MISSING")
    
    if missing_models:
        logging.info(f"\n⚠️  Missing model files: {len(missing_models)}")
        logging.info("The application may not work properly without these models")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    logging.info(f"  Total model size: {total_size:.1f} MB")
    return True

def copy_models_explicitly():
    """Explicitly copy model files to ensure they're included - COMPLETE nnUNet structure"""
    
    #   NEW: Copy entire directories for nnUNet
    nnunet_dirs_to_copy = [
        "models/segmentation_2/nnUNet_results/Dataset001_BoneRegion"
    ]
    
    for dir_path in nnunet_dirs_to_copy:
        src_dir = Path(dir_path)
        if src_dir.exists():
            dest_dir = Path("dist/HotspotAnalyzer") / dir_path
            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy entire directory structure
            import shutil
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)
            logging.info(f"  Copied entire directory: {dir_path}")
        else:
            logging.info(f" Directory not found: {dir_path}")
    
    #   IMPROVED: Individual critical files
    model_files = [
        "models/hotspot_detection/models/model_detection_hs_yolov8.pt",
        "models/classification/model_classification_hs_xgboost_250724.pkl",
        "models/classification/scaler_classification_32features.pkl"
    ]
    
    #   NEW: Verify nnUNet files after directory copy
    nnunet_verification_files = [
        "models/segmentation_2/nnUNet_results/Dataset001_BoneRegion/dataset.json",
        "models/segmentation_2/nnUNet_results/Dataset001_BoneRegion/nnUNetTrainer_50epochs__nnUNetPlans__2d/dataset.json",
        "models/segmentation_2/nnUNet_results/Dataset001_BoneRegion/nnUNetTrainer_50epochs__nnUNetPlans__2d/plans.json",
        "models/segmentation_2/nnUNet_results/Dataset001_BoneRegion/nnUNetTrainer_50epochs__nnUNetPlans__2d/fold_0/checkpoint_best.pth",
        "models/segmentation_2/nnUNet_results/Dataset001_BoneRegion/nnUNetTrainer_50epochs__nnUNetPlans__2d/fold_0/checkpoint_final.pth"
    ]
    
    logging.info("\n  Verifying nnUNet files in build:")
    for verification_file in nnunet_verification_files:
        build_file_path = Path("dist/HotspotAnalyzer") / verification_file
        src_file_path = Path(verification_file)
        
        if build_file_path.exists():
            size_mb = build_file_path.stat().st_size / (1024 * 1024)
            logging.info(f"  {verification_file} ({size_mb:.1f} MB)")
        elif src_file_path.exists():
            # File exists in source but not in build - copy it explicitly
            build_file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file_path, build_file_path)
            size_mb = build_file_path.stat().st_size / (1024 * 1024)
            logging.info(f"  Copied missing file: {verification_file} ({size_mb:.1f} MB)")
        else:
            logging.info(f" Missing: {verification_file}")
    
    # Copy individual model files
    for model_file in model_files:
        src_path = Path(model_file)
        if src_path.exists():
            dest_path = Path("dist/HotspotAnalyzer") / model_file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(src_path, dest_path)
            logging.info(f"  Copied model: {model_file}")
        else:
            logging.info(f" Model not found: {model_file}")
    
    logging.info("  Model files explicitly copied with complete nnUNet structure")

def verify_nnunet_structure():
    """NEW: Verify complete nnUNet structure exists"""
    logging.info("\nVerifying complete nnUNet structure...")
    
    base_path = Path("dist/HotspotAnalyzer/models/segmentation_2/nnUNet_results/Dataset001_BoneRegion")
    
    required_structure = {
        "dataset.json": "Dataset configuration",
        "nnUNetTrainer_50epochs__nnUNetPlans__2d/dataset.json": "Training dataset config", 
        "nnUNetTrainer_50epochs__nnUNetPlans__2d/plans.json": "Training plans",
        "nnUNetTrainer_50epochs__nnUNetPlans__2d/fold_0/checkpoint_best.pth": "Best model checkpoint",
        "nnUNetTrainer_50epochs__nnUNetPlans__2d/fold_0/checkpoint_final.pth": "Final model checkpoint"
    }
    
    missing_files = []
    total_size = 0
    
    for rel_path, description in required_structure.items():
        full_path = base_path / rel_path
        if full_path.exists():
            size_mb = full_path.stat().st_size / (1024 * 1024)
            total_size += size_mb
            logging.info(f"  {description}: {rel_path} ({size_mb:.1f} MB)")
        else:
            missing_files.append((rel_path, description))
            logging.info(f" {description}: {rel_path}")
    
    if missing_files:
        logging.info(f"\n⚠️  Missing {len(missing_files)} critical nnUNet files:")
        for rel_path, description in missing_files:
            logging.info(f"   - {description}: {rel_path}")
        return False
    else:
        logging.info(f"\n  All nnUNet files present (Total: {total_size:.1f} MB)")
        return True

def run_pyinstaller():
    """Run PyInstaller with the spec file"""
    spec_file = "hotspot_analyzer.spec"
    
    if not Path(spec_file).exists():
        logging.info(f" Spec file not found: {spec_file}")
        return False
    
    logging.info(f"🚀 Starting PyInstaller build with {spec_file}")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",           # Clean cache and temporary files
        "--noconfirm",       # Don't ask for confirmation
        "--log-level", "INFO",  # Set log level
        spec_file
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logging.info("  PyInstaller build completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logging.info(f" PyInstaller build failed with exit code {e.returncode}")
        logging.info(f"STDOUT:\n{e.stdout}")
        logging.info(f"STDERR:\n{e.stderr}")
        return False

def post_build_cleanup():
    """Cleanup and optimization after build"""
    dist_dir = Path("dist/HotspotAnalyzer")
    
    if not dist_dir.exists():
        logging.info(" Build directory not found")
        return False
    
    # Calculate build size
    total_size = 0
    file_count = 0
    
    for file_path in dist_dir.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size
            file_count += 1
    
    size_mb = total_size / (1024 * 1024)
    logging.info(f"📦 Build size: {size_mb:.1f} MB ({file_count:,} files)")
    
    # Optional: Remove debug files for smaller distribution
    debug_patterns = ['*.pdb', '*.debug', '*.map']
    removed_files = 0
    
    for pattern in debug_patterns:
        for debug_file in dist_dir.rglob(pattern):
            debug_file.unlink()
            removed_files = 1
    
    if removed_files > 0:
        logging.info(f"🧹 Removed {removed_files} debug files")
    
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
    
    logging.info(f"  Created installer script: {installer_path}")

def main():
    """Main build process"""
    logging.info("🏗️  Hotspot Analyzer Build Script")
    logging.info("=" * 50)
    
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
    # Step 4.5: Ensure hooks directory exists
    hooks_dir = Path("hooks")
    hooks_dir.mkdir(exist_ok=True)
    logging.info("  Hooks directory ready")

    # Step 5: Run PyInstaller
    if not run_pyinstaller():
        sys.exit(1)
    
    # Step 6: Post-build cleanup
    if not post_build_cleanup():
        sys.exit(1)
    
    # Step 6.5: Copy models explicitly
    copy_models_explicitly()
    
    if not verify_nnunet_structure():
        logging.info("⚠️  nnUNet structure incomplete - segmentation may not work")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Step 7: Create installer
    create_installer_script()
    
    logging.info("\n" + "=" * 50)
    logging.info("🎉 Build completed successfully!")
    logging.info("\nNext steps:")
    logging.info("1. Test the executable: dist/HotspotAnalyzer/HotspotAnalyzer.exe")
    logging.info("2. Run the installer: dist/install.bat")
    logging.info("3. Distribute the dist/HotspotAnalyzer folder")

if __name__ == "__main__":
    main()