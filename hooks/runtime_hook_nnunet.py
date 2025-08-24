#hooks/runtime_hook_nnunet.py
"""
Runtime hook for nnUNet to setup environment and handle trainer classes
"""

import sys
import os
from pathlib import Path

def setup_nnunet_environment():
    """Setup nnUNet environment variables for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        # Set base paths untuk nnUNet
        meipass = Path(sys._MEIPASS)
        exe_dir = Path(sys.executable).parent
        
        # Try to find models directory
        models_dir = None
        for potential_path in [meipass / "models", exe_dir / "models"]:
            if potential_path.exists():
                models_dir = potential_path
                break
        
        if models_dir:
            seg_models = models_dir / "segmentation_2"
            
            # Set nnUNet environment variables
            os.environ["nnUNet_raw"] = str(seg_models / "_nn_raw")
            os.environ["nnUNet_preprocessed"] = str(seg_models / "_nn_pre") 
            os.environ["nnUNet_results"] = str(seg_models / "nnUNet_results")
            
            print(f"[RUNTIME-NNUNET] Set nnUNet paths:")
            print(f"[RUNTIME-NNUNET]   nnUNet_raw: {os.environ['nnUNet_raw']}")
            print(f"[RUNTIME-NNUNET]   nnUNet_preprocessed: {os.environ['nnUNet_preprocessed']}")
            print(f"[RUNTIME-NNUNET]   nnUNet_results: {os.environ['nnUNet_results']}")
        else:
            print("[RUNTIME-NNUNET] ❌ Models directory not found")

def fix_triton_conflicts():
    """Fix triton conflicts that cause _register_fake errors"""
    
    # ✅ CRITICAL: Remove any existing triton modules that might conflict
    triton_modules = [key for key in sys.modules.keys() if key.startswith('triton')]
    for module in triton_modules:
        if 'TritonBlocker' in str(sys.modules[module]):
            print(f"[RUNTIME-NNUNET] Removing conflicting triton module: {module}")
            del sys.modules[module]
    
    # ✅ Set additional triton disable flags
    os.environ.update({
        'TRITON_DISABLE': '1',
        'TORCH_DISABLE_TRITON_LIBRARY': '1',
        'TORCH_COMPILE_DISABLE': '1',
        'TORCH_TRITON_DISABLE': '1',
        'USE_TRITON': '0',
        'TORCH_DISABLE_TRITON_OPS': '1',
        'TORCH_DISABLE_TRITON_REGISTRATION': '1'
    })
    
    print("[RUNTIME-NNUNET] ✅ Triton conflicts resolved")

def preregister_nnunet_trainers():
    """Pre-register nnUNet trainer classes - SIMPLIFIED VERSION"""
    try:
        print("[RUNTIME-NNUNET] Attempting to pre-register nnUNet trainers...")
        
        # ✅ ADD DEBUG: Check multiprocessing state
        import multiprocessing
        print(f"[DEBUG-NNUNET] Current process PID: {os.getpid()}")
        print(f"[DEBUG-NNUNET] Parent PID: {os.getppid()}")
        print(f"[DEBUG-NNUNET] Multiprocessing method: {multiprocessing.get_start_method()}")
        
        # ✅ ADD DEBUG: Check before import
        print("[DEBUG-NNUNET] About to import nnunetv2.training...")
        
        # ✅ WORKAROUND: Instead of importing specific trainers, 
        # just ensure the training module is available
        import nnunetv2.training.nnUNetTrainer.nnUNetTrainer
        
        print("[RUNTIME-NNUNET] ✅ nnUNet training module imported")
        
        # ✅ ADD DEBUG: Success confirmation
        print("[DEBUG-NNUNET] Import successful, continuing...")
        
    except Exception as e:
        print(f"[RUNTIME-NNUNET] Note: Trainer pre-registration failed: {e}")
        print("[RUNTIME-NNUNET] Will attempt dynamic loading during inference")
        # ✅ ADD DEBUG: Exception details
        import traceback
        print(f"[DEBUG-NNUNET] Full traceback: {traceback.format_exc()}")

# Run fixes
if hasattr(sys, '_MEIPASS'):
    setup_nnunet_environment()
    fix_triton_conflicts()
    preregister_nnunet_trainers()