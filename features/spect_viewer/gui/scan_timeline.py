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
    get_hotspot_files, 
    get_segmentation_files_with_edited,
    extract_study_date_from_dicom,
    generate_filename_stem
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
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # State variables
        self.current_view = "Anterior"  # ✅ FIXED: Track current view properly
        self._active_layers = []
        self._scans_cache: List[Dict] = []
        self.active_scan_index = 0
        self._zoom_factor = 1.0
        self.card_width = 350
        
        # Layer opacity settings
        self._layer_opacities = {
            "Original": 1.0,
            "Segmentation": 0.7,
            "Hotspot": 0.8,           # ✅ Classification mask only
            "HotspotBBox": 1.0        # ✅ Classification XML only
        }
        
        # Session code for path resolution
        self.session_code = None
        
        # ✅ NEW: BSI integration
        self.bsi_integration = get_bsi_integration()
        
        self._build_ui()
        self._setup_keyboard_shortcuts()

    def _build_ui(self):
        """Build the resizable UI layout with FIXED scrolling"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create main splitter for resizable layout
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # ✅ FIXED: LEFT SIDE - Scrollable timeline area with BOTH axes
        self._setup_timeline_scroll_area()
        
        # RIGHT SIDE: Layer control panel (resizable)
        self.control_panel = self._create_control_panel()
        
        # Add to splitter
        self.main_splitter.addWidget(self.scroll_area)
        self.main_splitter.addWidget(self.control_panel)
        
        # Set initial splitter sizes: Timeline | Controls
        self.main_splitter.setStretchFactor(0, 3)  # Timeline gets 75%
        self.main_splitter.setStretchFactor(1, 1)  # Controls get 25%
        self.main_splitter.setSizes([800, 200])    # Initial pixel sizes
        
        # Enable splitter handle styling
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e9ecef;
                width: 3px;
                margin: 2px;
                border-radius: 1px;
            }
            QSplitter::handle:hover {
                background-color: #4e73ff;
            }
        """)
        
        main_layout.addWidget(self.main_splitter)

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

    def _update_active_layers_display(self):
        """Update the active layers display in control panel"""
        if not self._active_layers:
            self.active_layers_label.setText("Active Layers: <i>None selected</i>")
            self.active_layers_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #dc3545;
                    padding: 8px;
                    background: #f8d7da;
                    border: 1px solid #f5c6cb;
                    border-radius: 4px;
                    margin: 5px 0px;
                }
            """)
        else:
            layers_text = ", ".join(self._active_layers)
            self.active_layers_label.setText(f"Active Layers: <b>{layers_text}</b>")
            self.active_layers_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #155724;
                    padding: 8px;
                    background: #d4edda;
                    border: 1px solid #c3e6cb;
                    border-radius: 4px;
                    margin: 5px 0px;
                }
            """)

    def _update_edit_button_states(self):
        """Update edit button enabled/disabled states and styling"""
        has_segmentation = "Segmentation" in self._active_layers
        has_hotspot = "Hotspot" in self._active_layers
        has_scan = bool(self._scans_cache)
        
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
        
        # ✅ UPDATED: Classification edit button
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

    def _update_scan_info_display(self):
        """✅ FIXED: Update scan information with BSI data"""
        if not self._scans_cache or self.active_scan_index < 0:
            self.scan_info_label.setText("No scan selected")
            return
            
        if self.active_scan_index < len(self._scans_cache):
            scan = self._scans_cache[self.active_scan_index]
            meta = scan["meta"]
            
            # Format scan info
            scan_num = self.active_scan_index + 1
            total_scans = len(self._scans_cache)
            date = meta.get("study_date", "Unknown")
            
            try:
                formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%b %d, %Y")
            except ValueError:
                formatted_date = date
            
            # ✅ NEW: Get BSI information
            bsi_info = ""
            if meta.get("has_bsi", False):
                bsi_score = meta.get("bsi_score", 0.0)
                bsi_info = f"<br>BSI: {bsi_score:.1f}%"
            
            info_text = f"""
            <b>Scan {scan_num}/{total_scans}</b><br>
            Date: {formatted_date}<br>
            View: {self.current_view}{bsi_info}
            """
            
            self.scan_info_label.setText(info_text)

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
        """✅ FIXED: Display timeline with BSI integration"""
        print(f"[DEBUG] display_timeline called with {len(scans)} scan(s), active_index = {active_index}")
        
        # ✅ NEW: Update scans with BSI information
        updated_scans = []
        for scan in scans:
            updated_scan = self.bsi_integration.update_scan_meta_with_bsi(scan, self.session_code)
            updated_scans.append(updated_scan)
        
        self._scans_cache = updated_scans
        self.active_scan_index = active_index
        self._zoom_factor = 1.0
        self._rebuild()
        self._update_scan_info_display()
        self._update_edit_button_states()

    def set_active_view(self, v: str): 
        """✅ FIXED: Properly set view and force rebuild"""
        old_view = self.current_view
        self.current_view = v
        print(f"[DEBUG] Setting view to: {self.current_view} (was: {old_view})")
        
        # ✅ CRITICAL: Force rebuild to show different view
        if old_view != self.current_view:
            print(f"[DEBUG] View changed from {old_view} to {self.current_view}, forcing rebuild...")
            self._rebuild()
            self._update_scan_info_display()
        
    def set_active_layers(self, layers: list): 
        """Set active layers from checkbox mode selector"""
        self._active_layers = layers.copy()
        print(f"[DEBUG] Timeline active layers set to: {self._active_layers}")
        self._rebuild()
        self._update_active_layers_display()
        self._update_edit_button_states()
    
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
        """✅ FIXED: Rebuild with proper view handling"""
        print(f"[DEBUG] Rebuilding timeline for view: {self.current_view}")
        self._clear()
        
        if not self._scans_cache:
            placeholder = QLabel("No scans available")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("""
                QLabel {
                    color: #6c757d;
                    font-size: 14px;
                    padding: 40px;
                    background: #f8f9fa;
                    border: 2px dashed #dee2e6;
                    border-radius: 8px;
                }
            """)
            self.timeline_layout.addWidget(placeholder)
            return

        w = int(self.card_width * self._zoom_factor)
        
        # Show cards based on active layers
        if not self._active_layers:
            # No layers selected - show placeholder
            placeholder = QLabel("No layers selected\nPlease select layers to display")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("""
                QLabel {
                    color: #6c757d;
                    font-size: 14px;
                    padding: 40px;
                    background: #f8f9fa;
                    border: 2px dashed #dee2e6;
                    border-radius: 8px;
                }
            """)
            self.timeline_layout.addWidget(placeholder)
        else:
            # Show scans with active layers
            for i, scan in enumerate(self._scans_cache):
                card = self._make_layered_card(scan, w, i)
                self.timeline_layout.addWidget(card)
                print(f"[DEBUG] Created card {i} for view {self.current_view}")

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
            bsi_score = meta.get("bsi_score", 0.0)
            bsi_text = f"<br><small>BSI: {bsi_score:.1f}%</small>"

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
        self._update_scan_info_display()
        self._update_edit_button_states()
        
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
    
    def _create_bbox_visualization_from_classification(self, xml_path: Path, original_frame: np.ndarray) -> Optional[Image.Image]:
        """✅ FIXED: Create bounding box visualization from CLASSIFICATION XML only"""
        try:
            import xml.etree.ElementTree as ET
            from PIL import ImageDraw, ImageFont
            
            print(f"[DEBUG] Loading CLASSIFICATION XML for bbox: {xml_path}")
            
            # Parse XML file
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Get image dimensions
            height, width = original_frame.shape[:2]
            
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
    
    def _get_layer_images(self, scan: Dict) -> Dict[str, Image.Image]:
        """✅ FIXED: Get layer images - CLASSIFICATION ONLY"""
        frame_map = scan["frames"]
        dicom_path = Path(scan["path"])
        filename = dicom_path.stem
        
        layers = {}
        
        # ✅ Layer 1: Original (base) - convert to RGBA for opacity support
        if self.current_view in frame_map:
            original_arr = frame_map[self.current_view]
            # Convert to PIL Image with RGBA mode for opacity support
            original_normalized = ((original_arr - original_arr.min()) / max(1, np.ptp(original_arr)) * 255).astype(np.uint8)
            original_image = Image.fromarray(original_normalized).convert("RGBA")
            layers["Original"] = original_image
            print(f"[DEBUG] Loaded Original layer for {self.current_view}")
        
        # Layer 2: Segmentation - with transparency processing
        try:
            study_date = extract_study_date_from_dicom(dicom_path)
            patient_id, session_code = self._get_patient_session_from_scan(scan)
            filename_with_date = generate_filename_stem(patient_id, study_date)
            print(f"[DEBUG] Using filename stem with study date: {filename_with_date}")
        except Exception as e:
            print(f"[WARN] Could not extract study date, using original filename: {e}")
            study_date = None
            filename_with_date = filename
        
        seg_files = get_segmentation_files_with_edited(dicom_path.parent, filename_with_date, self.current_view)
        
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
                layers["Segmentation"] = seg_image
                print(f"[DEBUG] Loaded segmentation with transparency: {seg_png}")
            except Exception as e:
                print(f"[WARN] Failed to load segmentation image: {e}")
        else:
            print(f"[WARN] Segmentation file not found: {seg_png}")
        
        # ✅ Layer 3: Hotspot - CLASSIFICATION MASKS ONLY
        view_normalized = self.current_view.lower()
        classification_mask_path = dicom_path.parent / f"{filename_with_date}_{view_normalized}_classification_mask.png"
        
        print(f"[DEBUG] Looking for CLASSIFICATION mask ONLY: {classification_mask_path}")
        
        if classification_mask_path.exists():
            try:
                # Load classification mask with transparency
                classification_image = load_image_with_transparency(classification_mask_path, make_transparent=True)
                layers["Hotspot"] = classification_image
                print(f"[DEBUG] ✅ Loaded CLASSIFICATION MASK as Hotspot layer: {classification_mask_path}")
            except Exception as e:
                print(f"[WARN] Failed to load classification mask: {e}")
        else:
            print(f"[DEBUG] ❌ CLASSIFICATION mask not found: {classification_mask_path}")
            print(f"[DEBUG] ❌ NO FALLBACK - Classification results only!")
        
        # ✅ Layer 4: HotspotBBox - CLASSIFICATION XML ONLY
        try:
            # Determine view for XML files (use short names: ant/post)
            view_short = "ant" if "ant" in self.current_view.lower() else "post"
            classification_xml_path = dicom_path.parent / f"{filename_with_date}_{view_short}_classification.xml"
            
            print(f"[DEBUG] Looking for CLASSIFICATION XML ONLY: {classification_xml_path}")
            
            if classification_xml_path.exists():
                # Create bounding box visualization from CLASSIFICATION XML
                bbox_image = self._create_bbox_visualization_from_classification(classification_xml_path, original_arr)
                if bbox_image:
                    layers["HotspotBBox"] = bbox_image
                    print(f"[DEBUG] ✅ Created HotspotBBox from CLASSIFICATION XML: {classification_xml_path}")
                else:
                    print(f"[DEBUG] ❌ Failed to create bbox visualization from CLASSIFICATION XML: {classification_xml_path}")
            else:
                print(f"[DEBUG] ❌ CLASSIFICATION XML not found: {classification_xml_path}")
                print(f"[DEBUG] ❌ NO FALLBACK - Classification results only!")
        except Exception as e:
            print(f"[WARN] Error loading CLASSIFICATION HotspotBBox: {e}")
        
        print(f"[DEBUG] Total CLASSIFICATION layers loaded for {self.current_view}: {list(layers.keys())}")
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
        status_label = QLabel(f"{self.current_view} (Classification)")
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
    
    # ------------------------------------------------------ editor dialogs
    def _open_segmentation_editor(self):
        """Open segmentation editor for current scan"""
        if not self._scans_cache or self.active_scan_index < 0 or self.active_scan_index >= len(self._scans_cache):
            print("[DEBUG] No valid scan selected for segmentation editing")
            return
            
        scan = self._scans_cache[self.active_scan_index]
        print(f"[DEBUG] Opening segmentation editor for scan {self.active_scan_index + 1}")
        
        dlg = SegmentationEditorDialog(scan, self.current_view, parent=self)
        if dlg.exec():
            print("[DEBUG] Segmentation editor completed, refreshing timeline")
            self._rebuild()

    def _open_hotspot_editor(self):
        """✅ UPDATED: Open hotspot editor for current scan - CLASSIFICATION FILES ONLY"""
        if not self._scans_cache or self.active_scan_index < 0 or self.active_scan_index >= len(self._scans_cache):
            print("[DEBUG] No valid scan selected for classification editing")
            return
            
        scan = self._scans_cache[self.active_scan_index]
        print(f"[DEBUG] Opening CLASSIFICATION editor for scan {self.active_scan_index + 1}")
        
        # ✅ PREPARE CLASSIFICATION-SPECIFIC DATA FOR EDITOR
        try:
            dicom_path = Path(scan["path"])
            study_date = extract_study_date_from_dicom(dicom_path)
            patient_id, session_code = self._get_patient_session_from_scan(scan)
            filename_with_date = generate_filename_stem(patient_id, study_date)
            
            # Get classification files
            view_normalized = self.current_view.lower()
            view_short = "ant" if "ant" in self.current_view.lower() else "post"
            
            classification_files = {
                'mask_path': dicom_path.parent / f"{filename_with_date}_{view_normalized}_classification_mask.png",
                'xml_path': dicom_path.parent / f"{filename_with_date}_{view_short}_classification.xml",
                'json_path': dicom_path.parent / f"{filename_with_date}_{view_normalized}_classification.json"
            }
            
            print(f"[DEBUG] CLASSIFICATION files for editor:")
            for key, path in classification_files.items():
                exists = "✅" if path.exists() else "❌"
                print(f"[DEBUG]   {key}: {exists} {path}")
            
            # Check if classification files exist
            if not classification_files['mask_path'].exists():
                print(f"[ERROR] No classification mask found: {classification_files['mask_path']}")
                return
            
            # Create enhanced scan data with classification paths
            enhanced_scan = scan.copy()
            enhanced_scan['classification_files'] = classification_files
            enhanced_scan['is_classification_mode'] = True  # Flag for editor
            
            # Open hotspot editor with classification data
            dlg = HotspotEditorDialog(enhanced_scan, self.current_view, parent=self)
            if dlg.exec():
                print("[DEBUG] CLASSIFICATION editor completed, refreshing timeline")
                self._rebuild()
                
        except Exception as e:
            print(f"[ERROR] Failed to prepare classification data for editor: {e}")
    
    # ------------------------------------------------------ backward compatibility
    def set_image_mode(self, mode: str):
        """Backward compatibility method - convert old mode to layer list"""
        print(f"[DEBUG] Legacy set_image_mode called with: {mode}")
        
        if mode == "Original":
            self.set_active_layers(["Original"])
        elif mode == "Segmentation":
            self.set_active_layers(["Original", "Segmentation"])
        elif mode == "Hotspot":
            self.set_active_layers(["Original", "Hotspot"])  # ✅ Classification mask only
        elif mode == "Both":
            self.set_active_layers(["Original", "Segmentation", "Hotspot"])  # ✅ Classification mask only
        else:
            self.set_active_layers([])
            
    def cleanup(self):
        """Cleanup resources"""
        print("[DEBUG] Cleaning up ScanTimelineWidget...")
        self._clear()
        self._scans_cache.clear()