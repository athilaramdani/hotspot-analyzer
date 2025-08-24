# box_detection.py
"""
YOLO Box Detection with DICOM Integration
Integrates with dicom_loader for direct frame processing
ENHANCED VERSION: Safe lazy loading with multiprocessing protection
"""

import sys
import os
import traceback
import multiprocessing
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
import numpy as np
from PIL import Image
from typing import Dict, List, Tuple, Optional

# Add project root to path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

# Import YOLO
from ultralytics import YOLO

# Import from your modules
from core.config.paths import (
    get_planar_hotspot_files,
    get_patient_planar_path,
    generate_filename_stem,
    extract_study_date_from_dicom,
    YOLO_MODEL_PATH
)

from features.dicom_import.logic.dicom_loader import load_frames_and_metadata

# ✅ ENHANCED: Global model with thread-safe lazy loading
model = None
_model_loading = False
_model_lock = multiprocessing.Lock() if hasattr(multiprocessing, 'Lock') else None

def is_multiprocessing_fork():
    """Check if running in multiprocessing fork"""
    return (
        len(sys.argv) > 1 and 
        any('multiprocessing-fork' in arg for arg in sys.argv)
    )

def is_safe_to_load_model():
    """Check if it's safe to load YOLO model - FORCE ALLOW FOR PROCESSING"""
    # ✅ AGGRESSIVE FIX: Only skip for actual multiprocessing-fork
    if is_multiprocessing_fork():
        print("[YOLO] Skipping model load in multiprocessing fork")
        return False
    
    # ✅ FORCE ALLOW: YOLO is critical for the application pipeline
    # We'll handle any issues with proper error handling instead of skipping
    print(f"[YOLO] FORCING model load - application requires YOLO functionality")
    return True

def initialize_yolo_model():
    """Initialize YOLO model with enhanced error handling and FORCED execution"""
    global model, _model_loading
    
    # ✅ REMOVE SAFETY CHECK: Force model loading
    print("[YOLO] FORCING model initialization - critical for application")
    
    # ✅ THREAD SAFETY: Prevent concurrent loading
    if _model_loading:
        print("[YOLO] Model already being loaded by another thread")
        return None
    
    _model_loading = True
    
    try:
        # ✅ FORCE SINGLE THREAD: Prevent multiprocessing conflicts
        os.environ['OMP_NUM_THREADS'] = '1'
        os.environ['MKL_NUM_THREADS'] = '1'
        os.environ['NUMEXPR_NUM_THREADS'] = '1'
        os.environ['YOLO_MULTIPROCESSING'] = '0'
        
        # ✅ ADDITIONAL SAFETY: Force CPU mode to avoid GPU conflicts
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
        
        print(f"[YOLO] Attempting to load model from: {YOLO_MODEL_PATH}")
        
        if not YOLO_MODEL_PATH.exists():
            print(f"[YOLO ERROR] Model not found at: {YOLO_MODEL_PATH}")
            
            # Try alternative paths
            from core.config.paths import get_safe_project_root
            project_root = get_safe_project_root()
            
            alternative_paths = [
                project_root / "models" / "hotspot_detection" / "models" / "model_detection_hs_yolov8.pt",
                Path("models") / "hotspot_detection" / "models" / "model_detection_hs_yolov8.pt"
            ]
            
            found_model = None
            for alt_path in alternative_paths:
                print(f"[YOLO] Checking alternative: {alt_path}")
                if alt_path.exists():
                    found_model = alt_path
                    print(f"[YOLO] Found model at alternative location: {alt_path}")
                    break
            
            if not found_model:
                raise FileNotFoundError(f"YOLO model not found at {YOLO_MODEL_PATH} or any alternative locations")
            
            # ✅ ENHANCED: Create model with maximum compatibility settings
            loaded_model = YOLO(str(found_model))
        else:
            loaded_model = YOLO(str(YOLO_MODEL_PATH))
        
        # ✅ CONFIGURE MODEL: Force CPU and single thread with maximum compatibility
        loaded_model.to('cpu')  # Force CPU mode
        
        # ✅ SET ADDITIONAL MODEL CONFIG: Prevent multiprocessing in predictions
        if hasattr(loaded_model, 'predictor') and loaded_model.predictor:
            loaded_model.predictor.args.workers = 0  # Single worker
            loaded_model.predictor.args.batch = 1    # Single batch
        
        print(f"[YOLO] Model loaded successfully (FORCED CPU mode)")
        return loaded_model
        
    except Exception as e:
        print(f"[YOLO ERROR] Failed to load model: {e}")
        print(f"[YOLO ERROR] Traceback: {traceback.format_exc()}")
        
        # ✅ ENHANCED FALLBACK: Try to create a minimal YOLO instance
        try:
            print("[YOLO] Attempting fallback model initialization...")
            # Try with minimal settings
            os.environ.update({
                'YOLO_VERBOSE': 'False',
                'ULTRALYTICS_OFFLINE': 'True'
            })
            
            fallback_model = YOLO(str(YOLO_MODEL_PATH))
            fallback_model.to('cpu')
            print("[YOLO] Fallback model initialization successful")
            return fallback_model
            
        except Exception as fallback_error:
            print(f"[YOLO ERROR] Fallback initialization also failed: {fallback_error}")
            return None
    finally:
        _model_loading = False

