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
from core.config.paths import generate_edit_date, generate_edit_timestamp
import logging
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
    ("Malignant", "Terdeteksi anomali"),
    ("Benign", "Tidak terdeteksi anomali")
]
#   ADD THIS after _HOTSPOT_LABEL_INFO:
# Mapping for XML output (keeps compatibility)
_XML_LABEL_MAPPING = {
    "Background": "background",
    "Malignant": "abnormal",  #   UI "Malignant" -> XML "abnormal"
    "Benign": "normal"        #   UI "Benign" -> XML "normal"
}


class HotspotCanvas(BaseCanvas):
    """Canvas with hotspot-specific functionality including segmentation validation."""

    def __init__(self, orig: np.ndarray, mask: np.ndarray, parent=None):
        # Initialize required attributes before parent call
        self._bg_alpha = 0.0
        self._segmentation_arr = None
        self._item_segmentation = None
        
        # Call parent constructor first
        super().__init__(orig, mask, parent)
        
        # Initialize layers AFTER parent constructor
        self._layers = {
            0: np.zeros_like(mask, dtype=np.uint8),  # Background
            1: (mask == 1).astype(np.uint8),         # Abnormal
            2: (mask == 2).astype(np.uint8)          # Normal
        }

        # This ensures Undo stack has the base state [State0]
        self._save_all_states()
    
        # Initialize brush tracking
        self._last_brush_pos = None

        
        # Set the hotspot-specific palette
        self._palette = _HOTSPOT_PALLETTE
        
        # Create mask display
        self._mask_img = self._mask_to_qimage(show_all=True, label=1)
        self._item_mask = QGraphicsPixmapItem(QPixmap.fromImage(self._mask_img))
        self._item_mask.setZValue(2)  # Ensure hotspots are above segmentation (Z=1)
        self._scene.addItem(self._item_mask)

    def _init_history(self):
        """Initialize history for hotspot layers."""
        #   FIX: Initialize _layer_history if it doesn't exist
        if not hasattr(self, '_layer_history'):
            self._layer_history = {}
            
        for label_id in range(len(_HOTSPOT_PALLETTE)):
            self._layer_history[label_id] = {'undo': [], 'redo': []}
        self._save_all_states()

    def _save_all_states(self):
        """Save initial state for all layers."""
        #   FIX: Ensure _layers exists before trying to save states
        if not hasattr(self, '_layers') or not self._layers:
            return
            
        for label_id in range(len(_HOTSPOT_PALLETTE)):
            if label_id in self._layers:
                self._save_layer_state(label_id)

    def _save_layer_state(self, label_id: int):
        """Save state for specific label - adapted for hotspot canvas."""
        #   FIX: Ensure _layer_history exists
        if not hasattr(self, '_layer_history'):
            self._layer_history = {}
        
        #   FIX: Ensure the label_id exists in _layer_history
        if label_id not in self._layer_history:
            self._layer_history[label_id] = {'undo': [], 'redo': []}
        
        history = self._layer_history[label_id]
        
        # Check if this canvas uses layers
        if hasattr(self, '_layers') and label_id in self._layers:
            # Use layer-based saving
            state = self._layers[label_id].copy()
        else:
            # Fallback to mask-based saving
            state = self._mask_arr.copy()
        
        if len(history['undo']) >= self._max_history:
            history['undo'].pop(0)
        
        history['undo'].append(state)
        history['redo'].clear()

    def _save_current_state(self):
        """Save current state for active layer."""
        #   FIX: Check if _cur_label is valid
        if hasattr(self, '_cur_label') and self._cur_label is not None:
            self._save_layer_state(self._cur_label)

    def set_brush_cursor_visible(self, visible: bool):
        """Set brush cursor visibility."""
        self._brush_cursor_visible = getattr(self, '_brush_cursor_visible', True)
        if visible != self._brush_cursor_visible:
            self._brush_cursor_visible = visible
            # Update cursor if it exists
            if hasattr(self, '_update_cursor'):
                self._update_cursor()

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
                self._item_segmentation.setZValue(1)  # Ensure segmentation is below hotspots (Z=2)
                
                #   FIX: Check if _scene exists before adding item
                if hasattr(self, '_scene') and self._scene:
                    self._scene.addItem(self._item_segmentation)
                
                return True
            return False
        except Exception as e:
            logging.info(f"Failed to load segmentation: {e}")
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

    # def set_bg_opacity(self, alpha: float):
    #     """Set background opacity."""
    #     self._bg_alpha = alpha
    #     self._refresh_mask()

    def get_segment_at_position(self, x: int, y: int) -> str:
        """Get segment name at given position."""
        if self._segmentation_arr is not None:
            if 0 <= x < self._segmentation_arr.shape[1] and 0 <= y < self._segmentation_arr.shape[0]:
                segment_label = self._segmentation_arr[y, x]
                return _SEGMENT_NAMES.get(segment_label, "unknown")
        return "manual_annotation"

    def _mask_to_qimage(self, *, show_all: bool, label: int) -> QImage:
        """Convert mask to QImage with hotspot colors."""
        #   FIX: Check if _mask_arr exists
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
        #   FIX: Add safety checks
        if not hasattr(self, '_show_all'):
            self._show_all = True
        if not hasattr(self, '_cur_label'):
            self._cur_label = 1
            
        self._mask_img = self._mask_to_qimage(show_all=self._show_all, label=self._cur_label)
        
        #   FIX: Check if _item_mask exists
        if hasattr(self, '_item_mask') and self._item_mask:
            self._item_mask.setPixmap(QPixmap.fromImage(self._mask_img))
        
        if hasattr(self, 'viewport'):
            self.viewport().update()

    def _rebuild_combined(self):
        """Rebuild combined mask from all layers."""
        #   FIX: Add safety checks
        if not hasattr(self, '_layers') or not self._layers or not hasattr(self, '_mask_arr'):
            return
            
        combined = np.zeros_like(self._mask_arr)
        for lbl in range(len(_HOTSPOT_PALLETTE)):
            if lbl in self._layers:
                layer = self._layers[lbl]
                combined[layer == 1] = lbl
        self._mask_arr = combined

    def _apply_brush(self, scene_pos: QPointF):
        """Apply brush (unrestricted)."""
        if not hasattr(self, '_cur_label') or self._cur_label is None:
            return
        if not hasattr(self, '_layers') or self._cur_label not in self._layers:
            return

        # Handle drawing state saving logic (copied from SegmentationCanvas)
        # Handle drawing state saving logic
        if not hasattr(self, '_drawing') or not self._drawing:
            # Start of drawing - just set flag, save happens on release
            self._drawing = True
            
        x, y = self._get_pixel_coordinates(scene_pos)
        targets = self._get_brush_targets(x, y)

        layer = self._layers[self._cur_label]
        
