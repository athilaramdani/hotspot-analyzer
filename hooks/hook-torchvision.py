"""
PyInstaller hook for torchvision with comprehensive extension support
FIXED VERSION - handles missing extensions gracefully
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files
import os
import sys

print("[HOOK] torchvision: Starting comprehensive collection...")

# Collect ALL torchvision modules including extensions
try:
    datas, binaries, hiddenimports = collect_all('torchvision')
    print(f"[HOOK] torchvision: base collection successful")
except Exception as e:
    print(f"[HOOK] torchvision: base collection failed: {e}")
    datas, binaries, hiddenimports = [], [], []

# Core torchvision modules that should always be included
core_modules = [
    'torchvision.transforms',
    'torchvision.transforms.functional', 
    'torchvision.transforms._transforms_video',
    'torchvision.models',
    'torchvision.utils',
    'torchvision.datasets',
    'torchvision.io',
    'torchvision.ops',
]

# Extension modules - try to include but don't fail if missing
extension_modules = [
    'torchvision.extension',
    'torchvision._extension',
    'torchvision.ops._extension',
    'torchvision.ops._register_ops',
    'torchvision._C',
]

# Add core modules
for module in core_modules:
    if module not in hiddenimports:
        hiddenimports.append(module)

# Try to add extension modules - but handle failures gracefully
extensions_found = []
for module in extension_modules:
    try:
        # Test if module can be imported
        __import__(module)
        if module not in hiddenimports:
            hiddenimports.append(module)
        extensions_found.append(module)
        print(f"[HOOK] torchvision: ✅ Found extension: {module}")
    except ImportError:
        print(f"[HOOK] torchvision: ⚠️ Extension not available: {module}")
    except Exception as e:
        print(f"[HOOK] torchvision: ❌ Error testing {module}: {e}")

# Collect torchvision binary files (DLLs, shared libraries)
try:
    import torchvision
    tv_path = os.path.dirname(torchvision.__file__)
    
    # Add extension DLLs and shared libraries
    extension_files = []
    binary_extensions = ('.dll', '.so', '.dylib', '.pyd', '.so.*')
    
    for root, dirs, files in os.walk(tv_path):
        for file in files:
            if any(file.endswith(ext) for ext in binary_extensions):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, tv_path)
                dest_dir = f'torchvision/{os.path.dirname(rel_path)}'.replace('\\', '/')
                
                # Clean up destination directory path
                if dest_dir.endswith('/'):
                    dest_dir = dest_dir[:-1]
                if dest_dir == 'torchvision/':
                    dest_dir = 'torchvision'
                
                extension_files.append((src_path, dest_dir))
                
    datas.extend(extension_files)
    print(f"[HOOK] torchvision: ✅ Found {len(extension_files)} binary extension files")
    
    # Log some example extension files for debugging
    for i, (src, dest) in enumerate(extension_files[:3]):
        print(f"[HOOK] torchvision: Extension file {i+1}: {os.path.basename(src)} -> {dest}")
    
except Exception as e:
    print(f"[HOOK] torchvision: ⚠️ Binary collection failed: {e}")

# Try to collect additional data files that might be needed
try:
    # Collect any additional data files from torchvision
    additional_datas = collect_data_files('torchvision', include_py_files=False)
    datas.extend(additional_datas)
    print(f"[HOOK] torchvision: ✅ Found {len(additional_datas)} additional data files")
except Exception as e:
    print(f"[HOOK] torchvision: ⚠️ Additional data collection failed: {e}")

# Special handling for torchvision.ops which often contains extensions
try:
    ops_modules = collect_submodules('torchvision.ops')
    for module in ops_modules:
        if module not in hiddenimports:
            hiddenimports.append(module)
    print(f"[HOOK] torchvision: ✅ Collected {len(ops_modules)} ops modules")
except Exception as e:
    print(f"[HOOK] torchvision: ⚠️ Ops modules collection failed: {e}")

# Remove duplicates from hiddenimports
hiddenimports = list(set(hiddenimports))

# Final summary
print(f"[HOOK] torchvision: FINAL SUMMARY:")
print(f"[HOOK] torchvision:   - {len(hiddenimports)} hidden imports")
print(f"[HOOK] torchvision:   - {len(datas)} data files") 
print(f"[HOOK] torchvision:   - {len(binaries)} binaries")
print(f"[HOOK] torchvision:   - {len(extensions_found)} extensions found: {extensions_found}")

# Export for PyInstaller
excludedimports = [
    # Don't exclude anything - let PyInstaller handle unused modules
]