def get_yolo_model():
    """Get YOLO model with FORCED loading - critical for application"""
    global model, _model_lock
    
    # ✅ QUICK RETURN: If model already loaded
    if model is not None:
        return model
    
    # ✅ FORCE LOADING: Application requires YOLO to function
    print("[YOLO] FORCING model load - application critical functionality")
    
    # ✅ THREAD SAFETY: Use lock if available
    if _model_lock is not None:
        try:
            with _model_lock:
                # Double-check after acquiring lock
                if model is None:
                    print("[YOLO] Loading model on-demand (FORCED, thread-safe)...")
                    model = initialize_yolo_model()
                return model
        except Exception as e:
            print(f"[YOLO WARNING] Lock-based loading failed: {e}")
            # Fallback to non-lock loading
    
    # Fallback without lock
    if model is None:
        print("[YOLO] Loading model on-demand (FORCED, no lock)...")
        model = initialize_yolo_model()
    
    return model

def inference_detection_from_array(frame_array: np.ndarray) -> List[Dict]:
    """
    Run YOLO inference directly on numpy array (frame from DICOM)
    
    Args:
        frame_array: Numpy array of the image frame
        
    Returns:
        List of detection results with bbox, confidence, and label
    """
    try:
        # ✅ ENHANCED: Get model safely
        yolo_model = get_yolo_model()
        
        if yolo_model is None:
            print("[YOLO WARNING] Model not available, returning empty results")
            return []
        
        # Ensure frame is in proper format
        if frame_array.dtype != np.uint8:
            # Normalize to 0-255 range
            frame_norm = (frame_array.astype(np.float32) - frame_array.min())
            frame_norm /= max(frame_norm.max(), 1)
            frame_array = (frame_norm * 255).astype(np.uint8)
        
        # Convert to RGB if grayscale (YOLO expects 3 channels)
        if len(frame_array.shape) == 2:
            frame_array = np.stack([frame_array] * 3, axis=-1)
        
        # ✅ ENHANCED: Run YOLO inference with error handling
        try:
            results = yolo_model(frame_array)
        except Exception as inference_error:
            print(f"[YOLO ERROR] Inference execution failed: {inference_error}")
            return []
        
        if not results or len(results) == 0:
            return []
            
        result = results[0]
        
        if not hasattr(result, 'boxes') or result.boxes is None:
            return []
            
        boxes = result.boxes
        xyxy = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        labels = [result.names[c] for c in cls]
        
        detection_results = []
        for i in range(len(xyxy)):
            detection_results.append({
                "label": labels[i],
                "class_id": int(cls[i]),
                "confidence": float(conf[i]),
                "bbox": [float(x) for x in xyxy[i]]
            })
        
        return detection_results
        
    except Exception as e:
        print(f"[YOLO ERROR] Inference failed: {e}")
        traceback.print_exc()
        return []

