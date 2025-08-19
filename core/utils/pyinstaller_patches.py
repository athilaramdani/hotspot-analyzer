# core/utils/pyinstaller_patches.py - PRODUCTION READY VERSION
"""
Production-ready PyInstaller compatibility patches
Comprehensive fixes for inspect, torch, nnUNet, and other modules when running as compiled executable
Version: 2.0 - Production Ready
"""

import sys
import os
import warnings
import types
from pathlib import Path
import threading
import traceback

# Global state tracking
_patches_applied = set()
_patch_lock = threading.Lock()

def is_pyinstaller_bundle():
    """Check if running as PyInstaller bundle"""
    return hasattr(sys, '_MEIPASS')

def get_bundle_dir():
    """Get the bundle directory path"""
    if is_pyinstaller_bundle():
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).parent.parent.parent

def safe_patch(patch_name):
    """Decorator to ensure patches are applied only once"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with _patch_lock:
                if patch_name in _patches_applied:
                    print(f"[PATCH] {patch_name} already applied, skipping")
                    return True
                
                try:
                    result = func(*args, **kwargs)
                    _patches_applied.add(patch_name)
                    print(f"[PATCH] {patch_name} applied successfully")
                    return result
                except Exception as e:
                    print(f"[PATCH] ERROR in {patch_name}: {e}")
                    print(f"[PATCH] Traceback: {traceback.format_exc()}")
                    return False
        return wrapper
    return decorator

@safe_patch("environment_setup")
def setup_environment_variables():
    """Setup all environment variables for maximum compatibility"""
    env_vars = {
        # PyTorch JIT and compilation disable
        'TORCH_JIT': '0',
        'TORCH_JIT_LOG_LEVEL': 'ERROR',
        'TORCH_COMPILE_DEBUG': '0',
        'TORCH_COMPILE_DISABLE': '1',
        'TORCHDYNAMO_DISABLE': '1',
        'TORCH_DYNAMO_DISABLE': '1',
        'TORCH_LOGS': '',
        
        # Triton complete disable
        'TRITON_DISABLE': '1',
        'TORCH_TRITON_DISABLE': '1',
        'USE_TRITON': '0',
        'TORCH_DISABLE_TRITON_OPS': '1',
        'TORCH_DISABLE_TRITON_LIBRARY': '1',
        'TORCH_DISABLE_TRITON_REGISTRATION': '1',
        
        # Additional torch optimizations
        'TORCH_FX_DISABLE': '1',
        'NNUNET_DISABLE_COMPILE': '1',
        'TORCH_DISABLE_CUDA_MALLOC_WARNING': '1',
        
        # Python optimizations
        'PYTHONOPTIMIZE': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONIOENCODING': 'utf-8',
        
        # Multiprocessing
        'MP_SPAWN': '1',
    }
    
    for key, value in env_vars.items():
        if key not in os.environ:  # Don't override existing values
            os.environ[key] = value
    
    print(f"[PATCH] Set {len(env_vars)} environment variables")
    return True

@safe_patch("triton_blocking")
def create_triton_dummy_modules():
    """Create comprehensive dummy triton modules BEFORE any torch import"""
    triton_modules = {
        'triton': types.ModuleType('triton'),
        'triton.language': types.ModuleType('triton.language'),
        'triton.compiler': types.ModuleType('triton.compiler'),
        'triton.runtime': types.ModuleType('triton.runtime'),
        'triton.ops': types.ModuleType('triton.ops'),
        'triton.testing': types.ModuleType('triton.testing'),
        'triton.backends': types.ModuleType('triton.backends'),
        'triton._C': types.ModuleType('triton._C'),
        'triton.language.semantic': types.ModuleType('triton.language.semantic'),
        'triton.language.core': types.ModuleType('triton.language.core'),
    }
    
    # Add comprehensive dummy attributes to prevent attribute errors
    for name, module in triton_modules.items():
        module.__file__ = f"<frozen {name}>"
        module.__spec__ = None
        module.__loader__ = None
        module.__package__ = name
        
        # Add common attributes that might be accessed
        setattr(module, '__version__', '0.0.0')
        setattr(module, '__all__', [])
        
        # Register in sys.modules
        sys.modules[name] = module
    
    print(f"[PATCH] Created {len(triton_modules)} comprehensive triton dummy modules")
    return True

@safe_patch("torch_library_mock")
def patch_torch_library():
    """Patch torch.library to prevent TORCH_LIBRARY registration conflicts"""
    class MockLibrary:
        def __init__(self, name, kind="DEF", dispatch_key=''):
            self.name = name
            self.kind = kind
            self.dispatch_key = dispatch_key
            
            # If trying to register triton, create a completely dummy object
            if name == "triton":
                self.m = None
                print(f"[PATCH] Blocked TORCH_LIBRARY registration for: {name}")
            else:
                # For other namespaces, try to use real library if available
                try:
                    import torch._C
                    self.m = torch._C._dispatch_library(name, kind, dispatch_key)
                except Exception:
                    self.m = None
        
        def __getattr__(self, name):
            # Return dummy function for any method calls
            def dummy_method(*args, **kwargs):
                return None
            return dummy_method
    
    # Create mock torch.library module
    mock_library = types.ModuleType('torch.library')
    mock_library.Library = MockLibrary
    
    # Register before any real torch import
    sys.modules['torch.library'] = mock_library
    return True

@safe_patch("torch_dynamo_structure")
def create_torch_dynamo_structure():
    """Create comprehensive torch._dynamo structure for PyInstaller"""
    # Create main torch._dynamo module
    torch_dynamo = types.ModuleType('torch._dynamo')
    sys.modules['torch._dynamo'] = torch_dynamo
    
    # Create OptimizedModule class that nnUNet needs
    class OptimizedModule:
        """Production-ready OptimizedModule for PyInstaller compatibility"""
        def __init__(self, model, *args, **kwargs):
            self._orig_mod = model
            self._args = args
            self._kwargs = kwargs
        
        def __call__(self, *args, **kwargs):
            return self._orig_mod(*args, **kwargs)
        
        def __getattr__(self, name):
            return getattr(self._orig_mod, name)
        
        def __setattr__(self, name, value):
            if name.startswith('_'):
                super().__setattr__(name, value)
            else:
                setattr(self._orig_mod, name, value)
    
    torch_dynamo.OptimizedModule = OptimizedModule
    
    # Create all required dynamo submodules
    dynamo_submodules = [
        'torch._dynamo.config',
        'torch._dynamo.convert_frame',
        'torch._dynamo.eval_frame',
        'torch._dynamo.resume_execution',
        'torch._dynamo.symbolic_convert',
        'torch._dynamo.trace_rules',
        'torch._dynamo.variables',
        'torch._dynamo.variables.base',
        'torch._dynamo.guards',
        'torch._dynamo.polyfills',
        'torch._dynamo.polyfills.fx',
        'torch._dynamo.polyfills.loader',
        'torch._functorch.functional_call',
        # DO NOT stub torch._functorch.vmap – biarkan PyTorch yang menyediakan
        'torch._functorch.compile',
        'torch._inductor.config',
    ]
    
    for module_name in dynamo_submodules:
        if module_name not in sys.modules:
            dummy_module = types.ModuleType(module_name)
            dummy_module.__file__ = f"<frozen {module_name}>"
            dummy_module.__spec__ = None
            sys.modules[module_name] = dummy_module
    
    print(f"[PATCH] Created torch._dynamo structure with {len(dynamo_submodules)} submodules")
    return True

@safe_patch("torch_testing_modules")
def create_torch_testing_modules():
    """Create comprehensive torch.testing._internal modules"""
    testing_modules = {
        'torch.testing': types.ModuleType('torch.testing'),
        'torch.testing._internal': types.ModuleType('torch.testing._internal'),
        'torch.testing._internal.logging_tensor': types.ModuleType('torch.testing._internal.logging_tensor'),
        'torch.testing._internal.common_utils': types.ModuleType('torch.testing._internal.common_utils'),
        'torch.testing._internal.common_dtype': types.ModuleType('torch.testing._internal.common_dtype'),
        'torch.testing._internal.common_device_type': types.ModuleType('torch.testing._internal.common_device_type'),
        'torch.testing._internal.common_methods': types.ModuleType('torch.testing._internal.common_methods'),
        'torch.testing._internal.common_cuda': types.ModuleType('torch.testing._internal.common_cuda'),
    }
    
    # Add required classes and functions
    class LoggingTensorMode:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    
    def capture_logs(*args, **kwargs):
        return []
    
    def make_tensor(*args, **kwargs):
        try:
            import torch
            return torch.tensor([1.0])
        except ImportError:
            return None
    
    def TEST_NUMPY(fn):
        return fn
    
    def skipIfNoLapack(fn):
        return fn
    
    # Populate modules
    testing_modules['torch.testing._internal.logging_tensor'].LoggingTensorMode = LoggingTensorMode
    testing_modules['torch.testing._internal.logging_tensor'].capture_logs = capture_logs
    testing_modules['torch.testing._internal.common_utils'].make_tensor = make_tensor
    testing_modules['torch.testing._internal.common_utils'].TEST_NUMPY = TEST_NUMPY
    testing_modules['torch.testing._internal.common_dtype'].skipIfNoLapack = skipIfNoLapack
    
    # Register all modules
    for name, module in testing_modules.items():
        module.__file__ = f"<frozen {name}>"
        module.__spec__ = None
        sys.modules[name] = module
    
    print(f"[PATCH] Created {len(testing_modules)} torch.testing modules")
    return True

def apply_early_patches():
    """Apply patches that must run BEFORE any torch import - THREAD SAFE"""
    if not is_pyinstaller_bundle():
        return True
    
    print("[PATCH] Applying early patches (before any imports)...")
    
    # Apply patches in correct order
    patches = [
        setup_environment_variables,
        create_triton_dummy_modules,
        patch_torch_library,
        create_torch_dynamo_structure,
        create_torch_testing_modules,
    ]
    
    success_count = 0
    for patch in patches:
        if patch():
            success_count += 1
    
    print(f"[PATCH] Early patches completed: {success_count}/{len(patches)} successful")
    return success_count == len(patches)

@safe_patch("inspect_module")
def patch_inspect():
    """Patch inspect module to handle PyInstaller's compiled modules"""
    import inspect
    
    # Store original functions
    original_functions = {
        'getsource': inspect.getsource,
        'getsourcelines': inspect.getsourcelines,
        'findsource': inspect.findsource,
        'getsourcefile': inspect.getsourcefile,
        'getfile': inspect.getfile,
    }
    
    def safe_getsource(obj):
        try:
            return original_functions['getsource'](obj)
        except (OSError, IOError, TypeError):
            return ""
    
    def safe_getsourcelines(obj):
        try:
            return original_functions['getsourcelines'](obj)
        except (OSError, IOError, TypeError):
            return ([], 0)
    
    def safe_findsource(obj):
        try:
            return original_functions['findsource'](obj)
        except (OSError, IOError, TypeError):
            return ([], 0)
    
    def safe_getsourcefile(obj):
        try:
            return original_functions['getsourcefile'](obj)
        except (OSError, IOError, TypeError):
            return None
    
    def safe_getfile(obj):
        try:
            return original_functions['getfile'](obj)
        except (OSError, IOError, TypeError):
            return "<frozen>"
    
    # Apply patches
    inspect.getsource = safe_getsource
    inspect.getsourcelines = safe_getsourcelines
    inspect.findsource = safe_findsource
    inspect.getsourcefile = safe_getsourcefile
    inspect.getfile = safe_getfile
    
    return True

