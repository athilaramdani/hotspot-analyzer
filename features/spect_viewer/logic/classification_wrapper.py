# features/spect_viewer/logic/classification_wrapper.py - UPDATED WITH XML CREATION

import sys
from pathlib import Path
import json
import cv2
import numpy as np
import xml.etree.ElementTree as ET
from core.logger import _log
from core.config.paths import CLASSIFICATION_MODEL_PATH

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
        _log(f"Failed to load XML bounding boxes: {e}")
        return []

def create_classification_xml(classification_json_path: Path, output_xml_path: Path, 
                            original_image_width: int = 512, original_image_height: int = 512) -> bool:
    """
    ✅ NEW: Convert classification JSON to XML format
    
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
            _log(f"[XML CREATE] No hotspots found in classification JSON")
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
            name.text = hotspot.get("prediction", "Unknown")  # ✅ Abnormal or Normal from classification
            
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
            
            # ✅ NEW: Add classification-specific attributes as comments
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
        
        _log(f"[XML CREATE] ✅ Created classification XML: {output_xml_path.name}")
        _log(f"[XML CREATE] Converted {len(hotspots)} classified hotspots")
        
        return True
        
    except Exception as e:
        _log(f"[XML CREATE] ❌ Failed to create classification XML: {e}")
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
        _log(f"[XML CREATE] Could not determine image dimensions, using default: {e}")
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
        _log(f"[XML COMPARE] Error comparing XML files: {e}")
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
        _log(f"[DEBUG] Starting classification inference with automatic conversion")
        _log(f"[DEBUG] Raw PNG path: {raw_path}")
        _log(f"[DEBUG] Segment path: {segment_path}")
        _log(f"[DEBUG] Hotspot path: {hotspot_path}")
        _log(f"[DEBUG] XML path: {xml_path}")
        
        # Check if files exist
        for name, path in [("Raw PNG", raw_path), ("Segment", segment_path), ("Hotspot", hotspot_path), ("XML", xml_path)]:
            if not Path(path).exists():
                _log(f"[ERROR] {name} file does not exist: {path}")
                return [], None
            else:
                _log(f"[DEBUG] {name} file exists: {Path(path).stat().st_size} bytes")
        
        # Setup paths
        setup_classification_path()
        _log(f"[DEBUG] Python path setup completed")
        
        # Import classification module
        import inference_classification_hs as clf_module
        _log(f"[DEBUG] Module imported successfully")
        
        # Update model paths
        clf_module.MODEL_PATH = str(CLASSIFICATION_MODEL_PATH / "model_classification_hs_xgboost_250724.pkl")
        clf_module.SCALER_PATH = str(CLASSIFICATION_MODEL_PATH / "scaler_classification_32features.pkl")
        _log(f"[DEBUG] Model paths updated")
        
        # Check model files
        if not Path(clf_module.MODEL_PATH).exists():
            _log(f"[ERROR] Model file not found: {clf_module.MODEL_PATH}")
            return [], None
        if not Path(clf_module.SCALER_PATH).exists():
            _log(f"[ERROR] Scaler file not found: {clf_module.SCALER_PATH}")
            return [], None
        
        # Reload models
        import joblib
        clf_module.model = joblib.load(clf_module.MODEL_PATH)
        clf_module.scaler = joblib.load(clf_module.SCALER_PATH)
        _log(f"[DEBUG] Models loaded successfully")
        
        # Load XML bounding boxes
        xml_bboxes = load_xml_bounding_boxes(Path(xml_path))
        if not xml_bboxes:
            _log(f"[ERROR] No bounding boxes found in XML: {xml_path}")
            return [], None
        
        _log(f"[DEBUG] Loaded {len(xml_bboxes)} bounding boxes from XML")
        for i, bbox in enumerate(xml_bboxes):
            _log(f"[DEBUG] Bbox {i}: {bbox}")
        
        # Test image loading
        try:
            test_raw = cv2.imread(raw_path, cv2.IMREAD_GRAYSCALE)  # Original PNG file
            test_segment = cv2.imread(segment_path, cv2.IMREAD_COLOR)  # Check if colored
            test_hotspot = cv2.imread(hotspot_path, cv2.IMREAD_GRAYSCALE)  # Hotspot PNG
            
            # Check if segment is colored
            is_colored = 'colored' in Path(segment_path).name
            _log(f"[DEBUG] Image loading test:")
            _log(f"  Raw: {test_raw.shape if test_raw is not None else 'Failed'}")
            _log(f"  Segment: {test_segment.shape if test_segment is not None else 'Failed'} (colored: {is_colored})")
            _log(f"  Hotspot: {test_hotspot.shape if test_hotspot is not None else 'Failed'}")
            
            if test_raw is None or test_segment is None or test_hotspot is None:
                _log(f"[ERROR] Failed to load one or more images")
                return [], None
                
        except Exception as e:
            _log(f"[ERROR] Image loading test failed: {e}")
            return [], None
        
        # ✅ Use inference_classification with automatic conversion
        _log(f"[DEBUG] Starting inference_classification with automatic colored-to-grayscale conversion...")
        _log(f"[DEBUG] Conversion will create: {Path(segment_path).stem}_grayscaledSegmentation.png if needed")
        result_list, result_mask = clf_module.inference_classification(
            path_raw=raw_path,          # Original PNG file
            path_segment=segment_path,   # Colored PNG (will be auto-converted to grayscale)
            path_hotspot=hotspot_path,   # Hotspot PNG
            path_xml=xml_bboxes         # List of bboxes
        )
        
        _log(f"[DEBUG] Classification completed")
        _log(f"[DEBUG] Result list length: {len(result_list) if result_list else 0}")
        _log(f"[DEBUG] Result mask shape: {result_mask.shape if result_mask is not None else 'None'}")
        
        if result_list:
            for i, result in enumerate(result_list):
                _log(f"[DEBUG] Result {i}: prediction={result.get('prediction', 'Unknown')}, "
                     f"prob_abnormal={result.get('probability_abnormal', 0):.3f}")
        
        return result_list, result_mask
        
    except Exception as e:
        _log(f"[ERROR] Classification inference failed: {e}")
        import traceback
        _log(f"[ERROR] Full traceback: {traceback.format_exc()}")
        return [], None

def run_classification_for_patient(dicom_path: Path, patient_id: str, study_date: str) -> bool:
    """
    Run hotspot classification for both anterior and posterior views with grayscale conversion
    """
    try:
        session_code = dicom_path.parent.parent.name
        patient_folder = dicom_path.parent
        filename_stem = f"{patient_id}_{study_date}"
        
        _log(f"     Starting classification for patient {patient_id}")
        _log(f"     Study date: {study_date}")
        _log(f"     Session: {session_code}")
        _log(f"     Grayscale conversion: Enabled")
        
        results = []
        
        # Process both views with grayscale conversion
        for view in ['anterior', 'posterior']:
            view_short = 'ant' if view == 'anterior' else 'post'
            
            _log(f"     Processing {view} view with grayscale conversion...")
            
            # Get file paths with priority: edited → original
            paths = get_classification_input_paths(patient_folder, filename_stem, view, view_short)
            
            # Check if all required files exist
            missing_files = []
            if not paths['raw_original'].exists():
                missing_files.append(f"original frame ({paths['raw_original'].name})")
            if not paths['region_mask'].exists():
                missing_files.append(f"region mask ({paths['region_mask'].name})")
            if not paths['hotspot_mask'].exists():
                missing_files.append(f"hotspot mask ({paths['hotspot_mask'].name})")
            if not paths['xml_file'].exists():
                missing_files.append(f"XML file ({paths['xml_file'].name})")
            
            if missing_files:
                _log(f"     Missing files for {view}: {', '.join(missing_files)}")
                results.append(False)
                continue
            
            # ✅ Run classification with automatic colored-to-grayscale conversion
            classification_result, classification_mask = run_classification_inference(
                raw_path=str(paths['raw_original']),      # Original PNG
                segment_path=str(paths['region_mask']),   # Colored PNG (will be auto-converted)
                hotspot_path=str(paths['hotspot_mask']),  # Hotspot PNG
                xml_path=str(paths['xml_file'])          # XML file
            )
            
            if classification_result:
                # Save results
                save_classification_results(
                    patient_folder, filename_stem, view, classification_result, classification_mask
                )
                _log(f"     {view.title()} classification completed: {len(classification_result)} hotspots classified")
                results.append(True)
            else:
                _log(f"     {view.title()} classification failed")
                results.append(False)
        
        success = any(results)
        if success:
            _log(f"     Classification completed for patient {patient_id}")
        else:
            _log(f"     Classification failed for all views")
            
        return success
        
    except Exception as e:
        _log(f"Classification error for patient {patient_id}: {e}")
        return False

def get_classification_input_paths(patient_folder: Path, filename_stem: str, view: str, view_short: str) -> dict:
    """Get input file paths with edited priority and grayscale conversion support"""
    
    # Use original PNG file as raw input
    raw_original = patient_folder / f"{filename_stem}_{view}_original.png"
    
    # Priority: edited → original for processed files (these may be colored)
    region_candidates = [
        patient_folder / f"{filename_stem}_{view}_edited_colored.png",
        patient_folder / f"{filename_stem}_{view}_colored.png"
    ]
    
    # ✅ UPDATED: Hotspot file pattern - new format
    hotspot_candidates = [
        patient_folder / f"{filename_stem}_{view_short}_hotspot_mask.png",  # NEW: 2011_20250628_ant_hotspot_mask.png
    ]
    
    xml_candidates = [
        patient_folder / f"{filename_stem}_{view_short}_edited.xml",
        patient_folder / f"{filename_stem}_{view_short}.xml"
    ]
    
    return {
        'raw_original': raw_original,
        'region_mask': next((p for p in region_candidates if p.exists()), region_candidates[-1]),
        'hotspot_mask': next((p for p in hotspot_candidates if p.exists()), hotspot_candidates[-1]),
        'xml_file': next((p for p in xml_candidates if p.exists()), xml_candidates[-1])
    }

def save_classification_results(patient_folder: Path, filename_stem: str, view: str, results: list, mask: any):
    """✅ UPDATED: Save classification results with XML creation"""
    try:
        # Save classification results as JSON
        json_path = patient_folder / f"{filename_stem}_{view}_classification.json"
        
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
        
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        # ✅ NEW: Create classification XML from JSON results
        view_short = "ant" if "anterior" in view.lower() else "post"
        xml_output_path = patient_folder / f"{filename_stem}_{view_short}_classification.xml"
        
        # Get actual image dimensions
        img_width, img_height = get_image_dimensions_from_files(patient_folder, filename_stem, view)
        
        # Convert JSON to XML
        xml_success = create_classification_xml(
            classification_json_path=json_path,
            output_xml_path=xml_output_path,
            original_image_width=img_width,
            original_image_height=img_height
        )
        
        # ✅ Optional: Compare with original YOLO XML to show filtering effect
        original_xml = patient_folder / f"{filename_stem}_{view_short}.xml"
        if xml_success and original_xml.exists():
            comparison = compare_xml_files(original_xml, xml_output_path)
            removed_count = comparison.get('removed_hotspots', 0)
            original_count = comparison.get('original_count', 0)
            final_count = comparison.get('classification_count', 0)
            
            _log(f"       📊 YOLO→Classification filtering: {original_count} → {final_count} hotspots")
            if removed_count > 0:
                _log(f"       🗑️  Removed {removed_count} background hotspots (outside bone segments)")
            
            # Show class distribution changes
            orig_classes = comparison.get('original_classes', {})
            final_classes = comparison.get('classification_classes', {})
            if orig_classes or final_classes:
                _log(f"       📈 YOLO classes: {orig_classes}")
                _log(f"       📈 Final classes: {final_classes}")
        
        # ✅ PIL ONLY: Save mask with PIL - pure RGB, no OpenCV BGR confusion!
        if mask is not None:
            _log(f"[PIL SAVE] Using PIL to save mask - pure RGB mode")
            _log(f"[PIL SAVE] Mask shape: {mask.shape}")
            _log(f"[PIL SAVE] Unique colors: {np.unique(mask.reshape(-1, 3), axis=0) if len(mask.shape) == 3 else 'Not RGB'}")
            
            mask_path = patient_folder / f"{filename_stem}_{view}_classification_mask.png"
            
            # ✅ SAVE WITH PIL ONLY - PURE RGB, NO BGR!
            if len(mask.shape) == 3 and mask.shape[2] == 3:
                from PIL import Image
                
                # Convert numpy array to PIL Image (RGB mode)
                mask_pil = Image.fromarray(mask, mode='RGB')
                
                # Save with PIL - preserves RGB order
                mask_pil.save(mask_path)
                
                _log(f"[PIL SAVE] Saved with PIL RGB mode - colors preserved correctly")
                
            else:
                # Fallback for non-RGB masks
                cv2.imwrite(str(mask_path), mask)
                _log(f"[PIL SAVE] Saved without conversion (not RGB)")
            
            # Output file summary
            if xml_success:
                _log(f"       ✅ Saved: {json_path.name}, {xml_output_path.name}, {mask_path.name}")
            else:
                _log(f"       ⚠️  Saved: {json_path.name}, {mask_path.name} (XML creation failed)")
        else:
            if xml_success:
                _log(f"       ✅ Saved: {json_path.name}, {xml_output_path.name}")
            else:
                _log(f"       ⚠️  Saved: {json_path.name} (XML creation failed)")
        
    except Exception as e:
        _log(f"Failed to save classification results: {e}")
        import traceback
        _log(f"Full traceback: {traceback.format_exc()}")