# box_detection.py
"""
YOLO Box Detection with DICOM Integration
Integrates with dicom_loader for direct frame processing
"""

import sys
import traceback
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
    YOLO_MODEL_PATH, 
    get_hotspot_files, 
    extract_study_date_from_dicom, 
    generate_filename_stem
)
from features.dicom_import.logic.dicom_loader import load_frames_and_metadata

# Initialize YOLO model
print(f"[YOLO] Loading model from: {YOLO_MODEL_PATH}")
if not YOLO_MODEL_PATH.exists():
    raise FileNotFoundError(f"YOLO model not found at: {YOLO_MODEL_PATH}")

model = YOLO(str(YOLO_MODEL_PATH))
print(f"[YOLO] Model loaded successfully")


def inference_detection_from_array(frame_array: np.ndarray) -> List[Dict]:
    """
    Run YOLO inference directly on numpy array (frame from DICOM)
    
    Args:
        frame_array: Numpy array of the image frame
        
    Returns:
        List of detection results with bbox, confidence, and label
    """
    try:
        # Ensure frame is in proper format
        if frame_array.dtype != np.uint8:
            # Normalize to 0-255 range
            frame_norm = (frame_array.astype(np.float32) - frame_array.min())
            frame_norm /= max(frame_norm.max(), 1)
            frame_array = (frame_norm * 255).astype(np.uint8)
        
        # Convert to RGB if grayscale (YOLO expects 3 channels)
        if len(frame_array.shape) == 2:
            frame_array = np.stack([frame_array] * 3, axis=-1)
        
        # Run YOLO inference
        results = model(frame_array)
        
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
        results = model(image_path)
        
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
    Process DICOM file for hotspot detection using YOLO
    
    Args:
        dicom_path: Path to DICOM file
        patient_id: Patient ID
        session_code: Session code (extracted from path if None)
        
    Returns:
        Dictionary indicating success for each view
    """
    try:
        print(f"[DETECTION] Processing DICOM: {dicom_path}")
        
        # Load frames from DICOM
        frames_dict, metadata = load_frames_and_metadata(str(dicom_path))
        
        if not frames_dict:
            print(f"[DETECTION ERROR] No frames loaded from {dicom_path}")
            return {"anterior": False, "posterior": False}
        
        # Extract study date
        study_date = extract_study_date_from_dicom(dicom_path)
        
        # Extract session code from path if not provided
        if not session_code:
            session_code = dicom_path.parent.parent.name
        
        print(f"[DETECTION] Patient: {patient_id}, Session: {session_code}, Study Date: {study_date}")
        print(f"[DETECTION] Loaded {len(frames_dict)} frames: {list(frames_dict.keys())}")
        
        results = {"anterior": False, "posterior": False}
        
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
                
                # Get output paths
                hotspot_files = get_hotspot_files(patient_id, session_code, view_type, study_date)
                xml_output_path = Path(hotspot_files['xml_file'])
                
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
                
                # Run YOLO detection
                print(f"[DETECTION] Running YOLO on {view_full} view...")
                detections = inference_detection_from_array(processed_frame)
                
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


def run_yolo_detection_for_patient(scan_path: Path, patient_id: str) -> Dict[str, bool]:
    """
    Main function to run YOLO detection for a patient scan
    
    Args:
        scan_path: Path to DICOM file
        patient_id: Patient ID
        
    Returns:
        Dictionary indicating success for each view
    """
    try:
        print(f"[YOLO WRAPPER] Starting detection for patient {patient_id}")
        print(f"[YOLO WRAPPER] DICOM file: {scan_path}")
        
        # Extract session code from path structure
        session_code = scan_path.parent.parent.name
        
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


# For backward compatibility
def inference_detection(path_image: str) -> List[Dict]:
    """
    Backward compatibility function
    """
    return inference_detection_from_path(path_image)


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