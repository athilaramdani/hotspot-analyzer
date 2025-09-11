# hooks/hook-triton.py
"""
Hook to completely disable triton imports in PyInstaller
This hook runs BEFORE torch and ensures triton is blocked completely
"""

import sys
import types
import logging
# Create comprehensive dummy triton structure
triton_dummy = types.ModuleType('triton')
triton_language = types.ModuleType('triton.language')
triton_compiler = types.ModuleType('triton.compiler')
triton_runtime = types.ModuleType('triton.runtime')
triton_ops = types.ModuleType('triton.ops')
triton_testing = types.ModuleType('triton.testing')
triton_backends = types.ModuleType('triton.backends')
triton_c = types.ModuleType('triton._C')

# Register ALL possible triton modules as dummies
sys.modules['triton'] = triton_dummy
sys.modules['triton.language'] = triton_language
sys.modules['triton.compiler'] = triton_compiler
sys.modules['triton.runtime'] = triton_runtime
sys.modules['triton.ops'] = triton_ops
sys.modules['triton.testing'] = triton_testing
sys.modules['triton.backends'] = triton_backends
sys.modules['triton._C'] = triton_c

# Completely exclude triton to prevent conflicts
excludedimports = [
    'triton',
    'triton.language', 
    'triton.compiler',
    'triton.runtime',
    'triton.ops',
    'triton.testing',
    'triton.backends',
    'triton._C',
    'triton.backends.cuda',
    'triton.backends.driver',
]

logging.info("[HOOK] Triton modules completely blocked and excluded")
logging.info(f"[HOOK] Registered {len(sys.modules)} triton dummy modules")