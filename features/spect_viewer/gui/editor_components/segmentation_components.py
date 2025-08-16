# features/spect_viewer/gui/editor_components/segmentation_components.py
"""
Segmentation-specific components that inherit from base components.
Focuses on anatomical segmentation editing with multi-layer support.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
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
        super().__init__(orig, mask, parent)
        
        # Segmentation-specific layers (one per anatomical structure)
        self._layers = {lbl: (self._mask_arr == lbl).astype(np.uint8)
                        for lbl in range(len(_PALETTE))}
        self._bg_alpha = 0.0  # Background opacity
        
        # Create mask display
        self._mask_img = self._mask_to_qimage(show_all=False, label=1)
        self._item_mask = QGraphicsPixmapItem(QPixmap.fromImage(self._mask_img))
        self._scene.addItem(self._item_mask)
        
        self._init_history()

    def _init_history(self):
        """Initialize history for segmentation layers."""
        for label_id in range(len(_PALETTE)):
            self._layer_history[label_id] = {'undo': [], 'redo': []}
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
    
    def __init__(self, canvas: SegmentationCanvas, seg_files_edited: Dict[str, Path],
                 patient_id: str, session_code: str, study_date: str):
        super().__init__()
        self.canvas = canvas
        self.seg_files_edited = seg_files_edited
        self.patient_id = patient_id
        self.session_code = session_code
        self.study_date = study_date

    def _perform_save(self):
        """Perform segmentation save operations."""
        mask = self.canvas.current_mask()
        
        self.progress_updated.emit(10, "Preparing images...")
        
        # Prepare images
        bin_img = (mask > 0).astype(np.uint8) * 255
        rgb_img = label_mask_to_rgb(mask)
        
        self.progress_updated.emit(30, "Creating directories...")
        
        # Create parent directories
        self.seg_files_edited['png_mask_edited'].parent.mkdir(parents=True, exist_ok=True)
        
        self.progress_updated.emit(50, "Saving PNG mask...")
        
        # Save PNG files
        Image.fromarray(bin_img, mode="L").save(self.seg_files_edited['png_mask_edited'])
        
        self.progress_updated.emit(70, "Saving PNG colored...")
        
        Image.fromarray(rgb_img).save(self.seg_files_edited['png_colored_edited'])
        
        self.progress_updated.emit(85, "Uploading to cloud...")
        
        # Upload to cloud
        cloud_success = self._upload_to_cloud()
        
        self.progress_updated.emit(90, "Running quantification...")
        
        # Trigger quantification
        quant_success = self._trigger_quantification()
        
        self.progress_updated.emit(100, "Save completed!")
        
        # Build success message
        success_msg = (
            f"Edited segmentation saved successfully!\n\n"
            f"PNG files saved with study date naming:\n"
            f"• {self.seg_files_edited['png_mask_edited'].name}\n"
            f"• {self.seg_files_edited['png_colored_edited'].name}\n\n"
            f"Study Date: {self.study_date}\n"
            f"Patient ID: {self.patient_id}\n"
            f"Session: {self.session_code}"
        )
        
        if quant_success:
            success_msg += "\n\n✅ Quantification pipeline completed successfully"
        else:
            success_msg += "\n\n⚠️ Quantification pipeline failed (segmentation saved)"

        if cloud_success:
            success_msg += "\n\n✅ Colored PNG synced to cloud storage"
        else:
            success_msg += "\n\n⚠️ Cloud sync failed (files saved locally)"

    def _upload_to_cloud(self) -> bool:
        """Upload edited files to cloud storage."""
        try:
            from core.config.cloud_storage import upload_patient_file
            
            file_path = self.seg_files_edited['png_colored_edited']
            
            if file_path.exists():
                return upload_patient_file(
                    file_path, 
                    self.session_code, 
                    self.patient_id, 
                    is_edited=True
                )
            return False
            
        except Exception as e:
            print(f"Cloud upload failed: {e}")
            return False

    def _trigger_quantification(self) -> bool:
        """Trigger quantification after segmentation save."""
        try:
            from features.spect_viewer.logic.processing_wrapper import (
                run_quantification_for_patient
            )
            
            # Find DICOM file in patient folder
            patient_folder = self.seg_files_edited['png_mask_edited'].parent
            dicom_path = None
            
            for possible_dicom in patient_folder.glob("*.dcm"):
                if not any(skip in possible_dicom.name.lower() 
                          for skip in ['mask', 'colored', 'edited']):
                    dicom_path = possible_dicom
                    break
            
            if not dicom_path or not dicom_path.exists():
                print("No DICOM file found, skipping quantification")
                return False
            
            # Run quantification with updated segmentation
            return run_quantification_for_patient(
                dicom_path,
                self.patient_id,
                self.study_date
            )
            
        except Exception as e:
            print(f"Quantification failed: {e}")
            return False


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