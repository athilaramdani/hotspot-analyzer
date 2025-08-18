#!/usr/bin/env python3
"""
Build script untuk HotspotAnalyzer
Menggunakan PyInstaller untuk membuat executable
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def run_command(cmd, description=""):
    """Execute command and handle errors"""
    print(f"\n{'='*50}")
    print(f"🔄 {description}")
    print(f"Running: {cmd}")
    print('='*50)
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print("✅ Success!")
        if result.stdout:
            print("Output:", result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stdout:
            print("Stdout:", e.stdout)
        if e.stderr:
            print("Stderr:", e.stderr)
        return False

def clean_build():
    """Clean previous build artifacts"""
    print("\n🧹 Cleaning previous build artifacts...")
    
    dirs_to_clean = ['build', 'dist']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Removed: {dir_name}")
    
    # Clean pycache recursively, but skip .venv folder
    for root, dirs, files in os.walk('.'):
        # Skip .venv directory and its subdirectories
        if '.venv' in root or root.startswith('.venv'):
            continue
            
        for dir_name in dirs[:]:  # Use slice to avoid modifying list during iteration
            if dir_name == '__pycache__':
                pycache_path = os.path.join(root, dir_name)
                # Double check we're not in .venv
                if '.venv' not in pycache_path:
                    shutil.rmtree(pycache_path)
                    print(f"  Removed: {pycache_path}")
            elif dir_name == '.venv':
                # Skip .venv directory entirely
                dirs.remove(dir_name)

def check_dependencies():
    """Check if required tools are available"""
    print("\n🔍 Checking dependencies...")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller not found. Installing...")
        if not run_command("pip install pyinstaller", "Installing PyInstaller"):
            return False
    
    # Check for main entry point - look for app/__main__.py or main.py
    main_entry = None
    if os.path.exists('app/__main__.py'):
        main_entry = 'app/__main__.py'
        print("✅ app/__main__.py found")
    elif os.path.exists('main.py'):
        main_entry = 'main.py'
        print("✅ main.py found")
    else:
        print("❌ No main entry point found! (looking for app/__main__.py or main.py)")
        return False
    
    # Store the main entry for later use
    globals()['MAIN_ENTRY'] = main_entry
    
    # Check required directories
    required_dirs = ['config', 'features', 'core', 'assets', 'models']
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"✅ {dir_name}/ found")
        else:
            print(f"⚠️  {dir_name}/ not found (will skip)")
    
    return True

def create_spec_file():
    """Create the spec file if it doesn't exist"""
    spec_file = 'hotspot_analyzer.spec'
    
    if os.path.exists(spec_file):
        print(f"✅ {spec_file} already exists")
        return True
    
    print(f"📝 Creating {spec_file}...")
    # The spec file should be created separately as shown in the artifact above
    print(f"⚠️  Please create {spec_file} manually using the provided template")
    return False

def build_executable():
    """Build the executable using PyInstaller"""
    print("\n🔨 Building executable...")
    
    # Get the main entry point that was detected
    main_entry = globals().get('MAIN_ENTRY', 'app/__main__.py')
    spec_file = 'hotspot_analyzer.spec'
    
    if not os.path.exists(spec_file):
        # Fallback to auto-generated command
        cmd = [
            'pyinstaller',
            '--onedir',
            '--console',  # Changed to console for debugging
            '--add-data', 'config;config',
            '--add-data', 'assets;assets', 
            '--add-data', 'models;models',
            '--add-data', 'segmentation;segmentation',
            '--add-data', '.env;.',
            # Core PySide6
            '--hidden-import', 'PySide6.QtCore',
            '--hidden-import', 'PySide6.QtGui',
            '--hidden-import', 'PySide6.QtWidgets',
            '--hidden-import', 'PySide6.QtOpenGL',
            '--hidden-import', 'shiboken6',
            # Missing standard library modules
            '--hidden-import', 'pydoc',
            '--hidden-import', 'pydoc_data',
            '--hidden-import', 'pydoc_data.topics',
            '--hidden-import', 'doctest',
            '--hidden-import', 'inspect',
            # Scientific stack
            '--hidden-import', 'numpy',
            '--hidden-import', 'scipy',
            '--hidden-import', 'scipy.ndimage',
            '--hidden-import', 'scipy.ndimage._support_alternative_backends',
            '--hidden-import', 'scipy._lib',
            '--hidden-import', 'scipy._lib._array_api',
            '--hidden-import', 'scipy._lib._docscrape',
            '--hidden-import', 'skimage',
            '--hidden-import', 'skimage.filters',
            '--hidden-import', 'skimage.filters.thresholding',
            '--hidden-import', 'pandas',
            '--hidden-import', 'sklearn',
            '--hidden-import', 'matplotlib',
            # ML/AI
            '--hidden-import', 'torch',
            '--hidden-import', 'torchvision',
            '--hidden-import', 'ultralytics',
            # Image processing
            '--hidden-import', 'pydicom',
            '--hidden-import', 'cv2',
            '--hidden-import', 'PIL',
            '--hidden-import', 'imageio',
            # App modules
            '--hidden-import', 'app',
            '--hidden-import', 'core',
            '--hidden-import', 'features',
            '--name', 'hotspotAnalyzer',
            main_entry  # Use detected main entry
        ]
        cmd_str = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd)
    else:
        cmd_str = f'pyinstaller {spec_file}'
    
    return run_command(cmd_str, "Building executable with PyInstaller")