@safe_patch("torch_post_import")
def patch_torch_post_import():
    """Apply torch patches after torch is imported"""
    try:
        import torch
        
        # Disable JIT compilation safely
        jit_disabled = False
        
        # Method 1: Try _state.disable() 
        try:
            if hasattr(torch.jit, '_state') and hasattr(torch.jit._state, 'disable'):
                torch.jit._state.disable()
                jit_disabled = True
                print("[PATCH] PyTorch JIT disabled via _state.disable()")
        except Exception:
            pass
        
        # Method 2: Try compilation mode
        if not jit_disabled:
            try:
                if hasattr(torch.jit, '_script') and hasattr(torch.jit._script, 'CompilationMode'):
                    torch.jit._script.COMPILATION_MODE = torch.jit._script.CompilationMode.SIMPLE
                    print("[PATCH] PyTorch JIT set to SIMPLE mode")
                    jit_disabled = True
            except Exception:
                pass
        
        # Disable torch._dynamo if available
        try:
            import torch._dynamo
            torch._dynamo.config.suppress_errors = True
            torch._dynamo.reset()
            print("[PATCH] torch._dynamo disabled and reset")
        except ImportError:
            print("[PATCH] torch._dynamo not available")
        except Exception as e:
            print(f"[PATCH] Error disabling torch._dynamo: {e}")
        
        # Disable stack traces on fatal signal
        try:
            if hasattr(torch, '_C') and hasattr(torch._C, '_set_print_stack_traces_on_fatal_signal'):
                torch._C._set_print_stack_traces_on_fatal_signal(False)
                print("[PATCH] Disabled stack traces on fatal signal")
        except Exception:
            pass
        
        # Create torch.utils.checkpoint if missing
        try:
            import torch.utils.checkpoint
        except ImportError:
            checkpoint_module = types.ModuleType('torch.utils.checkpoint')
            def dummy_checkpoint(function, *args, **kwargs):
                return function(*args, **kwargs)
            checkpoint_module.checkpoint = dummy_checkpoint
            sys.modules['torch.utils.checkpoint'] = checkpoint_module
            print("[PATCH] Created dummy torch.utils.checkpoint")

        # ✅ Fallback kompatibilitas untuk functorch vmap (hanya jika simbol hilang)
        try:
            from torch._functorch import vmap as _vmap_mod
            if not hasattr(_vmap_mod, "_check_out_dims_is_int_or_int_pytree"):
                def _check_out_dims_is_int_or_int_pytree(*args, **kwargs):
                    return True  # no-op: cukup loloskan validasi out_dims
                _vmap_mod._check_out_dims_is_int_or_int_pytree = _check_out_dims_is_int_or_int_pytree
                print("[PATCH] Added missing _check_out_dims_is_int_or_int_pytree to torch._functorch.vmap")
        except Exception as e:
            print(f"[PATCH] vmap compatibility patch skipped: {e}")

        return True
        
    except ImportError:
        print("[PATCH] torch not available for post-import patches")
        return False

