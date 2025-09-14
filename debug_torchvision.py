# debug_torchvision.py
"""
Debug script untuk analyze torchvision circular import di PyInstaller
"""

import sys
import os
from pathlib import Path

def debug_torch_modules():
    """Debug torch modules yang sudah ter-load"""
    logging.info("  [DEBUG] Torch modules currently loaded:")
    torch_modules = [k for k in sys.modules.keys() if 'torch' in k.lower()]
    
    for module in sorted(torch_modules):
        mod = sys.modules[module]
        mod_type = type(mod).__name__
        logging.info(f"  {module}: {mod_type}")
        
        # Check for TritonBlocker
        if 'TritonBlocker' in str(type(mod)):
            logging.info(f"    ⚠️  TRITON BLOCKER DETECTED: {module}")
        
        # Check for torch.library
        if hasattr(mod, '_register_fake'):
            logging.info(f"      Has _register_fake: {module}")
        elif 'library' in module and hasattr(mod, 'register_fake'):
            logging.info(f"      Has register_fake: {module}")

def debug_import_sequence():
    """Debug import sequence untuk find circular import"""
    logging.info("\n  [DEBUG] Testing critical imports...")
    
    try:
        logging.info("1. Testing torch.library import...")
        import torch.library
        logging.info(f"   torch.library type: {type(torch.library)}")
        logging.info(f"   torch.library._register_fake: {hasattr(torch.library, '_register_fake')}")
        logging.info(f"   torch.library.register_fake: {hasattr(torch.library, 'register_fake')}")
    except Exception as e:
        logging.info(f"    torch.library import failed: {e}")
    
    try:
        logging.info("2. Testing torchvision.extension import...")
        import torchvision.extension
        logging.info(f"   torchvision.extension: {torchvision.extension}")
    except Exception as e:
        logging.info(f"    torchvision.extension import failed: {e}")
    
    try:
        logging.info("3. Testing torchvision._meta_registrations import...")
        import torchvision._meta_registrations
        logging.info(f"   torchvision._meta_registrations: SUCCESS")
    except Exception as e:
        logging.info(f"    torchvision._meta_registrations import failed: {e}")

def debug_triton_blockers():
    """Find all TritonBlocker instances"""
    logging.info("\n  [DEBUG] Searching for TritonBlocker instances...")
    
    triton_modules = []
    for key, mod in sys.modules.items():
        if 'triton' in key.lower() or 'TritonBlocker' in str(type(mod)):
            triton_modules.append((key, type(mod).__name__, str(mod)))
    
    for key, mod_type, mod_str in triton_modules:
        logging.info(f"  {key}: {mod_type}")
        if 'TritonBlocker' in mod_str:
            logging.info(f"    ⚠️  CONTAINS TRITONBLOCKER")

if __name__ == "__main__":
    logging.info("  [DEBUG] PyInstaller TorchVision Debug Analysis")
    logging.info("=" * 60)
    
    if hasattr(sys, '_MEIPASS'):
        logging.info(f"Running in PyInstaller mode: {sys._MEIPASS}")
    else:
        logging.info("Running in development mode")
    
    debug_torch_modules()
    debug_import_sequence() 
    debug_triton_blockers()