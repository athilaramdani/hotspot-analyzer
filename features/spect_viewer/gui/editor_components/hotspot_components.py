# features/spect_viewer/gui/editor_components/hotspot_components.py
"""
Hotspot-specific components that inherit from base components.
Adds segmentation validation and hotspot classification functionality.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
from PIL import Image
import datetime

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QWidget, QCheckBox, QGraphicsPixmapItem
)

from .base_components import BaseCanvas, BaseEditorDialog, BaseSaveThread
from features.spect_viewer.logic.colorizer import _HOTSPOT_PALLETTE, label_mask_to_hotspot_rgb

# Segment names mapping for hotspot detection
_SEGMENT_NAMES = {
    0: "background", 1: "skull", 2: "cervical_vertebrae", 3: "thoracic_vertebrae",
    4: "rib", 5: "sternum", 6: "collarbone", 7: "scapula", 8: "humerus",
    9: "lumbar_vertebrae", 10: "sacrum", 11: "pelvis", 12: "femur"
}

# Hotspot label information
_HOTSPOT_LABEL_INFO: List[Tuple[str, str]] = [
    ("Background", "kosong"),
    ("Abnormal", "Terdeteksi anomali"),
    ("Normal", "Tidak terdeteksi anomali")
]


class HotspotCanvas(BaseCanvas):
    """Canvas with hotspot-specific functionality including segmentation validation."""

    def __init__(self, orig: np.ndarray, mask: np.ndarray, parent=None):
        # ✅ FIX: Call parent constructor with correct arguments
        # BaseCanvas expects: (orig, mask, parent=None)
        super().__init__(orig, mask, parent)
        
        # Set the hotspot-specific palette after initialization
        self._palette = _HOTSPOT_PALLETTE
        
        # --- HotspotCanvas-specific attributes ---
        self._bg_alpha = 0.0  # Background opacity

        # Segmentation layer for validation
        self._segmentation_arr = None
        self._item_segmentation = None

        # The BaseCanvas creates the self._item_mask, now we just need to
        # draw the initial image on it using our specific colorizer.
        self._refresh_mask()

    def _init_history(self):
        """Initialize history for hotspot layers."""
        # ✅ FIX: Initialize _layer_history if it doesn't exist
        if not hasattr(self, '_layer_history'):
            self._layer_history = {}
            
        for label_id in range(len(_HOTSPOT_PALLETTE)):
            self._layer_history[label_id] = {'undo': [], 'redo': []}
        self._save_all_states()

    def _save_all_states(self):
        """Save initial state for all layers."""
        # ✅ FIX: Ensure _layers exists before trying to save states
        if not hasattr(self, '_layers') or not self._layers:
            return
            
        for label_id in range(len(_HOTSPOT_PALLETTE)):
            if label_id in self._layers:
                self._save_layer_state(label_id)

    def _save_layer_state(self, label_id: int):
        """Save state for specific layer."""
        # ✅ FIX: Add safety checks
        if not hasattr(self, '_layer_history'):
            self._init_history()
            
        if label_id not in self._layers:
            return
            
        history = self._layer_history[label_id]
        state = self._layers[label_id].copy()
        
        if len(history['undo']) >= self._max_history:
            history['undo'].pop(0)
        
        history['undo'].append(state)
        history['redo'].clear()

    def _save_current_state(self):
        """Save current state for active layer."""
        # ✅ FIX: Check if _cur_label is valid
        if hasattr(self, '_cur_label') and self._cur_label is not None:
            self._save_layer_state(self._cur_label)

    def set_segmentation_layer(self, segmentation_path: Path) -> bool:
        """Load and set segmentation layer for validation."""
        try:
            if segmentation_path and segmentation_path.exists():
                from features.spect_viewer.logic.colorizer import _PALETTE
                
                # Load RGB image and convert to label mask
                rgb_img = np.array(Image.open(segmentation_path).convert("RGB"))
                label_mask = np.zeros(rgb_img.shape[:2], dtype=np.uint8)
                
                for label_id, color in enumerate(_PALETTE):
                    mask_matches = np.all(rgb_img == color, axis=-1)
                    label_mask[mask_matches] = label_id
                
                self._segmentation_arr = label_mask
                
                # Update graphics item
                if self._item_segmentation:
                    self._scene.removeItem(self._item_segmentation)
                
                self._segmentation_img = self._segmentation_to_qimage()
                self._item_segmentation = QGraphicsPixmapItem(QPixmap.fromImage(self._segmentation_img))
                self._item_segmentation.setOpacity(0.3)
                
                # ✅ FIX: Check if _scene exists before adding item
                if hasattr(self, '_scene') and self._scene:
                    self._scene.addItem(self._item_segmentation)
                
                return True
            return False
        except Exception as e:
            print(f"Failed to load segmentation: {e}")
            return False

    def _segmentation_to_qimage(self) -> QImage:
        """Convert segmentation array to QImage with transparency."""
        if self._segmentation_arr is None:
            return QImage()
        
        from features.spect_viewer.logic.colorizer import _PALETTE
        h, w = self._segmentation_arr.shape
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        alpha = np.zeros((h, w), dtype=np.uint8)
        
        # Apply colors from palette
        for label_id, color in enumerate(_PALETTE):
            mask = (self._segmentation_arr == label_id)
            if label_id == 0:  # Background transparent
                alpha[mask] = 0
            else:  # Segments visible
                rgb[mask] = color
                alpha[mask] = 255
        
        # Create RGBA
        rgba = np.dstack([rgb, alpha])
        return QImage(rgba.data, w, h, 4*w, QImage.Format_RGBA8888).copy()

    def set_segmentation_opacity(self, alpha: float):
        """Set segmentation layer opacity."""
        if self._item_segmentation:
            self._item_segmentation.setOpacity(alpha)

    def set_bg_opacity(self, alpha: float):
        """Set background opacity."""
        self._bg_alpha = alpha
        self._refresh_mask()

    def get_segment_at_position(self, x: int, y: int) -> str:
        """Get segment name at given position."""
        if self._segmentation_arr is not None:
            if 0 <= x < self._segmentation_arr.shape[1] and 0 <= y < self._segmentation_arr.shape[0]:
                segment_label = self._segmentation_arr[y, x]
                return _SEGMENT_NAMES.get(segment_label, "unknown")
        return "manual_annotation"

    def _mask_to_qimage(self, *, show_all: bool, label: int) -> QImage:
        """Convert mask to QImage with hotspot colors."""
        # ✅ FIX: Check if _mask_arr exists
        if not hasattr(self, '_mask_arr') or self._mask_arr is None:
            return QImage()
            
        rgb = label_mask_to_hotspot_rgb(self._mask_arr)
        h, w, _ = rgb.shape

        # Always show all hotspots
        alpha = np.full((h, w), 255, np.uint8)
        
        # Set background transparency
        alpha[self._mask_arr == 0] = int(self._bg_alpha * 255)

        # Create RGBA
        rgba = np.dstack([rgb, alpha])
        return QImage(rgba.data, w, h, 4*w, QImage.Format_RGBA8888).copy()

    def _refresh_mask(self):
        """Refresh mask display."""
        # ✅ FIX: Add safety checks
        if not hasattr(self, '_show_all'):
            self._show_all = True
        if not hasattr(self, '_cur_label'):
            self._cur_label = 1
            
        self._mask_img = self._mask_to_qimage(show_all=self._show_all, label=self._cur_label)
        
        # ✅ FIX: Check if _item_mask exists
        if hasattr(self, '_item_mask') and self._item_mask:
            self._item_mask.setPixmap(QPixmap.fromImage(self._mask_img))
        
        if hasattr(self, 'viewport'):
            self.viewport().update()

    def _rebuild_combined(self):
        """Rebuild combined mask from all layers."""
        # ✅ FIX: Add safety checks
        if not hasattr(self, '_layers') or not self._layers or not hasattr(self, '_mask_arr'):
            return
            
        combined = np.zeros_like(self._mask_arr)
        for lbl in range(len(_HOTSPOT_PALLETTE)):
            if lbl in self._layers:
                layer = self._layers[lbl]
                combined[layer == 1] = lbl
        self._mask_arr = combined

    def _apply_brush(self, scene_pos: QPointF):
        """Apply brush with segmentation validation."""
        # ✅ FIX: Add safety checks for required attributes
        if not hasattr(self, '_cur_label') or self._cur_label is None:
            return
        if not hasattr(self, '_layers') or self._cur_label not in self._layers:
            return
            
        x, y = self._get_pixel_coordinates(scene_pos)
        targets = self._get_brush_targets(x, y)

        # Get active layer
        layer = self._layers[self._cur_label]
        
        for px, py in targets:
            # Validation: Only allow editing on non-background segments
            if self._segmentation_arr is not None:
                if 0 <= py < self._segmentation_arr.shape[0] and 0 <= px < self._segmentation_arr.shape[1]:
                    segment_label = self._segmentation_arr[py, px]
                    if segment_label == 0:  # Background segment
                        continue  # Skip painting on background
            
            # ✅ FIX: Check bounds before accessing layer
            if 0 <= py < layer.shape[0] and 0 <= px < layer.shape[1]:
                # Apply brush/eraser
                if hasattr(self, '_eraser') and self._eraser:
                    layer[py, px] = 0
                else:
                    layer[py, px] = 1

        # Rebuild and refresh
        self._rebuild_combined()
        self._refresh_mask()

    def undo(self, label_id: int):
        """Undo for specific layer."""
        # ✅ FIX: Add safety checks
        if not hasattr(self, '_layer_history'):
            return
            
        history = self._layer_history.get(label_id)
        if not history or len(history['undo']) < 2:
            return
        
        current_state = history['undo'].pop()
        history['redo'].append(current_state)
        
        prev_state = history['undo'][-1]
        self._restore_layer_state(label_id, prev_state)

    def redo(self, label_id: int):
        """Redo for specific layer."""
        # ✅ FIX: Add safety checks
        if not hasattr(self, '_layer_history'):
            return
            
        history = self._layer_history.get(label_id)
        if not history or not history['redo']:
            return
        
        state = history['redo'].pop()
        history['undo'].append(state)
        self._restore_layer_state(label_id, state)

    def _restore_layer_state(self, label_id: int, state: np.ndarray):
        """Restore state for specific layer."""
        # ✅ FIX: Add safety checks
        if not hasattr(self, '_layers') or label_id not in self._layers:
            return
            
        self._layers[label_id] = state.copy()
        self._rebuild_combined()
        self._refresh_mask()


class HotspotOpacityPanel(QWidget):
    """Opacity control panel with hotspot-specific sliders."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        
        # Create opacity sliders
        from .base_components import BaseOpacitySlider
        
        self.original_opacity = BaseOpacitySlider("Original Opacity", 50)
        self.mask_opacity = BaseOpacitySlider("Mask Opacity", 100)
        self.bg_opacity = BaseOpacitySlider("BG Opacity", 0)
        self.segmentation_opacity = BaseOpacitySlider("Segmentation Opacity", 30)
        
        layout.addWidget(self.original_opacity)
        layout.addWidget(self.mask_opacity)
        layout.addWidget(self.bg_opacity)
        layout.addWidget(self.segmentation_opacity)

    def connect_to_canvas(self, canvas: HotspotCanvas):
        """Connect opacity sliders to canvas."""
        self.original_opacity.valueChanged.connect(
            lambda v: canvas.set_gray_opacity(v / 100.0)
        )
        self.mask_opacity.valueChanged.connect(
            lambda v: canvas.set_mask_opacity(v / 100.0)
        )
        self.bg_opacity.valueChanged.connect(
            lambda v: canvas.set_bg_opacity(v / 100.0)
        )
        self.segmentation_opacity.valueChanged.connect(
            lambda v: canvas.set_segmentation_opacity(v / 100.0)
        )