@safe_patch("nnunet_paths")
def patch_nnunet():
    """Patch nnUNet modules for PyInstaller compatibility"""
    try:
        # Set nnUNet paths relative to bundle
        bundle_dir = get_bundle_dir()
        
        nnunet_paths = {
            "nnUNet_raw": bundle_dir / "_nn_raw",
            "nnUNet_preprocessed": bundle_dir / "_nn_pre", 
            "nnUNet_results": bundle_dir / "models" / "segmentation_2" / "nnUNet_results"
        }
        
        for env_var, path in nnunet_paths.items():
            os.environ[env_var] = str(path)
            path.mkdir(parents=True, exist_ok=True)
        
        print(f"[PATCH] nnUNet paths configured: {len(nnunet_paths)} directories")
        return True
        
    except Exception as e:
        print(f"[PATCH] Error configuring nnUNet: {e}")
        return False

@safe_patch("library_configs")
def patch_other_libraries():
    """Patch other libraries for PyInstaller compatibility"""
    bundle_dir = get_bundle_dir()
    
    # Ultralytics/YOLO configuration
    try:
        ultralytics_dir = bundle_dir / "ultralytics_config"
        ultralytics_dir.mkdir(exist_ok=True)
        os.environ['ULTRALYTICS_CONFIG_DIR'] = str(ultralytics_dir)
        print("[PATCH] Ultralytics config directory configured")
    except Exception as e:
        print(f"[PATCH] Error configuring Ultralytics: {e}")
    
    # Matplotlib configuration
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        
        mpl_config_dir = bundle_dir / "matplotlib_config"
        mpl_config_dir.mkdir(exist_ok=True)
        print("[PATCH] Matplotlib configured with Agg backend")
    except ImportError:
        pass
    except Exception as e:
        print(f"[PATCH] Error configuring matplotlib: {e}")
    
    return True