<<<<<<< Updated upstream
        for px, py in targets:
            # Check if erasing
            is_erasing = hasattr(self, '_eraser') and self._eraser
            
            # Validation: Only restrict PAINTING to non-background segments
            # ERASING is allowed everywhere/outside segmentation
            if not is_erasing and self._segmentation_arr is not None:
                if 0 <= py < self._segmentation_arr.shape[0] and 0 <= px < self._segmentation_arr.shape[1]:
                    segment_label = self._segmentation_arr[py, px]
                    if segment_label == 0:  # Background segment
                        continue  # Skip painting on background
            
            #   FIX: Check bounds before accessing layer
            if 0 <= py < layer.shape[0] and 0 <= px < layer.shape[1]:
                # Apply brush/eraser
                if hasattr(self, '_eraser') and self._eraser:
                    layer[py, px] = 0
                else:
                    layer[py, px] = 1
=======
        # New value: 0 if eraser, 1 if painting (binary mask per layer)
        new_val = 0 if (hasattr(self, '_eraser') and self._eraser) else 1
        
        changes_made = False

        for px, py in targets:
            if 0 <= py < layer.shape[0] and 0 <= px < layer.shape[1]:
                if layer[py, px] != new_val:
                    layer[py, px] = new_val
                    changes_made = True

        if changes_made:
            self._rebuild_combined()
            self._refresh_mask()