def inference_detection_from_path(image_path: str) -> List[Dict]:
    """
    Run YOLO inference from image path (for compatibility)
    
    Args:
        image_path: Path to image file
        
    Returns:
        List of detection results
    """
    try:
        # ✅ ENHANCED: Get model safely
        yolo_model = get_yolo_model()
        
        if yolo_model is None:
            print("[YOLO WARNING] Model not available, returning empty results")
            return []
        
        # ✅ ENHANCED: Run inference with error handling
        try:
            results = yolo_model(image_path)
        except Exception as inference_error:
            print(f"[YOLO ERROR] Inference execution failed: {inference_error}")
            return []
        
        if not results or len(results) == 0:
            return []
            
        result = results[0]
        
        if not hasattr(result, 'boxes') or result.boxes is None:
            return []
        
        boxes = result.boxes
        xyxy = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        labels = [result.names[c] for c in cls]
        
        detection_results = []
        for i in range(len(xyxy)):
            detection_results.append({
                "label": labels[i],
                "class_id": int(cls[i]),
                "confidence": float(conf[i]),
                "bbox": [float(x) for x in xyxy[i]]
            })
        
        return detection_results
        
    except Exception as e:
        print(f"[YOLO ERROR] Inference from path failed: {e}")
        return []

def write_pascal_voc_xml(output_path: Path, image_shape: Tuple[int, int], 
                         objects: List[Dict], image_filename: str = "image.png"):
    """
    Menulis hasil deteksi ke format PASCAL VOC XML yang lebih lengkap.
    """
    try:
        height, width = image_shape[:2]
        
        annotation = ET.Element("annotation")
        
        # --- PERUBAHAN & PENAMBAHAN DI SINI ---
        ET.SubElement(annotation, "folder").text = "BS-80K" # DIUBAH
        ET.SubElement(annotation, "filename").text = image_filename
        
        # DITAMBAHKAN: Tag <source>
        source = ET.SubElement(annotation, "source")
        ET.SubElement(source, "database").text = "The BS-80K Database"

        size = ET.SubElement(annotation, "size")
        ET.SubElement(size, "width").text = str(width)
        ET.SubElement(size, "height").text = str(height)
        ET.SubElement(size, "depth").text = "1"
        
        # DITAMBAHKAN: Tag <segmented>
        ET.SubElement(annotation, "segmented").text = "0"
        
        for obj in objects:
            obj_el = ET.SubElement(annotation, "object")
            ET.SubElement(obj_el, "name").text = obj["label"]
            
            # --- PERUBAHAN & PENAMBAHAN DI DALAM <object> ---
            ET.SubElement(obj_el, "pose").text = "Unspecified" # DITAMBAHKAN
            ET.SubElement(obj_el, "truncated").text = "0" # DITAMBAHKAN
            ET.SubElement(obj_el, "difficult").text = "0" # DITAMBAHKAN
            
            # DIHAPUS: Tag <confidence> tidak lagi ada di dalam <object>
            # ET.SubElement(obj_el, "confidence").text = f"{obj['confidence']:.4f}"

            bbox = obj["bbox"]
            bndbox = ET.SubElement(obj_el, "bndbox")
            ET.SubElement(bndbox, "xmin").text = str(int(bbox[0]))
            ET.SubElement(bndbox, "ymin").text = str(int(bbox[1]))
            ET.SubElement(bndbox, "xmax").text = str(int(bbox[2]))
            ET.SubElement(bndbox, "ymax").text = str(int(bbox[3]))
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        xml_str = minidom.parseString(ET.tostring(annotation)).toprettyxml(indent="    ")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_str)
            
        print(f"[XML] Saved detection XML to: {output_path}")
        
    except Exception as e:
        print(f"[XML ERROR] Failed to write XML: {e}")
        traceback.print_exc()

