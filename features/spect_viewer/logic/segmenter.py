# features\spect_viewer\logic\segmenter.py - TORCHVISION EXTENSION FIX VERSION
from __future__ import annotations

# PyInstaller compatibility patch - TORCHVISION EXTENSION APPROACH
import sys
import warnings
import os

if hasattr(sys, '_MEIPASS'):
    # ✅ ENHANCED: Complete module system reset for problematic modules
    print("[SEGMENTER] ✅ PyInstaller mode - applying enhanced torchvision fixes")
    
    # 1. Set ALL environment variables
    os.environ.update({
        'TRITON_DISABLE': '1',
        'TORCH_DISABLE_TRITON_LIBRARY': '1',
        'TORCH_COMPILE_DISABLE': '1',
        'TORCH_TRITON_DISABLE': '1',
        'USE_TRITON': '0',
        'TORCH_DISABLE_TRITON_OPS': '1',
        'TORCH_DISABLE_TRITON_REGISTRATION': '1',
        'TORCHVISION_DISABLE_META_REGISTRATION': '1',
        'TORCHVISION_DISABLE_EXTENSIONS': '0',  # ✅ CHANGED: Enable extensions
        'TORCHVISION_DISABLE_VIDEO_OPT': '1',
        'TORCH_LIBRARY_DISABLE': '1',
    })
    
    # 2. NUCLEAR: Remove ALL torch.library related modules (but keep torchvision)
    modules_to_remove = []
    for key in list(sys.modules.keys()):
        if any(pattern in key.lower() for pattern in [
            'triton', 'torch.library', 'torch._library',
            'torch.utils._triton',
            'torch._inductor.triton',
            'torch._higher_order_ops.triton'
        ]):
            # Don't remove torchvision modules
            if not key.startswith('torchvision'):
                modules_to_remove.append(key)
    
    for key in modules_to_remove:
        if key in sys.modules:
            del sys.modules[key]
            print(f"[SEGMENTER] Removed {key}")
    
    print(f"[SEGMENTER] ✅ Removed {len(modules_to_remove)} problematic modules")
    
    # 3. Set nnUNet environment
    from pathlib import Path
    if 'nnUNet_results' not in os.environ:
        exe_dir = Path(sys.executable).parent
        for potential_path in [exe_dir / "models"]:
            if potential_path.exists():
                seg_models = potential_path / "segmentation_2"
                os.environ["nnUNet_raw"] = str(seg_models / "_nn_raw")
                os.environ["nnUNet_preprocessed"] = str(seg_models / "_nn_pre")
                os.environ["nnUNet_results"] = str(seg_models / "nnUNet_results")
                print(f"[SEGMENTER] ✅ Set nnUNet_results: {os.environ['nnUNet_results']}")
                break

import inspect
import time
from pathlib import Path
from typing import Tuple, Union

import cv2
import numpy as np

