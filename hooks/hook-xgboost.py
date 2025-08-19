"""
PyInstaller hook for XGBoost to include native libraries and VERSION file
"""
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
import os

# Collect XGBoost dynamic libraries
binaries = collect_dynamic_libs('xgboost')

# Collect XGBoost data files including VERSION
datas = collect_data_files('xgboost', include_py_files=False)

# Additional manual collection for XGBoost files
try:
    import xgboost
    xgb_path = os.path.dirname(xgboost.__file__)
    
    # Collect VERSION file
    version_file = os.path.join(xgb_path, 'VERSION')
    if os.path.exists(version_file):
        datas.append((version_file, 'xgboost'))
        print(f"[HOOK-XGBOOST] Found VERSION file: {version_file}")
    else:
        # Create dummy VERSION file if not found
        print("[HOOK-XGBOOST] VERSION file not found, will create dummy")
    
    # Look for xgboost.dll in common locations
    potential_dll_paths = [
        os.path.join(xgb_path, 'lib', 'xgboost.dll'),
        os.path.join(xgb_path, '..', 'Library', 'bin', 'xgboost.dll'),
        os.path.join(xgb_path, '..', 'Library', 'lib', 'xgboost.dll'),
    ]
    
    for dll_path in potential_dll_paths:
        if os.path.exists(dll_path):
            binaries.append((dll_path, 'lib'))
            binaries.append((dll_path, 'xgboost/lib'))
            print(f"[HOOK-XGBOOST] Found XGBoost DLL: {dll_path}")
            break
    else:
        print("[HOOK-XGBOOST] XGBoost DLL not found in common locations")
        
except Exception as e:
    print(f"[HOOK-XGBOOST] Error collecting XGBoost files: {e}")

print(f"[HOOK-XGBOOST] Collected {len(binaries)} binaries and {len(datas)} data files")