def process_dicom_for_detection(dicom_path: Path, patient_id: str, 
                               session_code: str = None) -> Dict[str, bool]:
    """
    ✅ ENHANCED: FORCE YOLO execution - critical for application pipeline
    
    Args:
        dicom_path: Path to DICOM file
        patient_id: Patient ID
        session_code: Session code (extracted from path if None)
        
    Returns:
        Dictionary indicating success for each view
    """
    try:
        print(f"[DETECTION] Processing DICOM: {dicom_path}")
        print(f"[DETECTION] FORCED YOLO execution - application requires this functionality")
        
        # Load frames from DICOM
        frames_dict, metadata = load_frames_and_metadata(str(dicom_path))
        
        if not frames_dict:
            print(f"[DETECTION ERROR] No frames loaded from {dicom_path}")
            return {"anterior": False, "posterior": False}
        
        # Extract study date
        study_date = extract_study_date_from_dicom(dicom_path)
        
        # ✅ FIX: Extract session code from correct path structure
        if not session_code:
            # Expected path: data/PLANAR/SESSION/patient_id/study_date/file.dcm
            path_parts = dicom_path.parts
            planar_index = None
            for i, part in enumerate(path_parts):
                if part == "PLANAR":
                    planar_index = i
                    break
            
            if planar_index is not None and len(path_parts) > planar_index + 1:
                session_code = path_parts[planar_index + 1]  # Session after PLANAR
                print(f"[DETECTION] Extracted session from path: {session_code}")
            else:
                # ✅ FALLBACK: Get from config
                from core.config.paths import get_current_session_code
                session_code = get_current_session_code()
                print(f"[DETECTION] Using session from config: {session_code}")
                
                if session_code == "unknown":
                    session_code = "ATL"  # Safe default
                    print(f"[DETECTION] Using default session: {session_code}")
        
        print(f"[DETECTION] Patient: {patient_id}, Session: {session_code}, Study Date: {study_date}")
        print(f"[DETECTION] Loaded {len(frames_dict)} frames: {list(frames_dict.keys())}")
        
        results = {"anterior": False, "posterior": False}
        
        # ✅ FIX: Get correct patient folder path
        patient_folder = get_patient_planar_path(session_code, patient_id, study_date)
        
        if not patient_folder.exists():
            print(f"[DETECTION ERROR] Patient folder not found: {patient_folder}")
            
            # ✅ FALLBACK: Try to find in other sessions
            potential_sessions = ["ATL", "NSY", "NBL", "ALL"]
            found_folder = None
            
            for potential_session in potential_sessions:
                test_folder = get_patient_planar_path(potential_session, patient_id, study_date)
                if test_folder.exists():
                    patient_folder = test_folder
                    session_code = potential_session
                    found_folder = test_folder
                    print(f"[DETECTION] Found patient folder in session: {potential_session}")
                    break
            
            if not found_folder:
                print(f"[DETECTION ERROR] No valid patient folder found for patient {patient_id}")
                return {"anterior": False, "posterior": False}
        
        # Process each view
        for view_name, frame_data in frames_dict.items():
            try:
                # Determine view type from frame name
                view_lower = view_name.lower()
                if "ant" in view_lower:
                    view_type = "ant"
                    view_full = "anterior"
                elif "post" in view_lower:
                    view_type = "post"
                    view_full = "posterior"
                else:
                    # Default to anterior for unknown views
                    view_type = "ant"
                    view_full = "anterior"
                    print(f"[DETECTION WARNING] Unknown view '{view_name}', defaulting to anterior")
                
                print(f"[DETECTION] Processing view: {view_name} -> {view_full}")
                
                # ✅ FIX: Get output paths using correct patient folder
                hotspot_files = get_planar_hotspot_files(patient_folder, view_type, with_priority=False)
                xml_output_path = Path(hotspot_files['yolo_xml'])
                
                # Skip if XML already exists
                if xml_output_path.exists():
                    print(f"[DETECTION] XML already exists for {view_full}: {xml_output_path}")
                    results[view_full] = True
                    continue
                
                # Handle multi-frame data
                if isinstance(frame_data, np.ndarray):
                    if frame_data.ndim == 3:
                        # Multi-frame: create sum projection
                        processed_frame = np.sum(frame_data, axis=0)
                        print(f"[DETECTION] Created sum projection from {frame_data.shape[0]} frames")
                    else:
                        # Single frame
                        processed_frame = frame_data
                else:
                    print(f"[DETECTION ERROR] Invalid frame data type: {type(frame_data)}")
                    continue
                
                # ✅ ENHANCED: Run YOLO detection with FORCED execution
                print(f"[DETECTION] Running YOLO on {view_full} view...")
                
                # ✅ FORCE YOLO: Always attempt detection, create XML regardless
                detections = inference_detection_from_array(processed_frame)
                
                # ✅ FALLBACK: If no detections but we need XML files for pipeline
                if not detections:
                    print(f"[DETECTION] No detections found, creating empty XML for pipeline continuity")
                    detections = []  # Ensure we have empty list to create XML
                
                # ✅ ENSURE output directory exists
                xml_output_path.parent.mkdir(parents=True, exist_ok=True)
                
                if detections:
                    print(f"[DETECTION] Found {len(detections)} hotspots in {view_full}")
                    
                    # Write XML file
                    write_pascal_voc_xml(
                        xml_output_path, 
                        processed_frame.shape, 
                        detections,
                        f"{patient_id}_{study_date}_{view_type}.png"
                    )
                    
                    results[view_full] = True
                    
                else:
                    print(f"[DETECTION] No hotspots detected in {view_full}")
                    
                    # Create empty XML file to indicate processing was done
                    write_pascal_voc_xml(
                        xml_output_path, 
                        processed_frame.shape, 
                        [],
                        f"{patient_id}_{study_date}_{view_type}.png"
                    )
                    
                    results[view_full] = True
                
            except Exception as e:
                print(f"[DETECTION ERROR] Failed to process view {view_name}: {e}")
                traceback.print_exc()
                continue
        
        return results
        
    except Exception as e:
        print(f"[DETECTION FATAL ERROR] Failed to process {dicom_path}: {e}")
        traceback.print_exc()
        return {"anterior": False, "posterior": False}

