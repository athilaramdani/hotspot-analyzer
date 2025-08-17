# features/spect_viewer/gui/scan_timeline.py – FIXED TO SHOW CLASSIFICATION ONLY
# ---------------------------------------------------------------------
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QWheelEvent
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton, QSplitter, QSlider
)

# Import NEW config paths for edited files support
from core.config.paths import (
    extract_study_date_from_dicom,
    generate_filename_stem,
    get_planar_hotspot_files,
    get_planar_segmentation_files,
    get_patient_planar_path,
    load_original_image_from_path  # ✅ TAMBAHAN
)

# Import legacy functions from archive if needed
from core.config.paths_archive import (
    get_hotspot_files,
    get_segmentation_files_with_edited
)

# Import NEW transparency utilities
from core.utils.image_converter import (
    make_black_transparent,
    load_image_with_transparency,
    create_composite_image,
    get_layer_preview,
    apply_opacity_to_image
)

# Import for patient/session extraction from path
from features.dicom_import.logic.dicom_loader import extract_patient_info_from_path
# ✅ FIXED: Import updated image inverter functions
from ..logic.image_inverter import invert_image_colors, simple_invert_pil_image
from ..logic.adjust_contrast import apply_brightness_contrast

from .segmentation_editor_dialog import SegmentationEditorDialog
from .hotspot_editor_dialog import HotspotEditorDialog
from pydicom import dcmread

# Import UI constants for edit buttons
from core.gui.ui_constants import (
    SUCCESS_BUTTON_STYLE,
    ZOOM_BUTTON_STYLE, 
    GRAY_BUTTON_STYLE
)

# Import BSI integration
from features.spect_viewer.logic.bsi_timeline_integration import get_bsi_integration

# --------------------------- helpers -----------------------------------------
def _array_to_pixmap(arr: np.ndarray, width: int) -> QPixmap:
    """Convert numpy array to QPixmap with proper scaling"""
    arr_f = arr.astype(np.float32)
    arr_f = (arr_f - arr_f.min()) / max(1, np.ptp(arr_f)) * 255.0
    img_u8 = arr_f.astype(np.uint8)
    h, w = img_u8.shape
    qim = QImage(img_u8.data, w, h, w, QImage.Format_Grayscale8)
    return QPixmap.fromImage(qim).scaledToWidth(width, Qt.SmoothTransformation)


def _pil_to_pixmap(pil_image: Image.Image, width: int) -> QPixmap:
    """Convert PIL Image to QPixmap with scaling"""
    # Handle different PIL Image modes
    if pil_image.mode == 'RGBA':
        # RGBA image
        np_array = np.array(pil_image)
        height, width_orig, channels = np_array.shape
        bytes_per_line = channels * width_orig
        q_image = QImage(np_array.data, width_orig, height, bytes_per_line, QImage.Format_RGBA8888)
    elif pil_image.mode == 'RGB':
        # RGB image
        np_array = np.array(pil_image)
        height, width_orig, channels = np_array.shape
        bytes_per_line = channels * width_orig
        q_image = QImage(np_array.data, width_orig, height, bytes_per_line, QImage.Format_RGB888)
    elif pil_image.mode == 'L':
        # Grayscale image
        np_array = np.array(pil_image)
        height, width_orig = np_array.shape
        q_image = QImage(np_array.data, width_orig, height, width_orig, QImage.Format_Grayscale8)
    else:
        # Convert to RGB if other format
        pil_image = pil_image.convert('RGB')
        np_array = np.array(pil_image)
        height, width_orig, channels = np_array.shape
        bytes_per_line = channels * width_orig
        q_image = QImage(np_array.data, width_orig, height, bytes_per_line, QImage.Format_RGB888)
    
    return QPixmap.fromImage(q_image).scaledToWidth(width, Qt.SmoothTransformation)


