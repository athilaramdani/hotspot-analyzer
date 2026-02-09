# features/spect_viewer/logic/classification_wrapper.py - UPDATED WITH XML CREATION

import sys
from pathlib import Path
import json
import cv2
import numpy as np
import xml.etree.ElementTree as ET
from core.config.paths import CLASSIFICATION_MODEL_PATH
from core.config.paths import get_classification_files # Pastikan ini di-import
import logging
logging.info(">>>>>> [BUKTI] MEMUAT classification_wrapper.py VERSI TERBARU <<<<<<") # <-- TAMBAHKAN INI

def setup_classification_path():
    """Add classification model path to Python path"""
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))

def load_xml_bounding_boxes(xml_path: Path) -> list:
    """Load bounding boxes from XML file and convert to expected format"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        bboxes = []
        for obj in root.findall('object'):
            name = obj.find('name').text
            bbox_elem = obj.find('bndbox')
            
            xmin = int(bbox_elem.find('xmin').text)
            ymin = int(bbox_elem.find('ymin').text)
            xmax = int(bbox_elem.find('xmax').text)
            ymax = int(bbox_elem.find('ymax').text)
            
            bboxes.append({
                'label': name,
                'bbox': [xmin, ymin, xmax, ymax],
                'xmin': xmin,
                'ymin': ymin, 
                'xmax': xmax,
                'ymax': ymax
            })
        
        return bboxes
        
    except Exception as e:
        logging.info(f"Failed to load XML bounding boxes: {e}")
        return []

def create_classification_xml(classification_json_path: Path, output_xml_path: Path, 
                            original_image_width: int = 512, original_image_height: int = 512) -> bool:
    """
      NEW: Convert classification JSON to XML format
    
    Args:
        classification_json_path: Path to classification JSON file
        output_xml_path: Output path for classification XML
        original_image_width: Original image width for XML
        original_image_height: Original image height for XML
        
    Returns:
        bool: Success status
    """
    try:
        # Load classification JSON
        with open(classification_json_path, 'r') as f:
            classification_data = json.load(f)
        
        patient_info = classification_data.get("patient_info", {})
        hotspots = classification_data.get("hotspots", [])
        
        if not hotspots:
            logging.info(f"[XML CREATE] No hotspots found in classification JSON")
            return False
        
        # Create XML structure (PASCAL VOC format)
        annotation = ET.Element("annotation")
        
        # Add folder
        folder = ET.SubElement(annotation, "folder")
        folder.text = "classification_results"
        
        # Add filename  
        filename = ET.SubElement(annotation, "filename")
        filename.text = f"{patient_info.get('filename_stem', 'unknown')}_{patient_info.get('view', 'unknown')}_classification.png"
        
        # Add path
        path = ET.SubElement(annotation, "path")
        path.text = str(output_xml_path.parent / filename.text)
        
        # Add source
        source = ET.SubElement(annotation, "source")
        database = ET.SubElement(source, "database")
        database.text = "Hotspot Classification Results"
        
        # Add size
        size = ET.SubElement(annotation, "size")
        width = ET.SubElement(size, "width")
        width.text = str(original_image_width)
        height = ET.SubElement(size, "height")
        height.text = str(original_image_height)
        depth = ET.SubElement(size, "depth")
        depth.text = "1"  # Grayscale
        
        # Add segmented
        segmented = ET.SubElement(annotation, "segmented")
        segmented.text = "0"
        
        # Add objects (hotspots with classification results)
        for hotspot in hotspots:
            obj = ET.SubElement(annotation, "object")
            
            # Object name (prediction result)
            name = ET.SubElement(obj, "name")
            name.text = hotspot.get("prediction", "Unknown")  #   Abnormal or Normal from classification
            
            # Pose
            pose = ET.SubElement(obj, "pose")
            pose.text = "Unspecified"
            
            # Truncated
            truncated = ET.SubElement(obj, "truncated")
            truncated.text = "0"
            
            # Difficult
            difficult = ET.SubElement(obj, "difficult")
            difficult.text = "0"
            
            # Bounding box
            bounding_box = hotspot.get("bounding_box", {})
            bndbox = ET.SubElement(obj, "bndbox")
            
            xmin = ET.SubElement(bndbox, "xmin")
            xmin.text = str(bounding_box.get("xmin", 0))
            
            ymin = ET.SubElement(bndbox, "ymin")
            ymin.text = str(bounding_box.get("ymin", 0))
            
            xmax = ET.SubElement(bndbox, "xmax")
            xmax.text = str(bounding_box.get("xmax", 0))
            
            ymax = ET.SubElement(bndbox, "ymax")
            ymax.text = str(bounding_box.get("ymax", 0))
            
            #   NEW: Add classification-specific attributes as comments
            # (Can't use custom attributes in standard PASCAL VOC, but we can add comments)
            comment_data = {
                "segment": hotspot.get("segment", "unknown"),
                "probability_normal": hotspot.get("probability_normal", 0.0),
                "probability_abnormal": hotspot.get("probability_abnormal", 0.0),
                "hotspot_pixels": hotspot.get("area_measurements", {}).get("hotspot_pixels", 0),
                "hotspot_mm2": hotspot.get("area_measurements", {}).get("hotspot_mm2", 0.0)
            }
            
            # Add as XML comment within the object
            comment_text = f" Classification data: {json.dumps(comment_data)} "
            obj.append(ET.Comment(comment_text))
        
        # Create tree and write to file
        tree = ET.ElementTree(annotation)
        ET.indent(tree, space="  ", level=0)  # Pretty formatting
        
        # Write XML file
        tree.write(output_xml_path, encoding="utf-8", xml_declaration=True)
        
        logging.info(f"[XML CREATE]   Created classification XML: {output_xml_path.name}")
        logging.info(f"[XML CREATE] Converted {len(hotspots)} classified hotspots")
        
        return True
        
    except Exception as e:
        logging.info(f"[XML CREATE]  Failed to create classification XML: {e}")
        return False

def get_image_dimensions_from_files(patient_folder: Path, filename_stem: str, view: str) -> tuple[int, int]:
    """
    Get actual image dimensions from existing files
    
    Args:
        patient_folder: Patient folder path
        filename_stem: Filename stem (patient_id_study_date)
        view: View name (anterior/posterior)
        
    Returns:
        tuple: (width, height) or (512, 512) as fallback
    """
    try:
        # Try to get dimensions from original PNG
        original_png = patient_folder / f"{filename_stem}_{view}_original.png"
        
        if original_png.exists():
            from PIL import Image
            with Image.open(original_png) as img:
                return img.size  # Returns (width, height)
        
        # Fallback to default SPECT dimensions
        return (512, 512)
        
    except Exception as e:
        logging.info(f"[XML CREATE] Could not determine image dimensions, using default: {e}")
        return (512, 512)

def compare_xml_files(original_xml: Path, classification_xml: Path) -> dict:
    """
    Compare original YOLO XML with classification XML to show filtering results
    
    Args:
        original_xml: Path to original YOLO XML
        classification_xml: Path to classification XML
        
    Returns:
        dict: Comparison results
    """
    try:
        comparison = {
            "original_count": 0,
            "classification_count": 0,
            "removed_hotspots": 0,
            "original_classes": {},
            "classification_classes": {}
        }
        
        # Parse original XML
        if original_xml.exists():
            orig_tree = ET.parse(original_xml)
            orig_objects = orig_tree.findall('.//object')
            comparison["original_count"] = len(orig_objects)
            
            for obj in orig_objects:
                class_name = obj.find('name').text
                comparison["original_classes"][class_name] = comparison["original_classes"].get(class_name, 0) + 1
        
        # Parse classification XML
        if classification_xml.exists():
            class_tree = ET.parse(classification_xml)
            class_objects = class_tree.findall('.//object')
            comparison["classification_count"] = len(class_objects)
            
            for obj in class_objects:
                class_name = obj.find('name').text
                comparison["classification_classes"][class_name] = comparison["classification_classes"].get(class_name, 0) + 1
        
        # Calculate differences
        comparison["removed_hotspots"] = comparison["original_count"] - comparison["classification_count"]
        
        return comparison
        
    except Exception as e:
        logging.info(f"[XML COMPARE] Error comparing XML files: {e}")
        return {}

def run_classification_inference(raw_path: str, segment_path: str, hotspot_path: str, xml_path: str):
    """
    Run classification inference with automatic colored-to-grayscale conversion
    
    Args:
        raw_path: Path to original PNG file ([patient_id]_[study_date]_[view]_original.png)
        segment_path: Path to segmentation file (colored or grayscale)  
        hotspot_path: Path to hotspot mask (grayscale)
        xml_path: Path to XML bounding box file
        
    Returns:
        tuple: (classification_results_list, classification_mask)
    """
    try:
        logging.info(f"[DEBUG] Starting classification inference with automatic conversion")
        logging.info(f"[DEBUG] Raw PNG path: {raw_path}")
        logging.info(f"[DEBUG] Segment path: {segment_path}")
        logging.info(f"[DEBUG] Hotspot path: {hotspot_path}")
        logging.info(f"[DEBUG] XML path: {xml_path}")
        
        # Check if files exist
        for name, path in [("Raw PNG", raw_path), ("Segment", segment_path), ("Hotspot", hotspot_path), ("XML", xml_path)]:
            if not Path(path).exists():
                logging.info(f"[ERROR] {name} file does not exist: {path}")
                return [], None
            else:
                logging.info(f"[DEBUG] {name} file exists: {Path(path).stat().st_size} bytes")
        
        # Setup paths
        setup_classification_path()
        logging.info(f"[DEBUG] Python path setup completed")
        
        # Import classification module
        import inference_classification_hs as clf_module
        logging.info(f"[DEBUG] Module imported successfully")
        
        # Update model paths
        from core.config.paths import CLASSIFICATION_XGBOOST_MODEL, CLASSIFICATION_SCALER_MODEL
        clf_module.MODEL_PATH = str(CLASSIFICATION_XGBOOST_MODEL)
        clf_module.SCALER_PATH = str(CLASSIFICATION_SCALER_MODEL)
        logging.info(f"[DEBUG] Model paths updated")
        
        # Check model files
        if not Path(clf_module.MODEL_PATH).exists():
            logging.info(f"[ERROR] Model file not found: {clf_module.MODEL_PATH}")
            return [], None
        if not Path(clf_module.SCALER_PATH).exists():
            logging.info(f"[ERROR] Scaler file not found: {clf_module.SCALER_PATH}")
            return [], None
        
        # Reload models
        import joblib
        clf_module.model = joblib.load(clf_module.MODEL_PATH)
        clf_module.scaler = joblib.load(clf_module.SCALER_PATH)
        logging.info(f"[DEBUG] Models loaded successfully")
        
        # Load XML bounding boxes
        xml_bboxes = load_xml_bounding_boxes(Path(xml_path))
        if not xml_bboxes:
            logging.info(f"[ERROR] No bounding boxes found in XML: {xml_path}")
            return [], None
        
        logging.info(f"[DEBUG] Loaded {len(xml_bboxes)} bounding boxes from XML")
        for i, bbox in enumerate(xml_bboxes):
            logging.info(f"[DEBUG] Bbox {i}: {bbox}")
        
        # Test image loading
        try:
            test_raw = cv2.imread(raw_path, cv2.IMREAD_GRAYSCALE)  # Original PNG file
            test_segment = cv2.imread(segment_path, cv2.IMREAD_COLOR)  # Check if colored
            test_hotspot = cv2.imread(hotspot_path, cv2.IMREAD_GRAYSCALE)  # Hotspot PNG
            
            # Check if segment is colored
            is_colored = 'colored' in Path(segment_path).name
            logging.info(f"[DEBUG] Image loading test:")
            logging.info(f"  Raw: {test_raw.shape if test_raw is not None else 'Failed'}")
            logging.info(f"  Segment: {test_segment.shape if test_segment is not None else 'Failed'} (colored: {is_colored})")
            logging.info(f"  Hotspot: {test_hotspot.shape if test_hotspot is not None else 'Failed'}")
            
            if test_raw is None or test_segment is None or test_hotspot is None:
                logging.info(f"[ERROR] Failed to load one or more images")
                return [], None
                
        except Exception as e:
            logging.info(f"[ERROR] Image loading test failed: {e}")
            return [], None
        
        #   Use inference_classification with automatic conversion
        logging.info(f"[DEBUG] Starting inference_classification with automatic colored-to-grayscale conversion...")
        logging.info(f"[DEBUG] Conversion will create: {Path(segment_path).stem}_grayscaledSegmentation.png if needed")
        result_list, result_mask = clf_module.inference_classification(
            path_raw=raw_path,          # Original PNG file
            path_segment=segment_path,   # Colored PNG (will be auto-converted to grayscale)
            path_hotspot=hotspot_path,   # Hotspot PNG
            path_xml=xml_bboxes         # List of bboxes
        )
        
        logging.info(f"[DEBUG] Classification completed")
        logging.info(f"[DEBUG] Result list length: {len(result_list) if result_list else 0}")
        logging.info(f"[DEBUG] Result mask shape: {result_mask.shape if result_mask is not None else 'None'}")
        
        if result_list:
            for i, result in enumerate(result_list):
                logging.info(f"[DEBUG] Result {i}: prediction={result.get('prediction', 'Unknown')}, "
                     f"prob_abnormal={result.get('probability_abnormal', 0):.3f}")
        
        return result_list, result_mask
        
    except Exception as e:
        logging.info(f"[ERROR] Classification inference failed: {e}")
        import traceback
        logging.info(f"[ERROR] Full traceback: {traceback.format_exc()}")
        return [], None

def run_classification_for_patient(dicom_path: Path, patient_id: str, study_date: str, source_is_editor: bool = False) -> bool:
    """
      FIXED: Run hotspot classification with proper temp directory file checking
    """
    try:
        session_code = dicom_path.parent.parent.name
        patient_folder = dicom_path.parent
        filename_stem = f"{patient_id}_{study_date}"
        
        logging.info(f"     Starting classification for patient {patient_id}")
        logging.info(f"     Study date: {study_date}")
        logging.info(f"     Session: {session_code}")
        logging.info(f"     Grayscale conversion: Enabled")
        
        results = []
        
        # Process both views with grayscale conversion
        for view in ['anterior', 'posterior']:
            view_short = 'ant' if view == 'anterior' else 'post'
            
            logging.info(f"     Processing {view} view with grayscale conversion...")
            
            #   FIXED: Get file paths for current working directory (temp folder)
            paths = get_classification_input_paths(patient_folder, filename_stem, view, view_short)
            
            #   FIXED: Check if all required files exist in CURRENT DIRECTORY
            missing_files = []
            for file_type, file_path in paths.items():
                if not file_path.exists():
                    missing_files.append(f"{file_type} ({file_path.name})")
                else:
                    #   DEBUG: Log found files
                    logging.info(f"       Found {file_type}: {file_path.name}")
            
            if missing_files:
                logging.info(f"     Missing files for {view}: {', '.join(missing_files)}")
                results.append(False)
                continue
            
            #   Run classification with files in current directory
            classification_result, classification_mask = run_classification_inference(
                raw_path=str(paths['raw_original']),      # Direct filename in temp dir
                segment_path=str(paths['region_mask']),   # Direct filename in temp dir
                hotspot_path=str(paths['hotspot_mask']),  # Direct filename in temp dir
                xml_path=str(paths['xml_file'])          # Direct filename in temp dir
            )
            
            if classification_result:
                # Save results (will save in current working directory = temp dir)
                save_classification_results(
                    Path.cwd(), filename_stem, view, classification_result, classification_mask, source_is_editor
                )
                logging.info(f"     {view.title()} classification completed: {len(classification_result)} hotspots classified")
                results.append(True)
            else:
                logging.info(f"     {view.title()} classification failed")
                results.append(False)
        
        success = any(results)
        if success:
            logging.info(f"     Classification completed for patient {patient_id}")
        else:
            logging.info(f"     Classification failed for all views")
            
        return success
        
    except Exception as e:
        logging.info(f"Classification error for patient {patient_id}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
def get_classification_input_paths(patient_folder: Path, filename_stem: str, view: str, view_short: str) -> dict:
    """
      FIXED: Get input file paths for current working directory (temp folder)
    When running in temp directory, all files use the old naming convention
    """
    
    #   FIXED: Since we're running in temp directory, use old naming directly
    # These files were already mapped in run_classification_with_new_paths
    
    return {
        'raw_original': Path(f"{filename_stem}_{view}_original.png"),
        'region_mask': Path(f"{filename_stem}_{view}_colored.png"),
        'hotspot_mask': Path(f"{filename_stem}_{view_short}_hotspot_mask.png"),
        'xml_file': Path(f"{filename_stem}_{view_short}.xml")
    }

def save_classification_results(patient_folder: Path, filename_stem: str, view: str, results: list, mask: any, source_is_editor: bool = False):
    """
      FIXED: Save classification results in current working directory (temp folder)
    """
    try:
        #   FIXED: Save in current directory (temp folder) using old naming
        view_short = "ant" if "anterior" in view.lower() else "post"
        
        # Old naming convention for temp directory
        json_path = Path(f"{filename_stem}_{view_short}_classification.json")
        xml_path = Path(f"{filename_stem}_{view_short}_classification.xml")
        mask_path = Path(f"{filename_stem}_{view}_classification_mask.png")
        
        logging.info(f"     Saving classification results to temp directory:")
        logging.info(f"       JSON: {json_path.name}")
        logging.info(f"       XML: {xml_path.name}")
        logging.info(f"       Mask: {mask_path.name}")
        
        # Convert results to JSON-serializable format
        json_data = {
            "patient_info": {
                "filename_stem": filename_stem,
                "view": view,
                "total_hotspots": len(results)
            },
            "hotspots": []
        }
        
        for i, result in enumerate(results):
            hotspot_data = {
                "id": i,
                "prediction": result.get('prediction', 'Unknown'),
                "probability_normal": float(result.get('probability_normal', 0.0)),
                "probability_abnormal": float(result.get('probability_abnormal', 0.0)),
                "coordinates": result.get('coordinates', []),
                "segment": result.get('segment', 'Unknown'),
                "bounding_box": result.get('bounding_box', {}),
                "area_measurements": result.get('area_measurements', {})
            }
            json_data["hotspots"].append(hotspot_data)
        
        # Save JSON
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        #   Create classification XML from JSON results
        # Get actual image dimensions (fallback to default)
        img_width, img_height = 512, 512  # Default SPECT dimensions
        
        # Convert JSON to XML
        xml_success = create_classification_xml(
            classification_json_path=json_path,
            output_xml_path=xml_path,
            original_image_width=img_width,
            original_image_height=img_height
        )
        
        #   Save mask with PIL (RGB mode)
        if mask is not None:
            from PIL import Image
            
            if len(mask.shape) == 3 and mask.shape[2] == 3:
                # Convert numpy array to PIL Image (RGB mode)
                mask_pil = Image.fromarray(mask, mode='RGB')
                # Save with PIL - preserves RGB order
                mask_pil.save(mask_path)
                logging.info(f"         Saved mask with PIL RGB mode")
            else:
                # Fallback for non-RGB masks
                import cv2
                cv2.imwrite(str(mask_path), mask)
                logging.info(f"       ⚠️ Saved mask without RGB conversion")
        
        logging.info(f"         Classification results saved successfully")
        
    except Exception as e:
        logging.info(f"Failed to save classification results: {e}")
        import traceback
        traceback.print_exc()