class HotspotPalette(QWidget):
    """Hotspot color palette widget."""
    currentRowChanged = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Palette / Layers</b>"))
        
        self.list_palette = QListWidget()
        for rgb, (name, desc) in zip(_HOTSPOT_PALLETTE, _HOTSPOT_LABEL_INFO):
            item = QListWidgetItem()
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            
            # Color box
            color_box = QLabel()
            color_box.setFixedSize(22, 22)
            color_box.setStyleSheet(
                f"background:rgb({rgb[0]},{rgb[1]},{rgb[2]});"
                "border:1px solid #000;"
            )
            
            h_layout.addWidget(color_box)
            h_layout.addWidget(QLabel(name))
            h_layout.addWidget(QLabel(f"({desc})"))
            h_layout.addStretch()
            
            item.setSizeHint(widget.sizeHint())
            self.list_palette.addItem(item)
            self.list_palette.setItemWidget(item, widget)
        
        self.list_palette.setCurrentRow(1)
        self.list_palette.currentRowChanged.connect(self.currentRowChanged.emit)
        
        layout.addWidget(self.list_palette, 1)


class HotspotSaveThread(BaseSaveThread):
    """Save thread for hotspot classification data."""
    
    def __init__(self, canvas: HotspotCanvas, session_path: Path, 
                 patient_id: str, view_short: str, filename_stem: str, 
                 dicom_path: Path, study_date: str, current_session: str = None):
        super().__init__()
        self.canvas = canvas
        self.session_path = session_path  # Base session directory path
        self.patient_id = patient_id
        self.view_short = view_short
        self.filename_stem = filename_stem
        self.dicom_path = dicom_path
        self.study_date = study_date
        self.current_session = current_session
        
        # ✅ FIX: Initialize attributes to None to prevent AttributeError
        self.classification_mask_edited = None
        self.xml_edited = None
        
        # Initialize save paths
        self._initialize_save_paths()

    def _initialize_save_paths(self):
        """Initialize the save paths with date-based directory structure."""
        from datetime import datetime
        
        # Get current date in YYYY-MM-DD format
        current_date = datetime.now().strftime("%Y%m%d")  # YYYYMMDD format to match your structure
        
        # Determine session code to use
        session_code = self._get_session_code()
        if session_code is None:  # User cancelled session selection
            return
        
        # ✅ NEW: Special handling for ALL session
        if self.current_session == "ALL":
            # For ALL session: ALL/PatientID/YYYYMMDD/DoctorCode/YYYYMMDD/filename_timestamp.png
            patient_dir = self.session_path / "ALL" / self.patient_id / current_date
            doctor_date_dir = patient_dir / session_code / current_date
            save_dir = doctor_date_dir
        else:
            # For regular sessions: SessionCode/PatientID/YYYYMMDD/filename_timestamp.png
            patient_dir = self.session_path / session_code / self.patient_id
            save_dir = patient_dir / current_date
        
        # Create directories if they don't exist
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp for filenames (HHMMSS format only)
        timestamp = datetime.now().strftime("%H%M%S")
        
        # Set file paths with timestamp
        base_filename = f"{self.view_short}_hotspot_classification_{timestamp}"
        self.classification_mask_edited = save_dir / f"{base_filename}.png"
        self.xml_edited = save_dir / f"{base_filename}.xml"
        
        print(f"[SAVE] Saving to: {save_dir}")
        print(f"[SAVE] Files: {base_filename}.png, {base_filename}.xml")

    def _get_session_code(self) -> Optional[str]:
        """Get session code, showing dialog if current session is ALL."""
        if self.current_session != "ALL":
            return self.current_session
        
        # Show dialog to select session code
        return self._show_session_selection_dialog()

    def _show_session_selection_dialog(self) -> Optional[str]:
        """Show dialog to select session code from doctor_tags.json."""
        import json
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel
        from PySide6.QtCore import Qt
        
        try:
            # Load doctor tags from config file
            config_path = Path("C:/hotspot/hotspot-analyzer/config/doctor_tags.json")
            if not config_path.exists():
                print(f"Config file not found: {config_path}")
                return "NSY"  # Fallback to default
            
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Filter out "ALL" and get available tags
            available_tags = [tag for tag in config_data.get("doctor_tags", []) if tag.get("code") != "ALL"]
            
            if not available_tags:
                print("No available doctor tags found")
                return "NSY"  # Fallback to default
            
            # Create dialog
            dialog = QDialog()
            dialog.setWindowTitle("Select Session Code")
            dialog.setModal(True)
            dialog.resize(400, 300)
            
            layout = QVBoxLayout(dialog)
            
            # ✅ FIX: Move current_date declaration to module level to avoid repeated definition
            current_date = datetime.now().strftime("%Y%m%d")
            
            if self.current_session == "ALL":
                layout.addWidget(QLabel("Select doctor code for saving to ALL session workspace:"))
                layout.addWidget(QLabel(f"Files will be saved in: ALL/{self.patient_id}/{current_date}/[doctor]/"))
            else:
                layout.addWidget(QLabel("Select a session code to save the classification data:"))
            
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
                
                # Code and name with save path info
                if self.current_session == "ALL":
                    save_path_info = f"→ ALL/{self.patient_id}/{current_date}/{tag.get('code', 'N/A')}/"
                    text_label = QLabel(f"{tag.get('code', 'N/A')} - {tag.get('name', 'Unknown')}\n{save_path_info}")
                    text_label.setStyleSheet("font-size: 11px;")
                else:
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
            print(f"Error showing session selection dialog: {e}")
            return "NSY"  # Fallback to default
        
    def _get_save_path_preview(self, doctor_code: str) -> str:
        """Get a preview of where files will be saved."""
        from datetime import datetime
        current_date = datetime.now().strftime("%Y%m%d")
        
        if self.current_session == "ALL":
            return f"ALL/{self.patient_id}/{current_date}/{doctor_code}/{current_date}/"
        else:
            return f"{doctor_code}/{self.patient_id}/{current_date}/"
        
    def _perform_save(self):
        """Perform hotspot save operations."""
        # Check if paths were initialized successfully
        if not hasattr(self, 'classification_mask_edited') or self.classification_mask_edited is None:
            self.error_occurred.emit("Save cancelled: No session selected")
            return
        
        # ✅ FIX: Add safety check for canvas and its current_mask method
        if not self.canvas or not hasattr(self.canvas, 'current_mask'):
            self.error_occurred.emit("Canvas not properly initialized")
            return
            
        try:
            mask = self.canvas.current_mask()
        except Exception as e:
            self.error_occurred.emit(f"Failed to get current mask: {e}")
            return
        
        self.progress_updated.emit(10, "Preparing classification data...")
        
        # Save classification mask
        from features.spect_viewer.logic.colorizer import label_mask_to_hotspot_rgb
        rgb_img = label_mask_to_hotspot_rgb(mask)
        
        self.progress_updated.emit(30, "Saving classification mask...")
        
        # Save PNG file (directory already created in _initialize_save_paths)
        try:
            Image.fromarray(rgb_img).save(self.classification_mask_edited)
        except Exception as e:
            self.error_occurred.emit(f"Failed to save classification mask: {e}")
            return
        
        self.progress_updated.emit(50, "Generating XML annotations...")
        
        # Generate and save XML
        xml_result = self._save_xml_with_backup(mask)
        
        self.progress_updated.emit(80, "Running quantification...")
        
        # Trigger quantification
        quant_success = self._trigger_quantification()
        
        self.progress_updated.emit(100, "Save completed!")
        
        # Build success message
        success_msg = (
            f"Classification edits saved successfully!\n\n"
            f"Files saved to: {self.classification_mask_edited.parent}\n"
            f"• {self.classification_mask_edited.name}\n"
            f"• {self.xml_edited.name}\n\n"
        )
        
        if xml_result:
            success_msg += f"XML annotations: {xml_result['bbox_stats']}\n"
        
        if quant_success:
            success_msg += "\n✅ Quantification pipeline completed successfully"
        else:
            success_msg += "\n⚠️ Quantification pipeline failed (check logs for details)"

        # ✅ FIX: Emit success signal with message
        self.finished.emit(success_msg)

    def _save_xml_with_backup(self, mask: np.ndarray) -> Optional[Dict]:
        """Save XML annotations with bounding box generation."""
        try:
            from .xml_utils import mask_to_bounding_boxes, create_xml_from_bboxes, save_xml_file
            
            # Generate bounding boxes
            segmentation_arr = getattr(self.canvas, '_segmentation_arr', None)
            bounding_boxes = mask_to_bounding_boxes(mask, segmentation_arr, min_area=10)
            
            # Get image dimensions
            img_height, img_width = mask.shape
            
            # Generate XML content
            xml_content = create_xml_from_bboxes(
                bounding_boxes, img_width, img_height, 
                self.patient_id, self.view_short, self.filename_stem
            )
            
            # Save XML file (path already set in _initialize_save_paths)
            save_xml_file(xml_content, self.xml_edited)
            
            # Prepare result statistics
            bbox_count = len(bounding_boxes)
            abnormal_count = len([b for b in bounding_boxes if b['label'] == 'abnormal'])
            normal_count = len([b for b in bounding_boxes if b['label'] == 'normal'])
            
            if bbox_count == 0:
                bbox_stats = "No annotations (empty but valid for quantification)"
            else:
                bbox_stats = f"{bbox_count} annotations ({abnormal_count} abnormal, {normal_count} normal)"
            
            return {
                'bbox_stats': bbox_stats
            }
            
        except Exception as e:
            print(f"Failed to save XML: {e}")
            return None

    def _trigger_quantification(self) -> bool:
        """Trigger quantification pipeline."""
        try:
            from features.spect_viewer.logic.processing_wrapper import (
                run_quantification_for_patient
            )
            
            return run_quantification_for_patient(
                self.dicom_path,
                self.patient_id,
                self.study_date
            )
            
        except Exception as e:
            print(f"Quantification failed: {e}")
            return False

    def get_save_info(self) -> Dict[str, Path]:
        """Get information about save paths for external use."""
        # ✅ FIX: Add safety checks for None values
        if self.classification_mask_edited is None or self.xml_edited is None:
            return {}
            
        return {
            'png_path': self.classification_mask_edited,
            'xml_path': self.xml_edited,
            'date_dir': self.classification_mask_edited.parent
        }