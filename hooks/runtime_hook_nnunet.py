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
            print("[RUNTIME-NNUNET]  Models directory not found")

def fix_triton_conflicts():
    """Fix triton conflicts that cause _register_fake errors"""
    
    #   CRITICAL: Remove any existing triton modules that might conflict
    triton_modules = [key for key in sys.modules.keys() if key.startswith('triton')]
    for module in triton_modules:
        if 'TritonBlocker' in str(sys.modules[module]):
            print(f"[RUNTIME-NNUNET] Removing conflicting triton module: {module}")
            del sys.modules[module]
    
    #   Set additional triton disable flags
    os.environ.update({
        'TRITON_DISABLE': '1',
        'TORCH_DISABLE_TRITON_LIBRARY': '1',
        'TORCH_COMPILE_DISABLE': '1',
        'TORCH_TRITON_DISABLE': '1',
        'USE_TRITON': '0',
        'TORCH_DISABLE_TRITON_OPS': '1',
        'TORCH_DISABLE_TRITON_REGISTRATION': '1'
    })
    
    print("[RUNTIME-NNUNET]   Triton conflicts resolved")

def preregister_nnunet_trainers():
    """BYPASS nnUNet trainer pre-registration to prevent loops"""
    try:
        print("[RUNTIME-NNUNET] Attempting to pre-register nnUNet trainers...")
        print(f"[DEBUG-NNUNET] Current process PID: {os.getpid()}")
        print(f"[DEBUG-NNUNET] Parent PID: {os.getppid()}")
        
        #   CHECK: Skip in spawned processes
        if len(sys.argv) > 1 and '--multiprocessing-fork' in sys.argv:
            print("[DEBUG-NNUNET] Skipping nnUNet import in multiprocessing fork")
            return
        
        #   CHECK: Skip if already spawned process detected
        current_pid = os.getpid()
        parent_pid = os.getppid() 
        if current_pid != parent_pid and parent_pid > 0:
            print(f"[DEBUG-NNUNET] Skipping nnUNet import in spawned process (PID: {current_pid})")
            return
        
        print("[DEBUG-NNUNET] About to import nnunetv2.training...")
        
        #   SAFE IMPORT: Add timeout protection
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError("nnUNet import timeout")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10 second timeout
        
        try:
            import nnunetv2.training.nnUNetTrainer.nnUNetTrainer
            print("[RUNTIME-NNUNET]   nnUNet training module imported")
        finally:
            signal.alarm(0)  # Cancel timeout
        
    except TimeoutError:
        print("[RUNTIME-NNUNET] ⚠️ nnUNet import timeout - skipping for safety")
    except Exception as e:
        print(f"[RUNTIME-NNUNET] Note: Trainer pre-registration failed: {e}")
        print("[RUNTIME-NNUNET] Will attempt dynamic loading during inference")

# Run fixes
if hasattr(sys, '_MEIPASS'):
    setup_nnunet_environment()
    fix_triton_conflicts()
    preregister_nnunet_trainers()