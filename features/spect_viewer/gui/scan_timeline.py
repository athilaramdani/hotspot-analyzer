# features/spect_viewer/gui/scan_timeline.py – v8 (Fixed Opacity + Select Button + Missing Methods)
# ---------------------------------------------------------------------
from __future__ import annotations
from pathlib import Path
from typing import List, Dict
from datetime import datetime

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton, QSplitter
)

# Import NEW config paths for edited files support
from core.config.paths import (
    get_hotspot_files, 
    get_segmentation_files_with_edited,
    extract_study_date_from_dicom,     # ← BARU
    generate_filename_stem             # ← BARU
)

# Import NEW transparency utilities
from core.utils.image_converter import (
    make_black_transparent,
    load_image_with_transparency,
    create_composite_image,
    get_layer_preview,
    apply_opacity_to_image  # NEW: Import this function
)

# Import for patient/session extraction from path
from features.dicom_import.logic.dicom_loader import extract_patient_info_from_path

from .segmentation_editor_dialog import SegmentationEditorDialog
from .hotspot_editor_dialog import HotspotEditorDialog
from pydicom import dcmread

# Import UI constants for edit buttons
from core.gui.ui_constants import (
    SUCCESS_BUTTON_STYLE,  # Green for segmentation edit
    ZOOM_BUTTON_STYLE,     # Orange for hotspot edit  
    GRAY_BUTTON_STYLE      # Gray for disabled
)


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
    Enhanced timeline widget with resizable layout and improved edit buttons:
    - Resizable splitter between timeline and layer controls
    - Separate edit buttons for Segmentation and Hotspot
    - Better visual separation and user control
    """
    # NEW: Add signal for scan selection
    scan_selected = Signal(int)  # Emit scan index when selected
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # State variables
        self.current_view = "Anterior"
        self._active_layers = []
        self._scans_cache: List[Dict] = []
        self.active_scan_index = 0
        self._zoom_factor = 1.0
        self.card_width = 350
        
        # Layer opacity settings
        self._layer_opacities = {
            "Original": 1.0,
            "Segmentation": 0.7,
            "Hotspot": 0.8
        }
        
        # Session code for path resolution
        self.session_code = None
        
        self._build_ui()

    def _build_ui(self):
        """Build the resizable UI layout"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create main splitter for resizable layout
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # LEFT SIDE: Scrollable timeline area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.container = QWidget()
        self.timeline_layout = QHBoxLayout(self.container)
        self.timeline_layout.setAlignment(Qt.AlignLeft)
        self.scroll_area.setWidget(self.container)
        
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
        
        # Hotspot edit button  
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
        
        # Hotspot edit button
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
        """Update scan information in control panel"""
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
            bsi = meta.get("bsi_value", "N/A")
            
            try:
                formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%b %d, %Y")
            except ValueError:
                formatted_date = date
            
            info_text = f"""
            <b>Scan {scan_num}/{total_scans}</b><br>
            Date: {formatted_date}<br>
            BSI: {bsi}<br>
            View: {self.current_view}
            """
            
            self.scan_info_label.setText(info_text)

    # ------------------------------------------------------ zoom
    def zoom_in(self):  
        self._zoom_factor *= 1.2
        self._rebuild()
        
    def zoom_out(self): 
        self._zoom_factor *= 0.8
        self._rebuild()

    # ------------------------------------------------------ public API
    def display_timeline(self, scans: List[Dict], active_index: int = -1):
        print(f"[DEBUG] display_timeline called with {len(scans)} scan(s), active_index = {active_index}")
        self._scans_cache = scans
        self.active_scan_index = active_index
        self._zoom_factor = 1.0
        self._rebuild()
        self._update_scan_info_display()
        self._update_edit_button_states()

    def set_active_view(self, v: str): 
        self.current_view = v
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

    # ===== NEW METHODS TO FIX THE ERROR =====
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
    # ========================================

    # ------------------------------------------------------ rebuild
    def _clear(self):
        while self.timeline_layout.count():
            w = self.timeline_layout.takeAt(0).widget()
            if w: 
                w.deleteLater()

    def _rebuild(self):
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
                self.timeline_layout.addWidget(self._make_layered_card(scan, w, i))

        self.timeline_layout.addStretch()

    # ------------------------------------------------------ card builders
    def _make_header(self, scan: Dict, idx: int) -> QHBoxLayout:
        meta = scan["meta"]
        date_raw = meta.get("study_date", "")
        try:   
            hdr = datetime.strptime(date_raw, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError: 
            hdr = "Unknown"
        bsi = meta.get("bsi_value", "N/A")

        hbox = QHBoxLayout()
        
        # Header info
        header_label = QLabel(f"<b>{hdr}</b><br>BSI: {bsi}")
        header_label.setStyleSheet("font-size: 11px;")
        hbox.addWidget(header_label)
        hbox.addStretch()
        
        # FIXED: Select button now emits signal properly
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
        # FIXED: Connect to new method that emits signal
        select_btn.clicked.connect(lambda *_: self._on_scan_selected(idx))
        hbox.addWidget(select_btn)
        
        return hbox
    
    def _on_scan_selected(self, idx: int):
        """FIXED: Handle scan selection and emit signal to parent"""
        print(f"[DEBUG] Timeline scan selected: {idx}")
        self.active_scan_index = idx
        self._update_scan_info_display()
        self._update_edit_button_states()
        
        # Emit signal to parent (MainWindow) to sync with scan buttons
        self.scan_selected.emit(idx)
        
        # Rebuild to update visual selection
        self._rebuild()
    
    def _select_scan(self, idx: int):
        """DEPRECATED: Use _on_scan_selected instead"""
        self._on_scan_selected(idx)
    
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
    
    # UPDATE _get_layer_images method in scan_timeline.py

    def _get_layer_images(self, scan: Dict) -> Dict[str, Image.Image]:
        """Get all layer images for a scan with transparency processing - UPDATED to use PURE hotspot"""
        frame_map = scan["frames"]
        dicom_path = scan["path"]
        filename = dicom_path.stem
        
        layers = {}
        
        # FIXED: Layer 1: Original (base) - convert to RGBA for opacity support
        if self.current_view in frame_map:
            original_arr = frame_map[self.current_view]
            # Convert to PIL Image with RGBA mode for opacity support
            original_normalized = ((original_arr - original_arr.min()) / max(1, np.ptp(original_arr)) * 255).astype(np.uint8)
            original_image = Image.fromarray(original_normalized).convert("RGBA")
            layers["Original"] = original_image
        
        # Layer 2: Segmentation - with transparency processing
        # FIXED: Extract patient info properly
        try:
            study_date = extract_study_date_from_dicom(dicom_path)
            
            # FIXED: Get clean patient_id from path, not from metadata
            patient_id, session_code = self._get_patient_session_from_scan(scan)
            
            filename_with_date = generate_filename_stem(patient_id, study_date)
            print(f"[DEBUG] Using filename stem with study date: {filename_with_date}")
            print(f"[DEBUG] Patient ID: {patient_id}, Study Date: {study_date}")
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
        
        # ✅ Layer 3: Hotspot - UPDATED to use PURE version with transparency processing  
        # FIXED: Include study_date parameter
        if study_date:
            hotspot_files = get_hotspot_files(patient_id, session_code, self.current_view, study_date)
        else:
            # Fallback: try to get study date from meta or use current date
            fallback_date = scan["meta"].get("study_date")
            if not fallback_date:
                from datetime import datetime
                fallback_date = datetime.now().strftime("%Y%m%d")
            hotspot_files = get_hotspot_files(patient_id, session_code, self.current_view, fallback_date)
        
        # ✅ PRIORITIZE PURE VERSION (edited first, then original)
        hotspot_png = None
        if hotspot_files['pure_colored_png_edited'].exists():
            hotspot_png = hotspot_files['pure_colored_png_edited']
            print(f"[DEBUG] Found edited PURE hotspot: {hotspot_png}")
        elif hotspot_files['pure_colored_png'].exists():
            hotspot_png = hotspot_files['pure_colored_png']
            print(f"[DEBUG] Found original PURE hotspot: {hotspot_png}")
        # ✅ FALLBACK to blended version if pure not available
        elif hotspot_files['colored_png_edited'].exists():
            hotspot_png = hotspot_files['colored_png_edited']
            print(f"[DEBUG] Fallback to edited BLENDED hotspot: {hotspot_png}")
        elif hotspot_files['colored_png'].exists():
            hotspot_png = hotspot_files['colored_png']
            print(f"[DEBUG] Fallback to original BLENDED hotspot: {hotspot_png}")
        
        if hotspot_png and hotspot_png.exists():
            try:
                # Load with transparency (make black pixels transparent)
                hotspot_image = load_image_with_transparency(hotspot_png, make_transparent=True)
                layers["Hotspot"] = hotspot_image
                print(f"[DEBUG] Loaded hotspot with transparency: {hotspot_png}")
            except Exception as e:
                print(f"[WARN] Failed to load hotspot image: {e}")
        else:
            print(f"[WARN] No hotspot files found for {filename_with_date}")
        
        return layers
    
    def _make_layered_card(self, scan: Dict, w: int, idx: int) -> QFrame:
        """Create card with layered display based on active layers"""
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
        
        # Get all available layer images
        all_layers = self._get_layer_images(scan)
        
        # FIXED: Apply opacity to individual layers before compositing
        active_layer_images = {}
        for layer_name in self._active_layers:
            if layer_name in all_layers:
                layer_image = all_layers[layer_name]
                layer_opacity = self._layer_opacities.get(layer_name, 1.0)
                
                # Apply opacity to the layer
                if layer_opacity < 1.0:
                    layer_image = apply_opacity_to_image(layer_image, layer_opacity)
                
                active_layer_images[layer_name] = layer_image
        
        if not active_layer_images:
            lbl.setText("No layer data available")
            lbl.setStyleSheet("color:#888; font-size: 12px; padding: 20px;")
        else:
            # Create composite image from active layers (don't apply opacity again)
            try:
                # Use opacity 1.0 for all layers since we already applied opacity above
                uniform_opacities = {layer: 1.0 for layer in active_layer_images.keys()}
                
                composite_image = create_composite_image(
                    layers=active_layer_images,
                    layer_order=self._active_layers,
                    layer_opacities=uniform_opacities  # Don't double-apply opacity
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
                
                lbl.setToolTip("Active layers: " + " | ".join(tooltip_parts))
                
            except Exception as e:
                print(f"[ERROR] Failed to create composite image: {e}")
                lbl.setText("Error creating composite")
                lbl.setStyleSheet("color:#dc3545; font-size: 12px; padding: 20px;")
                lbl.setToolTip(str(e))
        
        lay.addWidget(lbl)
        
        # Create status label showing active layers
        layer_status = ", ".join(self._active_layers) if self._active_layers else "None"
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
        """Open hotspot editor for current scan"""
        if not self._scans_cache or self.active_scan_index < 0 or self.active_scan_index >= len(self._scans_cache):
            print("[DEBUG] No valid scan selected for hotspot editing")
            return
            
        scan = self._scans_cache[self.active_scan_index]
        print(f"[DEBUG] Opening hotspot editor for scan {self.active_scan_index + 1}")
        
        dlg = HotspotEditorDialog(scan, self.current_view, parent=self)
        if dlg.exec():
            print("[DEBUG] Hotspot editor completed, refreshing timeline")
            self._rebuild()
    
    # ------------------------------------------------------ backward compatibility
    def set_image_mode(self, mode: str):
        """Backward compatibility method - convert old mode to layer list"""
        print(f"[DEBUG] Legacy set_image_mode called with: {mode}")
        
        if mode == "Original":
            self.set_active_layers(["Original"])
        elif mode == "Segmentation":
            self.set_active_layers(["Original", "Segmentation"])
        elif mode == "Hotspot":
            self.set_active_layers(["Original", "Hotspot"])
        elif mode == "Both":
            self.set_active_layers(["Original", "Segmentation", "Hotspot"])
        else:
            self.set_active_layers([])
            
    def cleanup(self):
        """Cleanup resources"""
        print("[DEBUG] Cleaning up ScanTimelineWidget...")
        self._clear()
        self._scans_cache.clear()