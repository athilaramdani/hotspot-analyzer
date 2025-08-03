# features/spect_viewer/logic/classification_xml_converter.py
"""
Convert classification JSON results to XML format compatible with YOLO format
This creates a new XML file that reflects the final classification results
after filtering out hotspots outside bone segments.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List
from core.logger import _log


def create_classification_xml(classification_json_path: Path, output_xml_path: Path, 
                            original_image_width: int = 512, original_image_height: int = 512) -> bool:
    """
    Convert classification JSON to XML format
    
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
            _log(f"[XML CONVERT] No hotspots found in classification JSON")
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
        database.text = "Classification Results"
        
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
            name.text = hotspot.get("prediction", "Unknown")  # Abnormal or Normal
            
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
            
            # ✅ NEW: Add classification-specific attributes
            attributes = ET.SubElement(obj, "attributes")
            
            # Segment information
            segment_attr = ET.SubElement(attributes, "attribute")
            segment_attr.set("name", "segment")
            segment_attr.text = hotspot.get("segment", "unknown")
            
            # Probability scores
            prob_normal_attr = ET.SubElement(attributes, "attribute")
            prob_normal_attr.set("name", "probability_normal")
            prob_normal_attr.text = str(hotspot.get("probability_normal", 0.0))
            
            prob_abnormal_attr = ET.SubElement(attributes, "attribute")
            prob_abnormal_attr.set("name", "probability_abnormal")
            prob_abnormal_attr.text = str(hotspot.get("probability_abnormal", 0.0))
            
            # Area measurements
            area_measurements = hotspot.get("area_measurements", {})
            
            hotspot_pixels_attr = ET.SubElement(attributes, "attribute")
            hotspot_pixels_attr.set("name", "hotspot_pixels")
            hotspot_pixels_attr.text = str(area_measurements.get("hotspot_pixels", 0))
            
            hotspot_mm2_attr = ET.SubElement(attributes, "attribute")
            hotspot_mm2_attr.set("name", "hotspot_mm2")
            hotspot_mm2_attr.text = str(area_measurements.get("hotspot_mm2", 0.0))
            
            ratio_pixels_attr = ET.SubElement(attributes, "attribute")
            ratio_pixels_attr.set("name", "ratio_pixels")
            ratio_pixels_attr.text = str(area_measurements.get("ratio_pixels", 0.0))
        
        # Create tree and write to file
        tree = ET.ElementTree(annotation)
        ET.indent(tree, space="  ", level=0)  # Pretty formatting
        
        # Write XML file
        tree.write(output_xml_path, encoding="utf-8", xml_declaration=True)
        
        _log(f"[XML CONVERT] ✅ Created classification XML: {output_xml_path.name}")
        _log(f"[XML CONVERT] Converted {len(hotspots)} classified hotspots")
        
        return True
        
    except Exception as e:
        _log(f"[XML CONVERT] ❌ Failed to create classification XML: {e}")
        return False


def update_classification_wrapper_with_xml_creation():
    """
    Update the classification wrapper to automatically create XML from JSON results
    This should be called at the end of save_classification_results()
    """
    return """
    # Add this to the end of save_classification_results() function:
    
    def save_classification_results(patient_folder: Path, filename_stem: str, view: str, results: list, mask: any):
        try:
            # ... existing JSON and mask saving code ...
            
            # ✅ NEW: Create classification XML from JSON results
            json_path = patient_folder / f"{filename_stem}_{view}_classification.json"
            
            # Determine view for XML file naming (use short names: ant/post)
            view_short = "ant" if "anterior" in view.lower() else "post"
            xml_output_path = patient_folder / f"{filename_stem}_{view_short}_classification.xml"
            
            # Convert JSON to XML
            xml_success = create_classification_xml(
                classification_json_path=json_path,
                output_xml_path=xml_output_path,
                original_image_width=512,  # Default SPECT image size
                original_image_height=512
            )
            
            if xml_success:
                _log(f"       ✅ Created classification XML: {xml_output_path.name}")
            else:
                _log(f"       ❌ Failed to create classification XML")
            
            # ... rest of existing code ...
            
        except Exception as e:
            _log(f"Failed to save classification results: {e}")
    """


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
        _log(f"[XML CONVERT] Could not determine image dimensions, using default: {e}")
        return (512, 512)


def compare_xml_files(original_xml: Path, classification_xml: Path) -> Dict:
    """
    Compare original YOLO XML with classification XML to show differences
    
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
            "class_changes": [],
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
        
        _log(f"[XML COMPARE] Original hotspots: {comparison['original_count']}")
        _log(f"[XML COMPARE] Final hotspots: {comparison['classification_count']}")
        _log(f"[XML COMPARE] Removed hotspots (outside segments): {comparison['removed_hotspots']}")
        _log(f"[XML COMPARE] Original classes: {comparison['original_classes']}")
        _log(f"[XML COMPARE] Final classes: {comparison['classification_classes']}")
        
        return comparison
        
    except Exception as e:
        _log(f"[XML COMPARE] Error comparing XML files: {e}")
        return {}


# ✅ EXAMPLE USAGE AND INTEGRATION
def example_integration():
    """
    Example of how to integrate this into your existing workflow
    """
    example_code = '''
    # In features/spect_viewer/logic/classification_wrapper.py
    # Add this import at the top:
    from .classification_xml_converter import create_classification_xml, get_image_dimensions_from_files
    
    # Modify save_classification_results function:
    def save_classification_results(patient_folder: Path, filename_stem: str, view: str, results: list, mask: any):
        """Save classification results to patient folder with XML generation"""
        try:
            # ... existing JSON saving code ...
            
            # Save classification results as JSON
            json_path = patient_folder / f"{filename_stem}_{view}_classification.json"
            # ... JSON saving code ...
            
            # ✅ NEW: Create classification XML
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
            
            if xml_success:
                _log(f"       ✅ Saved: {json_path.name}, {xml_output_path.name}")
                
                # Optional: Compare with original YOLO XML
                original_xml = patient_folder / f"{filename_stem}_{view_short}.xml"
                if original_xml.exists():
                    comparison = compare_xml_files(original_xml, xml_output_path)
                    _log(f"       📊 Filtering removed {comparison.get('removed_hotspots', 0)} background hotspots")
            else:
                _log(f"       ❌ Failed to create XML from: {json_path.name}")
            
            # ... existing mask saving code ...
            
        except Exception as e:
            _log(f"Failed to save classification results: {e}")
    '''
    
    return example_code