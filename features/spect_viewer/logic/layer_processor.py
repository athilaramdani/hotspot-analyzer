# features/spect_viewer/logic/layer_processor.py
"""
Layer processing logic for SPECT timeline widget
Handles loading and processing of different layer types
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, Tuple
import numpy as np
from PIL import Image

from core.config.paths import (
    get_hotspot_files,
    get_segmentation_files_with_edited,
    get_hotspot_xml_files,
    extract_study_date_from_dicom,
    generate_filename_stem
)

from core.utils.image_converter import (
    load_image_with_transparency,
    apply_opacity_to_image
)

from features.dicom_import.logic.dicom_loader import extract_patient_info_from_path
from .bounding_box_renderer import BoundingBoxRenderer


class LayerProcessor:
    """Handles processing and loading of different layer types"""
    
    def __init__(self, session_code: Optional[str] = None):
        self.session_code = session_code
        self.bbox_renderer = BoundingBoxRenderer()
    
    def get_patient_session_from_scan(self, scan: Dict) -> Tuple[str, str]:
        """Extract patient ID and session code from scan path"""
        try:
            dicom_path = scan["path"]
            patient_id, session_code = extract_patient_info_from_path(dicom_path)
            
            # Fallback to session from processor if extraction fails
            if session_code == "UNKNOWN" and self.session_code:
                session_code = self.session_code
                
            print(f"[DEBUG] Extracted from {dicom_path}: patient={patient_id}, session={session_code}")
            return patient_id, session_code
        except Exception as e:
            print(f"[WARN] Failed to extract patient/session from scan: {e}")
            return "UNKNOWN", self.session_code or "UNKNOWN"
    
    def get_layer_images(self, scan: Dict, current_view: str) -> Dict[str, Image.Image]:
        """Get all layer images for a scan with proper file naming"""
        frame_map = scan["frames"]
        dicom_path = scan["path"]
        
        layers = {}
        
        # Layer 1: Original (base) - convert to RGBA for opacity support
        if current_view in frame_map:
            original_arr = frame_map[current_view]
            # Convert to PIL Image with RGBA mode for opacity support
            original_normalized = ((original_arr - original_arr.min()) / max(1, np.ptp(original_arr)) * 255).astype(np.uint8)
            original_image = Image.fromarray(original_normalized).convert("RGBA")
            layers["Original"] = original_image
        
        # Extract patient info for file paths
        try:
            study_date = extract_study_date_from_dicom(dicom_path)
            patient_id, session_code = self.get_patient_session_from_scan(scan)
            filename_with_date = generate_filename_stem(patient_id, study_date)
            print(f"[DEBUG] Using filename stem with study date: {filename_with_date}")
            print(f"[DEBUG] Patient ID: {patient_id}, Study Date: {study_date}")
        except Exception as e:
            print(f"[WARN] Could not extract study date, using original filename: {e}")
            study_date = None
            filename_with_date = dicom_path.stem
            patient_id, session_code = self.get_patient_session_from_scan(scan)
        
        # Layer 2: Segmentation
        segmentation_layer = self._load_segmentation_layer(
            dicom_path.parent, filename_with_date, current_view
        )
        if segmentation_layer:
            layers["Segmentation"] = segmentation_layer
        
        # Layer 3: Hotspot
        hotspot_layer = self._load_hotspot_layer(
            patient_id, session_code, current_view, study_date, scan
        )
        if hotspot_layer:
            layers["Hotspot"] = hotspot_layer
        
        # Layer 4: Hotspot Bounding Box
        bbox_layer = self._load_bbox_layer(
            patient_id, session_code, current_view, study_date, layers.get("Original")
        )
        if bbox_layer:
            layers["HotspotBBox"] = bbox_layer
        
        return layers
    
    def _load_segmentation_layer(self, patient_folder: Path, filename_stem: str, view: str) -> Optional[Image.Image]:
        """Load segmentation layer with edited file priority"""
        seg_files = get_segmentation_files_with_edited(patient_folder, filename_stem, view)
        
        # Prioritize edited files
        if seg_files['png_colored_edited'].exists():
            seg_png = seg_files['png_colored_edited']
            print(f"[DEBUG] Found edited segmentation: {seg_png}")
        else:
            seg_png = seg_files['png_colored']
            print(f"[DEBUG] Found original segmentation: {seg_png}")
        
        if seg_png.exists():
            try:
                # Load with transparency (make black pixels transparent)
                seg_image = load_image_with_transparency(seg_png, make_transparent=True)
                print(f"[DEBUG] Loaded segmentation with transparency: {seg_png}")
                return seg_image
            except Exception as e:
                print(f"[WARN] Failed to load segmentation image: {e}")
        else:
            print(f"[WARN] Segmentation file not found: {seg_png}")
        
        return None
    
    def _load_hotspot_layer(self, patient_id: str, session_code: str, view: str, 
                           study_date: Optional[str], scan: Dict) -> Optional[Image.Image]:
        """Load hotspot layer with edited file priority"""
        if study_date:
            hotspot_files = get_hotspot_files(patient_id, session_code, view, study_date)
        else:
            # Fallback: try to get study date from meta or use current date
            fallback_date = scan["meta"].get("study_date")
            if not fallback_date:
                from datetime import datetime
                fallback_date = datetime.now().strftime("%Y%m%d")
            hotspot_files = get_hotspot_files(patient_id, session_code, view, fallback_date)
        
        # Priority system for loading hotspot files
        hotspot_png = None
        
        # Priority 1: Try EDITED version first (user's latest changes)
        if hotspot_files['colored_png_edited'].exists():
            hotspot_png = hotspot_files['colored_png_edited']
            print(f"[DEBUG] Found EDITED hotspot: {hotspot_png}")
        # Priority 2: Try original version 
        elif hotspot_files['colored_png'].exists():
            hotspot_png = hotspot_files['colored_png']
            print(f"[DEBUG] Found original hotspot: {hotspot_png}")
        # Priority 3: Fallback to legacy naming for backward compatibility
        elif hotspot_files.get('colored_png_legacy') and hotspot_files['colored_png_legacy'].exists():
            hotspot_png = hotspot_files['colored_png_legacy']
            print(f"[DEBUG] Found hotspot (legacy naming): {hotspot_png}")
        
        if hotspot_png and hotspot_png.exists():
            try:
                # Load with transparency (make black pixels transparent)
                hotspot_image = load_image_with_transparency(hotspot_png, make_transparent=True)
                print(f"[DEBUG] Loaded hotspot with transparency: {hotspot_png}")
                return hotspot_image
            except Exception as e:
                print(f"[WARN] Failed to load hotspot image: {e}")
        else:
            filename_stem = generate_filename_stem(patient_id, study_date) if study_date else "unknown"
            print(f"[WARN] No hotspot files found for {filename_stem}")
        
        return None
    
    def _load_bbox_layer(self, patient_id: str, session_code: str, view: str,
                        study_date: Optional[str], original_image: Optional[Image.Image]) -> Optional[Image.Image]:
        """Load bounding box layer from XML files"""
        if not study_date or not original_image:
            return None
        
        xml_files = get_hotspot_xml_files(patient_id, session_code, view, study_date)
        
        # Priority 1: Try EDITED XML first
        xml_file = None
        if xml_files['xml_file_edited'].exists():
            xml_file = xml_files['xml_file_edited']
            print(f"[DEBUG] Found EDITED XML: {xml_file}")
        elif xml_files['xml_file'].exists():
            xml_file = xml_files['xml_file']
            print(f"[DEBUG] Found original XML: {xml_file}")
        
        if xml_file and xml_file.exists():
            try:
                # Create bounding box overlay
                bbox_image = self.bbox_renderer.create_bounding_box_overlay(xml_file, original_image.size)
                print(f"[DEBUG] Created bounding box overlay from: {xml_file}")
                return bbox_image
            except Exception as e:
                print(f"[WARN] Failed to create bounding box overlay: {e}")
        else:
            print(f"[WARN] No XML file found for bounding boxes")
        
        return None
    
    def apply_layer_opacities(self, layers: Dict[str, Image.Image], 
                             active_layers: list, opacities: Dict[str, float]) -> Dict[str, Image.Image]:
        """Apply opacity to active layers"""
        processed_layers = {}
        
        for layer_name in active_layers:
            if layer_name in layers:
                layer_image = layers[layer_name]
                layer_opacity = opacities.get(layer_name, 1.0)
                
                # Apply opacity to the layer
                if layer_opacity < 1.0:
                    layer_image = apply_opacity_to_image(layer_image, layer_opacity)
                
                processed_layers[layer_name] = layer_image
        
        return processed_layers