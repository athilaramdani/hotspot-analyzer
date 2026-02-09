# test_segmentation_standalone.py
"""
Standalone test script untuk segmentasi nnUNet
Test environment PyInstaller tanpa build
"""

import sys
import os
import warnings
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
import time

# Simulate PyInstaller environment
logging.info("  [TEST] Simulating PyInstaller environment...")

# Mock PyInstaller _MEIPASS
if not hasattr(sys, '_MEIPASS'):
    # Set mock _MEIPASS to current directory
    sys._MEIPASS = str(Path.cwd())
    sys.frozen = True
    logging.info(f"  [TEST] Mock _MEIPASS set to: {sys._MEIPASS}")

# Apply PyInstaller compatibility patches EARLY
os.environ.update({
    'TRITON_DISABLE': '1',
    'TORCH_DISABLE_TRITON_LIBRARY': '1',
    'TORCH_COMPILE_DISABLE': '1',
    'TORCH_JIT': '0',
    'TORCH_TRITON_DISABLE': '1',
    'USE_TRITON': '0',
    'TORCH_DISABLE_TRITON_OPS': '1',
    'TORCH_DISABLE_TRITON_REGISTRATION': '1',
    'TORCHDYNAMO_DISABLE': '1',
    'TORCH_DYNAMO_DISABLE': '1'
})

logging.info("  [TEST] Environment variables set")

# Comprehensive triton blocking
import types

class SafeTritonBlocker:
    def __getattr__(self, name):
        if name.startswith('_') and name != '__class__':
            raise AttributeError(f"'SafeTritonBlocker' object has no attribute '{name}'")
        return SafeTritonBlocker()
    
    def __call__(self, *args, **kwargs):
        return SafeTritonBlocker()
    
    def __bool__(self):
        return False
    
    def __iter__(self):
        return iter([])
    
    def __getitem__(self, key):
        return SafeTritonBlocker()

# Block triton completely
triton_blocker = SafeTritonBlocker()
triton_modules = [
    'triton', 'triton.language', 'triton.compiler', 'triton.runtime',
    'triton.ops', 'triton.testing', 'triton.backends', 'triton._C'
]

for module_name in triton_modules:
    sys.modules[module_name] = triton_blocker

logging.info("  [TEST] Triton modules blocked")

# Set nnUNet environment
PROJECT_ROOT = Path.cwd()
SEGMENTATION_MODEL_PATH = PROJECT_ROOT / "models" / "segmentation_2"
SEG_DIR = SEGMENTATION_MODEL_PATH / "nnUNet_results"

os.environ["nnUNet_raw"] = str(PROJECT_ROOT / "_nn_raw")
os.environ["nnUNet_preprocessed"] = str(PROJECT_ROOT / "_nn_pre")
os.environ["nnUNet_results"] = str(SEG_DIR)

logging.info(f"  [TEST] nnUNet_results: {os.environ['nnUNet_results']}")
logging.info(f"  [TEST] SEG_DIR exists: {SEG_DIR.exists()}")

# Now import torch and nnunet
logging.info("  [TEST] Importing torch...")
import torch

# Disable torch JIT
if hasattr(torch.jit, '_state'):
    try:
        torch.jit._state.disable()
        logging.info("  [TEST]   Torch JIT disabled")
    except:
        logging.info("  [TEST] ⚠️ Could not disable torch JIT")

logging.info("  [TEST] Importing nnUNet...")
from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

# Pre-import trainer classes
logging.info("  [TEST] Pre-importing trainer classes...")
try:
    import nnunetv2.training.nnUNetTrainer.nnUNetTrainer as trainer_module
    
    # Try to import the specific trainer
    try:
        from nnunetv2.training.nnUNetTrainer.nnUNetTrainer import nnUNetTrainer_50epochs
        logging.info("  [TEST]   nnUNetTrainer_50epochs imported successfully")
    except ImportError as e:
        logging.info(f"  [TEST]  Failed to import nnUNetTrainer_50epochs: {e}")
        logging.info("  [TEST] Available trainers:")
        for attr in dir(trainer_module):
            if 'Trainer' in attr and not attr.startswith('_'):
                logging.info(f"  [TEST]   - {attr}")
    
except Exception as e:
    logging.info(f"  [TEST]  Failed to import trainer module: {e}")

def create_predictor():
    """Create nnUNet predictor"""
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda:0" if use_cuda else "cpu")
    logging.info(f"  [TEST] CUDA available: {use_cuda}, using device: {device}")
    
    try:
        predictor = nnUNetPredictor(
            tile_step_size=0.5,
            use_gaussian=True,
            use_mirroring=True,
            perform_everything_on_device=use_cuda,
            device=device,
            allow_tqdm=True
        )
        logging.info("  [TEST]   Predictor created successfully")
        return predictor
    except Exception as e:
        logging.info(f"  [TEST]  Failed to create predictor: {e}")
        raise

