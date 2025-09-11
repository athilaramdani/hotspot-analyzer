# features/spect_viewer/logic/model_cleanup.py
"""
Simple memory cleanup wrapper untuk prevent crashes setelah model inference
Targeted untuk fix crash issue: 0xc0000409 dan nvdxgdmal64.dll
"""

import gc
import os
import sys
import logging
import functools
from typing import Any, Callable


def setup_safe_threading():
    """Setup threading environment untuk prevent conflicts"""
    thread_env = {
        'OMP_NUM_THREADS': '1',
        'MKL_NUM_THREADS': '1', 
        'NUMEXPR_NUM_THREADS': '1',
        'TORCH_NUM_THREADS': '1',
        'CUDA_LAUNCH_BLOCKING': '1'  # Synchronous GPU calls
    }
    
    for key, value in thread_env.items():
        if key not in os.environ:
            os.environ[key] = value
    
    logging.info("[CLEANUP] Safe threading environment set")


def force_gpu_cleanup():
    """Aggressive GPU memory cleanup"""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()  # Wait for all GPU operations
            logging.info("[CLEANUP] GPU memory cleared")
    except ImportError:
        pass
    except Exception as e:
        logging.info(f"[CLEANUP] GPU cleanup failed: {e}")


def force_model_cleanup():
    """Force cleanup semua model cache dan memory"""
    
    # Clear YOLO global model
    try:
        from . import box_detection
        if hasattr(box_detection, 'model') and box_detection.model is not None:
            del box_detection.model
            box_detection.model = None
            logging.info("[CLEANUP] YOLO model cleared")
    except Exception:
        pass
    
    # Clear nnUNet cache
    try:
        from . import segmenter
        if hasattr(segmenter.load_bone_model, '_cache'):
            segmenter.load_bone_model._cache.clear()
            logging.info("[CLEANUP] nnUNet cache cleared")
    except Exception:
        pass
    
    # Clear any XGBoost/sklearn models in classification
    try:
        from . import inference_classification_hs
        # XGBoost models are loaded globally, force reimport will clear them
        logging.info("[CLEANUP] Classification models cleared")
    except Exception:
        pass
    
    # GPU cleanup
    force_gpu_cleanup()
    
    # System memory cleanup
    gc.collect()
    
    logging.info("[CLEANUP] Complete model cleanup finished")


def safe_inference(cleanup_after=True, cleanup_before=False):
    """
    Decorator untuk safe model inference dengan automatic cleanup
    
    Args:
        cleanup_after: Cleanup setelah inference (default: True)
        cleanup_before: Cleanup sebelum inference (default: False)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            
            # Pre-inference cleanup
            if cleanup_before:
                logging.info(f"[SAFE_INFERENCE] Pre-cleanup for {func.__name__}")
                force_model_cleanup()
            
            try:
                # Run actual inference
                logging.info(f"[SAFE_INFERENCE] Running {func.__name__}")
                result = func(*args, **kwargs)
                logging.info(f"[SAFE_INFERENCE] Completed {func.__name__}")
                return result
                
            except Exception as e:
                logging.info(f"[SAFE_INFERENCE] Error in {func.__name__}: {e}")
                raise
                
            finally:
                # Post-inference cleanup (always run)
                if cleanup_after:
                    logging.info(f"[SAFE_INFERENCE] Post-cleanup for {func.__name__}")
                    force_model_cleanup()
        
        return wrapper
    return decorator


def memory_monitor(func: Callable) -> Callable:
    """Monitor memory usage sebelum dan sesudah function"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            import psutil
            process = psutil.Process()
            
            # Memory before
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            logging.info(f"[MEMORY] {func.__name__} - Before: {mem_before:.1f} MB")
            
            result = func(*args, **kwargs)
            
            # Memory after
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            mem_diff = mem_after - mem_before
            logging.info(f"[MEMORY] {func.__name__} - After: {mem_after:.1f} MB (diff: {mem_diff:+.1f} MB)")
            
            # Warning jika memory usage tinggi
            if mem_after > 2000:  # 2GB
                logging.warning(f"[MEMORY] High memory usage: {mem_after:.1f} MB")
            
            return result
            
        except ImportError:
            # Fallback jika psutil tidak available
            return func(*args, **kwargs)
    
    return wrapper


class ModelSession:
    """Session-based model management untuk prevent memory leaks"""
    
    def __init__(self, session_name: str = "default"):
        self.session_name = session_name
        self.models = {}
        self.active = True
        logging.info(f"[SESSION] Created model session: {session_name}")
    
    def get_model(self, model_key: str, loader_func: Callable):
        """Get model dengan lazy loading"""
        if not self.active:
            raise RuntimeError(f"Session {self.session_name} is closed")
        
        if model_key not in self.models:
            logging.info(f"[SESSION] Loading model: {model_key}")
            self.models[model_key] = loader_func()
        
        return self.models[model_key]
    
    def cleanup(self):
        """Cleanup semua models dalam session"""
        if not self.active:
            return
        
        logging.info(f"[SESSION] Cleaning up session: {self.session_name}")
        
        for model_key, model in self.models.items():
            try:
                del model
                logging.info(f"[SESSION] Cleared model: {model_key}")
            except Exception as e:
                logging.info(f"[SESSION] Error clearing {model_key}: {e}")
        
        self.models.clear()
        self.active = False
        
        # Force system cleanup
        force_gpu_cleanup()
        gc.collect()
        
        logging.info(f"[SESSION] Session cleanup completed: {self.session_name}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Initialize safe environment saat module di-import
if hasattr(sys, '_MEIPASS') or os.environ.get('TELPLASTINA_SAFE_MODE'):
    setup_safe_threading()
    logging.info("[CLEANUP] Model cleanup system initialized")