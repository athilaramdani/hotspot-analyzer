# features/spect_viewer/gui/editor_components/segmentation_components.py
"""
Segmentation-specific components that inherit from base components.
Focuses on anatomical segmentation editing with multi-layer support.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import datetime as datetime
from PIL import Image

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QWidget, QCheckBox, QGraphicsPixmapItem
)

from .base_components import BaseCanvas, BaseEditorDialog, BaseSaveThread
from features.spect_viewer.logic.colorizer import label_mask_to_rgb, _PALETTE

# Segmentation label information
_SEGMENTATION_LABEL_INFO: List[Tuple[str, str]] = [
    ("Background", "kosong"),
    ("Skull", "Tulang tengkorak"),
    ("Cervical", "Vertebra servikal"),
    ("Thoracic", "Vertebra torakal"),
    ("Rib", "Tulang rusuk"),
    ("Sternum", "Tulang dada"),
    ("Clavicle", "Klavikula"),
    ("Scapula", "Belikat"),
    ("Humerus", "Lengan atas"),
    ("Lumbar", "Vertebra lumbal"),
    ("Sacrum", "Sakrum"),
    ("Pelvis", "Pelvis"),
    ("Femur", "Paha"),
]


class SegmentationCanvas(BaseCanvas):
    """Canvas with segmentation-specific functionality and layer management."""

    def __init__(self, orig: np.ndarray, mask: np.ndarray, parent=None):
        # Initialize segmentation-specific attributes BEFORE calling parent
        self._layers = {}
        self._bg_alpha = 0.0  # Background opacity
        
        super().__init__(orig, mask, parent)
        
        # Now populate the layers after parent initialization is complete
        self._layers = {lbl: (self._mask_arr == lbl).astype(np.uint8)
                        for lbl in range(len(_PALETTE))}
        
        # Create mask display
        self._mask_img = self._mask_to_qimage(show_all=False, label=1)
        self._item_mask = QGraphicsPixmapItem(QPixmap.fromImage(self._mask_img))
        self._scene.addItem(self._item_mask)

    def _init_history(self):
        """Initialize history for segmentation layers."""
        for label_id in range(len(_PALETTE)):
            self._layer_history[label_id] = {'undo': [], 'redo': []}
        # Only save states if layers are properly initialized
        if hasattr(self, '_layers') and self._layers:
            self._save_all_states()

    def _save_all_states(self):
        """Save initial state for all layers."""
        for label_id in range(len(_PALETTE)):
            self._save_layer_state(label_id)

    def _save_layer_state(self, label_id: int):
        """Save state for specific layer."""
        history = self._layer_history[label_id]
        state = self._layers[label_id].copy()
        
        if len(history['undo']) >= self._max_history:
            history['undo'].pop(0)
        
        history['undo'].append(state)
        history['redo'].clear()

    def _save_current_state(self):
        """Save current state for active layer."""
        self._save_layer_state(self._cur_label)

    def set_bg_opacity(self, alpha: float):
        """Set background opacity."""
        self._bg_alpha = alpha
        self._refresh_mask()

    def _mask_to_qimage(self, *, show_all: bool, label: int) -> QImage:
        """Convert mask to QImage with segmentation colors."""
        rgb = label_mask_to_rgb(self._mask_arr)
        h, w, _ = rgb.shape

        if show_all:
            # Show all segments
            alpha = np.full((h, w), 255, np.uint8)
            alpha[self._mask_arr == 0] = int(self._bg_alpha * 255)
        else:
            # Show only selected layer
            selected_layer = (self._layers[label] == 1)
            rgb[selected_layer] = np.array(_PALETTE[label], dtype=np.uint8)
            alpha = np.zeros((h, w), np.uint8)
            alpha[selected_layer] = 255

        # Create RGBA
        rgba = np.dstack([rgb, alpha])
        return QImage(rgba.data, w, h, 4*w, QImage.Format_RGBA8888).copy()

    def _refresh_mask(self):
        """Refresh mask display."""
        self._mask_img = self._mask_to_qimage(show_all=self._show_all, label=self._cur_label)
        self._item_mask.setPixmap(QPixmap.fromImage(self._mask_img))
        self.viewport().update()

    def _rebuild_combined(self):
        """Rebuild combined mask from all layers."""
        combined = np.zeros_like(self._mask_arr)
        for lbl in range(len(_PALETTE)):
            layer = self._layers[lbl]
            combined[layer == 1] = lbl
        self._mask_arr = combined

    def _apply_brush(self, scene_pos: QPointF):
        """Apply brush for segmentation editing."""
        x, y = self._get_pixel_coordinates(scene_pos)
        targets = self._get_brush_targets(x, y)

        # Get active layer
        layer = self._layers[self._cur_label]
        
        for px, py in targets:
            if self._eraser:
                layer[py, px] = 0
            else:
                layer[py, px] = 1

        # Rebuild and refresh
        self._rebuild_combined()
        self._refresh_mask()

    def undo(self, label_id: int):
        """Undo for specific layer."""
        history = self._layer_history.get(label_id)
        if not history or len(history['undo']) < 2:
            return
        
        current_state = history['undo'].pop()
        history['redo'].append(current_state)
        
        prev_state = history['undo'][-1]
        self._restore_layer_state(label_id, prev_state)

    def redo(self, label_id: int):
        """Redo for specific layer."""
        history = self._layer_history.get(label_id)
        if not history or not history['redo']:
            return
        
        state = history['redo'].pop()
        history['undo'].append(state)
        self._restore_layer_state(label_id, state)

    def _restore_layer_state(self, label_id: int, state: np.ndarray):
        """Restore state for specific layer."""
        self._layers[label_id] = state.copy()
        self._rebuild_combined()
        self._refresh_mask()


class SegmentationOpacityPanel(QWidget):
    """Opacity control panel for segmentation editing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        
        # Create opacity sliders (no segmentation layer for this editor)
        from .base_components import BaseOpacitySlider
        
        self.original_opacity = BaseOpacitySlider("Original Opacity", 50)
        self.mask_opacity = BaseOpacitySlider("Mask Opacity", 100)
        self.bg_opacity = BaseOpacitySlider("BG Opacity", 0)
        
        layout.addWidget(self.original_opacity)
        layout.addWidget(self.mask_opacity)
        layout.addWidget(self.bg_opacity)

    def connect_to_canvas(self, canvas: SegmentationCanvas):
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