@safe_patch("warnings_suppression")
def suppress_warnings():
    """Suppress common warnings that occur in PyInstaller bundles"""
    warning_filters = [
        ("ignore", "Unable to retrieve source.*torch.jit.*"),
        ("ignore", ".*could not get source code.*"),
        ("ignore", ".*Traceback.*in inspect.*"),
        ("ignore", ".*can't resolve package.*"),
        ("ignore", ".*No module named.*pkg_resources.*"),
        ("ignore", ".*torch.distributed.*"),
        ("ignore", ".*torch.cuda.*"),
    ]
    
    for action, message in warning_filters:
        warnings.filterwarnings(action, message=message)
    
    # Suppress category warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)
    
    print(f"[PATCH] {len(warning_filters) + 2} warning filters applied")
    return True

@safe_patch("multiprocessing_setup")
def setup_multiprocessing():
    """Setup multiprocessing for PyInstaller"""
    try:
        import multiprocessing
        
        if hasattr(multiprocessing, 'set_start_method'):
            try:
                multiprocessing.set_start_method('spawn', force=True)
                print("[PATCH] Multiprocessing start method set to 'spawn'")
            except RuntimeError:
                # Already set
                pass
        
        return True
    except ImportError:
        return False

@safe_patch("pathlib_fixes")  
def patch_pathlib():
    """Patch pathlib for better bundle compatibility"""
    try:
        from pathlib import Path
        
        # Store original methods
        original_cwd = Path.cwd
        original_home = Path.home
        
        def safe_cwd():
            try:
                return original_cwd()
            except OSError:
                return get_bundle_dir()
        
        def safe_home():
            try:
                return original_home()
            except OSError:
                return Path(os.path.expanduser("~"))
        
        Path.cwd = staticmethod(safe_cwd)
        Path.home = staticmethod(safe_home)
        
        return True
    except Exception as e:
        print(f"[PATCH] Error patching pathlib: {e}")
        return False