>>>>>>> Stashed changes


    def undo(self, label_id: int):
        """Undo for specific layer."""
        #   FIX: Add safety checks
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
        #   FIX: Add safety checks
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
        #   FIX: Add safety checks
        if not hasattr(self, '_layers') or label_id not in self._layers:
            return
            
        self._layers[label_id] = state.copy()
        self._rebuild_combined()
        self._refresh_mask()

    def _apply_brush_line(self, start_pos: QPointF, end_pos: QPointF):
        """Apply brush along a line for smooth drawing."""
        start_x, start_y = self._get_pixel_coordinates(start_pos)
        end_x, end_y = self._get_pixel_coordinates(end_pos)

        distance = max(abs(end_x - start_x), abs(end_y - start_y))

        if distance == 0:
            self._apply_brush(end_pos)
            return

        if not hasattr(self, '_cur_label') or self._cur_label not in self._layers:
            return

        layer = self._layers[self._cur_label]
        new_val = 0 if (hasattr(self, '_eraser') and self._eraser) else 1
        overall_changes_made = False

        num_points = max(distance, self._brush_radius * 2, 3)

        for i in range(num_points + 1):
            t = i / num_points if num_points > 0 else 0
            
            # Linear interpolation
            interp_x = start_x + t * (end_x - start_x)
            interp_y = start_y + t * (end_y - start_y)
            
            x, y = int(interp_x + 0.5), int(interp_y + 0.5)
            targets = self._get_brush_targets(x, y)

            for px, py in targets:
                if 0 <= py < layer.shape[0] and 0 <= px < layer.shape[1]:
                    if layer[py, px] != new_val:
                        layer[py, px] = new_val
                        overall_changes_made = True

        if overall_changes_made:
            self._rebuild_combined()
            self._refresh_mask()

    def mousePressEvent(self, ev):
        """Handle mouse press."""
        if ev.button() == Qt.LeftButton and not self._pan_mode:
            # FIX: Reset drawing state and start new operation
            self._drawing = False  # Reset first
            scene_pos = self.mapToScene(ev.position().toPoint())
            self._last_brush_pos = scene_pos
            self._apply_brush(scene_pos)
            ev.accept()
        elif ev.button() == Qt.MiddleButton:
            self._pan_mode = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(QCursor(Qt.OpenHandCursor))
            fake_press = ev
            super().mousePressEvent(fake_press)
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        """Handle mouse move with smooth line interpolation."""
        scene_pos = self.mapToScene(ev.position().toPoint())
        self._mouse_pos = scene_pos

        if self._drawing and (ev.buttons() & Qt.LeftButton) and not self._pan_mode:
            if self._last_brush_pos is not None:
                self._apply_brush_line(self._last_brush_pos, scene_pos)
            else:
                self._apply_brush(scene_pos)
            
            self._last_brush_pos = scene_pos
            ev.accept()
        elif self._pan_mode:
            super().mouseMoveEvent(ev)
        else:
            self.viewport().update()
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        """Handle mouse release."""
        if ev.button() == Qt.LeftButton and self._drawing:
            # FIX: Save state on RELEASE to capture the stroke result
            self._save_current_state()
            self._drawing = False
            self._last_brush_pos = None
            ev.accept()
        elif ev.button() == Qt.MiddleButton and self._pan_mode:
            self._pan_mode = False
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(QCursor(Qt.CrossCursor))
            super().mouseReleaseEvent(ev)
        else:
            super().mouseReleaseEvent(ev)



