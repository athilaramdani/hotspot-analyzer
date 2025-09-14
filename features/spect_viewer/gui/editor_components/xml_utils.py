# features/spect_viewer/gui/editor_components/xml_utils.py
"""
XML utilities for hotspot annotation management.
Updated to support Benign/Malignant UI labels while maintaining normal/abnormal XML format.
"""
from pathlib import Path
from typing import Dict, List
import numpy as np
import xml.etree.ElementTree as ET
from skimage import measure
import logging
# Segment names mapping
_SEGMENT_NAMES = {
    0: "background", 1: "skull", 2: "cervical_vertebrae", 3: "thoracic_vertebrae",
    4: "rib", 5: "sternum", 6: "collarbone", 7: "scapula", 8: "humerus",
    9: "lumbar_vertebrae", 10: "sacrum", 11: "pelvis", 12: "femur"
}

#   NEW: Label mappings for UI vs XML compatibility
_UI_TO_XML_LABELS = {
    # UI Display -> XML Output (for saving)
    "Background": "background",
    "Malignant": "abnormal",  #   UI shows "Malignant", XML saves "abnormal"
    "Benign": "normal"        #   UI shows "Benign", XML saves "normal"
}

_XML_TO_UI_LABELS = {
    # XML Input -> UI Display (for loading)
    "background": "Background",
    "abnormal": "Malignant",  #   XML "abnormal" displays as "Malignant"
    "normal": "Benign"        #   XML "normal" displays as "Benign"
}

def mask_to_bounding_boxes(mask: np.ndarray, segmentation_arr: np.ndarray = None, 
                          min_area: int = 10) -> List[Dict]:
    """
    Convert mask annotations to bounding boxes with XML-compatible labels.
    
      UPDATED: Always outputs 'normal'/'abnormal' for XML compatibility
    regardless of UI terminology.
    """
    bounding_boxes = []
    
    # Process Malignant (label=1) and Benign (label=2) areas
    for label_value in [1, 2]:
        label_mask = (mask == label_value).astype(np.uint8)
        
        if not np.any(label_mask):
            continue
            
        # Find connected components
        labeled_regions = measure.label(label_mask)
        
        for region_id in range(1, labeled_regions.max() + 1):
            region = (labeled_regions == region_id)
            
            # Skip small regions
            if np.sum(region) < min_area:
                continue
                
            # Get bounding box coordinates
            coords = np.where(region)
            y_min, y_max = coords[0].min(), coords[0].max()
            x_min, x_max = coords[1].min(), coords[1].max()
            
            # Detect dominant segment in this region
            segment_name = "manual_annotation"
            if segmentation_arr is not None:
                # Get segment labels in this region
                region_segments = segmentation_arr[region]
                # Find most common non-background segment
                unique_segments, counts = np.unique(region_segments, return_counts=True)
                # Filter out background (label 0)
                non_bg_mask = unique_segments != 0
                if np.any(non_bg_mask):
                    dominant_segment_id = unique_segments[non_bg_mask][np.argmax(counts[non_bg_mask])]
                    segment_name = _SEGMENT_NAMES.get(dominant_segment_id, "unknown")
            
            #   CRITICAL: Always use XML-compatible labels for file output
            # label_value 1 = Malignant (UI) -> "abnormal" (XML)
            # label_value 2 = Benign (UI) -> "normal" (XML)
            xml_label = 'abnormal' if label_value == 1 else 'normal'
            
            # Convert to proper format
            bbox = {
                'x': int(x_min),
                'y': int(y_min),
                'width': int(x_max - x_min + 1),
                'height': int(y_max - y_min + 1),
                'label': xml_label,  #   Always 'abnormal'/'normal' for XML
                'confidence': 1.0,   # Manual annotation = high confidence
                'hotspot_pixels': int(np.sum(region)),
                'segment': segment_name,
                #   NEW: Add UI label for reference (optional)
                'ui_label': 'Malignant' if label_value == 1 else 'Benign'
            }
            
            bounding_boxes.append(bbox)
            
            #   DEBUG: Show label conversion
            ui_term = 'Malignant' if label_value == 1 else 'Benign'
            logging.info(f"[XML] Converted {ui_term} (UI) -> {xml_label} (XML) for bbox at ({x_min},{y_min})")
    
    return bounding_boxes

