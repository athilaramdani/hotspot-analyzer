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
    get_planar_segmentation_files
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
        self.current_view = "Anterior"  # ✅ FIXED: Track current view properly
        self._active_layers = []
        self._scans_cache: List[Dict] = []
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
            "HotspotBBox": 1.0
        }
        
        # Session code for path resolution
        self.session_code = None
        
        # ✅ NEW: BSI integration
        self.bsi_integration = get_bsi_integration()
        
        self._build_ui()
        self._setup_keyboard_shortcuts()

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
        ✅ FIXED: Sets the B/C values for a specific view and rebuilds the timeline.
        """
        if view_name in self._adjustments:
            print(f"[DEBUG] Setting {view_name} contrast: B={brightness:.2f}, C={contrast:.2f}")
            self._adjustments[view_name]["brightness"] = brightness
            self._adjustments[view_name]["contrast"] = contrast
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

    def _load_original_image(self, dicom_path: Path, filename_with_date: str, view_name: str, frame_map: dict) -> Optional[Image.Image]:
        """Load original PNG image for the specified view"""
        try:
            # ✅ NEW: Load from PNG file instead of DICOM frames
            view_normalized = view_name.lower()  # "anterior" atau "posterior"
            
            # Construct PNG filename: patient_studydate_view_original.png
            png_filename = f"{filename_with_date}_{view_normalized}_original.png"
            png_path = dicom_path.parent / png_filename
            
            print(f"[DEBUG] Looking for original PNG: {png_path}")
            
            if png_path.exists():
                # Load PNG directly
                original_image = Image.open(png_path)
                
                # Convert to grayscale if needed
                if original_image.mode != 'L':
                    original_image = original_image.convert('L')
                
                print(f"[DEBUG] Loaded original PNG: {original_image.size}, mode: {original_image.mode}")
                return original_image
            else:
                print(f"[DEBUG] Original PNG not found: {png_path}")
                
                # ✅ FALLBACK: Try to load from DICOM frames if PNG not available
                if view_name in frame_map:
                    frame_data = frame_map[view_name]
                    if isinstance(frame_data, np.ndarray):
                        # Normalize to uint8
                        if frame_data.dtype != np.uint8:
                            frame_norm = (frame_data - frame_data.min()) / max(frame_data.max() - frame_data.min(), 1)
                            frame_uint8 = (frame_norm * 255).astype(np.uint8)
                        else:
                            frame_uint8 = frame_data.copy()
                        
                        # Convert to PIL Image
                        original_image = Image.fromarray(frame_uint8, 'L')
                        print(f"[DEBUG] Fallback: Loaded from DICOM frame: {original_image.size}")
                        return original_image
                
                print(f"[DEBUG] No image source available for {view_name}")
                return None
                
        except Exception as e:
            print(f"[ERROR] Failed to load original image: {e}")
            return None
        
    def _load_segmentation_layer(self, layers: dict, dicom_path: Path, filename_with_date: str, view_normalized: str):
        """✅ CORRECTED: Load segmentation layer if available"""
        try:
            seg_files = get_planar_segmentation_files(dicom_path.parent, filename_with_date, view_normalized)
            
            # ✅ FIX: Prioritize the edited file first, then the original
            if seg_files['png_colored_edited'].exists():
                seg_png = seg_files['png_colored_edited']
                print(f"[DEBUG] Found edited segmentation: {seg_png}")
            else:
                seg_png = seg_files['png_colored']
                print(f"[DEBUG] Looking for original segmentation: {seg_png}")

            if seg_png.exists():
                # Load with transparency (make black pixels transparent)
                seg_image = load_image_with_transparency(seg_png, make_transparent=True)
                if seg_image:
                    layers["Segmentation"] = seg_image
                    print(f"[DEBUG] Loaded segmentation with transparency: {seg_png}")
            else:
                print(f"[WARN] Segmentation file not found: {seg_png}")
                
        except Exception as e:
            print(f"[ERROR] Failed to load segmentation layer: {e}")

    def _load_hotspot_layer(self, layers: dict, dicom_path: Path, filename_with_date: str, view_normalized: str):
        """Load hotspot layer (classification mask) with edited file priority"""
        try:
            # ✅ FIXED: Check edited file first, then fallback to original
            classification_mask_edited = dicom_path.parent / f"{filename_with_date}_{view_normalized}_classification_mask_edited.png"
            classification_mask_original = dicom_path.parent / f"{filename_with_date}_{view_normalized}_classification_mask.png"
            
            # Priority: edited file first
            if classification_mask_edited.exists():
                hotspot_image = load_image_with_transparency(classification_mask_edited)
                if hotspot_image:
                    layers["Hotspot"] = hotspot_image
                    print(f"[DEBUG] Loaded hotspot layer from EDITED: {classification_mask_edited.name}")
                    return
            
            # Fallback: original file
            if classification_mask_original.exists():
                hotspot_image = load_image_with_transparency(classification_mask_original)
                if hotspot_image:
                    layers["Hotspot"] = hotspot_image
                    print(f"[DEBUG] Loaded hotspot layer from ORIGINAL: {classification_mask_original.name}")
                    return
            
            print(f"[DEBUG] No hotspot classification mask found (checked both edited and original)")
                
        except Exception as e:
            print(f"[ERROR] Failed to load hotspot layer: {e}")

    def _load_bbox_layer(self, layers: dict, dicom_path: Path, filename_with_date: str, view_normalized: str):
        """Load bounding box layer (classification XML) with edited file priority"""
        try:
            # ✅ FIXED: Check edited XML first, then fallback to original
            view_short = "ant" if "ant" in view_normalized else "post"
            classification_xml_edited = dicom_path.parent / f"{filename_with_date}_{view_short}_classification_edited.xml"
            classification_xml_original = dicom_path.parent / f"{filename_with_date}_{view_short}_classification.xml"
            
            # Priority: edited file first
            target_xml = classification_xml_edited if classification_xml_edited.exists() else classification_xml_original
            
            if target_xml.exists():
                # ✅ FIX: Use "Image" instead of "Original"
                if "Image" in layers:
                    image_dimensions = layers["Image"].size
                    bbox_image = self._create_bbox_visualization_from_classification(target_xml, image_dimensions)
                    if bbox_image:
                        layers["HotspotBBox"] = bbox_image
                        file_type = "EDITED" if target_xml == classification_xml_edited else "ORIGINAL"
                        print(f"[DEBUG] Loaded bbox layer from {file_type}: {target_xml.name}")
            else:
                print(f"[DEBUG] No classification XML found (checked both edited and original)")
                
        except Exception as e:
            print(f"[ERROR] Failed to load bbox layer: {e}")
    
    def set_invert_original(self, inverted: bool):
        """✅ OPTIMIZED: Set invert status with change detection"""
        print(f"[DEBUG] set_invert_original called: {inverted} (current: {self.invert_original})")
        print(f"[DEBUG] Change detection: old={self.invert_original}, new={inverted}, changed={self.invert_original != inverted}")
        
        # Only rebuild if state actually changed
        if self.invert_original != inverted:
            old_state = self.invert_original
            self.invert_original = inverted
            self._last_invert_state = inverted
            
            print(f"[DEBUG] Invert state changed: {old_state} → {inverted}")
            
            # Clear image cache if it exists (invert affects caching)
            if hasattr(self, '_image_cache'):
                self._image_cache.clear()
                print(f"[DEBUG] Cleared image cache due to invert change")
            
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
        """✅ FIXED: Zoom in with better increment"""
        self._zoom_factor *= 1.15  # Smaller increment for smoother zoom
        print(f"[DEBUG] Timeline zoom in: {self._zoom_factor:.2f}")
        self._rebuild()
        
    def zoom_out(self): 
        """✅ FIXED: Zoom out with better increment"""
        self._zoom_factor *= 0.87  # Smaller decrement for smoother zoom
        print(f"[DEBUG] Timeline zoom out: {self._zoom_factor:.2f}")
        self._rebuild()

    def zoom_reset(self):
        """✅ NEW: Reset zoom to default"""
        self._zoom_factor = 1.0
        print(f"[DEBUG] Timeline zoom reset: {self._zoom_factor:.2f}")
        self._rebuild()

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
        """Set active layers from checkbox mode selector"""
        self._active_layers = layers.copy()
        print(f"[DEBUG] Timeline active layers set to: {self._active_layers}")
        self._rebuild()
      
    
    def set_session_code(self, session_code: str):
        """Set session code for path resolution"""
        self.session_code = session_code
    
    def set_layer_opacity(self, layer: str, opacity: float):
        """Set opacity for a specific layer"""
        self._layer_opacities[layer] = opacity
        print(f"[DEBUG] Set {layer} opacity to {opacity:.2f}")
        # Trigger rebuild to apply new opacity
        self._rebuild()
    
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

    def has_layer_data(self, layer: str) -> bool:
        """Check if layer data is available for current scans"""
        if not self._scans_cache:
            return False
        
        try:
            # Check if any scan has data for this layer
            for scan in self._scans_cache:
                layer_images = self._get_layer_images(scan)
                if layer in layer_images:
                    return True
            return False
        except Exception as e:
            print(f"[WARN] Error checking layer data: {e}")
            return False

    # ------------------------------------------------------ rebuild
    def _clear(self):
        while self.timeline_layout.count():
            w = self.timeline_layout.takeAt(0).widget()
            if w: 
                w.deleteLater()

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

    # ------------------------------------------------------ card builders
    def _make_header(self, scan: Dict, idx: int) -> QHBoxLayout:
        """✅ FIXED: Header with BSI information"""
        meta = scan["meta"]
        date_raw = meta.get("study_date", "")
        try:   
            hdr = datetime.strptime(date_raw, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError: 
            hdr = "Unknown"
        
        # ✅ NEW: Include BSI in header
        bsi_text = ""
        if meta.get("has_bsi", False):
            # ✅ DEBUG: Print what's in meta
            print(f"[BSI HEADER DEBUG] Meta keys: {list(meta.keys())}")
            print(f"[BSI HEADER DEBUG] Current view: {self.current_view}")
            print(f"[BSI HEADER DEBUG] has_bsi: {meta.get('has_bsi', False)}")
            print(f"[BSI HEADER DEBUG] bsi_anterior: {meta.get('bsi_anterior', 'NOT_FOUND')}")
            print(f"[BSI HEADER DEBUG] bsi_posterior: {meta.get('bsi_posterior', 'NOT_FOUND')}")
            
            if self.current_view == "Anterior":
                bsi_score = meta.get("bsi_anterior", 0.0)  # ✅ ANTERIOR BSI
                print(f"[BSI HEADER DEBUG] Using anterior BSI: {bsi_score}")
            else:  # Posterior
                bsi_score = meta.get("bsi_posterior", 0.0)   # ✅ POSTERIOR BSI
                print(f"[BSI HEADER DEBUG] Using posterior BSI: {bsi_score}")
            bsi_text = f"<br><small>BSI: {bsi_score:.1f}</small>"
        else:
            print(f"[BSI HEADER DEBUG] No BSI data found in meta")
        hbox = QHBoxLayout()
        
        # Header info with BSI
        header_label = QLabel(f"<b>{hdr}</b>{bsi_text}")
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
            dicom_path = scan["path"]
            patient_id, session_code = extract_patient_info_from_path(dicom_path)
            
            # Fallback to session from widget if extraction fails
            if session_code == "UNKNOWN" and self.session_code:
                session_code = self.session_code
                
            print(f"[DEBUG] Extracted from {dicom_path}: patient={patient_id}, session={session_code}")
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
        """✅ FIXED: Now accepts optional override values for live previews."""
        frame_map = scan["frames"]
        dicom_path = Path(scan["path"])

        try:
            study_date = extract_study_date_from_dicom(dicom_path)
            patient_id, _ = self._get_patient_session_from_scan(scan)
            filename_with_date = generate_filename_stem(patient_id, study_date)
        except Exception:
            filename_with_date = dicom_path.stem

        layers = {}
        view_normalized = self.current_view.lower()
        
        original_image = self._load_original_image(dicom_path, filename_with_date, self.current_view, frame_map)
        
        if original_image:
            if self.invert_original:
                original_image = simple_invert_pil_image(original_image)
            
            # Determine which brightness/contrast values to use
            if override_b is not None and override_c is not None:
                # Use preview values if they were passed in
                brightness, contrast = override_b, override_c
            else:
                # Otherwise, use the stored values for the current view
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
        
        self._load_segmentation_layer(layers, dicom_path, filename_with_date, view_normalized)
        self._load_hotspot_layer(layers, dicom_path, filename_with_date, view_normalized)
        self._load_bbox_layer(layers, dicom_path, filename_with_date, view_normalized)
        
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
                
                lbl.setPixmap(_pil_to_pixmap(display_image, w))
                
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