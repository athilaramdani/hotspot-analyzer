# features/spect_viewer/gui/hotspot_editor_dialog.py - Fixed version
"""
Hotspot editor dialog using modular components.
Significantly reduced code through inheritance and composition.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict
import numpy as np
import json
from PIL import Image
import logging
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QSlider, QWidget, QGraphicsView, QScrollArea 
)
from PySide6.QtGui import QGuiApplication
from core.gui.ui_constants import OPACITY_SLIDER_STYLE, OPACITY_VALUE_LABEL_STYLE
from core.config.paths import (
    extract_study_date_from_dicom,
    generate_filename_stem,
)

# Import modular components
from .editor_components import (
    BaseEditorDialog,
    HotspotCanvas,
    HotspotOpacityPanel,
    HotspotPalette,
    HotspotSaveThread,
    BaseOpacitySlider
)
from .editor_components.base_components import BaseBrushSizeControl
from datetime import datetime
import time
import csv
from core.config.paths import PLANAR_DATA_PATH, generate_edit_date, generate_edit_timestamp
from core.config.paths import generate_edit_date, generate_edit_timestamp

from features.spect_viewer.logic.hotspot_processor import parse_xml_annotations, create_hotspot_mask

from core.gui.loading_dialog import LoadingDialog, show_loading_dialog


class HotspotEditorDialog(BaseEditorDialog):
    """Hotspot editor dialog using modular components."""
    
    editor_completed = Signal()

    def __init__(self, scan: Dict, view: str, parent=None):
        # 1. STORE INITIAL DATA
        self.scan = scan
        self.view = view
        view_key = view.lower()
        vtag = "ant" if "ant" in view_key else "post"

        # 2. ASSIGN DICOM PATH FIRST (before using it)
        self.dicom_path = Path(scan["path"])

        # 3. Extract patient info needed for getting newest paths
        patient_folder = self.dicom_path.parent
        self.patient_id = patient_folder.parent.name
        self.session_code = patient_folder.parent.parent.name
        self.study_date = extract_study_date_from_dicom(self.dicom_path)
        self.filename_stem = generate_filename_stem(self.patient_id, self.study_date)
        self.view_short = vtag

        # 4. GET NEWEST PATHS USING YOUR NEW METHODS (instead of workflow_files)
        from core.config.paths import get_newest_hotspot_classification_path, get_newest_segmentation_path
        
        # Use the newest hotspot classification file
        self.classification_mask_original = get_newest_hotspot_classification_path(patient_folder, view)
        
        # For XML, get the corresponding XML file (same directory as PNG)
        if self.classification_mask_original:
            xml_name = f"{vtag}_hotspot_classification.xml"
            # If PNG is timestamped, find corresponding timestamped XML
            if "_" in self.classification_mask_original.stem and self.classification_mask_original.stem.endswith("_" + self.classification_mask_original.stem.split("_")[-1]):
                # Extract timestamp from PNG filename
                png_parts = self.classification_mask_original.stem.split("_")
                if len(png_parts) >= 4 and len(png_parts[-1]) == 6 and png_parts[-1].isdigit():
                    timestamp = png_parts[-1]
                    xml_timestamped_name = f"{vtag}_hotspot_classification_{timestamp}.xml"
                    self.xml_original = self.classification_mask_original.parent / xml_timestamped_name
                else:
                    self.xml_original = self.classification_mask_original.parent / xml_name
            else:
                self.xml_original = self.classification_mask_original.parent / xml_name
        else:
            # Fallback to base XML path
            self.xml_original = patient_folder / f"{vtag}_hotspot_classification.xml"
        
        # Use the newest segmentation file
        self.segmentation_path = get_newest_segmentation_path(patient_folder, view)

        # 5. LOAD IMAGES AND MASKS (using the correct newest paths)
        # Get original image path from workflow_files (this should be correct)
        workflow_files = self.scan.get('workflow_files', {})
        original_png_path = workflow_files.get('original', {}).get(vtag)
        
        if original_png_path and original_png_path.exists():
            self.original_image_data = np.array(Image.open(original_png_path).convert('L'))
            self.has_orig_png = True
        else:
            # Fallback to raw DICOM frame if original PNG is missing
            self.original_image_data = scan["frames"][view_key]
            self.has_orig_png = False

        from features.spect_viewer.logic.image_inverter import simple_invert_image
        self.processed_image_data = simple_invert_image(self.original_image_data.copy())
        
        # Load mask using the newest paths
        self.mask_arr = self._load_existing_mask()
        self.xml_loaded_from_edited = self.xml_original and self.xml_original.name != f"{vtag}_hotspot_classification.xml"

        # 6. INITIALIZE THE BASE DIALOG UI
        super().__init__(f"Hotspot Editor – {view}", parent)
        
        # 7. SETUP ZOOM SYNC
        self._sync_zoom_in_progress = False
        self._setup_zoom_sync()

        # 8. INITIALIZE TIMER
        self._setup_editing_timer()
        # 9. INITIALIZE EDITOR SESSION
        self.editor_session = None

    def _load_existing_mask(self) -> np.ndarray:
        """Load existing mask with proper priority using NEWEST paths."""
        
        # Debug output to show which files we're using
        logging.info(f"  [HOTSPOT LOAD] Loading mask for {self.view_short}")
        logging.info(f"  [HOTSPOT LOAD] Classification PNG: {self.classification_mask_original}")
        logging.info(f"  [HOTSPOT LOAD] XML file: {self.xml_original}")
        logging.info(f"  [HOTSPOT LOAD] PNG exists: {self.classification_mask_original.exists() if self.classification_mask_original else False}")
        logging.info(f"  [HOTSPOT LOAD] XML exists: {self.xml_original.exists() if self.xml_original else False}")
        
        # The path self.classification_mask_original now points to the NEWEST file
        if self.classification_mask_original and self.classification_mask_original.exists():
            logging.info(f"✓ Loading NEWEST classification mask from: {self.classification_mask_original.name}")
            return self._load_mask_from_classification_png(self.classification_mask_original)
        
        # The path self.xml_original now points to the NEWEST XML file
        elif self.xml_original and self.xml_original.exists():
            logging.info(f"✓ Found NEWEST XML annotations: {self.xml_original.name}")
            return self._load_from_xml(self.xml_original)
        
        else:
            logging.info(f"✗ No classification data found. Creating empty mask.")
            return np.zeros_like(self.original_image_data, np.uint8)

    def _load_mask_from_classification_png(self, classification_path: Path) -> np.ndarray:
        """Load mask from classification PNG file."""
        try:
            rgb = np.array(Image.open(classification_path).convert("RGB"))
            mask = np.zeros(rgb.shape[:2], np.uint8)
            
            # Convert classification colors to hotspot labels
            red_mask = np.all(rgb == [255, 0, 0], axis=-1)  # Abnormal
            mask[red_mask] = 1
            
            cream_mask = np.all(rgb == [255, 241, 188], axis=-1)  # Normal
            mask[cream_mask] = 2
            
            logging.info(f"✓ Loaded classification mask from: {classification_path}")
            return mask
        except Exception as e:
            logging.info(f"✗ Failed to load classification mask: {e}")
            #   FIX: Use self.original_image_data
            return np.zeros_like(self.original_image_data, np.uint8)

    def _load_from_xml(self, xml_path: Path) -> np.ndarray:
        """Load mask from XML file."""
        try:
            # Use original PNG if available, otherwise save DICOM frame
            if self.has_orig_png:
                orig_png_path = self.dicom_path.parent / f"{self.dicom_path.stem}_{self.view_short}.png"
                input_image_path = str(orig_png_path)
            else:
                temp_png_path = self.dicom_path.parent / f"{self.filename_stem}_temp.png"
                Image.fromarray(self.original_image_data).save(temp_png_path)  # Fixed: use original_image_data
                input_image_path = str(temp_png_path)

            # Parse and process XML
            boxes = parse_xml_annotations(str(xml_path))
            if boxes:
                mask_arr, _, _ = create_hotspot_mask(
                    input_image_path, boxes, self.patient_id, 
                    self.view_short, str(self.dicom_path.parent)
                )
                # Convert to label format
                recolor = np.zeros_like(mask_arr, dtype=np.uint8)
                recolor[mask_arr > 200] = 1      # Abnormal
                recolor[(mask_arr > 50) & (mask_arr <= 200)] = 2  # Normal
                return recolor
            else:
                return np.zeros_like(self.original_image_data, np.uint8)
        except Exception as e:
            logging.info(f"✗ Error processing XML {xml_path}: {e}")
            return np.zeros_like(self.original_image_data, np.uint8)

    # Replace the opacity panel creation section in _create_toolbar() method

    def _create_toolbar(self):
        """Create hotspot-specific toolbar."""
        super()._create_toolbar()
        
        # Palette
        self.palette = HotspotPalette()
        self.toolbar_layout.addWidget(self.palette)
        
        # Tool buttons
        tool_row = QHBoxLayout()
        self.btn_brush = QPushButton("Brush")
        self.btn_brush.setCheckable(True)
        self.btn_brush.setChecked(True)
        
        self.btn_eraser = QPushButton("Eraser")
        self.btn_eraser.setCheckable(True)
        
        self.btn_showall = QPushButton("Show All")
        self.btn_showall.setCheckable(True)
        
        tool_row.addWidget(self.btn_brush)
        tool_row.addWidget(self.btn_eraser)
        tool_row.addWidget(self.btn_showall)
        self.toolbar_layout.addLayout(tool_row)
        
        # Undo/Redo buttons
        undo_row = QHBoxLayout()
        self.btn_undo = QPushButton("Undo")
        self.btn_redo = QPushButton("Redo")
        undo_row.addWidget(self.btn_undo)
        undo_row.addWidget(self.btn_redo)
        self.toolbar_layout.addLayout(undo_row)
        
        # Brush Size - Using base component
        from .editor_components.base_components import BaseBrushSizeControl
        self.brush_size_control = BaseBrushSizeControl("Brush Size", initial_radius=1, min_radius=1, max_radius=15)
        self.toolbar_layout.addWidget(self.brush_size_control)
        
        # Zoom controls - Using base component  
        self.zoom_slider = BaseOpacitySlider("Zoom", 10)
        self.zoom_slider.slider.setRange(1, 1000)
        self.zoom_slider.setValue(10)
        self.zoom_slider.lbl_value.setText("1.0x")
        self.toolbar_layout.addWidget(self.zoom_slider)
        
        #   SIMPLIFIED: Hotspot Layer Opacity - Using same base component
        # Use the same opacity panel as segmentation editor
        self.opacity_panel = HotspotOpacityPanel()
        self.toolbar_layout.addWidget(self.opacity_panel)
        
        # Contrast button
        btn_contrast = QPushButton("Contrast…")
        self.toolbar_layout.addWidget(btn_contrast)
        
        # Invert checkbox
        self.invert_checkbox = QCheckBox("Invert Image Colors")
        self.invert_checkbox.setChecked(True)
        self.invert_checkbox.setStyleSheet("margin-top: 8px; font-weight: bold;")
        self.toolbar_layout.addWidget(self.invert_checkbox)
        
        # Instructions
        instructions = self._create_instructions_label()
        self.toolbar_layout.addWidget(instructions)
        
        # Timer display
        self.timer_widget = self._create_timer_widget()
        self.toolbar_layout.addWidget(self.timer_widget)
        # Save/Cancel buttons
        btn_save = QPushButton("Save")
        btn_cancel = QPushButton("Cancel")
        self.toolbar_layout.addWidget(btn_save)
        self.toolbar_layout.addWidget(btn_cancel)
        self.toolbar_layout.addStretch()
        
        # Store references for signal connections
        self.btn_contrast = btn_contrast
        self.btn_save = btn_save
        self.btn_cancel = btn_cancel

    def _create_instructions_label(self) -> QWidget:
        """Create instructions with current data info using NEWEST file logic."""
        data_source = "Original PNG loaded" if self.has_orig_png else "DICOM frames used"
        
        #   UPDATED LOGIC: Show info about newest files loaded
        mask_status = ""
        
        if self.classification_mask_original and self.classification_mask_original.exists():
            # Check if this is a timestamped (edited) version
            if "_" in self.classification_mask_original.stem:
                png_parts = self.classification_mask_original.stem.split("_")
                if len(png_parts) >= 4 and len(png_parts[-1]) == 6 and png_parts[-1].isdigit():
                    timestamp = png_parts[-1]
                    # Extract date from parent folder
                    date_folder = self.classification_mask_original.parent.name
                    if len(date_folder) == 8 and date_folder.isdigit():
                        mask_status = f"✨ NEWEST edited version loaded: {date_folder} {timestamp[:2]}:{timestamp[2:4]}:{timestamp[4:6]}"
                    else:
                        mask_status = f"✨ NEWEST edited version loaded ({self.classification_mask_original.name})"
                else:
                    mask_status = "Original classification loaded"
            else:
                mask_status = "Original classification loaded"
        elif self.xml_original and self.xml_original.exists():
            # Check if XML is timestamped
            if "_" in self.xml_original.stem:
                xml_parts = self.xml_original.stem.split("_")
                if len(xml_parts) >= 4 and len(xml_parts[-1]) == 6 and xml_parts[-1].isdigit():
                    mask_status = "✨ NEWEST edited XML loaded (converted to mask)"
                else:
                    mask_status = "Loaded from original XML"
            else:
                mask_status = "Loaded from original XML"
        else:
            mask_status = "New mask will be created"
        
        # Segmentation status with newest info
        if self.segmentation_path and self.segmentation_path.exists():
            if "_" in self.segmentation_path.stem:
                segm_parts = self.segmentation_path.stem.split("_")
                if len(segm_parts) >= 3 and len(segm_parts[-1]) == 6 and segm_parts[-1].isdigit():
                    segmentation_status = f"✨ NEWEST segmentation loaded: {self.segmentation_path.name}"
                else:
                    segmentation_status = f"Segmentation loaded: {self.segmentation_path.name}"
            else:
                segmentation_status = f"Segmentation loaded: {self.segmentation_path.name}"
        else:
            segmentation_status = f"No segmentation found"

        #   CREATE COMPACT SCROLLABLE INSTRUCTIONS
        # Create main container
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(3)
        
        # Header label
        header_label = QLabel("<b>Instructions & Data Info</b>")
        header_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #333;
                padding: 3px;
                background: #e8f4f8;
                border-radius: 3px;
            }
        """)
        container_layout.addWidget(header_label)
        
        # Create scrollable area for instructions
        scroll_area = QScrollArea()
        scroll_area.setMaximumHeight(120)  #   Compact height
        scroll_area.setMinimumHeight(100)  #   Minimum height
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Instructions content
        instructions_content = QLabel(
            "<b>Controls:</b><br>"
            "• Left click/drag: Paint<br>"
            "• Middle click/drag: Pan<br>"
            "• Ctrl+scroll: Zoom<br>"
            "• Ctrl+Z: Undo edit<br>"
            "• Ctrl+Y: Redo Edit<br>"
            "• Grid appears at 2x+ zoom<br>"
            "• <b>Paint only on colored segments</b><br><br>"
            f"<b>Data Info:</b><br>"
            f"• Image: {data_source}<br>"
            f"• Mask: {mask_status}<br>"
            f"• {segmentation_status}<br>"
            f"• Size: {self.processed_image_data.shape[1]}×{self.processed_image_data.shape[0]}<br>"
            f"• Save: Creates new timestamped file"
        )
        instructions_content.setWordWrap(True)
        instructions_content.setStyleSheet("""
            QLabel {
                background: #f9f9f9;
                padding: 6px;
                border-radius: 4px;
                font-size: 12px;        /*   BIGGER FONT: 10px -> 12px */
                line-height: 1.4;       /*   BETTER SPACING */
                color: #333;            /*   DARKER COLOR */
                font-weight: 500;       /*   MEDIUM WEIGHT */
            }
        """)
        
        scroll_area.setWidget(instructions_content)
        container_layout.addWidget(scroll_area)
        
        # Style the container with height limit
        container.setMaximumHeight(180)  #   LIMIT TOTAL HEIGHT
        container.setStyleSheet("""
            QWidget {
                background: #f0f0f0;
                border-radius: 4px;
            }
        """)
        
        return container
    
    def _create_main_area(self):
        """Create main area with side-by-side canvases."""
        super()._create_main_area()
        
        # Side-by-side layout
        canvas_layout = QHBoxLayout()
        
        # Original scan view (read-only)
        # Left panel: View-only reference (no editing)
        scan_layout = QVBoxLayout()
        scan_header = QLabel("Scan Image (View Only)")
        scan_header.setAlignment(Qt.AlignCenter)
        scan_header.setStyleSheet("QLabel { background: #e0e0e0; padding: 5px; font-weight: bold; }")
        scan_layout.addWidget(scan_header)

        # Create view-only canvas with empty mask (no hotspot data shown)
        self.original_canvas = HotspotCanvas(self.processed_image_data, np.zeros_like(self.processed_image_data, np.uint8))
        self.original_canvas.setStyleSheet("QGraphicsView { border: 1px solid #888; }")

        # Make original canvas view-only (disable all editing interactions)
        # Make original canvas completely view-only (disable all editing interactions)
        self.original_canvas.setInteractive(False)  # Disable scene interactions
        self.original_canvas.setDragMode(QGraphicsView.NoDrag)  # Disable dragging
        
        # Override ALL mouse events to block editing completely
        def view_only_mouse_press(event):
            # Only allow middle-click for panning, block all left-click editing
            if event.button() == Qt.MiddleButton:
                # Enable panning for middle-click
                self.original_canvas.setDragMode(QGraphicsView.ScrollHandDrag)
                QGraphicsView.mousePressEvent(self.original_canvas, event)
            # Block all other mouse press events (including left-click)
            event.accept()
            
        def view_only_mouse_move(event):
            # Only allow mouse move during middle-click drag
            if event.buttons() & Qt.MiddleButton:
                QGraphicsView.mouseMoveEvent(self.original_canvas, event)
            # Block all other mouse move events
            event.accept()
            
        def view_only_mouse_release(event):
            # Handle middle-click release
            if event.button() == Qt.MiddleButton:
                QGraphicsView.mouseReleaseEvent(self.original_canvas, event)
                self.original_canvas.setDragMode(QGraphicsView.NoDrag)
            # Block all other mouse release events
            event.accept()

        def view_only_wheel_event(event):
            # Only allow Ctrl+Scroll for zooming
            if event.modifiers() & Qt.ControlModifier:
                # Allow zoom with Ctrl+Scroll
                HotspotCanvas.wheelEvent(self.original_canvas, event)
            # Block other wheel events
            event.accept()

        # Override all mouse events to make canvas truly view-only
        self.original_canvas.mousePressEvent = view_only_mouse_press
        self.original_canvas.mouseMoveEvent = view_only_mouse_move
        self.original_canvas.mouseReleaseEvent = view_only_mouse_release
        self.original_canvas.wheelEvent = view_only_wheel_event
        
        # Disable brush cursor on view-only canvas
        self.original_canvas.set_brush_cursor_visible(False)

        # Setup segmentation for view-only canvas (for reference)
        if self.segmentation_path.exists():
            self.original_canvas.set_segmentation_layer(self.segmentation_path)

        scan_layout.addWidget(self.original_canvas)

        # Right panel: Hotspot Editor (with editing capabilities)
        editor_layout = QVBoxLayout()
        editor_header = QLabel("Hotspot Editor (Editable)")
        editor_header.setAlignment(Qt.AlignCenter)
        editor_header.setStyleSheet("QLabel { background: #d0f0d0; padding: 5px; font-weight: bold; }")
        editor_layout.addWidget(editor_header)

        # Info panel
        info_frame = self._create_info_panel()
        editor_layout.addWidget(info_frame)

        # Main editing canvas with brush/eraser functionality
        self.canvas = HotspotCanvas(self.processed_image_data, self.mask_arr)
        self.canvas.set_info_callback(self._update_info_display)
        self.canvas.setStyleSheet("QGraphicsView { border: 1px solid #4a90e2; }")

        # Setup segmentation for editing canvas (for painting constraints)
        if self.segmentation_path.exists():
            success = self.canvas.set_segmentation_layer(self.segmentation_path)
            if not success:
                logging.info(f"✗ Segmentation load failed: {self.segmentation_path.name}")

        editor_layout.addWidget(self.canvas)
        
        # Add to main layout
        canvas_layout.addLayout(scan_layout)
        canvas_layout.addLayout(editor_layout)
        self.main_area_layout.addLayout(canvas_layout)

    def _connect_signals(self):
        """Connect UI signals to functionality."""
        # Palette
        self.palette.currentRowChanged.connect(self._change_label)
        
        # Tools
        self.btn_brush.clicked.connect(self._select_brush)
        self.btn_eraser.clicked.connect(self._select_eraser)
        self.btn_showall.toggled.connect(self.canvas.toggle_show_all)
        
        # Undo/Redo
        self.btn_undo.clicked.connect(self._perform_undo)
        self.btn_redo.clicked.connect(self._perform_redo)
        
        # Brush size and zoom - Using simplified connections
        self.brush_size_control.radiusChanged.connect(self._size_changed)
        self.zoom_slider.valueChanged.connect(self._zoom_slider_changed)
        
        # Set initial canvas opacity
        self.canvas.set_gray_opacity(1.0)
        self.original_canvas.set_gray_opacity(1.0)

        #   SIMPLIFIED: Connect opacity sliders using same pattern as zoom
        # Connect opacity panel to both canvases
        self.opacity_panel.connect_to_canvas(self.canvas)
        # Also connect to original canvas for segmentation opacity
        self.opacity_panel.segmentation_opacity.valueChanged.connect(
            lambda v: self.original_canvas.set_segmentation_opacity(v / 100.0) 
            if hasattr(self.original_canvas, 'set_segmentation_opacity') else None
        )
        
        # Contrast and invert
        self.btn_contrast.clicked.connect(self._open_contrast_popup)
        self.invert_checkbox.stateChanged.connect(self._on_invert_changed)
        
        # Save/Cancel
        self.btn_save.clicked.connect(self._save_all)
        self.btn_cancel.clicked.connect(self.reject)

    def _setup_zoom_sync(self):
        """Setup bidirectional zoom synchronization."""
        original_wheel_event = self.original_canvas.wheelEvent
        editor_wheel_event = self.canvas.wheelEvent
        
        def sync_original_wheel(event):
            if not self._sync_zoom_in_progress and event.modifiers() & Qt.ControlModifier:
                self._sync_zoom_in_progress = True
                original_wheel_event(event)
                current_zoom = self.original_canvas._zoom_factor
                self.canvas.set_zoom(current_zoom)
                slider_value = int(current_zoom * 10)
                self.zoom_slider.setValue(slider_value)
                self._sync_zoom_in_progress = False
            elif not (event.modifiers() & Qt.ControlModifier):
                original_wheel_event(event)
        
        def sync_editor_wheel(event):
            if not self._sync_zoom_in_progress and event.modifiers() & Qt.ControlModifier:
                self._sync_zoom_in_progress = True
                editor_wheel_event(event)
                current_zoom = self.canvas._zoom_factor
                self.original_canvas.set_zoom(current_zoom)
                slider_value = int(current_zoom * 10)
                self.zoom_slider.setValue(slider_value)
                self._sync_zoom_in_progress = False
            elif not (event.modifiers() & Qt.ControlModifier):
                editor_wheel_event(event)
        
        self.original_canvas.wheelEvent = sync_original_wheel
        self.canvas.wheelEvent = sync_editor_wheel

    def _show_session_selector_dialog(self):
        """Show session selector dialog reading from doctor_tags.json."""
        import json
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QScrollArea
        from PySide6.QtCore import Qt
        
        try:
            # Load doctor tags from config file
            from core.config.paths import CONFIG_ROOT
            config_path = CONFIG_ROOT / "doctor_tags.json"
            if not config_path.exists():
                logging.info(f"Config file not found: {config_path}")
                return "NONE"  # Fallback to default
            
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Filter out "ALL" and get available tags
            available_tags = [tag for tag in config_data.get("doctor_tags", []) if tag.get("code") != "ALL"]
            
            if not available_tags:
                logging.info("No available doctor tags found")
                return "NONE"  # Fallback to default
            
            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Session Code")
            dialog.setModal(True)
            dialog.resize(400, 300)
            
            layout = QVBoxLayout(dialog)
            
            layout.addWidget(QLabel("Select doctor code for saving hotspot classification:"))
            
            # Create list widget
            list_widget = QListWidget()
            for tag in available_tags:
                item = QListWidgetItem()
                
                # Create widget for each item
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                
                # Color indicator
                color_label = QLabel()
                color_label.setFixedSize(20, 20)
                color_label.setStyleSheet(f"background-color: {tag.get('color', '#000000')}; border: 1px solid #ccc;")
                
                # Code and name
                text_label = QLabel(f"{tag.get('code', 'N/A')} - {tag.get('name', 'Unknown')}")
                
                item_layout.addWidget(color_label)
                item_layout.addWidget(text_label)
                item_layout.addStretch()
                
                item.setSizeHint(item_widget.sizeHint())
                list_widget.addItem(item)
                list_widget.setItemWidget(item, item_widget)
                
                # Store the code in the item data
                item.setData(Qt.UserRole, tag.get('code'))
            
            # Select first item by default
            if list_widget.count() > 0:
                list_widget.setCurrentRow(0)
            
            layout.addWidget(list_widget)
            
            # Buttons
            button_layout = QHBoxLayout()
            ok_button = QPushButton("OK")
            cancel_button = QPushButton("Cancel")
            
            ok_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)
            
            button_layout.addStretch()
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            # Show dialog
            if dialog.exec() == QDialog.Accepted:
                current_item = list_widget.currentItem()
                if current_item:
                    return current_item.data(Qt.UserRole)
            
            return None  # User cancelled
            
        except Exception as e:
            logging.info(f"Error showing session selection dialog: {e}")
            return "NONE"  # Fallback to default
        
    def _change_label(self, idx: int):
        """Handle palette selection."""
        self.btn_brush.setChecked(True)
        self.btn_eraser.setChecked(False)
        self.canvas.set_label(idx)

    def _select_brush(self):
        """Select brush tool."""
        self.btn_eraser.setChecked(False)
        self.canvas.set_label(self.palette.list_palette.currentRow())

    def _select_eraser(self):
        """Select eraser tool."""
        self.btn_brush.setChecked(False)
        self.canvas.set_eraser()

    def _perform_undo(self):
        """Perform undo for current layer."""
        current_label = self.palette.list_palette.currentRow()
        self.canvas.undo(current_label)

    def _perform_redo(self):
        """Perform redo for current layer."""
        current_label = self.palette.list_palette.currentRow()
        self.canvas.redo(current_label)

    def _size_changed(self, radius: int):
        """Handle brush size change with the new brush control."""
        self.canvas.set_brush_size(radius)
        # The brush control already shows "Npx" format

    def _zoom_slider_changed(self, val: int):
        """Handle zoom slider change with sync."""
        if self._sync_zoom_in_progress:
            return
            
        self._sync_zoom_in_progress = True
        zoom_factor = val / 10.0
        
        self.canvas.set_zoom(zoom_factor)
        self.original_canvas.set_zoom(zoom_factor)
        self.zoom_slider.lbl_value.setText(f"{zoom_factor:.1f}x")
        
        self._sync_zoom_in_progress = False

    def _on_invert_changed(self, state: int):
        """Handle image inversion toggle."""
        from features.spect_viewer.logic.image_inverter import simple_invert_image
        
        try:
            if self.invert_checkbox.isChecked():
                inverted_data = simple_invert_image(self.original_image_data)
            else:
                inverted_data = self.original_image_data.copy()
            
            self._update_canvas_images(inverted_data)
        except Exception as e:
            logging.info(f"✗ Error during image inversion: {e}")
            self.invert_checkbox.setChecked(not self.invert_checkbox.isChecked())

    def _update_canvas_images(self, new_image_data: np.ndarray):
        """Update both canvases with new image data."""
        try:
            if new_image_data.dtype != np.uint8:
                normalized_data = ((new_image_data - new_image_data.min()) /
                                max(1, np.ptp(new_image_data)) * 255).astype(np.uint8)
            else:
                normalized_data = new_image_data.copy()

            # Update both canvases
            self.original_canvas._orig_base = normalized_data.copy()
            self.canvas._orig_base = normalized_data.copy()

            # Update pixmaps
            from PySide6.QtGui import QImage, QPixmap
            h, w = normalized_data.shape
            q_image = QImage(normalized_data.data, w, h, w, QImage.Format_Grayscale8)
            pixmap = QPixmap.fromImage(q_image.copy())

            self.original_canvas._item_gray.setPixmap(pixmap)
            self.canvas._item_gray.setPixmap(pixmap)

            # Refresh viewports
            self.original_canvas.viewport().update()
            self.canvas.viewport().update()
            
        except Exception as e:
            logging.info(f"✗ Error updating canvas images: {e}")

    def _get_session_base_path(self) -> Path:
        """Get the base session path for saving files."""
        # Based on your path structure: C:\hotspot\hotspot-analyzer\data\PLANAR\ATL\5001\20250115\<datenow>\ant/post_hotspot_classification_<timestamp>.png/xml
        
        if hasattr(self, 'classification_mask_original') and self.classification_mask_original:
            # Example: C:\hotspot\hotspot-analyzer\data\PLANAR\ATL\5001\20250115\ant_hotspot_classification.png
            # We want: C:\hotspot\hotspot-analyzer\data\PLANAR
            original_path = Path(self.classification_mask_original)
            # Go up 4 levels: filename -> date -> patient -> session -> PLANAR
            return original_path.parent.parent.parent.parent
        
        # Fallback to default path
        from core.config.paths import PLANAR_DATA_PATH
        return PLANAR_DATA_PATH

    def _save_all(self):
        """Save hotspot classification data with proper session handling."""
        # Stop timer and get duration
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        elapsed_seconds, formatted_time = self._get_editing_duration()
        
        # Handle session selection for ALL users
        self.editor_session = None
        if self.session_code == "ALL":
            session_choice = self._show_session_selector_dialog()
            if not session_choice:
                # Resume timer if user cancels
                if hasattr(self, 'update_timer'):
                    self.update_timer.start(1000)
                return  # User cancelled
            self.editor_session = session_choice
        
        # Show loading dialog immediately after session selection
        self.save_loading_dialog = LoadingDialog(
            title="Saving Hotspot Classification",
            message="Preparing to save hotspot classification data...",
            show_progress=True,
            show_cancel=False,
            parent=self
        )
        self.save_loading_dialog.show()
        
        # Disable save button during save operation
        self.btn_save.setEnabled(False)
            
        try:
            # Create and start save thread with editor session
            self.save_thread = HotspotSaveThread(
                canvas=self.canvas,
                session_path=self._get_session_base_path(),
                patient_id=self.patient_id,
                view_short=self.view_short,
                filename_stem=self.filename_stem,
                dicom_path=self.dicom_path,
                study_date=self.study_date,
                current_session=self.session_code,
                editor_session=self.editor_session
            )
            
            #   FIX: Connect signals - HANYA GUNAKAN SATU COMPLETION SIGNAL
            if hasattr(self.save_thread, 'progress_updated'):
                self.save_thread.progress_updated.connect(self._update_progress)
            
            #   GUNAKAN HANYA save_completed (yang ada editing time)
            if hasattr(self.save_thread, 'save_completed'):
                self.save_thread.save_completed.connect(self._on_save_success)
            
            #   HAPUS finished connection untuk avoid duplicate dialog
            # self.save_thread.finished.connect(self._on_save_finished)  # HAPUS INI
            
            if hasattr(self.save_thread, 'error_occurred'):
                self.save_thread.error_occurred.connect(self._on_save_error)
            
            # Start the thread
            self.save_thread.start()
            
        except Exception as e:
            # Re-enable save button if there's an error during setup
            self.btn_save.setEnabled(True)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Save Error", f"Failed to start save operation: {str(e)}")
    
    def _on_save_success(self, success_message: str):
        """Handle successful save with message."""
        from PySide6.QtWidgets import QMessageBox
        
        #   FIX 1: TUTUP LOADING DIALOG TERLEBIH DAHULU
        if hasattr(self, 'save_loading_dialog') and self.save_loading_dialog:
            self.save_loading_dialog.close()
            self.save_loading_dialog.deleteLater()  #   TAMBAHAN: hapus dari memory
            self.save_loading_dialog = None
            logging.info("[DEBUG] Loading dialog closed and deleted")
        
        #   FIX 2: PROSES EDITING TIME
        elapsed_seconds, formatted_time = self._get_editing_duration()
        self._save_editing_time_log(elapsed_seconds, formatted_time)
        
        #   FIX 3: RE-ENABLE SAVE BUTTON
        self.btn_save.setEnabled(True)
        self.btn_save.setText("Save")  #   TAMBAHAN: reset text button
        
        #   FIX 4: BUILD SUCCESS MESSAGE
        if hasattr(self.save_thread, 'get_save_info'):
            save_info = self.save_thread.get_save_info()
            if save_info and save_info:  # Check if save_info is not empty
                detailed_message = (
                    f"Hotspot classification saved successfully!\n\n"
                    f"Location: {save_info.get('date_dir', 'Unknown')}\n"
                    f"Files:\n"
                    f"• {save_info.get('png_path', {}).name if save_info.get('png_path') else 'Classification PNG'}\n"
                    f"• {save_info.get('xml_path', {}).name if save_info.get('xml_path') else 'Annotation XML'}\n\n"
                    f"⏱️ Editing Time: {formatted_time}"
                )
            else:
                detailed_message = f"{success_message}\n\n⏱️ Editing Time: {formatted_time}"
        else:
            detailed_message = f"Hotspot classification saved!\n\n⏱️ Editing Time: {formatted_time}"
        
        #   FIX 5: TAMPILKAN SUCCESS DIALOG
        QMessageBox.information(self, "Save Complete", detailed_message)
        
        #   FIX 6: EMIT SIGNAL DAN CLOSE
        if hasattr(self, 'editor_completed'):
            logging.info("[DEBUG] Emitting editor_completed signal")
            self.editor_completed.emit()
        
        # Close dialog
        self.accept()
    
    def _on_save_finished(self):
        """Handle save thread completion (cleanup only)."""
        # Re-enable save button
        self.btn_save.setEnabled(True)
        
        # Note: Success message is handled by _on_save_success
        # This method only handles cleanup

    def _on_save_error(self, error_message: str):
        """Handle save errors."""
        from PySide6.QtWidgets import QMessageBox
        
        #   FIX: TUTUP LOADING DIALOG TERLEBIH DAHULU
        if hasattr(self, 'save_loading_dialog') and self.save_loading_dialog:
            self.save_loading_dialog.close()
            self.save_loading_dialog.deleteLater()  #   TAMBAHAN: hapus dari memory
            self.save_loading_dialog = None
            logging.info("[DEBUG] Loading dialog closed due to error")
        
        # Show error message
        QMessageBox.critical(self, "Save Error", error_message)
        
        #   FIX: RE-ENABLE SAVE BUTTON
        self.btn_save.setEnabled(True)
        self.btn_save.setText("Save")  #   TAMBAHAN: reset text button
        
        #   FIX: RESUME TIMER IF STOPPED
        if hasattr(self, 'update_timer') and hasattr(self, 'update_timer'):
            if not self.update_timer.isActive():
                self.update_timer.start(1000)
                logging.info("[DEBUG] Timer resumed after error")
        
    def _update_progress(self, value: int, message: str):
        """Update progress bar and message."""
        logging.info(f"[PROGRESS] {value}% - {message}")
        
        # Update loading dialog if exists
        if hasattr(self, 'save_loading_dialog') and self.save_loading_dialog:
            self.save_loading_dialog.set_progress(value)
            
            #   FIX: Jangan update message jika sudah 100% (avoid stuck message)
            if value < 100:
                self.save_loading_dialog.set_message(f"Saving hotspot classification...\n{message}")
            else:
                #   FIX: Untuk progress 100%, set message yang menunjukkan akan segera tutup
                self.save_loading_dialog.set_message(f"Save completed! Preparing results...")
                logging.info("[DEBUG] Progress 100% reached, dialog will close soon")

    def _on_save_finished(self):
        """Handle save completion."""
        from PySide6.QtWidgets import QMessageBox
        
        logging.info("    [DEBUG HOTSPOT] ===================")
        logging.info("    [DEBUG HOTSPOT] Save finished!")
        logging.info("    [DEBUG HOTSPOT] About to emit signal...")
        
        # Close loading dialog
        if hasattr(self, 'save_loading_dialog') and self.save_loading_dialog:
            self.save_loading_dialog.close()
            self.save_loading_dialog = None
        
        # Get save information
        if hasattr(self.save_thread, 'get_save_info'):
            save_info = self.save_thread.get_save_info()
            success_message = (
                f"Files saved successfully!\n\n"
                f"Location: {save_info['date_dir']}\n"
                f"Files:\n"
                f"• {save_info['png_path'].name}\n"
                f"• {save_info['xml_path'].name}"
            )
        else:
            success_message = "Classification data saved successfully!"
        
        QMessageBox.information(self, "Save Complete", success_message)
        
        # Re-enable save button
        self.btn_save.setEnabled(True)
        
        #   TEST SIGNAL EMIT
        logging.info("    [DEBUG HOTSPOT] Checking if signal exists...")
        if hasattr(self, 'editor_completed'):
            logging.info("    [DEBUG HOTSPOT] Signal exists, emitting...")
            self.editor_completed.emit()
            logging.info("    [DEBUG HOTSPOT] Signal emitted!")
        else:
            logging.info("    [DEBUG HOTSPOT]  Signal does not exist!")
        
        # Close dialog
        self.accept()
    
    def _create_timer_widget(self) -> QWidget:
        """Create compact timer widget."""
        timer_widget = QWidget()
        timer_layout = QVBoxLayout(timer_widget)
        timer_layout.setContentsMargins(0, 0, 0, 0)
        timer_layout.setSpacing(2)
        
        # Timer label
        timer_header = QLabel("⏱️ Editing Time")
        timer_header.setAlignment(Qt.AlignCenter)
        timer_header.setStyleSheet("""
            QLabel {
                font-size: 10px;
                font-weight: bold;
                color: #666;
                padding: 2px;
            }
        """)
        
        self.timer_display = QLabel("00:00:00")
        self.timer_display.setAlignment(Qt.AlignCenter)
        self.timer_display.setStyleSheet("""
            QLabel {
                font-family: 'Courier New', monospace;
                font-size: 14px;
                font-weight: bold;
                color: #2c5282;
                background: #f0f8ff;
                border: 1px solid #4a90e2;
                border-radius: 4px;
                padding: 4px;
                min-width: 70px;
            }
        """)
        
        timer_layout.addWidget(timer_header)
        timer_layout.addWidget(self.timer_display)
        
        return timer_widget

    def _setup_editing_timer(self):
        """Initialize editing timer."""
        from PySide6.QtCore import QTimer
        import time
        
        self.start_time = time.time()
        self.editing_start_time = datetime.now()
        
        # Create update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_timer_display)
        self.update_timer.start(1000)  # Update every second

    def _update_timer_display(self):
        """Update timer display."""
        import time
        
        elapsed = int(time.time() - self.start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.timer_display.setText(time_str)

    # hotspot_editor_dialog.py -> _get_editing_duration()

    def _get_editing_duration(self) -> tuple[float, str]:
        """Get editing duration with millisecond precision."""
        import time
        
        elapsed_seconds_float = time.time() - self.start_time
        
        # Calculate components
        total_seconds_int = int(elapsed_seconds_float)
        hours = total_seconds_int // 3600
        minutes = (total_seconds_int % 3600) // 60
        seconds = total_seconds_int % 60
        milliseconds = int((elapsed_seconds_float - total_seconds_int) * 1000)
        
        # Format the string as HH:MM:SS:ms
        formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
        
        return elapsed_seconds_float, formatted_time

    # hotspot_editor_dialog.py -> _save_editing_time_log()

    def _save_editing_time_log(self, elapsed_seconds: float, formatted_time: str):
        """Save editing time to a CSV log file."""
        # ================== PERBAIKAN UTAMA ==================
        # Inisialisasi variabel di luar blok try untuk menghindari UnboundLocalError
        log_file = "Path tidak terdefinisi" 
        time_log_dir = "Path tidak terdefinisi"
        # =====================================================

        try:
            from pathlib import Path
            import csv
            from datetime import datetime
            import sys

            if getattr(sys, 'frozen', False):
                base_path = Path(sys.executable).parent
            else:
                base_path = Path(__file__).parent.parent.parent.parent

            time_log_dir = base_path / "data" / "PLANAR" / "timeEdit"
            time_log_dir.mkdir(parents=True, exist_ok=True)
            log_file = time_log_dir / "time_editing.csv"

            doctor_code = self.editor_session if self.session_code == "ALL" else self.session_code

            log_entry = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'session': self.session_code,
                'kode_dokter': doctor_code,
                'patient_id': self.patient_id,
                'study_date': self.study_date,
                'view': self.view_short,
                'duration_seconds': f"{elapsed_seconds:.3f}",
                'duration_formatted': formatted_time,
                'edit_type' : 'hotspot'
            }
            
            fieldnames = list(log_entry.keys())
            file_exists = log_file.exists()

            with open(log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(log_entry)
            
            logging.info(f"   Editing time logged to '{log_file.name}': {formatted_time} for patient {self.patient_id}")

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            logging.info(f" Failed to save editing time log: {e}")
            # Sekarang blok ini aman karena 'log_file' pasti punya nilai
            QMessageBox.critical(
                self, "Error Menyimpan Log",
                f"Gagal menyimpan log waktu editing.\n\n"
                f"Lokasi yang dituju: {time_log_dir}\n"
                f"File yang dituju: {log_file}\n\n"
                f"Error: {str(e)}"
            )

        except Exception as e:
            # SANGAT DISARANKAN: Tampilkan error sebagai pop-up
            from PySide6.QtWidgets import QMessageBox
            logging.info(f" Failed to save editing time log: {e}")
            QMessageBox.critical(
                self, "Error Menyimpan Log",
                f"Gagal menyimpan log waktu editing.\n\nFile: {log_file}\nError: {str(e)}"
            )

    def closeEvent(self, event):
        """Handle dialog close to stop timer."""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        super().closeEvent(event)
    