# --------------------------- main widget -------------------------------------
class ScanTimelineWidget(QWidget):
    """
    ✅ FIXED: Enhanced timeline widget - CLASSIFICATION ONLY:
    - ✅ Only shows classification results (no YOLO/Otsu)
    - ✅ Hotspot layer = classification_mask.png only
    - ✅ HotspotBBox layer = classification.xml only  
    - ✅ Editor sends classification files to hotspot editor
    - ✅ Clean separation from detection/segmentation pipeline
    """
    # Signals
    scan_selected = Signal(int)  # Emit scan index when selected
    editor_completed = Signal()  # Emit when editor is completed successfully
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # State variables
        self.current_view = "Anterior"
        self._active_layers = []
        self._scans_cache: List[Dict] = []
        
        # ✅ NEW: Track image labels for smooth zoom
        self._image_labels: List[QLabel] = []
        self._original_pixmaps: List[QPixmap] = []  # Store original size pixmaps
        
        # ✅ NEW: Layer caching system
        self._layer_image_cache = {}  # Format: "scan_path_view_layer" -> PIL_Image
        self._cache_stats = {"hits": 0, "misses": 0}  # Performance tracking

        # ✅ NEW: Smart update tracking
        self._previous_layers = []  # Track previous active layers
        self._previous_opacities = {}  # Track previous opacities
        self._previous_scan_index = -1  # Track previous scan
        self._last_update_type = "full"  # Track last update type

        self.active_scan_index = 0
        self._zoom_factor = 1.0
        self.card_width = 350
        self.invert_original = False
        self._adjustments = {
            "Anterior": {"brightness": 0.0, "contrast": 1.0},
            "Posterior": {"brightness": 0.0, "contrast": 1.0}
        }
        self._anterior_image_label: QLabel | None = None
        self._posterior_image_label: QLabel | None = None
        
        # Layer opacity settings
        self._layer_opacities = {
            "Image": 1.0,
            "Segmentation": 0.4,      # Updated to 40%
            "Hotspot": 0.5,           # Already correct at 50%
            "HotspotBBox": 1.0        # Hidden from UI but still loaded
        }
        
        # Session code for path resolution
        self.session_code = None
        
        # ✅ NEW: BSI integration
        self.bsi_integration = get_bsi_integration()
        
        self._build_ui()
        self._setup_keyboard_shortcuts()

    def _generate_cache_key(self, scan_path: str, view: str, layer: str) -> str:
        """✅ IMPROVED: Generate unique cache key including invert state"""
        invert_suffix = "_inverted" if self.invert_original else "_normal"
        return f"{scan_path}_{view}_{layer}{invert_suffix}"

    def _clear_layer_cache(self):
        """✅ NEW: Clear layer cache (memory management)"""
        cache_size = len(self._layer_image_cache)
        self._layer_image_cache.clear()
        print(f"[CACHE] Cleared layer cache ({cache_size} entries)")
        self._cache_stats = {"hits": 0, "misses": 0}

    def _print_cache_stats(self):
        """✅ NEW: Print cache performance statistics"""
        total = self._cache_stats["hits"] + self._cache_stats["misses"]
        if total > 0:
            hit_rate = (self._cache_stats["hits"] / total) * 100
            print(f"[CACHE STATS] Hits: {self._cache_stats['hits']}, Misses: {self._cache_stats['misses']}, Hit Rate: {hit_rate:.1f}%")

    def _get_cached_layers(self, scan_path: str, view: str) -> Dict[str, Image.Image]:
        """✅ NEW: Retrieve cached layers for a scan and view"""
        cached_layers = {}
        layers_to_check = ["Image", "Segmentation", "Hotspot", "HotspotBBox"]
        
        print(f"[CACHE DEBUG] Checking {len(layers_to_check)} layers in cache")
        print(f"[CACHE DEBUG] Current cache size: {len(self._layer_image_cache)} entries")
        
        for layer in layers_to_check:
            cache_key = self._generate_cache_key(scan_path, view, layer)
            print(f"[CACHE DEBUG] Looking for key: {cache_key}")
            
            if cache_key in self._layer_image_cache:
                cached_layers[layer] = self._layer_image_cache[cache_key]
                self._cache_stats["hits"] += 1
                print(f"[CACHE DEBUG] Found {layer} in cache")
            else:
                print(f"[CACHE DEBUG] {layer} not in cache")
                self._cache_stats["misses"] += 1
                # ✅ CHANGED: Don't return None immediately, try to get partial cache
        
        # ✅ IMPROVED: Return partial cache if available
        if cached_layers:
            print(f"[CACHE PARTIAL] Returning {len(cached_layers)} cached layers: {list(cached_layers.keys())}")
            return cached_layers
        else:
            print(f"[CACHE EMPTY] No layers found in cache")
            return None
        
        return cached_layers if cached_layers else None

    def _cache_layer_image(self, scan_path: str, view: str, layer: str, image: Image.Image):
        """✅ NEW: Cache a layer image"""
        cache_key = self._generate_cache_key(scan_path, view, layer)
        self._layer_image_cache[cache_key] = image.copy()  # Store copy to avoid reference issues
        print(f"[CACHE] Cached {layer} for {view}")
    
    def _detect_changes(self, new_layers: list, new_opacities: dict, new_scan_index: int) -> dict:
        """✅ NEW: Detect what changed since last update"""
        changes = {
            "type": "none",
            "layers_added": [],
            "layers_removed": [],
            "opacities_changed": [],
            "scan_changed": False,
            "full_rebuild_needed": False
        }
        
        # Check scan change
        if new_scan_index != self._previous_scan_index:
            changes["scan_changed"] = True
            changes["type"] = "scan"
            changes["full_rebuild_needed"] = True
            print(f"[SMART UPDATE] Scan changed: {self._previous_scan_index} -> {new_scan_index}")
            return changes
        
        # Check layer changes
        old_layers_set = set(self._previous_layers)
        new_layers_set = set(new_layers)
        
        changes["layers_added"] = list(new_layers_set - old_layers_set)
        changes["layers_removed"] = list(old_layers_set - new_layers_set)
        
        # Check opacity changes
        for layer in new_layers_set:
            old_opacity = self._previous_opacities.get(layer, 1.0)
            new_opacity = new_opacities.get(layer, 1.0)
            if abs(old_opacity - new_opacity) > 0.01:  # Threshold for change detection
                changes["opacities_changed"].append(layer)
        
        # Determine change type
        if changes["layers_added"] or changes["layers_removed"]:
            changes["type"] = "layers"
            changes["full_rebuild_needed"] = True  # Layer composition change needs rebuild
        elif changes["opacities_changed"]:
            changes["type"] = "opacity"
            changes["full_rebuild_needed"] = False  # Opacity can be updated smartly
        
        print(f"[SMART UPDATE] Change type: {changes['type']}")
        if changes["layers_added"]:
            print(f"[SMART UPDATE] Layers added: {changes['layers_added']}")
        if changes["layers_removed"]:
            print(f"[SMART UPDATE] Layers removed: {changes['layers_removed']}")
        if changes["opacities_changed"]:
            print(f"[SMART UPDATE] Opacities changed: {changes['opacities_changed']}")
        
        return changes

    def _update_state_tracking(self, layers: list, opacities: dict, scan_index: int, update_type: str):
        """✅ NEW: Update state tracking after changes"""
        self._previous_layers = layers.copy()
        self._previous_opacities = opacities.copy()
        self._previous_scan_index = scan_index
        self._last_update_type = update_type
        print(f"[SMART UPDATE] State updated - Type: {update_type}")

    def _smart_opacity_update(self, opacity_changes: list):
        """✅ NEW: Update only opacity without rebuilding"""
        if not self._image_labels:
            print(f"[SMART UPDATE] No image labels for opacity update, falling back to rebuild")
            return False
        
        print(f"[SMART UPDATE] Applying opacity-only update for: {opacity_changes}")
        
        try:
            # Get current scan and layers
            if not self._scans_cache or self.active_scan_index < 0:
                return False
                
            active_scan = self._scans_cache[self.active_scan_index]
            
            # Update both Anterior and Posterior cards
            for view in ["Anterior", "Posterior"]:
                self.current_view = view
                
                # Get cached layers
                scan_path_str = str(active_scan["path"])
                cached_layers = self._get_cached_layers(scan_path_str, view)
                
                if not cached_layers:
                    print(f"[SMART UPDATE] No cached layers for {view}, fallback to rebuild")
                    return False
                
                # Apply new opacities and create composite
                active_layer_images = {}
                for layer_name in self._active_layers:
                    if layer_name == "HotspotBBox":
                        continue
                        
                    if layer_name in cached_layers:
                        layer_image = cached_layers[layer_name]
                        layer_opacity = self._layer_opacities.get(layer_name, 1.0)
                        
                        # Apply opacity to the layer
                        if layer_opacity < 1.0:
                            layer_image = apply_opacity_to_image(layer_image, layer_opacity)
                        
                        active_layer_images[layer_name] = layer_image
                
                if active_layer_images:
                    # Create new composite
                    uniform_opacities = {layer: 1.0 for layer in active_layer_images.keys()}
                    composite_image = create_composite_image(
                        layers=active_layer_images,
                        layer_order=self._active_layers,
                        layer_opacities=uniform_opacities
                    )
                    
                    # Convert composite to displayable format
                    if composite_image.mode == 'RGBA':
                        background = Image.new('RGB', composite_image.size, (255, 255, 255))
                        display_image = Image.alpha_composite(background.convert('RGBA'), composite_image)
                        display_image = display_image.convert('RGB')
                    else:
                        display_image = composite_image
                    
                    # Find and update the corresponding image label
                    target_label = self._anterior_image_label if view == "Anterior" else self._posterior_image_label
                    if target_label:
                        w = int(self.card_width * self._zoom_factor)
                        pixmap = _pil_to_pixmap(display_image, w)
                        target_label.setPixmap(pixmap)
                        
                        # Update the cached pixmap for zoom
                        label_index = None
                        for i, label in enumerate(self._image_labels):
                            if label == target_label:
                                label_index = i
                                break
                        
                        if label_index is not None and label_index < len(self._original_pixmaps):
                            self._original_pixmaps[label_index] = pixmap
                        
                        print(f"[SMART UPDATE] Updated {view} composite without rebuild")
            
            return True
            
        except Exception as e:
            print(f"[SMART UPDATE ERROR] Opacity update failed: {e}")
            return False
    
    def _build_ui(self):
        """Build the UI which is now just the scrollable timeline area."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Setup the scroll area directly
        self._setup_timeline_scroll_area()

        main_layout.addWidget(self.scroll_area)

    def get_brightness_contrast(self, view_name: str) -> dict:
        """Returns the brightness and contrast values for a specific view."""
        return self._adjustments.get(view_name, {"brightness": 0.0, "contrast": 1.0})
    
    def set_brightness_contrast(self, view_name: str, brightness: float, contrast: float):
        """
        ✅ Sets the B/C values for a specific view and rebuilds the timeline.
        """
        if view_name in self._adjustments:
            print(f"[DEBUG] Setting {view_name} contrast: B={brightness:.2f}, C={contrast:.2f}")
            self._adjustments[view_name]["brightness"] = brightness
            self._adjustments[view_name]["contrast"] = contrast
            
            # ✅ NEW: Clear cache since B/C affects images
            self._clear_layer_cache()
            
            self._rebuild()
        else:
            print(f"[WARN] View '{view_name}' not found in adjustments dictionary. Cannot set contrast.")

 
    def preview_brightness_contrast(self, view_name: str, brightness: float, contrast: float):
        """✅ FIXED: Applies a temporary B/C adjustment using the new override logic."""
        if not self._scans_cache or self.active_scan_index < 0:
            return

        active_scan = self._scans_cache[self.active_scan_index]
        w = int(self.card_width * self._zoom_factor)

        target_label = self._anterior_image_label if view_name == "Anterior" else self._posterior_image_label
        if not target_label:
            print(f"[WARN] Preview failed: Could not find target label for {view_name}")
            return

        original_view_state = self.current_view
        self.current_view = view_name
        
        # Get all layers, passing the override values for the preview
        all_layers = self._get_layer_images(active_scan, override_b=brightness, override_c=contrast)

        # Re-composite the image with the adjusted layer
        active_layers_for_composite = {k: v for k, v in all_layers.items() if k in self._active_layers}
        
        if active_layers_for_composite:
            composite_image = create_composite_image(
                layers=active_layers_for_composite,
                layer_order=self._active_layers,
                layer_opacities=self._layer_opacities
            )
            
            pixmap = _pil_to_pixmap(composite_image, w)
            target_label.setPixmap(pixmap)
        
        self.current_view = original_view_state


    def set_brightness_contrast(self, view_name: str, brightness: float, contrast: float):
        """
        ✅ Sets the B/C values for a specific view and rebuilds the timeline.
        """
        if view_name in self._adjustments:
            print(f"[DEBUG] Setting {view_name} contrast: B={brightness:.2f}, C={contrast:.2f}")
            self._adjustments[view_name]["brightness"] = brightness
            self._adjustments[view_name]["contrast"] = contrast
            self._rebuild()
        else:
            print(f"[WARN] View '{view_name}' not found in adjustments. Cannot set contrast.")

    
    def _load_segmentation_layer(self, layers: dict, dicom_path: Path, filename_with_date: str, view_normalized: str, study_date_folder: Path = None, session_code: str = None):
        """✅ FIXED: Load segmentation layer using NEWEST priority system from paths.py"""
        try:
            if study_date_folder is None:
                study_date_folder = dicom_path.parent
                
            view_name = "anterior" if view_normalized in ["anterior", "ant"] else "posterior"
            
            # ✅ NEW: Use the same function as hotspot editor
            from core.config.paths import get_newest_segmentation_path
            
            segmentation_path = get_newest_segmentation_path(study_date_folder, view_name)
            print(f"[DEBUG] Looking for segmentation (NEWEST): {segmentation_path}")

            if segmentation_path and segmentation_path.exists():
                # Load with transparency (make black pixels transparent)
                seg_image = load_image_with_transparency(segmentation_path, make_transparent=True)
                if seg_image:
                    layers["Segmentation"] = seg_image
                    print(f"[DEBUG] ✅ Loaded segmentation with transparency: {segmentation_path}")
                    
                    # ✅ DEBUG: Show if this is edited or original file
                    is_edited = "_" in segmentation_path.stem and len(segmentation_path.stem.split('_')[-1]) == 6 and segmentation_path.stem.split('_')[-1].isdigit()
                    file_type = "EDITED" if is_edited else "ORIGINAL"
                    print(f"[DEBUG] Segmentation type: {file_type}")
            else:
                print(f"[WARN] Segmentation file not found: {segmentation_path}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to load segmentation layer: {e}")

    def _load_hotspot_layer(self, layers: dict, dicom_path: Path, filename_with_date: str, view_normalized: str, study_date_folder: Path = None, session_code: str = None):
        """✅ FIXED: Load hotspot layer using NEWEST priority system from paths.py"""
        try:
            if study_date_folder is None:
                study_date_folder = dicom_path.parent
                
            view_name = "anterior" if view_normalized in ["anterior", "ant"] else "posterior"
            
            # ✅ NEW: Use the same function as hotspot editor
            from core.config.paths import get_newest_hotspot_classification_path
            
            classification_png = get_newest_hotspot_classification_path(study_date_folder, view_name)
            print(f"[DEBUG] Looking for hotspot classification (NEWEST): {classification_png}")
            
            if classification_png and classification_png.exists():
                hotspot_image = load_image_with_transparency(classification_png)
                if hotspot_image:
                    layers["Hotspot"] = hotspot_image
                    print(f"[DEBUG] ✅ Loaded hotspot layer: {classification_png}")
                    
                    # ✅ DEBUG: Show if this is edited or original file
                    is_edited = "_" in classification_png.stem and len(classification_png.stem.split('_')[-1]) == 6 and classification_png.stem.split('_')[-1].isdigit()
                    file_type = "EDITED" if is_edited else "ORIGINAL"
                    print(f"[DEBUG] Hotspot type: {file_type}")
            else:
                print(f"[DEBUG] No hotspot classification found: {classification_png}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to load hotspot layer: {e}")

    def _load_bbox_layer(self, layers: dict, dicom_path: Path, filename_with_date: str, view_normalized: str, study_date_folder: Path = None, session_code: str = None):
        """✅ FIXED: Load bounding box layer using NEWEST priority system from paths.py"""
        try:
            if study_date_folder is None:
                study_date_folder = dicom_path.parent
                
            view_name = "anterior" if view_normalized in ["anterior", "ant"] else "posterior"
            view_short = "ant" if view_name == "anterior" else "post"
            
            # ✅ NEW: Use the same function as hotspot editor
            from core.config.paths import get_newest_hotspot_classification_path
            
            classification_png = get_newest_hotspot_classification_path(study_date_folder, view_name)
            
            # Get corresponding XML file using same logic as hotspot editor
            if classification_png:
                xml_name = f"{view_short}_hotspot_classification.xml"
                
                # If PNG is timestamped, find corresponding timestamped XML
                if "_" in classification_png.stem:
                    png_parts = classification_png.stem.split("_")
                    if len(png_parts) >= 4 and len(png_parts[-1]) == 6 and png_parts[-1].isdigit():
                        timestamp = png_parts[-1]
                        xml_timestamped_name = f"{view_short}_hotspot_classification_{timestamp}.xml"
                        classification_xml = classification_png.parent / xml_timestamped_name
                    else:
                        classification_xml = classification_png.parent / xml_name
                else:
                    classification_xml = classification_png.parent / xml_name
            else:
                classification_xml = study_date_folder / f"{view_short}_hotspot_classification.xml"
            
            print(f"[DEBUG] Looking for classification XML (NEWEST): {classification_xml}")
            
            if classification_xml and classification_xml.exists():
                if "Image" in layers:
                    image_dimensions = layers["Image"].size
                    bbox_image = self._create_bbox_visualization_from_classification(classification_xml, image_dimensions)
                    if bbox_image:
                        layers["HotspotBBox"] = bbox_image
                        print(f"[DEBUG] ✅ Loaded bbox layer: {classification_xml}")
                        
                        # ✅ DEBUG: Show if this is edited or original file
                        is_edited = "_" in classification_xml.stem and len(classification_xml.stem.split('_')[-1]) == 6 and classification_xml.stem.split('_')[-1].isdigit()
                        file_type = "EDITED" if is_edited else "ORIGINAL"
                        print(f"[DEBUG] BBox XML type: {file_type}")
            else:
                print(f"[DEBUG] No classification XML found: {classification_xml}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to load bbox layer: {e}")

    def has_layer_data(self, layer: str) -> bool:
        """✅ FIXED: Check if layer data is available using NEWEST priority system"""
        if not self._scans_cache:
            return False
        
        # HotspotBBox is hidden from UI
        if layer == "HotspotBBox":
            return False
        
        try:
            # Check if any scan has data for this layer using newest priority system
            for scan in self._scans_cache:
                dicom_path = Path(scan["path"])
                
                # Get patient info for session_code
                patient_id, session_code = self._get_patient_session_from_scan(scan)
                study_date = extract_study_date_from_dicom(dicom_path)
                
                # Use patient folder (study_date folder) directly
                patient_folder = dicom_path.parent

                # ✅ Check each view using newest priority system
                for view_name in ["anterior", "posterior"]:
                    if layer == "Image":
                        # Check for original image files
                        frame_map = scan.get("frames", {})
                        view_display_name = "Anterior" if view_name == "anterior" else "Posterior"
                        original_image = load_original_image_from_path(dicom_path, view_display_name, frame_map)
                        if original_image:
                            return True
                            
                    elif layer == "Segmentation":
                        # Check for segmentation files with newest priority
                        from core.config.paths import get_newest_segmentation_path
                        segmentation_path = get_newest_segmentation_path(patient_folder, view_name)
                        if segmentation_path and segmentation_path.exists():
                            return True
                            
                    elif layer == "Hotspot":
                        # Check for hotspot classification files with newest priority
                        from core.config.paths import get_newest_hotspot_classification_path
                        classification_path = get_newest_hotspot_classification_path(patient_folder, view_name)
                        if classification_path and classification_path.exists():
                            return True
            
            return False
            
        except Exception as e:
            print(f"[WARN] Error checking layer data with newest priority system: {e}")
            return False
    
    def set_invert_original(self, inverted: bool):
        """✅ OPTIMIZED: Set invert status with change detection"""
        print(f"[DEBUG] set_invert_original called: {inverted} (current: {self.invert_original})")
        
        # Only rebuild if state actually changed
        if self.invert_original != inverted:
            old_state = self.invert_original
            self.invert_original = inverted
            
            # ✅ UPDATED: Clear layer cache since invert affects all images
            self._clear_layer_cache()
            print(f"[DEBUG] Cleared layer cache due to invert change")
            
            # Force rebuild if we have scans loaded
            if self._scans_cache:
                print(f"[DEBUG] Forcing timeline rebuild for invert change...")
                self._rebuild()
            else:
                print(f"[DEBUG] No scans loaded, rebuild skipped")
        else:
            print(f"[DEBUG] Invert state unchanged, skipping rebuild")
        
    def _update_edit_button_states(self):
        """Update edit button enabled/disabled states and styling"""
        has_segmentation = "Segmentation" in self.timeline_widget._active_layers
        has_hotspot = "Hotspot" in self._active_layers
        has_scan = bool(self.timeline_widget._scans_cache)
        
        # Segmentation edit button
        if has_segmentation and has_scan:
            self.seg_edit_btn.setEnabled(True)
            self.seg_edit_btn.setStyleSheet(SUCCESS_BUTTON_STYLE + """
                QPushButton {
                    font-size: 11px;
                    padding: 6px 8px;
                    margin: 2px 0px;
                }
            """)
        else:
            self.seg_edit_btn.setEnabled(False)
            self.seg_edit_btn.setStyleSheet(GRAY_BUTTON_STYLE + """
                QPushButton {
                    font-size: 11px;
                    padding: 6px 8px;
                    margin: 2px 0px;
                    opacity: 0.6;
                }
            """)
        
        # ✅ FIXED: Hotspot edit button - require both hotspot layer AND scan
        if has_hotspot and has_scan:
            self.hotspot_edit_btn.setEnabled(True)
            self.hotspot_edit_btn.setStyleSheet(ZOOM_BUTTON_STYLE + """
                QPushButton {
                    font-size: 11px;
                    padding: 6px 8px;
                    margin: 2px 0px;
                }
            """)
        else:
            self.hotspot_edit_btn.setEnabled(False)
            self.hotspot_edit_btn.setStyleSheet(GRAY_BUTTON_STYLE + """
                QPushButton {
                    font-size: 11px;
                    padding: 6px 8px;
                    margin: 2px 0px;
                    opacity: 0.6;
                }
            """)
        
        
    def _setup_timeline_scroll_area(self):
        """✅ FIXED: Setup scrollable timeline area with BOTH horizontal and vertical scrolling"""
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        # ✅ FIXED: Enable BOTH horizontal AND vertical scrollbars
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # ✅ FIXED: Added vertical scroll
        
        # ✅ NEW: Enable mouse wheel support
        self.scroll_area.setFocusPolicy(Qt.WheelFocus)
        
        self.container = QWidget()
        self.timeline_layout = QHBoxLayout(self.container)
        self.timeline_layout.setAlignment(Qt.AlignLeft)
        self.scroll_area.setWidget(self.container)

    def _setup_keyboard_shortcuts(self):
        """✅ NEW: Setup keyboard shortcuts for zoom control"""
        # Zoom in: Ctrl + Plus
        self.zoom_in_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        self.zoom_in_shortcut.activated.connect(self.zoom_in)
        
        # Alternative: Ctrl + Equal (for keyboards without numpad)
        self.zoom_in_alt_shortcut = QShortcut(QKeySequence("Ctrl+="), self)
        self.zoom_in_alt_shortcut.activated.connect(self.zoom_in)
        
        # Zoom out: Ctrl + Minus
        self.zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        self.zoom_out_shortcut.activated.connect(self.zoom_out)
        
        # Reset zoom: Ctrl + 0
        self.zoom_reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        self.zoom_reset_shortcut.activated.connect(self.zoom_reset)
        
        print("[DEBUG] Timeline keyboard shortcuts enabled: Ctrl+/- for zoom, Ctrl+0 for reset")

    def wheelEvent(self, event: QWheelEvent):
        """✅ NEW: Handle mouse wheel events for zoom when Ctrl is pressed"""
        if event.modifiers() == Qt.ControlModifier:
            # Zoom with Ctrl + wheel
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            # Normal scrolling
            super().wheelEvent(event)

    def _create_control_panel(self) -> QWidget:
        """Create the resizable control panel"""
        panel = QWidget()
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(400)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Panel title
        title = QLabel("<b>Layer Controls</b>")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #495057;
                padding: 5px;
                background: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #e9ecef;
            }
        """)
        layout.addWidget(title)
        
        # Active layers display
        self.active_layers_label = QLabel("Active Layers: None")
        self.active_layers_label.setWordWrap(True)
        self.active_layers_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #6c757d;
                padding: 8px;
                background: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                margin: 5px 0px;
            }
        """)
        layout.addWidget(self.active_layers_label)
        
        # Edit buttons section
        edit_group = QWidget()
        edit_layout = QVBoxLayout(edit_group)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        
        edit_title = QLabel("<b>Edit Options</b>")
        edit_title.setStyleSheet("font-size: 12px; color: #495057; margin-bottom: 5px;")
        edit_layout.addWidget(edit_title)
        
        # Segmentation edit button
        self.seg_edit_btn = QPushButton("Edit Segmentation")
        self.seg_edit_btn.setStyleSheet(SUCCESS_BUTTON_STYLE + """
            QPushButton {
                font-size: 11px;
                padding: 6px 8px;
                margin: 2px 0px;
            }
        """)
        self.seg_edit_btn.clicked.connect(self._open_segmentation_editor)
        edit_layout.addWidget(self.seg_edit_btn)
        
        # ✅ UPDATED: Hotspot edit button (classification only)
        self.hotspot_edit_btn = QPushButton("Edit Hotspot")
        self.hotspot_edit_btn.setStyleSheet(ZOOM_BUTTON_STYLE + """
            QPushButton {
                font-size: 11px;
                padding: 6px 8px;
                margin: 2px 0px;
            }
        """)
        self.hotspot_edit_btn.clicked.connect(self._open_hotspot_editor)
        edit_layout.addWidget(self.hotspot_edit_btn)
        
        layout.addWidget(edit_group)
        
        # Current scan info
        self.scan_info_label = QLabel("No scan selected")
        self.scan_info_label.setWordWrap(True)
        self.scan_info_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #6c757d;
                padding: 6px;
                background: #f8f9fa;
                border-radius: 3px;
                margin-top: 10px;
            }
        """)
        layout.addWidget(self.scan_info_label)
        
        # ✅ NEW: Zoom controls and shortcuts info
        zoom_group = QWidget()
        zoom_layout = QVBoxLayout(zoom_group)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        
        zoom_title = QLabel("<b>Zoom Controls</b>")
        zoom_title.setStyleSheet("font-size: 12px; color: #495057; margin-bottom: 5px;")
        zoom_layout.addWidget(zoom_title)
        
        shortcuts_label = QLabel("Ctrl + / - : Zoom\nCtrl + 0 : Reset")
        shortcuts_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #6c757d;
                padding: 4px;
                background: #f8f9fa;
                border-radius: 3px;
            }
        """)
        zoom_layout.addWidget(shortcuts_label)
        
        layout.addWidget(zoom_group)
        layout.addStretch()
        
        # Update button states initially
        self._update_edit_button_states()
        
        return panel

    

    # ------------------------------------------------------ zoom
    def zoom_in(self):  
        """✅ OPTIMIZED: Smooth zoom in using Qt scaling"""
        self._zoom_factor *= 1.15
        print(f"[DEBUG] Timeline zoom in: {self._zoom_factor:.2f}")
        self._update_zoom_smooth()
        
    def zoom_out(self): 
        """✅ OPTIMIZED: Smooth zoom out using Qt scaling"""
        self._zoom_factor *= 0.87
        print(f"[DEBUG] Timeline zoom out: {self._zoom_factor:.2f}")
        self._update_zoom_smooth()

    def zoom_reset(self):
        """✅ OPTIMIZED: Reset zoom using Qt scaling"""
        self._zoom_factor = 1.0
        print(f"[DEBUG] Timeline zoom reset: {self._zoom_factor:.2f}")
        self._update_zoom_smooth()

    def _update_zoom_smooth(self):
        """✅ NEW: Update zoom using Qt's native scaling (no rebuild)"""
        if not self._original_pixmaps or not self._image_labels:
            print(f"[DEBUG] No cached pixmaps, falling back to rebuild")
            self._rebuild()
            return
        
        print(f"[DEBUG] Smooth zoom update for {len(self._image_labels)} labels")
        
        for i, (label, original_pixmap) in enumerate(zip(self._image_labels, self._original_pixmaps)):
            if original_pixmap and not original_pixmap.isNull():
                # Calculate new width based on zoom factor
                original_width = original_pixmap.width()
                new_width = int(original_width * self._zoom_factor)
                
                # Scale from original pixmap (better quality)
                scaled_pixmap = original_pixmap.scaledToWidth(
                    new_width, 
                    Qt.SmoothTransformation
                )
                
                label.setPixmap(scaled_pixmap)
                print(f"[DEBUG] Scaled label {i}: {original_width} -> {new_width}")

    # ------------------------------------------------------ public API
    def display_timeline(self, scans: List[Dict], active_index: int = -1):
        """✅ MODIFIED: Display timeline with BSI integration, defaulting to the first scan."""
        print(f"[DEBUG] display_timeline called with {len(scans)} scan(s), focusing on index = {active_index}")
        
        updated_scans = []
        for scan in scans:
            updated_scan = self.bsi_integration.update_scan_meta_with_bsi(scan, self.session_code)
            updated_scans.append(updated_scan)
        
        self._scans_cache = updated_scans
        # Set the active index. If -1 was passed, default to 0 if scans exist.
        self.active_scan_index = active_index if active_index >= 0 else (0 if self._scans_cache else -1)
        
        self._zoom_factor = 1.0
        self._rebuild()
        

    def set_active_view(self, v: str): 
        """
        ✅ MODIFIED: This method is no longer needed as Anterior/Posterior are shown together.
        Calling it will have no effect.
        """
        print(f"[DEBUG] set_active_view called with '{v}', but is now ignored.")
        # Intentionally do nothing. The _rebuild method now controls the view for each card.
        pass
        
    def set_active_layers(self, layers: list): 
        """✅ SMART: Set active layers with smart update detection"""
        new_layers = layers.copy()
        
        # Detect changes
        changes = self._detect_changes(
            new_layers=new_layers,
            new_opacities=self._layer_opacities,
            new_scan_index=self.active_scan_index
        )
        
        # Update active layers
        self._active_layers = new_layers
        print(f"[DEBUG] Timeline active layers set to: {self._active_layers}")
        
        # Apply appropriate update strategy
        if changes["type"] == "none":
            print(f"[SMART UPDATE] No changes detected, skipping update")
            return
        elif changes["full_rebuild_needed"]:
            print(f"[SMART UPDATE] Full rebuild required for change type: {changes['type']}")
            self._rebuild()
        else:
            print(f"[SMART UPDATE] Attempting smart update for change type: {changes['type']}")
            self._rebuild()  # For now, always rebuild for layer changes
        
        # Update state tracking
        self._update_state_tracking(new_layers, self._layer_opacities, self.active_scan_index, changes["type"])
    
    
    def set_session_code(self, session_code: str):
        """Set session code for path resolution"""
        self.session_code = session_code
    
    def set_layer_opacity(self, layer: str, opacity: float):
        """✅ SMART: Set opacity with smart update detection"""
        old_opacity = self._layer_opacities.get(layer, 1.0)
        self._layer_opacities[layer] = opacity
        print(f"[DEBUG] Set {layer} opacity to {opacity:.2f}")
        
        # Detect changes
        changes = self._detect_changes(
            new_layers=self._active_layers,
            new_opacities=self._layer_opacities,
            new_scan_index=self.active_scan_index
        )
        
        # Apply appropriate update strategy
        if changes["type"] == "opacity" and not changes["full_rebuild_needed"]:
            print(f"[SMART UPDATE] Attempting smart opacity update")
            success = self._smart_opacity_update(changes["opacities_changed"])
            if success:
                print(f"[SMART UPDATE] ✅ Smart opacity update successful")
                # Update state tracking
                self._update_state_tracking(self._active_layers, self._layer_opacities, self.active_scan_index, "opacity")
                return
            else:
                print(f"[SMART UPDATE] ❌ Smart opacity update failed, falling back to rebuild")
        
        # Fallback to full rebuild
        print(f"[SMART UPDATE] Using full rebuild for opacity change")
        self._rebuild()
        
        # Update state tracking
        self._update_state_tracking(self._active_layers, self._layer_opacities, self.active_scan_index, "rebuild")
    
    def get_layer_opacity(self, layer: str) -> float:
        """Get opacity for a specific layer"""
        return self._layer_opacities.get(layer, 1.0)

    # ===== Required methods =====
    def is_layer_active(self, layer: str) -> bool:
        """Check if a specific layer is currently active"""
        return layer in self._active_layers

    def refresh_current_view(self):
        """Refresh current view - rebuild the timeline display"""
        print("[DEBUG] Refreshing current timeline view...")
        self._rebuild()

    def get_active_layers(self) -> list:
        """Get list of currently active layers"""
        return self._active_layers.copy()

    
    def debug_layer_file_priority(self, scan_index: int = None):
        """✅ NEW: Debug method to show which files are being selected by priority system"""
        if scan_index is None:
            scan_index = self.active_scan_index
            
        if not self._scans_cache or scan_index < 0:
            print("[DEBUG PRIORITY] No active scan")
            return
            
        active_scan = self._scans_cache[scan_index]
        dicom_path = Path(active_scan["path"])
        
        try:
            patient_id, session_code = self._get_patient_session_from_scan(active_scan)
            study_date = extract_study_date_from_dicom(dicom_path)
            
            if session_code and session_code != "UNKNOWN":
                study_date_folder = get_patient_planar_path(session_code, patient_id, study_date)
            else:
                study_date_folder = dicom_path.parent
                
            print(f"\n🔍 [DEBUG PRIORITY] File priority analysis for scan {scan_index}")
            print(f"🔍 [DEBUG PRIORITY] Study date folder: {study_date_folder}")
            print(f"🔍 [DEBUG PRIORITY] Session code: {session_code}")
            
            for view in ["ant", "post"]:
                print(f"\n🔍 [DEBUG PRIORITY] === {view.upper()} VIEW ===")
                
                # Segmentation files
                seg_files = get_planar_segmentation_files(
                    study_date_folder, view, with_priority=True, session_code=session_code
                )
                seg_file = seg_files['segmentation_png']
                is_seg_edited = "_20" in str(seg_file) and len(seg_file.stem.split('_')[-1]) == 6
                print(f"🔍 [DEBUG PRIORITY] Segmentation: {seg_file}")
                print(f"🔍 [DEBUG PRIORITY] Segmentation type: {'EDITED' if is_seg_edited else 'ORIGINAL'}")
                print(f"🔍 [DEBUG PRIORITY] Segmentation exists: {seg_file.exists()}")
                
                # Hotspot files
                hotspot_files = get_planar_hotspot_files(
                    study_date_folder, view, with_priority=True, session_code=session_code
                )
                
                class_png = hotspot_files['classification_png']
                class_xml = hotspot_files['classification_xml']
                
                is_png_edited = "_20" in str(class_png) and len(class_png.stem.split('_')[-1]) == 6
                is_xml_edited = "_20" in str(class_xml) and len(class_xml.stem.split('_')[-1]) == 6
                
                print(f"🔍 [DEBUG PRIORITY] Classification PNG: {class_png}")
                print(f"🔍 [DEBUG PRIORITY] Classification PNG type: {'EDITED' if is_png_edited else 'ORIGINAL'}")
                print(f"🔍 [DEBUG PRIORITY] Classification PNG exists: {class_png.exists()}")
                
                print(f"🔍 [DEBUG PRIORITY] Classification XML: {class_xml}")
                print(f"🔍 [DEBUG PRIORITY] Classification XML type: {'EDITED' if is_xml_edited else 'ORIGINAL'}")
                print(f"🔍 [DEBUG PRIORITY] Classification XML exists: {class_xml.exists()}")
                
        except Exception as e:
            print(f"🔍 [DEBUG PRIORITY ERROR] {e}")
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------ rebuild
    def _clear(self):
        # ✅ NEW: Clear zoom cache
        self._image_labels.clear()
        self._original_pixmaps.clear()
        
        # ✅ NEW: Print cache stats before clearing
        self._print_cache_stats()
        
        while self.timeline_layout.count():
            w = self.timeline_layout.takeAt(0).widget()
            if w: 
                w.deleteLater()
    
    def _validate_zoom_cache(self) -> bool:
        """✅ NEW: Validate if zoom cache is still valid"""
        if len(self._image_labels) != len(self._original_pixmaps):
            return False
        
        if not self._scans_cache:
            return False
            
        # Check if number of labels matches expected scan count * 2 (anterior + posterior)
        expected_labels = len(self._scans_cache) if self._scans_cache else 0
        if self.active_scan_index >= 0:
            expected_labels = 2  # Only anterior + posterior for active scan
        
        return len(self._image_labels) == expected_labels

    def _force_rebuild_if_needed(self):
        """✅ NEW: Force rebuild if cache is invalid"""
        if not self._validate_zoom_cache():
            print(f"[DEBUG] Cache invalid, forcing rebuild")
            self._rebuild()
            return True
        return False
    
    def _rebuild(self):
        """✅ MODIFIED: Rebuild to show Anterior and Posterior of the active scan side-by-side."""
        self._clear()
        print(f"[DEBUG] Rebuilding timeline for active scan index: {self.active_scan_index}")

        if not self._scans_cache or self.active_scan_index < 0:
            placeholder = QLabel("No scan selected or available.")
            placeholder.setAlignment(Qt.AlignCenter)
            # (Stylesheet for placeholder remains the same)
            self.timeline_layout.addWidget(placeholder)
            return

        # Get the single active scan
        active_scan = self._scans_cache[self.active_scan_index]
        
        # Calculate card width based on zoom
        w = int(self.card_width * self._zoom_factor)

        # --- Create Anterior Card ---
        self.current_view = "Anterior"
        anterior_card = self._make_layered_card(active_scan, w, self.active_scan_index)
        self.timeline_layout.addWidget(anterior_card)
        # ✅ FIX: Find the UNIQUE object name for the anterior label
        self._anterior_image_label = anterior_card.findChild(QLabel, "image_display_Anterior")

        # --- Create Posterior Card ---
        self.current_view = "Posterior"
        posterior_card = self._make_layered_card(active_scan, w, self.active_scan_index)
        self.timeline_layout.addWidget(posterior_card)
        # ✅ FIX: Find the UNIQUE object name for the posterior label
        self._posterior_image_label = posterior_card.findChild(QLabel, "image_display_Posterior")

        self.timeline_layout.addStretch()

        # ✅ NEW: Update state tracking after rebuild
        self._update_state_tracking(self._active_layers, self._layer_opacities, self.active_scan_index, "full")

    # ------------------------------------------------------ card builders
    def _make_header(self, scan: Dict, idx: int) -> QHBoxLayout:
        """✅ FIXED: Header with BSI per frame information (no combined)"""
        meta = scan["meta"]
        date_raw = meta.get("study_date", "")
        try:   
            hdr = datetime.strptime(date_raw, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError: 
            hdr = "Unknown"
        
        # ✅ NEW: Always show view name, with BSI if available
        view_name = self.current_view
        color = "#ff6b6b" if self.current_view == "Anterior" else "#4ecdc4"
        
        if meta.get("has_bsi", False):
            if self.current_view == "Anterior":
                bsi_score = meta.get("bsi_anterior", 0.0)
            else:  # Posterior
                bsi_score = meta.get("bsi_posterior", 0.0)
            
            # ✅ FORMAT: 10 decimal places with truncation
            bsi_str = f"{bsi_score:.10f}".rstrip('0').rstrip('.')
            if len(bsi_str.split('.')[-1]) > 10:
                bsi_str = f"{bsi_score:.10f}..."
            
            # ✅ UPDATED: Show view with BSI (no percent sign)
            view_text = f"<span style='color: {color}; font-weight: bold; font-size: 12px;'>{view_name} BSI: {bsi_str}</span>"
        else:
            # ✅ NEW: Show view name only when no BSI
            view_text = f"<span style='color: {color}; font-weight: bold; font-size: 12px;'>{view_name}</span>"
        
        hbox = QHBoxLayout()
        
        # ✅ UPDATED: Always show view name
        header_label = QLabel(f"<b>{hdr}</b><br>{view_text}")
        header_label.setStyleSheet("font-size: 11px;")
        hbox.addWidget(header_label)
        hbox.addStretch()
        
        # Select button
        select_btn = QPushButton("Select")
        select_btn.setFixedSize(60, 24)
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)
        select_btn.clicked.connect(lambda *_: self._on_scan_selected(idx))
        hbox.addWidget(select_btn)
        
        return hbox
    
    def _on_scan_selected(self, idx: int):
        """Handle scan selection and emit signal to parent"""
        print(f"[DEBUG] Timeline scan selected: {idx}")
        self.active_scan_index = idx
        
        
        # Emit signal to parent (MainWindow) to sync with scan buttons
        self.scan_selected.emit(idx)
        
        # Rebuild to update visual selection
        self._rebuild()
    
    def _get_patient_session_from_scan(self, scan: Dict) -> tuple[str, str]:
        """Extract patient ID and session code from scan path using NEW structure"""
        try:
            dicom_path = Path(scan["path"])
            patient_id, session_code = extract_patient_info_from_path(dicom_path)
            
            # ✅ TAMBAHAN: Debug dan validasi
            print(f"[DEBUG] Extracted patient info - ID: {patient_id}, Session: {session_code}")
            print(f"[DEBUG] Original path: {dicom_path}")
            
            # ✅ VALIDASI: Pastikan patient_id bukan study_date (8 digit angka)
            if len(patient_id) == 8 and patient_id.isdigit():
                print(f"[WARN] Patient ID looks like study_date: {patient_id}")
                # Coba ekstrak ulang dengan manual parsing
                parts = dicom_path.parts
                planar_index = None
                for i, part in enumerate(parts):
                    if part == "PLANAR":
                        planar_index = i
                        break
                
                if planar_index is not None and len(parts) > planar_index + 2:
                    session_code = parts[planar_index + 1]  # ATL
                    patient_id = parts[planar_index + 2]    # 5001
                    print(f"[DEBUG] Manual extraction - ID: {patient_id}, Session: {session_code}")
            
            # Fallback to session from widget if extraction fails
            if session_code == "UNKNOWN" and self.session_code:
                session_code = self.session_code
                
            return patient_id, session_code
        except Exception as e:
            print(f"[WARN] Failed to extract patient/session from scan: {e}")
            return "UNKNOWN", self.session_code or "UNKNOWN"
    
    def _create_bbox_visualization_from_classification(self, xml_path: Path, image_dimensions: tuple) -> Optional[Image.Image]:
        """✅ FIXED: Create bounding box visualization from CLASSIFICATION XML only"""
        try:
            import xml.etree.ElementTree as ET
            from PIL import ImageDraw, ImageFont
            
            print(f"[DEBUG] Loading CLASSIFICATION XML for bbox: {xml_path}")
            
            # Parse XML file
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Get image dimensions
            width, height = image_dimensions  # (width, height) from PIL Image.size
            
            # Create transparent image for bounding boxes
            bbox_image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(bbox_image)
            
            # ✅ CLASSIFICATION COLOR MAPPING (from classification results)
            color_map = {
                "Abnormal": (255, 0, 0, 255),      # Red for abnormal classification
                "Normal": (255, 241, 188, 255)     # Light yellow for normal classification
            }
            
            # Try to load a font for labels (fallback to default if not available)
            try:
                # Try to use a small system font
                font = ImageFont.truetype("arial.ttf", 10)
            except (OSError, IOError):
                try:
                    # Fallback to default PIL font
                    font = ImageFont.load_default()
                except:
                    font = None
            
            # Extract bounding boxes from CLASSIFICATION XML
            boxes_found = 0
            for obj in root.findall('.//object'):
                try:
                    # Get class name (should be "Abnormal" or "Normal" from classification)
                    name_elem = obj.find('name')
                    if name_elem is None:
                        continue
                    class_name = name_elem.text.strip()
                    
                    # Get bounding box coordinates
                    bbox = obj.find('bndbox')
                    if bbox is not None:
                        xmin = int(float(bbox.find('xmin').text))
                        ymin = int(float(bbox.find('ymin').text))
                        xmax = int(float(bbox.find('xmax').text))
                        ymax = int(float(bbox.find('ymax').text))
                        
                        # Get color for this classification result
                        box_color = color_map.get(class_name, (255, 255, 255, 255))  # White fallback
                        
                        # ✅ Draw thin rectangle for classification result
                        draw.rectangle([xmin, ymin, xmax, ymax], 
                                    outline=box_color,
                                    fill=None,
                                    width=1)
                        
                        # ✅ Draw classification label
                        if font:
                            # Calculate label position (above the box)
                            label_x = xmin
                            label_y = max(0, ymin - 12)  # 12 pixels above, but not negative
                            
                            # Draw label background
                            try:
                                # Get text size
                                bbox_text = draw.textbbox((0, 0), class_name, font=font)
                                text_width = bbox_text[2] - bbox_text[0]
                                text_height = bbox_text[3] - bbox_text[1]
                            except:
                                # Fallback if textbbox is not available (older PIL)
                                text_width, text_height = font.getsize(class_name)
                            
                            # Draw background rectangle for text
                            bg_color = (*box_color[:3], 180)  # Semi-transparent background
                            draw.rectangle([label_x, label_y, 
                                        label_x + text_width + 4, 
                                        label_y + text_height + 2], 
                                        fill=bg_color, 
                                        outline=None)
                            
                            # Draw text
                            text_color = (0, 0, 0, 255) if class_name == "Normal" else (255, 255, 255, 255)
                            draw.text((label_x + 2, label_y + 1), class_name, 
                                    fill=text_color, font=font)
                        
                        boxes_found += 1
                        print(f"[DEBUG] Drew CLASSIFICATION {class_name} bbox: ({xmin},{ymin}) -> ({xmax},{ymax})")
                        
                except (ValueError, AttributeError) as e:
                    print(f"[WARN] Error parsing classification bbox in XML: {e}")
                    continue
            
            if boxes_found > 0:
                print(f"[DEBUG] ✅ Created CLASSIFICATION bbox visualization with {boxes_found} boxes")
                return bbox_image
            else:
                print(f"[DEBUG] ❌ No valid classification boxes found in XML")
                return None
                
        except Exception as e:
            print(f"[ERROR] Failed to create classification bbox visualization: {e}")
            return None
    
    def _get_layer_images(self, scan: Dict, override_b: float = None, override_c: float = None) -> Dict[str, Image.Image]:
        frame_map = scan["frames"]
        dicom_path = Path(scan["path"])
        scan_path_str = str(dicom_path)

        # ✅ TAMBAHAN: Debug print
        print(f"[DEBUG] DICOM path: {dicom_path}")
        print(f"[DEBUG] Current view: {self.current_view}")
        
        # ✅ NEW: Check cache first for non-adjusted images
        use_cache = (override_b is None and override_c is None)  # Remove invert check
        invert_suffix = "_inverted" if self.invert_original else "_normal"
        print(f"[CACHE DEBUG] use_cache={use_cache}, override_b={override_b}, override_c={override_c}, invert={self.invert_original}")

        if use_cache:
            print(f"[CACHE DEBUG] Checking cache for scan: {scan_path_str}, view: {self.current_view}, invert: {self.invert_original}")
            cached_layers = self._get_cached_layers(scan_path_str, self.current_view)
            if cached_layers:
                print(f"[CACHE HIT] Using cached layers for {self.current_view}: {list(cached_layers.keys())}")
                return cached_layers
            else:
                print(f"[CACHE MISS] No cached layers found for {self.current_view}")
        else:
            print(f"[CACHE SKIP] Skipping cache due to adjustments")

        try:
            study_date = extract_study_date_from_dicom(dicom_path)
            patient_id, session_code = self._get_patient_session_from_scan(scan)
            filename_with_date = generate_filename_stem(patient_id, study_date)
            
            # ✅ PERBAIKAN: Dapatkan path yang benar untuk study_date
            if session_code and session_code != "UNKNOWN":
                # ✅ VALIDASI: Jika patient_id adalah study_date, gunakan path dari DICOM
                if len(patient_id) == 8 and patient_id.isdigit():
                    print(f"[DEBUG] Patient ID is study_date, using DICOM path directly")
                    study_date_folder = dicom_path.parent  # langsung gunakan folder dimana DICOM berada
                else:
                    study_date_folder = get_patient_planar_path(session_code, patient_id, study_date)
            else:
                study_date_folder = dicom_path.parent

            # ✅ TAMBAHAN: Validasi path exists
            if not study_date_folder.exists():
                print(f"[WARN] Study date folder does not exist: {study_date_folder}")
                print(f"[DEBUG] Fallback to DICOM parent: {dicom_path.parent}")
                study_date_folder = dicom_path.parent
                        
            # ✅ TAMBAHAN: Debug print
            print(f"[DEBUG] Study date: {study_date}")
            print(f"[DEBUG] Patient ID: {patient_id}")
            print(f"[DEBUG] Session code: {session_code}")
            print(f"[DEBUG] Study date folder: {study_date_folder}")
                
        except Exception as e:
            print(f"[DEBUG] Exception in path extraction: {e}")
            filename_with_date = dicom_path.stem
            study_date_folder = dicom_path.parent
            print(f"[DEBUG] Fallback study_date_folder: {study_date_folder}")

        layers = {}
        view_normalized = self.current_view.lower()
        
        # ✅ GANTI: Gunakan fungsi dari paths.py
        original_image = load_original_image_from_path(dicom_path, self.current_view, frame_map)
        
        if original_image:
            if self.invert_original:
                original_image = simple_invert_pil_image(original_image)
            
            # Determine which brightness/contrast values to use
            if override_b is not None and override_c is not None:
                brightness, contrast = override_b, override_c
            else:
                adjustments = self._adjustments[self.current_view]
                brightness = adjustments["brightness"]
                contrast = adjustments["contrast"]

            # Apply adjustment if needed
            if brightness != 0.0 or contrast != 1.0:
                print(f"[DEBUG] Applying B/C adjustment to {self.current_view} (B={brightness:.2f}, C={contrast:.2f})")
                original_image = apply_brightness_contrast(
                    original_image, brightness, contrast
                )

            layers["Image"] = original_image
        
        # ✅ GUNAKAN study_date_folder yang benar
        self._load_segmentation_layer(layers, dicom_path, filename_with_date, view_normalized, study_date_folder, self.session_code)
        self._load_hotspot_layer(layers, dicom_path, filename_with_date, view_normalized, study_date_folder, self.session_code)  
        self._load_bbox_layer(layers, dicom_path, filename_with_date, view_normalized, study_date_folder, self.session_code)

        # ✅ NEW: Cache loaded layers if not using overrides
        if use_cache and layers:
            print(f"[CACHE STORE] Storing {len(layers)} layers in cache")
            for layer_name, layer_image in layers.items():
                self._cache_layer_image(scan_path_str, self.current_view, layer_name, layer_image)
                print(f"[CACHE STORE] Cached {layer_name} for {self.current_view}")
            print(f"[CACHE STORE] Cache now has {len(self._layer_image_cache)} total entries")
        else:
            print(f"[CACHE STORE] Not caching: use_cache={use_cache}, layers_count={len(layers) if layers else 0}")

        return layers
        
    def _make_layered_card(self, scan: Dict, w: int, idx: int) -> QFrame:
        """✅ FIXED: Create card with proper view-specific layered display"""
        card = QFrame()
        card.setFrameStyle(QFrame.Box | QFrame.Raised)
        card.setLineWidth(1)
        
        # Highlight active scan
        if idx == self.active_scan_index:
            card.setStyleSheet("""
                QFrame {
                    border: 2px solid #4e73ff;
                    border-radius: 6px;
                    background-color: #f0f4ff;
                }
            """)
        else:
            card.setStyleSheet("""
                QFrame {
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    background-color: white;
                }
                QFrame:hover {
                    border: 1px solid #4e73ff;
                }
            """)
        
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addLayout(self._make_header(scan, idx))
        
        lbl = QLabel(alignment=Qt.AlignCenter)
        lbl.setObjectName(f"image_display_{self.current_view}")
        # ✅ FIXED: Better debug messages
        print(f"[DEBUG] Creating CLASSIFICATION card {idx} for view: {self.current_view}")
        print(f"[DEBUG] Active layers selected: {self._active_layers}")
        
        all_layers = self._get_layer_images(scan)
        print(f"[DEBUG] Available CLASSIFICATION layers in files: {list(all_layers.keys())}")
        
        # Apply opacity to individual layers before compositing
        active_layer_images = {}
        for layer_name in self._active_layers:
            # Skip HotspotBBox even if somehow it gets into active_layers
            if layer_name == "HotspotBBox":
                print(f"[DEBUG] 🚫 Skipping HotspotBBox layer (hidden from UI)")
                continue
                
            if layer_name in all_layers:
                layer_image = all_layers[layer_name]
                layer_opacity = self._layer_opacities.get(layer_name, 1.0)
                
                # Apply opacity to the layer
                if layer_opacity < 1.0:
                    layer_image = apply_opacity_to_image(layer_image, layer_opacity)
                
                active_layer_images[layer_name] = layer_image
                print(f"[DEBUG] ✅ Added CLASSIFICATION {layer_name} to card {idx} (opacity: {layer_opacity:.2f})")
            else:
                print(f"[DEBUG] ❌ Layer {layer_name} not found in CLASSIFICATION files for card {idx}")
                
        if not active_layer_images:
            lbl.setText(f"No classification data available\nfor {self.current_view}")
            lbl.setStyleSheet("color:#888; font-size: 12px; padding: 20px;")
        else:
            # Create composite image from active layers
            try:
                # Use opacity 1.0 for all layers since we already applied opacity above
                uniform_opacities = {layer: 1.0 for layer in active_layer_images.keys()}
                
                composite_image = create_composite_image(
                    layers=active_layer_images,
                    layer_order=self._active_layers,
                    layer_opacities=uniform_opacities
                )
                
                # Convert composite to displayable format
                if composite_image.mode == 'RGBA':
                    # Create white background for transparency display
                    background = Image.new('RGB', composite_image.size, (255, 255, 255))
                    display_image = Image.alpha_composite(background.convert('RGBA'), composite_image)
                    display_image = display_image.convert('RGB')
                else:
                    display_image = composite_image
                
                # Create pixmap and cache it
                pixmap = _pil_to_pixmap(display_image, w)
                lbl.setPixmap(pixmap)

                # ✅ NEW: Cache label and original pixmap for smooth zoom
                self._image_labels.append(lbl)
                self._original_pixmaps.append(pixmap)
                
                # Create tooltip with layer info
                tooltip_parts = []
                for layer_name in self._active_layers:
                    if layer_name in active_layer_images:
                        opacity_pct = int(self._layer_opacities.get(layer_name, 1.0) * 100)
                        tooltip_parts.append(f"{layer_name}: {opacity_pct}%")
                
                lbl.setToolTip("Classification layers: " + " | ".join(tooltip_parts))
                print(f"[DEBUG] ✅ CLASSIFICATION card {idx} composite created with layers: {list(active_layer_images.keys())}")
                
            except Exception as e:
                print(f"[ERROR] Failed to create CLASSIFICATION composite image for card {idx}: {e}")
                lbl.setText(f"Error creating classification composite\nfor {self.current_view}")
                lbl.setStyleSheet("color:#dc3545; font-size: 12px; padding: 20px;")
                lbl.setToolTip(str(e))
        
        lay.addWidget(lbl)
        
        # ✅ FIXED: Create status label showing current view and classification status
        status_label = QLabel(f"{self.current_view}")
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #495057;
                padding: 4px;
                background: #e9ecef;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        lay.addWidget(status_label)
        
        return card
    
    # ------------------------------------------------------ backward compatibility
    def set_image_mode(self, mode: str):
        """Backward compatibility method - convert old mode to layer list"""
        print(f"[DEBUG] Legacy set_image_mode called with: {mode}")
        
        if mode == "Original":
            self.set_active_layers(["Image"])
        elif mode == "Segmentation":
            self.set_active_layers(["Image", "Segmentation"])
        elif mode == "Hotspot":
            self.set_active_layers(["Image", "Hotspot"])
        elif mode == "Both":
            self.set_active_layers(["Image", "Segmentation", "Hotspot"])
            
    def cleanup(self):
        """Cleanup resources"""
        print("[DEBUG] Cleaning up ScanTimelineWidget...")
        self._clear()
        self._scans_cache.clear()