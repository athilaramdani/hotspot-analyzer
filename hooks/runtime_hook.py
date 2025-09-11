"""
Runtime hook for PyInstaller - Applied during executable execution
Simple environment setup only
"""
import sys
import os
import logging
def setup_runtime_environment():
    """Setup environment at runtime - SIMPLE VERSION"""
    if hasattr(sys, '_MEIPASS'):
        # Hanya set environment variables, jangan ganggu imports
        env_vars = {
            'TRITON_DISABLE': '1',
            'TORCH_DISABLE_TRITON_LIBRARY': '1', 
            'TORCH_COMPILE_DISABLE': '1',
            'TORCH_JIT': '0',
        }
        
        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[key] = value
        
        logging.info("[RUNTIME] PyInstaller environment configured")

# Run setup
setup_runtime_environment()