def test_model_loading():
    """Test loading the segmentation model"""
    logging.info("\n  [TEST] Testing model loading...")
    
    dataset = "Dataset001_BoneRegion"
    model_path = SEG_DIR / dataset / "nnUNetTrainer_50epochs__nnUNetPlans__2d"
    
    logging.info(f"  [TEST] Model path: {model_path}")
    logging.info(f"  [TEST] Model path exists: {model_path.exists()}")
    
    if not model_path.exists():
        logging.info("  [TEST]  Model path does not exist!")
        return None
    
    # Check critical files
    critical_files = [
        model_path / "dataset.json",
        model_path / "plans.json",
        model_path / "fold_0" / "checkpoint_best.pth"
    ]
    
    logging.info("  [TEST] Checking critical files:")
    for file_path in critical_files:
        exists = file_path.exists()
        size = file_path.stat().st_size / (1024*1024) if exists else 0
        logging.info(f"  [TEST]   {file_path.name}: {' ' if exists else '❌'} ({size:.1f} MB)")
    
    try:
        predictor = create_predictor()
        logging.info("  [TEST] Initializing model from trained weights...")
        
        predictor.initialize_from_trained_model_folder(
            str(model_path), 
            use_folds=(0,), 
            checkpoint_name="checkpoint_best.pth"
        )
        
        logging.info("  [TEST]   Model loaded successfully!")
        return predictor
        
    except Exception as e:
        logging.info(f"  [TEST]  Model loading failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_segmentation(predictor, image_path):
    """Test segmentation on image"""
    logging.info(f"\n  [TEST] Testing segmentation on: {image_path}")
    
    if not Path(image_path).exists():
        logging.info(f"  [TEST]  Image not found: {image_path}")
        return None
    
    try:
        # Load image
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            # Try with PIL
            pil_image = Image.open(image_path).convert('L')
            image = np.array(pil_image)
        
        logging.info(f"  [TEST] Image loaded: {image.shape}, dtype: {image.dtype}")
        
        # Preprocess (resize to model input size)
        logging.info("  [TEST] Preprocessing image...")
        resized = cv2.resize(image, (256, 1024), interpolation=cv2.INTER_AREA)
        logging.info(f"  [TEST] Resized to: {resized.shape}")
        
        # Convert to tensor
        tensor = torch.from_numpy(resized.astype(np.float32)[None, None]).to(predictor.device)
        logging.info(f"  [TEST] Tensor shape: {tensor.shape}, device: {tensor.device}")
        
        # Run prediction
        logging.info("  [TEST] Running segmentation inference...")
        start_time = time.time()
        
        with torch.no_grad():
            logits = predictor.predict_sliding_window_return_logits(tensor)
        
        if logits.ndim == 4:
            logits = logits[:, 0]
        
        prediction = torch.argmax(logits, dim=0).cpu().numpy().astype(np.uint8)
        
        elapsed = time.time() - start_time
        logging.info(f"  [TEST]   Segmentation completed in {elapsed:.2f}s")
        logging.info(f"  [TEST] Output shape: {prediction.shape}")
        logging.info(f"  [TEST] Unique labels: {np.unique(prediction)}")
        
        # Save result
        output_path = Path(image_path).parent / "test_segmentation_result.png"
        cv2.imwrite(str(output_path), prediction * 50)  # Scale for visibility
        logging.info(f"  [TEST] Result saved to: {output_path}")
        
        return prediction
        
    except Exception as e:
        logging.info(f"  [TEST]  Segmentation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main test function"""
    logging.info("  [TEST] Starting nnUNet segmentation test")
    logging.info("=" * 60)
    
    # Test data path
    test_image = Path("data/PLANAR/ATL/0000085709/20250305/ant_original.png")
    
    if not test_image.exists():
        logging.info(f"  [TEST]  Test image not found: {test_image}")
        logging.info("  [TEST] Please ensure the test image exists")
        return
    
    logging.info(f"  [TEST] Test image: {test_image}")
    logging.info(f"  [TEST] Image exists: {test_image.exists()}")
    
    # Test model loading
    predictor = test_model_loading()
    if predictor is None:
        logging.info("  [TEST]  Cannot proceed without model")
        return
    
    # Test segmentation
    result = test_segmentation(predictor, test_image)
    if result is not None:
        logging.info("\n  [TEST]   Segmentation test completed successfully!")
        logging.info("  [TEST] Model and environment are working correctly")
    else:
        logging.info("\n  [TEST]  Segmentation test failed")
    
    logging.info("=" * 60)

if __name__ == "__main__":
    main()