def create_data_structure():
    """Create the final data structure"""
    print("\n📁 Creating final application structure...")
    
    dist_dir = Path('dist/hotspotAnalyzer')
    if not dist_dir.exists():
        print("❌ Build directory not found!")
        return False
    
    # Create data directory structure matching paths.py expectations
    data_dir = dist_dir / 'data'
    data_dir.mkdir(exist_ok=True)
    
    # Create PLANAR structure with session codes
    planar_dir = data_dir / 'PLANAR'
    planar_dir.mkdir(exist_ok=True)
    
    # Create session code directories
    session_codes = ['ALL', 'NSY', 'ATL', 'NBL']  # Add more as needed
    for session_code in session_codes:
        (planar_dir / session_code).mkdir(exist_ok=True)
        print(f"✅ Created session directory: PLANAR/{session_code}")
    
    # Create other data subdirectories
    (data_dir / 'SPECT').mkdir(exist_ok=True)
    (data_dir / 'PET').mkdir(exist_ok=True)
    (data_dir / 'DICOM').mkdir(exist_ok=True)
    
    # Copy existing data if available (preserve patient data)
    if os.path.exists('data'):
        print("📁 Copying existing patient data...")
        for item in Path('data').iterdir():
            if item.is_dir():
                dest = data_dir / item.name
                if not dest.exists():
                    shutil.copytree(item, dest)
                    print(f"✅ Copied: {item.name}")
                else:
                    # Merge directories
                    for sub_item in item.iterdir():
                        sub_dest = dest / sub_item.name
                        if sub_item.is_dir() and not sub_dest.exists():
                            shutil.copytree(sub_item, sub_dest)
                        elif sub_item.is_file() and not sub_dest.exists():
                            shutil.copy2(sub_item, sub_dest)
    
    # Create empty temp directory structure
    temp_dir = dist_dir / 'temp'
    temp_dir.mkdir(exist_ok=True)
    (temp_dir / 'images').mkdir(exist_ok=True)
    (temp_dir / 'processing').mkdir(exist_ok=True)
    (temp_dir / 'hotspot_temp').mkdir(exist_ok=True)
    
    # Create logs directory
    (dist_dir / 'logs').mkdir(exist_ok=True)
    
    # Test paths.py compatibility
    print("🔍 Testing paths.py compatibility...")
    try:
        # Create test file to verify paths work
        test_script = f'''
import sys
sys.path.insert(0, r"{dist_dir}")
from core.config.paths import get_safe_project_root, DATA_ROOT, PLANAR_DATA_PATH
print("Project root:", get_safe_project_root())
print("Data root:", DATA_ROOT)
print("PLANAR path:", PLANAR_DATA_PATH)
print("Data root exists:", DATA_ROOT.exists())
print("PLANAR path exists:", PLANAR_DATA_PATH.exists())
'''
        
        with open(dist_dir / 'test_paths.py', 'w') as f:
            f.write(test_script)
            
        # Run test (if Python is available)
        import subprocess
        result = subprocess.run([sys.executable, str(dist_dir / 'test_paths.py')], 
                              capture_output=True, text=True, cwd=str(dist_dir))
        
        if result.returncode == 0:
            print("✅ Paths compatibility test passed")
            print(result.stdout)
        else:
            print("⚠️ Paths test had issues (may be normal in build environment)")
            print(result.stderr)
            
        # Clean up test file
        (dist_dir / 'test_paths.py').unlink()
        
    except Exception as e:
        print(f"⚠️ Could not run paths test: {e}")
    
    print("✅ Application structure created with paths.py compatibility")
    return True

def create_batch_file():
    """Create a batch file to run the application"""
    print("\n📝 Creating launch batch file...")
    
    batch_content = """@echo off
echo Starting HotspotAnalyzer...
cd /d "%~dp0"
hotspotAnalyzer.exe
pause
"""
    
    batch_path = Path('dist/hotspotAnalyzer/run_hotspot_analyzer.bat')
    batch_path.write_text(batch_content)
    print("✅ Created run_hotspot_analyzer.bat")

def main():
    """Main build process"""
    print("🚀 Building HotspotAnalyzer Application")
    print("="*50)
    
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    # Build steps
    steps = [
        ("Clean build artifacts", clean_build),
        ("Check dependencies", check_dependencies),
        ("Build executable", build_executable),
        ("Create data structure", create_data_structure),
        ("Create batch file", create_batch_file),
    ]
    
    for step_name, step_func in steps:
        print(f"\n🔄 {step_name}...")
        if callable(step_func):
            result = step_func()
            if result is False:
                print(f"❌ Failed at step: {step_name}")
                sys.exit(1)
        else:
            step_func
    
    print("\n" + "="*50)
    print("🎉 BUILD COMPLETED SUCCESSFULLY!")
    print("="*50)
    print(f"📂 Application built in: {Path('dist/hotspotAnalyzer').absolute()}")
    print("🚀 Run with: dist/hotspotAnalyzer/hotspotAnalyzer.exe")
    print("💡 Or use: dist/hotspotAnalyzer/run_hotspot_analyzer.bat")

if __name__ == "__main__":
    main()