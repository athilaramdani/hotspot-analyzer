# features/spect_viewer/logic/bounding_box_renderer.py
"""
Bounding box rendering logic for XML annotations
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

from features.spect_viewer.logic.colorizer import _HOTSPOT_PALLETTE


class BoundingBoxRenderer:
    """Handles rendering of bounding boxes from XML annotations"""
    
    def __init__(self):
        # Color mapping for bounding box types
        self.colors = {
            'Normal': tuple(_HOTSPOT_PALLETTE[2]) + (255,),    # Normal color with full opacity
            'Abnormal': tuple(_HOTSPOT_PALLETTE[1]) + (255,),  # Abnormal color with full opacity
        }
        self.line_width = 2
        self.label_enabled = True
    
    def create_bounding_box_overlay(self, xml_file: Path, image_size: Tuple[int, int]) -> Image.Image:
        """Create bounding box overlay from XML file"""
        # Create transparent RGBA image
        width, height = image_size
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        try:
            # Parse XML file
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Extract bounding boxes
            for obj in root.findall('object'):
                name = obj.find('name').text if obj.find('name') is not None else 'Unknown'
                bndbox = obj.find('bndbox')
                
                if bndbox is not None:
                    bbox_coords = self._extract_bbox_coordinates(bndbox)
                    if bbox_coords:
                        self._draw_bounding_box(draw, bbox_coords, name)
            
            return overlay
            
        except Exception as e:
            print(f"[ERROR] Failed to parse XML {xml_file}: {e}")
            return overlay
    
    def _extract_bbox_coordinates(self, bndbox) -> Dict[str, int]:
        """Extract bounding box coordinates from XML element"""
        try:
            coords = {
                'xmin': int(float(bndbox.find('xmin').text)),
                'ymin': int(float(bndbox.find('ymin').text)),
                'xmax': int(float(bndbox.find('xmax').text)),
                'ymax': int(float(bndbox.find('ymax').text))
            }
            return coords
        except (AttributeError, ValueError, TypeError) as e:
            print(f"[WARN] Failed to extract bbox coordinates: {e}")
            return {}
    
    def _draw_bounding_box(self, draw: ImageDraw.Draw, coords: Dict[str, int], name: str):
        """Draw a single bounding box with label"""
        xmin, ymin = coords['xmin'], coords['ymin']
        xmax, ymax = coords['xmax'], coords['ymax']
        
        # Get color for this type
        color = self.colors.get(name, (255, 255, 255, 255))  # Default white if unknown
        
        # Draw rectangle outline (thicker for visibility)
        for i in range(self.line_width):
            draw.rectangle([xmin-i, ymin-i, xmax+i, ymax+i], outline=color, fill=None)
        
        # Draw label if enabled and valid type
        if self.label_enabled and name in ['Normal', 'Abnormal']:
            self._draw_label(draw, xmin, ymin, name, color)
    
    def _draw_label(self, draw: ImageDraw.Draw, x: int, y: int, text: str, color: Tuple[int, int, int, int]):
        """Draw label text with background"""
        try:
            # Get text dimensions
            text_bbox = draw.textbbox((0, 0), text)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            # Draw label background
            label_bg_color = color[:3] + (200,)  # Semi-transparent background
            draw.rectangle([x, y-text_height-4, x+text_width+6, y], fill=label_bg_color)
            
            # Draw label text
            draw.text((x+3, y-text_height-2), text, fill=(255, 255, 255, 255))
            
        except Exception as e:
            print(f"[WARN] Failed to draw label: {e}")
    
    def set_line_width(self, width: int):
        """Set bounding box line width"""
        self.line_width = max(1, width)
    
    def set_label_enabled(self, enabled: bool):
        """Enable/disable label drawing"""
        self.label_enabled = enabled
    
    def set_colors(self, color_mapping: Dict[str, Tuple[int, int, int, int]]):
        """Set custom color mapping"""
        self.colors.update(color_mapping)