class HotspotOpacityPanel(QWidget):
    """Opacity control panel with hotspot-specific sliders."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        
        # Create opacity sliders
        from .base_components import BaseOpacitySlider
        
        # self.original_opacity = BaseOpacitySlider("Original Opacity", 50)
        self.mask_opacity = BaseOpacitySlider("Mask Opacity", 100)
        # self.bg_opacity = BaseOpacitySlider("BG Opacity", 0)
        self.segmentation_opacity = BaseOpacitySlider("Segmentation Opacity", 30)
        
        # layout.addWidget(self.original_opacity)
        layout.addWidget(self.mask_opacity)
        # layout.addWidget(self.bg_opacity)
        layout.addWidget(self.segmentation_opacity)

    def connect_to_canvas(self, canvas: HotspotCanvas):
        """Connect opacity sliders to canvas."""
        # self.original_opacity.valueChanged.connect(
        #     lambda v: canvas.set_gray_opacity(v / 100.0)
        # )
        if hasattr(canvas, 'set_gray_opacity'):
            canvas.set_gray_opacity(1.0)
        self.mask_opacity.valueChanged.connect(
            lambda v: canvas.set_mask_opacity(v / 100.0)
        )
        # self.bg_opacity.valueChanged.connect(
        #     lambda v: canvas.set_bg_opacity(v / 100.0)
        # )
        self.segmentation_opacity.valueChanged.connect(
            lambda v: canvas.set_segmentation_opacity(v / 100.0)
        )


class HotspotPalette(QWidget):
    """Hotspot color palette widget."""
    currentRowChanged = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Classification Palette</b>"))
        
        self.list_palette = QListWidget()
        
        #   BEFORE: Tidak ada setMinimumHeight
        #   AFTER: Set minimum height untuk palette lebih panjang
        self.list_palette.setMinimumHeight(200)  # Tambah tinggi palette
        
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

            name_label = QLabel(name)
            name_label.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    font-size: 12px;
                    color: #333;
                }
            """)
            
            desc_label = QLabel(f"({desc})")
            desc_label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    color: #666;
                    font-style: italic;
                }
            """)
            
            h_layout.addWidget(color_box)
            h_layout.addWidget(QLabel(name))
            h_layout.addWidget(QLabel(f"({desc})"))
            h_layout.addStretch()
            
            item.setSizeHint(widget.sizeHint())
            self.list_palette.addItem(item)
            self.list_palette.setItemWidget(item, widget)
        
        self.list_palette.setCurrentRow(1)
        self.list_palette.currentRowChanged.connect(self.currentRowChanged.emit)
        
        layout.addWidget(self.list_palette, 1)  # Stretch factor 1 untuk mengisi ruang
        
        # Instruction label tetap di bawah
        instruction_label = QLabel(
            "<i>Click to select classification type.<br/>"
            "Paint regions as Benign or Malignant.</i>"
        )
        instruction_label.setStyleSheet("""
            QLabel {
                font-size: 9px;
                color: #888;
                padding: 4px;
                background: #f9f9f9;
                border-radius: 3px;
            }
        """)
        instruction_label.setWordWrap(True)
        layout.addWidget(instruction_label)

    
    def get_current_display_label(self) -> str:
        """Get the current display label (Benign/Malignant)."""
        current_row = self.list_palette.currentRow()
        if 0 <= current_row < len(_HOTSPOT_LABEL_INFO):
            return _HOTSPOT_LABEL_INFO[current_row][0]
        return "Background"

    def get_current_xml_label(self) -> str:
        """Get the XML-compatible label (normal/abnormal) for saving."""
        display_label = self.get_current_display_label()
        return _XML_LABEL_MAPPING.get(display_label, "background")



class HotspotSaveThread(BaseSaveThread):
    """Save thread for hotspot classification data."""
    progress_updated = Signal(int, str)      # (progress_percentage, message)
    error_occurred = Signal(str)             # (error_message)
    save_completed = Signal(str) 
    
    def __init__(self, canvas: HotspotCanvas, session_path: Path, 
                 patient_id: str, view_short: str, filename_stem: str, 
                 dicom_path: Path, study_date: str, current_session: str = None,
                 editor_session: str = None):  # ADD editor_session parameter
        super().__init__()
        self.canvas = canvas
        self.editor_session = editor_session
        self.session_path = session_path  # Base session directory path
        self.patient_id = patient_id
        self.view_short = view_short
        self.filename_stem = filename_stem
        self.dicom_path = dicom_path
        self.study_date = study_date
        self.current_session = current_session
        self.editor_session = editor_session  # NEW: Store editor session
        self.save_info = {}
        
        # Initialize attributes to None to prevent AttributeError
        self.classification_mask_edited = None
        self.xml_edited = None

    def _initialize_save_paths(self):
        """
        Initialize save paths with proper patient/study_date/session/editor structure.
        
        Expected structure:
        - Individual user: data/PLANAR/NSY/5001/20250115/20250817/
        - ALL user: data/PLANAR/ALL/5001/20250115/NSY/20250817/
        """
        try:
            # ADD MISSING IMPORTS
            from core.config.paths import generate_edit_date, generate_edit_timestamp
            
            # 1. DETERMINE THE CORRECT PATIENT STUDY FOLDER
            # Start from the dicom_path and work backwards to find the correct structure
            
            # Get the current file's directory (should be study_date folder)
            current_dir = self.dicom_path.parent
            
            # Extract components from the current path
            # Example path: C:\hotspot\hotspot-analyzer\data\PLANAR\ALL\5001\20250115\ant_hotspot_classification.png
            path_parts = current_dir.parts
            
            # Find PLANAR index
            try:
                planar_idx = path_parts.index('PLANAR')
            except ValueError:
                raise ValueError("Could not find PLANAR in path")
            
            # Extract path components
            if len(path_parts) <= planar_idx + 3:
                raise ValueError("Invalid path structure - missing components")
                
            base_planar = Path(*path_parts[:planar_idx + 1])  # .../PLANAR
            session_folder = path_parts[planar_idx + 1]       # ALL or NSY/ATL/NBL
            patient_id = path_parts[planar_idx + 2]           # 5001
            study_date = path_parts[planar_idx + 3]           # 20250115
            
            # Validate extracted components
            if not (len(patient_id) >= 1 and patient_id.isdigit()):
                raise ValueError(f"Invalid patient_id: {patient_id}")
            if not (len(study_date) == 8 and study_date.isdigit()):
                raise ValueError(f"Invalid study_date: {study_date}")
            
            # 2. BUILD THE CORRECT BASE PATH
            base_patient_study_folder = base_planar / session_folder / patient_id / study_date
            
            if not base_patient_study_folder.exists():
                raise ValueError(f"Patient study folder does not exist: {base_patient_study_folder}")
            
            # 3. DETERMINE SAVE DIRECTORY BASED ON SESSION TYPE
            edit_date = generate_edit_date()  # YYYYMMDD format for today
            
            if session_folder == "ALL":
                # ALL user structure: data/PLANAR/ALL/5001/20250115/NSY/20250817/
                # FIX: Handle editor_session properly
                if self.editor_session:
                    selected_editor = self.editor_session
                else:
                    # Fallback: get from dialog or use default
                    selected_editor = self._get_session_code()
                    if not selected_editor:
                        raise ValueError("Editor session required for ALL user")
                
                save_dir = base_patient_study_folder / selected_editor / edit_date
            else:
                # Individual user structure: data/PLANAR/NSY/5001/20250115/20250817/
                save_dir = base_patient_study_folder / edit_date
            
            # 4. CREATE SAVE DIRECTORY
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 5. GENERATE TIMESTAMPED FILENAMES
            edit_time = generate_edit_timestamp()  # HHMMSS format
            
            # Create timestamped filenames
            png_filename = f"{self.view_short}_hotspot_classification_{edit_time}.png"
            xml_filename = f"{self.view_short}_hotspot_classification_{edit_time}.xml"
            
            # 6. SET FINAL SAVE PATHS
            self.classification_mask_edited = save_dir / png_filename
            self.xml_edited = save_dir / xml_filename
            
            # 7. STORE SAVE INFO FOR SUCCESS MESSAGE
            self.save_info = {
                'base_folder': base_patient_study_folder,
                'save_dir': save_dir,
                'session_folder': session_folder,
                'patient_id': patient_id,
                'study_date': study_date,
                'editor_session': selected_editor if session_folder == "ALL" else session_folder,
                'edit_date': edit_date,
                'edit_time': edit_time
            }
            
            logging.info(f"  Save paths initialized:")
            logging.info(f"   Base: {base_patient_study_folder}")
            logging.info(f"   Save dir: {save_dir}")
            logging.info(f"   PNG: {png_filename}")
            logging.info(f"   XML: {xml_filename}")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize save paths: {e}"
            logging.info(f" {error_msg}")
            logging.info(f"   DICOM path: {self.dicom_path}")
            logging.info(f"   Current session: {self.current_session}")
            logging.info(f"   Editor session: {getattr(self, 'editor_session', 'Not set')}")
            self.error_occurred.emit(error_msg)
            return False

    def run(self):
        if not self._initialize_save_paths():
            return  # Error already emitted
        self._perform_save()

    def _get_session_code(self) -> Optional[str]:
        """Get session code, showing dialog if current session is ALL."""
        if self.current_session != "ALL":
            return self.current_session
        
        # Show dialog to select session code
        return self._show_session_selection_dialog()

    def _show_session_selection_dialog(self) -> Optional[str]:
        """Show dialog to select session code from doctor_tags.json."""
        import json
        from datetime import datetime
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel
        from PySide6.QtCore import Qt
        
        try:
            # Load doctor tags from config file
            from core.config.paths import CONFIG_ROOT
            config_path = CONFIG_ROOT / "doctor_tags.json"
            if not config_path.exists():
                logging.info(f"Config file not found: {config_path}")
                return "NSY"  # Fallback to default
            
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Filter out "ALL" and get available tags
            available_tags = [tag for tag in config_data.get("doctor_tags", []) if tag.get("code") != "ALL"]
            
            if not available_tags:
                logging.info("No available doctor tags found")
                return "NSY"  # Fallback to default
            
            # Create dialog
            dialog = QDialog()
            dialog.setWindowTitle("Select Session Code")
            dialog.setModal(True)
            dialog.resize(400, 300)
            
            layout = QVBoxLayout(dialog)
            
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
            logging.info(f"Error showing session selection dialog: {e}")
            return "NSY"  # Fallback to default

    # ... rest of your existing methods remain the same ...        
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
        
        # Add safety check for canvas and its current_mask method
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
        
        #   FIX: Build success message properly
        success_msg = (
            f"Classification edits saved successfully!\n\n"
            f"Files saved to: {self.classification_mask_edited.parent}\n"
            f"• {self.classification_mask_edited.name}\n"
            f"• {self.xml_edited.name}\n\n"
        )
        
        if xml_result:
            success_msg += f"XML annotations: {xml_result['bbox_stats']}\n"
        
        if quant_success:
            success_msg += "\n  Quantification pipeline completed successfully"
        else:
            success_msg += "\n⚠️ Quantification pipeline failed (check logs for details)"

        #   FIX: Use custom signal instead of built-in finished signal
        if hasattr(self, 'save_completed'):
            self.save_completed.emit(success_msg)  #   NOW success_msg IS DEFINED
            logging.info(f"[DEBUG] save_completed signal emitted: {len(success_msg)} chars")
        else:
            # Fallback if save_completed signal doesn't exist
            logging.info(f"Hotspot save completed: {success_msg}")
            
        # Store save info for get_save_info() method
        self.save_info = {
            'date_dir': self.classification_mask_edited.parent,
            'png_path': self.classification_mask_edited,
            'xml_path': self.xml_edited,
            'success': True,
            'message': success_msg
        }

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
            logging.info(f"Failed to save XML: {e}")
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
            logging.info(f"Quantification failed: {e}")
            return False

    def get_save_info(self) -> Dict[str, Path]:
        """Get information about save paths for external use."""
        #   FIX: Add safety checks for None values
        if self.classification_mask_edited is None or self.xml_edited is None:
            return {}
            
        return {
            'png_path': self.classification_mask_edited,
            'xml_path': self.xml_edited,
            'date_dir': self.classification_mask_edited.parent
        }