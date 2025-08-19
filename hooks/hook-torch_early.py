# hooks/hook-torch_early.py
"""
Runtime hook to fix torch import issues in PyInstaller
"""
import sys
import os

# Set environment variables
os.environ['TRITON_DISABLE'] = '1'
os.environ['TORCH_DISABLE_TRITON_LIBRARY'] = '1'
os.environ['TORCH_JIT'] = '0'
os.environ['TORCH_LOGS'] = ''

# Import torch properly to ensure all submodules are available
try:
    # Import torch first to initialize the package properly
    import torch
    print("[HOOK-EARLY] Torch imported successfully")
    
    # Ensure critical submodules are imported
    import torch.nn
    import torch._C
    import torch._ops
    print("[HOOK-EARLY] Torch submodules imported successfully")
    
except ImportError as e:
    print(f"[HOOK-EARLY] Warning: Could not import torch: {e}")

print("[HOOK-EARLY] Runtime hook completed")