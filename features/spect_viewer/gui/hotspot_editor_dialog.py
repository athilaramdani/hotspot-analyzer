# features/spect_viewer/gui/hotspot_editor_dialog.py - Fixed version
"""
Hotspot editor dialog using modular components.
Significantly reduced code through inheritance and composition.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QSlider, QWidget, QGraphicsView
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
from core.config.paths import PLANAR_DATA_PATH, generate_edit_date, generate_edit_timestamp


from features.spect_viewer.logic.hotspot_processor import parse_xml_annotations, create_hotspot_mask


class HotspotEditorDialog(BaseEditorDialog):
    """Hotspot editor dialog using modular components."""
    
    def __init__(self, scan: Dict, view: str, parent=None):
        # 1. STORE INITIAL DATA
        self.scan = scan
        self.view = view
        view_key = view.lower()
        vtag = "ant" if "ant" in view_key else "post"

        # 2. GET ALL PATHS FROM THE ENRICHED SCAN OBJECT (SINGLE SOURCE OF TRUTH)
        workflow_files = self.scan['workflow_files']
        self.classification_mask_original = workflow_files['classification'][vtag]['png']
        self.xml_original = workflow_files['classification'][vtag]['xml']
        self.segmentation_path = workflow_files['segmentation'][vtag]
        self.dicom_path = Path(scan["path"])
        
        # Extract patient info needed for saving
        # Assumes structure: .../PLANAR/SESSION/PATIENT_ID/
        patient_folder = self.dicom_path.parent
        self.patient_id = patient_folder.parent.name
        self.session_code = patient_folder.parent.parent.name
        self.study_date = extract_study_date_from_dicom(self.dicom_path)
        self.filename_stem = generate_filename_stem(self.patient_id, self.study_date)
        self.view_short = vtag

        # 3. LOAD IMAGES AND MASKS (using the correct paths from step 2)
        original_png_path = workflow_files['original'][vtag]
        if original_png_path and original_png_path.exists():
            self.original_image_data = np.array(Image.open(original_png_path).convert('L'))
            self.has_orig_png = True
        else:
            # Fallback to raw DICOM frame if original PNG is missing
            self.original_image_data = scan["frames"][view_key]
            self.has_orig_png = False

        from features.spect_viewer.logic.image_inverter import simple_invert_image
        self.processed_image_data = simple_invert_image(self.original_image_data.copy())
        
        # This now uses the correct paths assigned above
        self.mask_arr = self._load_existing_mask()
        self.xml_loaded_from_edited = self.xml_original and self.xml_original.name != f"{vtag}_hotspot_classification.xml"

        # 4. INITIALIZE THE BASE DIALOG UI
        super().__init__(f"Hotspot Editor – {view}", parent)
        
        # 5. SETUP ZOOM SYNC
        self._sync_zoom_in_progress = False
        self._setup_zoom_sync()

    def _load_existing_mask(self) -> np.ndarray:
        """Load existing mask with proper priority using CORRECT paths."""
        # This method is now much cleaner because it relies on paths set in __init__
        
        # The path self.classification_mask_original already points to the latest file
        if self.classification_mask_original and self.classification_mask_original.exists():
            print(f"✓ Loading classification mask from: {self.classification_mask_original.name}")
            return self._load_mask_from_classification_png(self.classification_mask_original)
        
        # The path self.xml_original already points to the latest file
        elif self.xml_original and self.xml_original.exists():
            print(f"✓ Found XML annotations: {self.xml_original.name}")
            return self._load_from_xml(self.xml_original)
        
        else:
            print(f"✗ No classification data found. Creating empty mask.")
            # ✅ FIX: Use self.original_image_data
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
            
            print(f"✓ Loaded classification mask from: {classification_path}")
            return mask
        except Exception as e:
            print(f"✗ Failed to load classification mask: {e}")
            # ✅ FIX: Use self.original_image_data
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
            print(f"✗ Error processing XML {xml_path}: {e}")
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
        
        # ✅ SIMPLIFIED: Hotspot Layer Opacity - Using same base component
        self.hotspot_opacity = BaseOpacitySlider("Hotspot Layer", 30)
        self.hotspot_opacity.slider.setRange(0, 100)
        self.hotspot_opacity.setValue(30)
        self.toolbar_layout.addWidget(self.hotspot_opacity)
        
        # ✅ SIMPLIFIED: Segmentation Opacity - Using same base component  
        self.segmentation_opacity = BaseOpacitySlider("Segmentation", 10)
        self.segmentation_opacity.slider.setRange(0, 100)
        self.segmentation_opacity.setValue(10)
        self.toolbar_layout.addWidget(self.segmentation_opacity)
        
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

    def _create_instructions_label(self) -> QLabel:
        """Create instructions with current data info using updated logic."""
        data_source = "Original PNG loaded" if self.has_orig_png else "DICOM frames used"
        
        # ✅ NEW LOGIC: Determine mask status based on available paths
        mask_status = ""
        # The 'classification_mask_original' now points to the LATEST version.
        # We check if its name is the default or a timestamped version.
        is_edited_version = (
            self.classification_mask_original and
            self.classification_mask_original.name != f"{self.view_short}_hotspot_classification.png"
        )

        if is_edited_version:
            mask_status = f"Edited version loaded ({self.classification_mask_original.name})"
        elif self.classification_mask_original and self.classification_mask_original.exists():
            mask_status = "Original classification loaded"
        elif self.xml_original and self.xml_original.exists():
            # Fallback check for XML if the PNG doesn't exist but the XML does
            mask_status = "Loaded from original XML"
        else:
            mask_status = "New mask will be created"
        
        # Segmentation status
        if self.segmentation_path.exists():
            segmentation_status = f"Segmentation loaded: {self.segmentation_path.name}"
        else:
            segmentation_status = f"No segmentation found: {self.segmentation_path.name}"

        instructions = QLabel(
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
        instructions.setWordWrap(True)
        instructions.setStyleSheet("QLabel { background: #f0f0f0; padding: 8px; border-radius: 4px; }")
        return instructions

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
                print(f"✗ Segmentation load failed: {self.segmentation_path.name}")

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

        # ✅ SIMPLIFIED: Connect opacity sliders using same pattern as zoom
        def update_hotspot_opacity(value):
            self.hotspot_opacity.lbl_value.setText(f"{value}%")
            self.canvas.set_mask_opacity(value / 100.0)

        def update_segmentation_opacity(value):
            self.segmentation_opacity.lbl_value.setText(f"{value}%")
            if hasattr(self.canvas, 'set_segmentation_opacity'):
                self.canvas.set_segmentation_opacity(value / 100.0)
            if hasattr(self.original_canvas, 'set_segmentation_opacity'):
                self.original_canvas.set_segmentation_opacity(value / 100.0)

        self.hotspot_opacity.valueChanged.connect(update_hotspot_opacity)
        self.segmentation_opacity.valueChanged.connect(update_segmentation_opacity)
        
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
            print(f"✗ Error during image inversion: {e}")
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
            print(f"✗ Error updating canvas images: {e}")

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
        return Path("C:/hotspot/hotspot-analyzer/data/PLANAR")

    def _save_all(self):
        """Save hotspot classification data with session selection."""
        # Get current session from the dialog's stored session_code
        current_session = getattr(self, 'session_code', 'ALL')
        
        # Disable save button during save operation
        self.btn_save.setEnabled(False)
        
        try:
            # Create and start save thread with corrected method call
            self.save_thread = HotspotSaveThread(
                canvas=self.canvas,
                session_path=self._get_session_base_path(),  # ✅ FIXED: Added underscore prefix
                patient_id=self.patient_id,
                view_short=self.view_short,
                filename_stem=self.filename_stem,
                dicom_path=self.dicom_path,
                study_date=self.study_date,
                current_session=current_session
            )
            
            # Connect signals - only connect to signals that exist
            if hasattr(self.save_thread, 'progress_updated'):
                self.save_thread.progress_updated.connect(self._update_progress)
            
            self.save_thread.finished.connect(self._on_save_finished)
            
            # Check if error_occurred signal exists before connecting
            if hasattr(self.save_thread, 'error_occurred'):
                self.save_thread.error_occurred.connect(self._on_save_error)
            
            # Start the thread
            self.save_thread.start()
            
        except Exception as e:
            # Re-enable save button if there's an error during setup
            self.btn_save.setEnabled(True)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Save Error", f"Failed to start save operation: {str(e)}")

    def _on_save_error(self, error_message: str):
        """Handle save errors."""
        from PySide6.QtWidgets import QMessageBox
        
        QMessageBox.critical(self, "Save Error", error_message)
        
        # Re-enable save button
        self.btn_save.setEnabled(True)

    def _update_progress(self, value: int, message: str):
        """Update progress bar and message."""
        # You can add progress bar updates here if you have progress UI elements
        print(f"Save progress: {value}% - {message}")

    def _on_save_finished(self):
        """Handle save completion."""
        from PySide6.QtWidgets import QMessageBox
        
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
        
        # Close dialog
        self.accept()