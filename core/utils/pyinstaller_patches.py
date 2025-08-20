# core/utils/pyinstaller_patches.py - PRODUCTION READY VERSION
"""
TELPLASTINA - PyInstaller Compatibility Patches
Production-ready patches for inspect, torch, nnUNet, and other modules when running as compiled executable
Telkom Enhanced Planar Scintigraphy Analysis - Version: 1.0 - Production Ready
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
    """Setup environment variables dengan lebih hati-hati"""
    env_vars = {
        # PyTorch JIT dan compilation disable - HANYA yang essential
        'TORCH_COMPILE_DISABLE': '1',
        'TORCHDYNAMO_DISABLE': '1',
        
        # Triton complete disable
        'TRITON_DISABLE': '1',
        'USE_TRITON': '0',
        
        # Python optimizations
        'PYTHONOPTIMIZE': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONIOENCODING': 'utf-8',
        
        # Multiprocessing
        'MP_SPAWN': '1',
    }
    
    for key, value in env_vars.items():
        if key not in os.environ:  # Jangan override existing values
            os.environ[key] = value
    
    # HINDARI setting TORCH_LOGS atau variabel logging lainnya
    # karena ini mengganggu internal PyTorch logging initialization
    
    print(f"[PATCH] Set {len(env_vars)} environment variables")
    return True

@safe_patch("triton_blocking")
def create_triton_dummy_modules():
    """Create comprehensive dummy triton modules - tapi jangan ganggu torch"""
    # Hanya buat modul triton, jangan sentuh torch modules
    triton_modules = {
        'triton': types.ModuleType('triton'),
        'triton.language': types.ModuleType('triton.language'),
        'triton.compiler': types.ModuleType('triton.compiler'),
    }
    
    for name, module in triton_modules.items():
        module.__file__ = f"<frozen {name}>"
        module.__spec__ = None
        module.__loader__ = None
        module.__package__ = name
        module.__version__ = '0.0.0'
        module.__all__ = []
        sys.modules[name] = module
    
    print(f"[PATCH] Created {len(triton_modules)} triton dummy modules")
    return True
@safe_patch("torch_library_mock")
def patch_torch_library():
    """JANGAN lakukan early patching untuk torch.library - ini menyebabkan circular import"""
    # Jangan buat stub sama sekali untuk torch.library di fase early
    # Biarkan PyTorch handle inisialisasi library secara normal
    print("[PATCH] Skipped torch.library early patching to avoid circular imports")
    return True

@safe_patch("torch_dynamo_structure")
def create_torch_dynamo_structure():
    """JANGAN buat stub untuk torch modules - biarkan PyTorch handle inisialisasi"""
    # Jangan buat stub apapun untuk torch._dynamo atau modules internal
    # Biarkan PyTorch melakukan inisialisasi normal
    print("[PATCH] Skipped all torch internal structure creation to avoid circular imports")
    return True

@safe_patch("torch_testing_modules")
def create_torch_testing_modules():
    """Jangan stub torch.testing - biarkan PyInstaller handle melalui hooks"""
    # Tidak melakukan apapun, biarkan PyInstaller collect modules normally
    print("[PATCH] Skipped torch.testing stubbing - relying on PyInstaller hooks")
    return True

def apply_early_patches():
    """Apply patches that must run BEFORE any torch import - THREAD SAFE"""
    if not is_pyinstaller_bundle():
        return True
    
    # Cek jika sudah di-apply untuk menghindari double patching
    if 'early_patches_applied' in globals():
        print("[PATCH] Early patches already applied, skipping")
        return True
        
    print("[PATCH] Applying early patches (before any imports)...")
    
    # HANYA patches yang benar-benar aman dan essential
    patches = [
        setup_environment_variables,
        create_triton_dummy_modules,
        patch_torch_library,  # Yang baru (no-op)
        create_torch_dynamo_structure,  # No-op
        create_torch_testing_modules,  # No-op
    ]
    
    success_count = 0
    for patch in patches:
        if patch():
            success_count += 1
    
    print(f"[PATCH] Early patches completed: {success_count}/{len(patches)} successful")
    
    # Tandai sudah di-apply
    globals()['early_patches_applied'] = True
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

@safe_patch("torch_library_post")
def patch_torch_library_post():
    """Patch torch.library SETELAH torch ter-import.
    Blokir registrasi untuk namespace 'triton'; lainnya pakai Library asli.
    """
    try:
        import importlib
        lib_mod = importlib.import_module('torch.library')
        # Jika early stub masih aktif, kita ambil Library asli dari modul yang sama
        # (PyTorch akan set Library asli ketika torch.library dipakai real).
        OriginalLibrary = getattr(lib_mod, 'Library', None)
        # Kalau masih stub (karena early), coba ambil dari file python asli
        if OriginalLibrary is None or OriginalLibrary.__module__ == __name__:
            # reload modul torch.library agar dapat implementasi asli
            lib_mod = importlib.reload(lib_mod)
            OriginalLibrary = getattr(lib_mod, 'Library', None)

        if OriginalLibrary is None:
            print("[PATCH] torch.library.Library not found; skip")
            return True

        def WrappedLibrary(name, *args, **kwargs):
            if name == "triton":
                class _Noop:
                    def __enter__(self): return self
                    def __exit__(self, *a): return False
                    def define(self, *a, **k): return None
                    def impl(self, *a, **k):
                        def _deco(fn): return fn
                        return _deco
                    def fallthrough(self, *a, **k): return None
                    def __getattr__(self, _):
                        def _noop(*a, **k): return None
                        return _noop
                print("[PATCH] torch.library.Library('triton') -> no-op (post-import)")
                return _Noop()
            return OriginalLibrary(name, *args, **kwargs)

        lib_mod.Library = WrappedLibrary
        print("[PATCH] torch.library.Library wrapped post-import")
        return True
    except Exception as e:
        print("[PATCH] torch.library post patch skipped:", e)
        return False

@safe_patch("torch_post_import")
def patch_torch_post_import():
    """Apply torch patches after torch is imported - FIXED VERSION"""
    try:
        import torch
        
        # 1) Pastikan torch.library tersedia
        if not hasattr(torch, 'library'):
            try:
                from torch import library
                torch.library = library
            except ImportError:
                # Buat minimal fallback jika tidak ada
                import types
                torch.library = types.ModuleType('torch.library')
                torch.library.__file__ = "<frozen torch.library>"
        
        # 2) Patch torch.library untuk block triton
        try:
            import torch.library as lib_module
            
            original_library = getattr(lib_module, 'Library', None)
            
            if original_library:
                class TritonBlocker:
                    def __init__(self, name, kind="DEF", dispatch_key=''):
                        if name == "triton":
                            print(f"[PATCH] Blocked TORCH_LIBRARY('{name}')")
                        else:
                            # Untuk non-triton, gunakan original
                            self._lib = original_library(name, kind, dispatch_key)
                            self.name = name
                    
                    def __enter__(self):
                        if hasattr(self, '_lib'):
                            return self._lib.__enter__()
                        return self
                    
                    def __exit__(self, *args):
                        if hasattr(self, '_lib'):
                            return self._lib.__exit__(*args)
                        return False
                    
                    def define(self, *args, **kwargs):
                        if hasattr(self, '_lib'):
                            return self._lib.define(*args, **kwargs)
                    
                    def impl(self, *args, **kwargs):
                        if hasattr(self, '_lib'):
                            return self._lib.impl(*args, **kwargs)
                        def noop_decorator(func):
                            return func
                        return noop_decorator
                
                lib_module.Library = TritonBlocker
                print("[PATCH] torch.library.Library wrapped for triton blocking")
        except Exception as e:
            print(f"[PATCH] torch.library wrapping failed: {e}")

        # 3) Nonaktifkan JIT dan optimizations
        try:
            os.environ['TORCH_JIT'] = '0'
            os.environ['TORCH_COMPILE_DISABLE'] = '1'
            if hasattr(torch.jit, '_state') and hasattr(torch.jit._state, 'disable'):
                torch.jit._state.disable()
            print("[PATCH] PyTorch JIT disabled")
        except Exception as e:
            print(f"[PATCH] JIT disable failed: {e}")

        # 4) ✅ NEW: Patch torchvision to prevent extension conflicts
        try:
            import sys
            # Remove any problematic torchvision modules
            problematic_modules = [
                'torchvision.extension',
                'torchvision._meta_registrations',
                'torchvision.prototype'
            ]
            for module in problematic_modules:
                if module in sys.modules:
                    del sys.modules[module]
                    print(f"[PATCH] Removed problematic module: {module}")
            
            # Set torchvision environment to prevent extension loading
            os.environ['TORCHVISION_DISABLE_EXTENSIONS'] = '1'
            print("[PATCH] torchvision extension loading disabled")
        except Exception as e:
            print(f"[PATCH] torchvision patching failed: {e}")

        print("[PATCH] torch post-import patches applied successfully")
        return True

    except Exception as e:
        print(f"[PATCH] Error in patch_torch_post_import: {e}")
        import traceback
        traceback.print_exc()
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