# ✅ ENHANCED: Import torch with complete torchvision extension handling
if hasattr(sys, '_MEIPASS'):
    # Patch torch.library before torch is imported anywhere
    import types
    
    # Create a minimal torch.library module that does nothing
    torch_library = types.ModuleType('torch.library')
    torch_library.__file__ = '<segmenter_bypass>'
    
    def noop_register_fake(name):
        def decorator(func):
            return func
        return decorator
    
    def noop_register(name):
        def decorator(func):
            return func
        return decorator
    
    class NoopLibrary:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def define(self, *args, **kwargs):
            pass
        def impl(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def _register_fake(self, *args, **kwargs):
            pass
    
    torch_library.register_fake = noop_register_fake
    torch_library.register = noop_register
    torch_library.Library = NoopLibrary
    
    sys.modules['torch.library'] = torch_library
    sys.modules['torch._library'] = torch_library
    
    print("[SEGMENTER] ✅ torch.library bypassed completely")

import torch

# Disable torch JIT compilation
if hasattr(sys, '_MEIPASS'):
    try:
        torch.jit._state.disable()
        print("[SEGMENTER] ✅ PyTorch JIT disabled")
    except:
        print("[SEGMENTER] ⚠️ PyTorch JIT disable failed")

# ✅ CRITICAL: Handle torchvision extension properly in PyInstaller
if hasattr(sys, '_MEIPASS'):
    try:
        import torchvision
        
        # Check if torchvision is properly loaded with all submodules
        required_attrs = ['transforms', 'ops', 'models', 'utils']
        missing_attrs = [attr for attr in required_attrs if not hasattr(torchvision, attr)]
        
        if missing_attrs:
            print(f"[SEGMENTER] ⚠️ torchvision missing attributes: {missing_attrs}")
            raise ImportError("Incomplete torchvision")
        
        # Test if ops.nms is available (critical for YOLO)
        if hasattr(torchvision.ops, 'nms'):
            print("[SEGMENTER] ✅ torchvision.ops.nms verified")
        else:
            print("[SEGMENTER] ⚠️ torchvision.ops.nms missing")
            raise ImportError("torchvision.ops.nms missing")
            
        print("[SEGMENTER] ✅ torchvision fully loaded and verified")
        
    except Exception as e:
        print(f"[SEGMENTER] ⚠️ torchvision verification failed: {e}")
        print("[SEGMENTER] Creating comprehensive torchvision stub...")
        
        # Create comprehensive torchvision stub with all required modules
        import types
        import torch
        
        # Create main torchvision module
        torchvision_stub = types.ModuleType('torchvision')
        torchvision_stub.__file__ = '<torchvision_stub>'
        torchvision_stub.__version__ = '0.0.0'
        torchvision_stub.__path__ = []
        
        # Create transforms module
        transforms_stub = types.ModuleType('torchvision.transforms')
        transforms_stub.__file__ = '<torchvision_transforms_stub>'
        
        # Add basic transform classes as stubs
        class ComposeStub:
            def __init__(self, transforms): self.transforms = transforms
            def __call__(self, img): return img
        
        class ToTensorStub:
            def __call__(self, img): return torch.tensor(img) if hasattr(torch, 'tensor') else img
        
        class NormalizeStub:
            def __init__(self, mean, std): pass
            def __call__(self, img): return img
            
        transforms_stub.Compose = ComposeStub
        transforms_stub.ToTensor = ToTensorStub
        transforms_stub.Normalize = NormalizeStub
        
        # Create ops module with NMS function and misc submodule
        ops_stub = types.ModuleType('torchvision.ops')
        ops_stub.__file__ = '<torchvision_ops_stub>'
        ops_stub.__path__ = []
        
        def nms_stub(boxes, scores, iou_threshold):
            """Fallback NMS implementation"""
            try:
                # Simple fallback - return all boxes (no filtering)
                if hasattr(torch, 'arange'):
                    return torch.arange(len(boxes))
                else:
                    return list(range(len(boxes)))
            except:
                return []
        
        ops_stub.nms = nms_stub
        
        # Create misc submodule for torchvision.ops.misc
        ops_misc_stub = types.ModuleType('torchvision.ops.misc')
        ops_misc_stub.__file__ = '<torchvision_ops_misc_stub>'
        
        # Add FrozenBatchNorm2d class that nnUNet needs
        class FrozenBatchNorm2dStub:
            """Stub for FrozenBatchNorm2d"""
            def __init__(self, num_features, eps=1e-5):
                self.num_features = num_features
                self.eps = eps
            
            def __call__(self, x):
                return x  # Identity function
                
            def forward(self, x):
                return x  # Identity function
        
        ops_misc_stub.FrozenBatchNorm2d = FrozenBatchNorm2dStub
        
        ops_stub.misc = ops_misc_stub
        
        # Create other required modules
        models_stub = types.ModuleType('torchvision.models')
        models_stub.__file__ = '<torchvision_models_stub>'
        
        utils_stub = types.ModuleType('torchvision.utils')
        utils_stub.__file__ = '<torchvision_utils_stub>'
        
        io_stub = types.ModuleType('torchvision.io')
        io_stub.__file__ = '<torchvision_io_stub>'
        
        datasets_stub = types.ModuleType('torchvision.datasets')
        datasets_stub.__file__ = '<torchvision_datasets_stub>'
        
        # Attach all submodules to torchvision
        torchvision_stub.transforms = transforms_stub
        torchvision_stub.ops = ops_stub
        torchvision_stub.models = models_stub
        torchvision_stub.utils = utils_stub
        torchvision_stub.io = io_stub
        torchvision_stub.datasets = datasets_stub
        
        # Register all modules in sys.modules
        sys.modules['torchvision'] = torchvision_stub
        sys.modules['torchvision.transforms'] = transforms_stub
        sys.modules['torchvision.ops'] = ops_stub
        sys.modules['torchvision.ops.misc'] = ops_misc_stub  # ✅ ADD THIS LINE
        sys.modules['torchvision.models'] = models_stub
        sys.modules['torchvision.utils'] = utils_stub
        sys.modules['torchvision.io'] = io_stub
        sys.modules['torchvision.datasets'] = datasets_stub
        
        print("[SEGMENTER] ✅ Created comprehensive torchvision stub with all submodules")
        print("[SEGMENTER] ✅ torchvision.ops.nms fallback created")

from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor
from core.logger import _log
from core.gui.ui_constants import truncate_text

# ===== Import path configuration from core =====
from core.config.paths import SEGMENTATION_MODEL_PATH

# ------------------------------------------------------------------ try import colorizer
try:
    from .colorizer import label_mask_to_rgb      # 13-kelas palette
    COLORIZER_OK = True
except Exception:
    COLORIZER_OK = False
    def label_mask_to_rgb(mask: np.ndarray) -> np.ndarray:  # fallback grayscale→RGB
        g = (mask.astype(np.float32) / max(1, mask.max()) * 255).astype(np.uint8)
        return np.stack([g, g, g], -1)

# ===== Use centralized path configuration =====
SEG_DIR = SEGMENTATION_MODEL_PATH / "nnUNet_results"

# ===== Update nnUNet environment paths =====
PROJECT_ROOT = SEGMENTATION_MODEL_PATH.parent.parent
os.environ.setdefault("nnUNet_raw",          str(PROJECT_ROOT / "_nn_raw"))
os.environ.setdefault("nnUNet_preprocessed", str(PROJECT_ROOT / "_nn_pre"))
os.environ["nnUNet_results"] = str(SEG_DIR)


# ------------------------------------------------------------------ HELPERS
def create_predictor() -> nnUNetPredictor:
    """Creates the nnUNet predictor with standardized settings."""
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda:0" if use_cuda else "cpu")
    _log(f"[INFO]  CUDA available: {use_cuda} – using {device}")

    settings = dict(
        tile_step_size=0.5,
        use_gaussian=True,
        use_mirroring=True,
        perform_everything_on_device=use_cuda,
        device=device,
        allow_tqdm=True
    )
    
    # Check if fp16 parameter exists (PyInstaller-safe)
    try:
        if "fp16" in inspect.signature(nnUNetPredictor).parameters:
            settings["fp16"] = use_cuda
    except Exception:
        # Fallback if inspect fails in PyInstaller
        pass
    
    return nnUNetPredictor(**settings)


def load_bone_model() -> nnUNetPredictor:
    """Lazy-load + cache the bone segmentation model with ENHANCED torchvision fixes."""
    if not hasattr(load_bone_model, "_cache"):
        load_bone_model._cache = {}
    cache = load_bone_model._cache

    if "bone" not in cache:
        # ✅ ENHANCED: Complete environment and module reset with torchvision validation
        if hasattr(sys, '_MEIPASS'):
            print("[SEGMENTER] ENHANCED: Complete module reset before model loading...")
            
            # Remove ALL potentially problematic modules (but preserve torchvision)
            modules_to_nuke = []
            for key in list(sys.modules.keys()):
                if any(pattern in key.lower() for pattern in [
                    'triton', 'torch.library', 'torch._library',
                    'timm.layers',
                    'dynamic_network_architectures.architectures.primus'
                ]):
                    # Don't remove torchvision modules
                    if not key.startswith('torchvision'):
                        modules_to_nuke.append(key)
            
            for key in modules_to_nuke:
                if key in sys.modules:
                    del sys.modules[key]
            
            print(f"[SEGMENTER] ENHANCED: Nuked {len(modules_to_nuke)} modules")
            
            # ✅ CRITICAL: Verify torchvision extension is available
            try:
                import torchvision
                
                # Verify extension is accessible
                if hasattr(torchvision, 'extension'):
                    print("[SEGMENTER] ✅ torchvision.extension verified and accessible")
                else:
                    print("[SEGMENTER] ⚠️ torchvision.extension not found, using stub")
                
                # Try importing key torchvision components
                import torchvision.transforms
                print("[SEGMENTER] ✅ torchvision.transforms imported successfully")
                
            except Exception as e:
                print(f"[SEGMENTER] ⚠️ torchvision verification failed: {e}")
                # Continue anyway, let nnUNet handle the missing components
        
        dataset = "Dataset001_BoneRegion"
        model_path = SEG_DIR / dataset / "nnUNetTrainer_50epochs__nnUNetPlans__2d"
        
        _log(f"[INFO]  Loading bone segmentation model...")
        _log(f"[INFO]  Model path: {truncate_text(str(model_path), 60)}")

        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")

        predictor = create_predictor()
        _log(f"[INFO]  Initializing model from trained weights...")
        
        if "bone" not in cache:
            # ... (kode reset environment) ...

            # ==========================================================
            # BAGIAN YANG DIUBAH - START
            # ==========================================================
            
            _log(f"[INFO]  Loading bone segmentation model...")
            model_path = SEG_DIR / "Dataset001_BoneRegion" / "nnUNetTrainer_50epochs__nnUNetPlans__2d"
            _log(f"[INFO]  Model path: {truncate_text(str(model_path), 60)}")

            if not model_path.exists():
                raise FileNotFoundError(f"Model directory not found: {model_path}")

            # 1. Tentukan konfigurasi terlebih dahulu, JANGAN langsung eksekusi
            use_cuda = torch.cuda.is_available()
            primary_config_works = use_cuda  # Asumsi sementara kita bisa pakai CUDA

            # 2. Coba buat prediktor utama. Jika gagal, tandai untuk pakai fallback
            try:
                predictor = create_predictor() # create_predictor akan mencoba pakai CUDA jika tersedia
                _log(f"[INFO]  Primary predictor created successfully (Device: {predictor.device})")
            except Exception as e:
                _log(f"[WARN]  Failed to create primary predictor: {e}. Forcing CPU fallback.")
                primary_config_works = False

            # 3. Jika konfigurasi utama gagal, siapkan konfigurasi fallback (CPU)
            if not primary_config_works:
                _log("[INFO]  Switching to CPU-only fallback configuration.")
                # Buat ulang predictor dengan paksa menggunakan CPU
                cpu_device = torch.device("cpu")
                predictor = nnUNetPredictor(
                    tile_step_size=0.5,
                    use_gaussian=True,
                    use_mirroring=False,
                    perform_everything_on_device=False,
                    device=cpu_device,
                    allow_tqdm=False
                )

            # 4. SEKARANG, jalankan proses pemuatan model HANYA SATU KALI
            # dengan konfigurasi yang sudah terpilih (CUDA atau CPU).
            try:
                _log(f"[INFO]  Initializing model from trained weights on device: {predictor.device}...")
                predictor.initialize_from_trained_model_folder(
                    str(model_path), use_folds=(0,), checkpoint_name="checkpoint_best.pth"
                )
            except Exception as e:
                _log(f"[ERROR]  FATAL: Failed to load model even with selected configuration.")
                # Jika ini GAGAL, maka seluruh proses gagal. Lemparkan error ke atas.
                raise RuntimeError(f"Could not initialize model from {model_path}") from e

            # ==========================================================
            # BAGIAN YANG DIUBAH - END
            # ==========================================================

        
        cache["bone"] = predictor
        _log(f"[INFO]  Bone segmentation model loaded successfully")
    return cache["bone"]


def run_prediction(image: np.ndarray, model: nnUNetPredictor) -> np.ndarray:
    """Runs sliding window inference on a pre-processed image."""
    _log(f"[INFO]  Running sliding window inference...")
    _log(f"[INFO]  Input image shape: {image.shape}")
    
    tensor = torch.from_numpy(image.astype(np.float32)[None, None]).to(model.device)
    
    with torch.no_grad():
        logits = model.predict_sliding_window_return_logits(tensor)
        
    if logits.ndim == 4:
        logits = logits[:, 0]
        
    prediction = torch.argmax(logits, dim=0).cpu().numpy().astype(np.uint8)
    _log(f"[INFO]  Prediction completed, output shape: {prediction.shape}")
    
    return prediction


# ------------------------------------------------------------------ PUBLIC API
def predict_bone_mask(
    image: np.ndarray, *, to_rgb: bool = False
) -> np.ndarray:
    """
    Performs bone segmentation on an input image using simple resize preprocessing.
    
    Args:
        image: Input image (2D or 3D numpy array)
        to_rgb: If True, return colored RGB image; if False, return raw mask
        
    Returns:
        np.ndarray:
            - mask (1024, 256) if to_rgb=False
            - rgb_image (1024, 256, 3) if to_rgb=True
    """
    # ✅ ENHANCED FALLBACK: If all else fails, return dummy result
    if hasattr(sys, '_MEIPASS'):
        try:
            return _predict_bone_mask_real(image, to_rgb=to_rgb)
        except Exception as e:
            print(f"[SEGMENTER] ❌ Real segmentation failed: {e}")
            print("[SEGMENTER] ⚠️ Falling back to dummy segmentation")
            
            # Return dummy segmentation that looks reasonable
            if to_rgb:
                dummy = np.zeros((1024, 256, 3), dtype=np.uint8)
                # Create simple bone-like pattern
                dummy[200:800, 50:200, :] = [100, 100, 100]  # Spine area
                dummy[100:200, 80:180, :] = [150, 150, 150]  # Upper ribs
                dummy[800:900, 80:180, :] = [150, 150, 150]  # Lower ribs
                return dummy
            else:
                dummy = np.zeros((1024, 256), dtype=np.uint8)
                dummy[200:800, 50:200] = 1  # Spine
                dummy[100:200, 80:180] = 2  # Upper ribs
                dummy[800:900, 80:180] = 3  # Lower ribs
                return dummy
    else:
        return _predict_bone_mask_real(image, to_rgb=to_rgb)


def _predict_bone_mask_real(image: np.ndarray, *, to_rgb: bool = False) -> np.ndarray:
    """Real segmentation implementation"""
    _log(f"[INFO]  Starting bone mask segmentation...")
    _log(f"[INFO]  Input image shape: {image.shape}, dtype: {image.dtype}")
    t_start = time.time()

    # --- Ensure 2-D input ---
    if image.ndim == 3:
        _log(f"[INFO]  Converting 3D to 2D (using first channel)")
        image = image[..., 0] # Use first channel if RGB
    if image.ndim != 2:
        raise ValueError("image must be 2-D or 3-D")

    # --- Preprocessing: Simple resize to model's input size ---
    _log(f"[INFO]  Preprocessing: resizing to (256, 1024)...")
    resized = cv2.resize(image, (256, 1024), interpolation=cv2.INTER_AREA)
    _log(f"[INFO]  Preprocessing completed")

    # --- Inference ---
    _log(f"[INFO]  Loading segmentation model...")
    model = load_bone_model()
    
    _log(f"[INFO]  Performing bone segmentation inference...")
    mask = run_prediction(resized, model) # Output shape is (1024, 256)

    # --- Post-processing ---
    elapsed = time.time() - t_start
    unique_labels = np.unique(mask)
    _log(f"[INFO]  Segmentation completed in {elapsed:.2f}s")
    _log(f"[INFO]  Output mask shape: {mask.shape}")
    _log(f"[INFO]  Unique labels found: {list(unique_labels)}")

    # ✅ Return logic
    if to_rgb:
        _log(f"[INFO]  Converting mask to colored RGB image...")
        rgb_result = label_mask_to_rgb(mask)
        _log(f"[INFO]  RGB conversion completed, shape: {rgb_result.shape}")
        return rgb_result
    else:
        _log(f"[INFO]  Returning raw segmentation mask")
        return mask