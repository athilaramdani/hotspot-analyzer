# features/spect_viewer/gui/editor_components/xml_utils.py
"""
XML utilities for hotspot annotation management.
"""
from pathlib import Path
from typing import Dict, List
import numpy as np
import xml.etree.ElementTree as ET
from skimage import measure

# Segment names mapping
_SEGMENT_NAMES = {
    0: "background", 1: "skull", 2: "cervical_vertebrae", 3: "thoracic_vertebrae",
    4: "rib", 5: "sternum", 6: "collarbone", 7: "scapula", 8: "humerus",
    9: "lumbar_vertebrae", 10: "sacrum", 11: "pelvis", 12: "femur"
}


def mask_to_bounding_boxes(mask: np.ndarray, segmentation_arr: np.ndarray = None, 
                          min_area: int = 10) -> List[Dict]:
    """Convert mask annotations to bounding boxes with proper segment detection."""
    bounding_boxes = []
    
    # Process Abnormal (label=1) and Normal (label=2) areas
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
            
            # Convert to proper format
            bbox = {
                'x': int(x_min),
                'y': int(y_min),
                'width': int(x_max - x_min + 1),
                'height': int(y_max - y_min + 1),
                'label': 'abnormal' if label_value == 1 else 'normal',
                'confidence': 1.0,  # Manual annotation = high confidence
                'hotspot_pixels': int(np.sum(region)),
                'segment': segment_name
            }
            
            bounding_boxes.append(bbox)
    
    return bounding_boxes


def create_xml_from_bboxes(bounding_boxes: List[Dict], img_width: int, img_height: int, 
                          patient_id: str, view: str, filename_stem: str) -> str:
    """Create XML content from bounding boxes with classification results format."""
    
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
    
    # Add bounding boxes
    for bbox in bounding_boxes:
        obj = ET.SubElement(root, 'object')
        # Use format with capital first letter
        label_name = bbox['label'].capitalize()  # 'abnormal' -> 'Abnormal'
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
    
    # Convert to string with proper formatting
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding='unicode')


def save_xml_file(xml_content: str, file_path: Path):
    """Save XML content to file with proper header."""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_content)