# debug_build.py - Khusus untuk test di PyInstaller build
"""
Debug script yang bisa dijalankan langsung di PyInstaller build
"""

import sys
import os
from pathlib import Path

print("  [DEBUG] PyInstaller Build Analysis")
print("=" * 60)

# Check if PyInstaller mode
if hasattr(sys, '_MEIPASS'):
    print(f"  Running in PyInstaller mode")
    print(f"   _MEIPASS: {sys._MEIPASS}")
    print(f"   executable: {sys.executable}")
else:
    print(" NOT running in PyInstaller mode")
    sys.exit(1)

def debug_torch_library():
    """Debug torch.library specifically"""
    print("\n  [DEBUG] torch.library Analysis:")
    
    if 'torch.library' in sys.modules:
        lib = sys.modules['torch.library']
        print(f"   torch.library exists: {type(lib)}")
        print(f"   torch.library file: {getattr(lib, '__file__', 'N/A')}")
        print(f"   Has register_fake: {hasattr(lib, 'register_fake')}")
        print(f"   Has _register_fake: {hasattr(lib, '_register_fake')}")
        
        # Check if it's a TritonBlocker
        if 'TritonBlocker' in str(type(lib)):
            print("   ⚠️  torch.library IS A TRITONBLOCKER!")
        else:
            print("     torch.library is normal module")
            
        # Check Library class
        if hasattr(lib, 'Library'):
            lib_class = lib.Library
            print(f"   Library class: {lib_class}")
            
            # Try to create instance
            try:
                test_lib = lib_class("test_lib")
                print(f"   Library instance: {type(test_lib)}")
                print(f"   Library has _register_fake: {hasattr(test_lib, '_register_fake')}")
            except Exception as e:
                print(f"    Library instantiation failed: {e}")
        else:
            print("    No Library class found")
    else:
        print("    torch.library not loaded")

def debug_triton_modules():
    """Debug all triton-related modules"""
    print("\n  [DEBUG] Triton Modules Analysis:")
    
    triton_modules = []
    triton_blockers = []
    
    for key, mod in sys.modules.items():
        if 'triton' in key.lower():
            triton_modules.append(key)
            if 'TritonBlocker' in str(type(mod)):
                triton_blockers.append(key)
    
    print(f"   Total triton modules: {len(triton_modules)}")
    print(f"   TritonBlocker modules: {len(triton_blockers)}")
    
    for key in triton_modules:
        mod = sys.modules[key]
        is_blocker = 'TritonBlocker' in str(type(mod))
        status = "⚠️ BLOCKER" if is_blocker else "  Normal"
        print(f"   {key}: {status}")

def test_critical_imports():
    """Test imports that are failing"""
    print("\n  [DEBUG] Critical Import Tests:")
    
    tests = [
        ("torch", "import torch"),
        ("torch.library", "import torch.library"),
        ("torchvision.extension", "import torchvision.extension"),
        ("torchvision._meta_registrations", "import torchvision._meta_registrations"),
        ("torchvision", "import torchvision"),
        ("ultralytics", "from ultralytics import YOLO"),
        ("nnunetv2", "from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor")
    ]
    
    for name, import_cmd in tests:
        try:
            exec(import_cmd)
            print(f"     {name}: SUCCESS")
        except Exception as e:
            print(f"    {name}: {type(e).__name__}: {str(e)[:100]}...")

def show_environment():
    """Show relevant environment variables"""
    print("\n  [DEBUG] Environment Variables:")
    
    relevant_vars = [
        'TRITON_DISABLE', 'TORCH_DISABLE_TRITON_LIBRARY', 'TORCH_COMPILE_DISABLE',
        'TORCH_TRITON_DISABLE', 'USE_TRITON', 'TORCH_LIBRARY_DISABLE'
    ]
    
    for var in relevant_vars:
        value = os.environ.get(var, 'NOT SET')
        print(f"   {var}: {value}")

if __name__ == "__main__":
    try:
        # Run all diagnostics
        debug_torch_library()
        debug_triton_modules()
        show_environment()
        test_critical_imports()
        
        print("\n" + "=" * 60)
        print("  [DEBUG] Analysis complete!")
        
    except Exception as e:
        print(f"\n [ERROR] Debug script failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Keep window open
    input("\nPress Enter to exit...")