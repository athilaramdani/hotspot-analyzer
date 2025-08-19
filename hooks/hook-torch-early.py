# hooks/hook-torch_early.py
"""
Early runtime hook to fix torch circular import issues
This must run BEFORE torch is imported
"""
import sys
import types
import os

# Set environment variables
os.environ['TRITON_DISABLE'] = '1'
os.environ['TORCH_DISABLE_TRITON_LIBRARY'] = '1'
os.environ['TORCH_JIT'] = '0'

# Pre-create torch._ops to prevent circular import
torch_module = types.ModuleType('torch')
torch_ops = types.ModuleType('torch._ops')
torch_ops.OpOverload = type('OpOverload', (), {})  # Dummy class

# Pre-register modules
sys.modules['torch'] = torch_module
sys.modules['torch._ops'] = torch_ops
torch_module._ops = torch_ops

# Create mock library to prevent triton registration
class MockLibrary:
    def __init__(self, name, kind):
        self.name = name
        self.m = None if name == "triton" else object()
    
    def define(self, *args, **kwargs):
        if self.name == "triton":
            return
        pass

mock_torch_library = types.ModuleType('torch.library')
mock_torch_library.Library = MockLibrary
sys.modules['torch.library'] = mock_torch_library

print("[HOOK-EARLY] Torch pre-patched to prevent circular imports")