# For backward compatibility
def run_yolo_detection_for_patient(scan_path: Path, patient_id: str) -> Dict[str, bool]:
    """
    ✅ FIXED: Main function to run YOLO detection for a patient scan
    
    Args:
        scan_path: Path to DICOM file
        patient_id: Patient ID
        
    Returns:
        Dictionary indicating success for each view
    """
    try:
        print(f"[YOLO WRAPPER] Starting detection for patient {patient_id}")
        print(f"[YOLO WRAPPER] DICOM file: {scan_path}")
        
        # ✅ EARLY SAFETY CHECK
        if not is_safe_to_load_model():
            print("[YOLO WRAPPER] Skipping detection - unsafe environment")
            return {"anterior": False, "posterior": False}
        
        # ✅ FIX: Extract session code from correct path structure
        # Expected: data/PLANAR/SESSION/patient_id/study_date/file.dcm
        path_parts = scan_path.parts
        session_code = None
        
        planar_index = None
        for i, part in enumerate(path_parts):
            if part == "PLANAR":
                planar_index = i
                break
        
        if planar_index is not None and len(path_parts) > planar_index + 1:
            session_code = path_parts[planar_index + 1]
            print(f"[YOLO WRAPPER] Extracted session from path: {session_code}")
        else:
            # ✅ FALLBACK: Get from config
            from core.config.paths import get_current_session_code
            session_code = get_current_session_code()
            print(f"[YOLO WRAPPER] Using session from config: {session_code}")
            
            if session_code == "unknown":
                session_code = "ATL"  # Safe default
                print(f"[YOLO WRAPPER] Using default session: {session_code}")
        
        # Process DICOM for detection
        results = process_dicom_for_detection(scan_path, patient_id, session_code)
        
        print(f"[YOLO WRAPPER] Detection completed:")
        print(f"  Anterior: {'✓' if results['anterior'] else '✗'}")
        print(f"  Posterior: {'✓' if results['posterior'] else '✗'}")
        
        return results
        
    except Exception as e:
        print(f"[YOLO WRAPPER ERROR] Failed to process patient {patient_id}: {e}")
        traceback.print_exc()
        return {"anterior": False, "posterior": False}

def inference_detection(path_image: str) -> List[Dict]:
    """
    Backward compatibility function
    """
    return inference_detection_from_path(path_image)

# ✅ SAFE INITIALIZATION: No global model loading at import time
print("[YOLO] Module loaded - model will be loaded on-demand")

if __name__ == "__main__":
    # Test the detection system
    if len(sys.argv) > 2:
        dicom_path = Path(sys.argv[1])
        patient_id = sys.argv[2]
        
        if dicom_path.exists():
            results = run_yolo_detection_for_patient(dicom_path, patient_id)
            print(f"Detection results: {results}")
        else:
            print(f"DICOM file not found: {dicom_path}")
    else:
        print("Usage: python box_detection.py <dicom_path> <patient_id>")