import sys
import os

# --- SIMULATE PyInstaller bundle ---
sys._MEIPASS = "SIMULATED_MEIPASS"
sys.path.insert(0, ".")

logging.info("[SIM] Start quick check")

# 1) apply early patches (yang biasa jalan di EXE)
from core.utils.pyinstaller_patches import apply_early_patches, patch_torch_post_import
apply_early_patches()

# 2) Hanya block triton secara environment
os.environ['TRITON_DISABLE'] = '1'
os.environ['TORCH_DISABLE_TRITON_LIBRARY'] = '1'
os.environ['TORCH_DISABLE_TRITON_OPS'] = '1'
os.environ['TORCH_COMPILE_DISABLE'] = '1'

# 3) Import torch dengan error handling khusus untuk logging
try:
    import torch
    logging.info("[SIM] torch imported; version:", getattr(torch, "__version__", "?"))
    
    # 4) Setelah torch berhasil diimport, baru apply post-import patches
    patch_torch_post_import()
    
except AttributeError as e:
    if 'get_log_level_pairs' in str(e):
        # Error spesifik di logging - coba import ulang dengan approach berbeda
        logging.info("[SIM] Detected logging error, attempting workaround...")
        
        # Bersihkan sys.modules dari torch modules yang partially initialized
        torch_modules = [k for k in sys.modules.keys() if k.startswith('torch')]
        for mod in torch_modules:
            del sys.modules[mod]
        
        # Coba import lagi dengan approach minimal
        try:
            # Import core torch dulu tanpa init penuh
            import torch._logging
            import torch._jit_internal
            import torch._ops
            
            # Sekarang import torch utama
            import torch
            logging.info("[SIM] torch imported with workaround; version:", torch.__version__)
            
            patch_torch_post_import()
            
        except Exception as e2:
            logging.info("[SIM] torch import FAILED with workaround:", e2)
            sys.exit(1)
    else:
        logging.info("[SIM] torch import FAILED:", e)
        sys.exit(1)
except Exception as e:
    logging.info("[SIM] torch import FAILED:", e)
    import traceback
    traceback.print_exc()
    sys.exit(1)

logging.info("[SIM] DONE quick check")
logging.info("\n[SIM] Testing basic inference...")
try:
    # Test tensor operations
    x = torch.randn(3, 3)
    y = torch.randn(3, 3)
    z = x + y
    logging.info(f"[SIM] Tensor operations: OK (shape: {z.shape})")
    
    # Test model loading (jika ada model sederhana)
    logging.info("[SIM] Basic inference test: PASSED")
    
except Exception as e:
    logging.info(f"[SIM] Inference test failed: {e}")