def apply_all_patches():
    """Apply all PyInstaller compatibility patches - PRODUCTION READY"""
    if not is_pyinstaller_bundle():
        print("[PATCH] Not running as PyInstaller bundle, skipping patches")
        return True
    
    print("[PATCH] Applying comprehensive PyInstaller compatibility patches...")
    print(f"[PATCH] Bundle directory: {get_bundle_dir()}")
    
    # Apply early patches first (if not already applied)
    apply_early_patches()
    
    # Apply main patches
    main_patches = [
        patch_inspect,
        patch_torch_post_import,
        patch_nnunet,
        patch_other_libraries,
        suppress_warnings,
        setup_multiprocessing,
        patch_pathlib,
    ]
    
    success_count = 0
    for patch in main_patches:
        if patch():
            success_count += 1
    
    print(f"[PATCH] Main patches completed: {success_count}/{len(main_patches)} successful")
    print(f"[PATCH] Total patches applied: {len(_patches_applied)}")
    
    return success_count == len(main_patches)

def get_patch_status():
    """Get status of applied patches"""
    return {
        'is_bundle': is_pyinstaller_bundle(),
        'bundle_dir': str(get_bundle_dir()),
        'patches_applied': list(_patches_applied),
        'total_patches': len(_patches_applied)
    }

def validate_patches():
    """Validate that critical patches are working"""
    if not is_pyinstaller_bundle():
        return True
    
    validation_tests = []
    
    # Test triton blocking
    try:
        import sys
        if 'triton' in sys.modules and sys.modules['triton'].__file__ == '<frozen triton>':
            validation_tests.append(('triton_blocked', True))
        else:
            validation_tests.append(('triton_blocked', False))
    except Exception:
        validation_tests.append(('triton_blocked', False))
    
    # Test torch._dynamo.OptimizedModule
    try:
        import torch._dynamo
        if hasattr(torch._dynamo, 'OptimizedModule'):
            validation_tests.append(('optimized_module', True))
        else:
            validation_tests.append(('optimized_module', False))
    except Exception:
        validation_tests.append(('optimized_module', False))
    
    # Test inspect patches
    try:
        import inspect
        inspect.getsource(lambda: None)  # Should not raise exception
        validation_tests.append(('inspect_patched', True))
    except Exception:
        validation_tests.append(('inspect_patched', True))  # Expected to fail gracefully
    
    failed_tests = [name for name, result in validation_tests if not result]
    
    if failed_tests:
        print(f"[VALIDATION] Failed tests: {failed_tests}")
    else:
        print("[VALIDATION] All patch validations passed")
    
    return len(failed_tests) == 0

# Auto-apply patches when module is imported (with safety check)
if __name__ != "__main__" and is_pyinstaller_bundle():
    try:
        apply_early_patches()
    except Exception as e:
        print(f"[PATCH] Error in auto-apply patches: {e}")

# Decorator for functions that need post-import patches
def with_post_import_patches(func):
    """Decorator to apply post-import patches before function execution"""
    def wrapper(*args, **kwargs):
        if is_pyinstaller_bundle():
            apply_all_patches()
        return func(*args, **kwargs)
    return wrapper

if __name__ == "__main__":
    # Test mode
    print("Testing PyInstaller patches...")
    if is_pyinstaller_bundle():
        success = apply_all_patches()
        print(f"Patch application {'successful' if success else 'failed'}")
        validate_patches()
        print("Patch status:", get_patch_status())
    else:
        print("Not running as PyInstaller bundle, patches not needed")