class SegmentationPalette(QWidget):
    """Segmentation color palette widget for anatomical structures."""
    currentRowChanged = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Palette / Layers</b>"))
        
        self.list_palette = QListWidget()
        for rgb, (name, desc) in zip(_PALETTE, _SEGMENTATION_LABEL_INFO):
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


class SegmentationSaveThread(BaseSaveThread):
    """Save thread for segmentation data."""
    
    def __init__(self, canvas: SegmentationCanvas, session_path: Path, 
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
        
        # Initialize attributes to None to prevent AttributeError
        self.segmentation_mask_edited = None
        self.segmentation_colored_edited = None
        
        # Initialize save paths
        self._initialize_save_paths()

    def _initialize_save_paths(self):
        """Initialize the save paths with proper session handling."""
        from datetime import datetime
        
        # Get current edit date in YYYYMMDD format
        edit_date = datetime.now().strftime("%Y%m%d")
        
        # Determine session code to use
        session_code = self._get_session_code()
        if session_code is None:  # User cancelled session selection
            return
        
        # Check if this is the special ALL session case
        if self.current_session == "ALL":
            # Special ALL workspace structure: ALL/PatientID/StudyDate/DoctorCode/EditDate/
            patient_dir = self.session_path / "ALL" / self.patient_id / self.study_date
            doctor_dir = patient_dir / session_code
            save_dir = doctor_dir / edit_date
            print(f"[SAVE] ALL session - saving to: ALL/{self.patient_id}/{self.study_date}/{session_code}/{edit_date}/")
        else:
            # Regular session structure: SessionCode/PatientID/StudyDate/EditDate/
            patient_dir = self.session_path / self.current_session / self.patient_id / self.study_date
            save_dir = patient_dir / edit_date
            print(f"[SAVE] Regular session - saving to: {self.current_session}/{self.patient_id}/{self.study_date}/{edit_date}/")
        
        # Create directories if they don't exist
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp for filenames (HHMMSS format only)
        timestamp = datetime.now().strftime("%H%M%S")
        
        # Set file paths with timestamp
        base_filename_mask = f"{self.view_short}_mask_{timestamp}"
        base_filename_segm = f"{self.view_short}_segm_{timestamp}"
        self.segmentation_mask_edited = save_dir / f"{base_filename_mask}.png"
        self.segmentation_colored_edited = save_dir / f"{base_filename_segm}.png"
        
        print(f"[SAVE] Files: {base_filename_mask}.png, {base_filename_segm}.png")

    def _get_session_code(self) -> Optional[str]:
        """Get session code, showing dialog only if current session is ALL."""
        if self.current_session != "ALL":
            return self.current_session
        
        # Show dialog to select doctor code only for ALL session
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
            
            if self.current_session == "ALL":
                layout.addWidget(QLabel("Select doctor code for saving edited segmentation to ALL workspace:"))
                edit_date = datetime.now().strftime("%Y%m%d")
                layout.addWidget(QLabel(f"Files will be saved in: ALL/{self.patient_id}/{self.study_date}/[doctor]/{edit_date}/"))
            else:
                layout.addWidget(QLabel("Select session code to save the segmentation data:"))
            
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
                    edit_date = datetime.now().strftime("%Y%m%d")
                    save_path_info = f"→ ALL/{self.patient_id}/{self.study_date}/{tag.get('code', 'N/A')}/{edit_date}/"
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
    def _perform_save(self):
        """Perform segmentation save operations."""
        try:
            # Check if paths were initialized successfully
            if not hasattr(self, 'segmentation_mask_edited') or self.segmentation_mask_edited is None:
                self.save_completed.emit(False, "Save cancelled: No session selected")
                return
            
            # Add safety check for canvas and its current_mask method
            if not self.canvas or not hasattr(self.canvas, 'current_mask'):
                self.save_completed.emit(False, "Canvas not properly initialized")
                return
                
            try:
                mask = self.canvas.current_mask()
            except Exception as e:
                self.save_completed.emit(False, f"Failed to get current mask: {e}")
                return
            
            self.progress_updated.emit(10, "Preparing segmentation data...")
            
            # Prepare images
            bin_img = (mask > 0).astype(np.uint8) * 255
            rgb_img = label_mask_to_rgb(mask)
            
            self.progress_updated.emit(30, "Saving mask files...")
            
            # Save PNG files (directory already created in _initialize_save_paths)
            try:
                Image.fromarray(bin_img, mode="L").save(self.segmentation_mask_edited)
                Image.fromarray(rgb_img).save(self.segmentation_colored_edited)
            except Exception as e:
                self.save_completed.emit(False, f"Failed to save segmentation files: {e}")
                return
            
            self.progress_updated.emit(80, "Running quantification...")
            
            # Trigger quantification
            quant_success = self._trigger_quantification()
            
            self.progress_updated.emit(100, "Save completed!")
            
            # Build success message
            success_msg = (
                f"Segmentation files saved successfully!\n\n"
                f"Location: {self.segmentation_mask_edited.parent}\n"
                f"Files:\n"
                f"• {self.segmentation_mask_edited.name}\n"
                f"• {self.segmentation_colored_edited.name}\n\n"
            )
            
            if quant_success:
                success_msg += "\n✅ Quantification pipeline completed successfully"
            else:
                success_msg += "\n⚠️ Quantification pipeline failed (check logs for details)"
            
            # Emit success signal
            self.save_completed.emit(True, success_msg)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f"Save failed: {str(e)}"
            self.save_completed.emit(False, error_msg)

    # def _upload_to_cloud(self) -> bool:
    #     """Upload edited files to cloud storage."""
    #     try:
    #         from core.config.cloud_storage import upload_patient_file
            
    #         file_path = self.seg_files_edited['png_colored_edited']
            
    #         if file_path.exists():
    #             return upload_patient_file(
    #                 file_path, 
    #                 self.session_code, 
    #                 self.patient_id, 
    #                 is_edited=True
    #             )
    #         return False
            
    #     except Exception as e:
    #         print(f"Cloud upload failed: {e}")
    #         return False

    def _trigger_quantification(self) -> bool:
        """Trigger quantification after segmentation save."""
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
        # Add safety checks for None values
        if self.segmentation_mask_edited is None or self.segmentation_colored_edited is None:
            return {}
            
        return {
            'mask_path': self.segmentation_mask_edited,
            'colored_path': self.segmentation_colored_edited,
            'date_dir': self.segmentation_mask_edited.parent
        }


class SegmentationToolPanel(QWidget):
    """Tool selection panel for segmentation editing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        
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
        layout.addLayout(tool_row)
        
        # Undo/Redo buttons
        undo_row = QHBoxLayout()
        self.btn_undo = QPushButton("Undo")
        self.btn_redo = QPushButton("Redo")
        undo_row.addWidget(self.btn_undo)
        undo_row.addWidget(self.btn_redo)
        layout.addLayout(undo_row)
        
        # Brush size controls
        from .base_components import BaseOpacitySlider
        
        layout.addWidget(QLabel("Brush Size (pixels)"))
        self.brush_size_slider = BaseOpacitySlider("", 1)
        self.brush_size_slider.slider.setRange(1, 15)
        self.brush_size_slider.setValue(1)
        layout.addWidget(self.brush_size_slider)
        
        # Zoom controls
        layout.addWidget(QLabel("Zoom"))
        self.zoom_slider = BaseOpacitySlider("", 10)
        self.zoom_slider.slider.setRange(1, 1000)
        self.zoom_slider.setValue(10)
        layout.addWidget(self.zoom_slider)

    def connect_to_canvas(self, canvas: SegmentationCanvas):
        """Connect tool controls to canvas."""
        # Tool selection
        self.btn_brush.clicked.connect(lambda: self._select_brush(canvas))
        self.btn_eraser.clicked.connect(lambda: self._select_eraser(canvas))
        self.btn_showall.toggled.connect(canvas.toggle_show_all)
        
        # Size and zoom
        self.brush_size_slider.valueChanged.connect(canvas.set_brush_size)
        self.zoom_slider.valueChanged.connect(
            lambda v: canvas.set_zoom(v / 10.0)
        )

    def _select_brush(self, canvas: SegmentationCanvas):
        """Select brush tool."""
        self.btn_eraser.setChecked(False)
        # Canvas will be updated via palette selection

    def _select_eraser(self, canvas: SegmentationCanvas):
        """Select eraser tool."""
        self.btn_brush.setChecked(False)
        canvas.set_eraser()

    def connect_undo_redo(self, undo_func, redo_func):
        """Connect undo/redo functions."""
        self.btn_undo.clicked.connect(undo_func)
        self.btn_redo.clicked.connect(redo_func)