def create_xml_from_bboxes(bounding_boxes: List[Dict], img_width: int, img_height: int, 
                          patient_id: str, view: str, filename_stem: str) -> str:
    """
    Create XML content from bounding boxes with classification results format.
    
      UPDATED: Ensures XML always uses 'Normal'/'Abnormal' for compatibility
    even when UI shows 'Benign'/'Malignant'.
    """
    
    # Create root element
    root = ET.Element('annotation')
    
    # Add metadata
    ET.SubElement(root, 'folder').text = 'classification_results'
    ET.SubElement(root, 'filename').text = f'{filename_stem}_{view}_classification.png'
    ET.SubElement(root, 'path').text = f'/path/to/{filename_stem}_{view}_classification.png'
    
    # Add source info
    source = ET.SubElement(root, 'source')
    ET.SubElement(source, 'database').text = 'Hotspot Classification Results'
    
    # Add image size
    size = ET.SubElement(root, 'size')
    ET.SubElement(size, 'width').text = str(img_width)
    ET.SubElement(size, 'height').text = str(img_height)
    ET.SubElement(size, 'depth').text = '1'
    
    ET.SubElement(root, 'segmented').text = '0'
    
    # Add bounding boxes with XML-compatible labels
    for bbox in bounding_boxes:
        obj = ET.SubElement(root, 'object')
        
        #   ENSURE XML COMPATIBILITY: Force standard labels
        xml_label = bbox['label']  # Should already be 'normal'/'abnormal'
        
        #   SAFETY CHECK: Convert if somehow UI labels got through
        if xml_label.lower() == 'malignant':
            xml_label = 'abnormal'
        elif xml_label.lower() == 'benign':
            xml_label = 'normal'
        
        # Use capitalized format for XML (Normal/Abnormal)
        label_name = xml_label.capitalize()  # 'abnormal' -> 'Abnormal', 'normal' -> 'Normal'
        
        ET.SubElement(obj, 'name').text = label_name
        ET.SubElement(obj, 'pose').text = 'Unspecified'
        ET.SubElement(obj, 'truncated').text = '0'
        ET.SubElement(obj, 'difficult').text = '0'
        
        # Add bounding box coordinates
        bndbox = ET.SubElement(obj, 'bndbox')
        ET.SubElement(bndbox, 'xmin').text = str(bbox['x'])
        ET.SubElement(bndbox, 'ymin').text = str(bbox['y'])
        ET.SubElement(bndbox, 'xmax').text = str(bbox['x'] + bbox['width'])
        ET.SubElement(bndbox, 'ymax').text = str(bbox['y'] + bbox['height'])
        
        #   DEBUG: Show final XML label
        ui_label = bbox.get('ui_label', 'Unknown')
        logging.info(f"[XML] Saved as <name>{label_name}</name> (from UI: {ui_label})")
    
    # Convert to string with proper formatting
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding='unicode')

def load_xml_annotations(xml_path: Path) -> List[Dict]:
    """
    Load XML annotations and convert to internal format.
    
      NEW: Converts XML labels to UI-compatible format for display.
    """
    annotations = []
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        for obj in root.findall('object'):
            name_elem = obj.find('name')
            if name_elem is None:
                continue
                
            xml_label = name_elem.text.strip().lower()  # Get XML label
            
            #   CONVERT: XML label -> UI label for display
            if xml_label == 'abnormal':
                ui_label = 'Malignant'
                mask_value = 1
            elif xml_label == 'normal':
                ui_label = 'Benign'  
                mask_value = 2
            else:
                ui_label = 'Background'
                mask_value = 0
            
            # Get bounding box
            bndbox = obj.find('bndbox')
            if bndbox is not None:
                xmin = int(float(bndbox.find('xmin').text))
                ymin = int(float(bndbox.find('ymin').text))
                xmax = int(float(bndbox.find('xmax').text))
                ymax = int(float(bndbox.find('ymax').text))
                
                annotation = {
                    'xml_label': xml_label,      # Original XML label ('normal'/'abnormal')
                    'ui_label': ui_label,        # UI display label ('Benign'/'Malignant')
                    'mask_value': mask_value,    # Mask array value (1/2)
                    'xmin': xmin,
                    'ymin': ymin,
                    'xmax': xmax,
                    'ymax': ymax,
                    'width': xmax - xmin,
                    'height': ymax - ymin
                }
                
                annotations.append(annotation)
                
                #   DEBUG: Show conversion
                logging.info(f"[XML LOAD] {xml_label} (XML) -> {ui_label} (UI) at ({xmin},{ymin})")
    
    except Exception as e:
        logging.info(f"[ERROR] Failed to load XML annotations: {e}")
        
    return annotations

def save_xml_file(xml_content: str, file_path: Path):
    """Save XML content to file with proper header."""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_content)
    
    logging.info(f"[XML SAVE] Saved classification XML: {file_path}")

def get_ui_label_from_xml(xml_label: str) -> str:
    """
    Convert XML label to UI display label.
    
      NEW: Helper function for label conversion.
    """
    return _XML_TO_UI_LABELS.get(xml_label.lower(), "Background")

def get_xml_label_from_ui(ui_label: str) -> str:
    """
    Convert UI display label to XML label.
    
      NEW: Helper function for label conversion.
    """
    return _UI_TO_XML_LABELS.get(ui_label, "background")

def validate_xml_compatibility(file_path: Path) -> Dict[str, any]:
    """
    Validate that XML file uses compatible labels.
    
      NEW: Validation function to ensure XML format compatibility.
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        labels_found = []
        total_objects = 0
        
        for obj in root.findall('object'):
            total_objects += 1
            name_elem = obj.find('name')
            if name_elem is not None:
                label = name_elem.text.strip().lower()
                if label not in labels_found:
                    labels_found.append(label)
        
        # Check for valid labels
        valid_labels = {'normal', 'abnormal', 'background'}
        invalid_labels = [l for l in labels_found if l not in valid_labels]
        
        return {
            'valid': len(invalid_labels) == 0,
            'total_objects': total_objects,
            'labels_found': labels_found,
            'invalid_labels': invalid_labels,
            'file_path': str(file_path)
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'file_path': str(file_path)
        }

#   EXAMPLE USAGE:
"""
# In your hotspot editor when saving:
mask = canvas.current_mask()  # Contains 1=Malignant, 2=Benign
bboxes = mask_to_bounding_boxes(mask)  # Converts to XML labels
xml_content = create_xml_from_bboxes(bboxes, w, h, patient_id, view, stem)
save_xml_file(xml_content, xml_path)

# Result: XML contains <name>Abnormal</name> and <name>Normal</name>
# Even though UI showed "Malignant" and "Benign"

# When loading existing XML:
annotations = load_xml_annotations(xml_path)
for ann in annotations:
    logging.info(f"XML: {ann['xml_label']} -> UI: {ann['ui_label']}")
    # Shows: "XML: abnormal -> UI: Malignant"
    #        "XML: normal -> UI: Benign"
"""