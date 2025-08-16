# features/spect_viewer/gui/editor_components/base_components.py
"""
Base components shared between hotspot and segmentation editors.
Contains common UI elements and canvas functionality.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable
import math
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QThread
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QWheelEvent, QCursor, QLinearGradient
)
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSlider, QWidget, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QFrame
)

import pydicom
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from core.gui.loading_dialog import LoadingDialog


class BaseBrightnessContrastPad(QWidget):
    """Reusable 2D brightness/contrast control pad.
    
    X-axis: brightness (-1 to +1)
    Y-axis: contrast (0.5 to 2.0)
    """
    valueChanged = Signal(float, float)  # (brightness, contrast)

    def __init__(self, size: int = 200, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._b = 0.0          # brightness
        self._c = 1.0          # contrast
        self._dragging = False
        self._hover = False
        self.setMouseTracking(True)

    def _emit(self):
        self.valueChanged.emit(self._b, self._c)

    def _update_from_pos(self, ev):
        x = ev.position().x()
        y = ev.position().y()
        w, h = self.width(), self.height()
        x = max(0, min(w, x))
        y = max(0, min(h, y))
        self._b = (x / w) * 2.0 - 1.0            # -1 to +1
        self._c = 0.5 + (1.0 - y / h) * 1.5      # 2.0 (top) to 0.5 (bottom)
        self._emit()
        self.update()

    def mousePressEvent(self, ev):
        if ev.buttons() & Qt.LeftButton:
            self._dragging = True
            self._update_from_pos(ev)

    def mouseMoveEvent(self, ev):
        if self._dragging:
            self._update_from_pos(ev)
        else:
            self._hover = True
            self.update()

    def mouseReleaseEvent(self, ev):
        self._dragging = False
        self.update()

    def leaveEvent(self, ev):
        self._hover = False
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)

        # Background gradients
        grad_h = QLinearGradient(0, 0, self.width(), 0)      # brightness
        grad_h.setColorAt(0.0, QColor("#404040"))
        grad_h.setColorAt(0.5, QColor("#808080"))
        grad_h.setColorAt(1.0, QColor("#c0c0c0"))

        grad_v = QLinearGradient(0, 0, 0, self.height())      # contrast
        grad_v.setColorAt(0.0, QColor("#ffffff"))
        grad_v.setColorAt(0.5, QColor("#808080"))
        grad_v.setColorAt(1.0, QColor("#404040"))

        p.fillRect(self.rect(), grad_h)
        p.setCompositionMode(QPainter.CompositionMode_Multiply)
        p.fillRect(self.rect(), grad_v)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # Grid and reference lines
        center_x = self.width() // 2
        center_y = int(self.height() * (1 - (1.0 - 0.5) / 1.5))  # C=1.0 pos-Y

        # Main lines
        p.setPen(QPen(QColor(255, 255, 255, 80), 1))
        p.drawLine(center_x, 0, center_x, self.height())   # B = 0
        p.drawLine(0, center_y, self.width(), center_y)    # C = 1

        # Quarter lines
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        quarter_x = self.width() // 4
        p.drawLine(quarter_x, 0, quarter_x, self.height())
        p.drawLine(3*quarter_x, 0, 3*quarter_x, self.height())

        # Labels
        p.setPen(QColor(255, 255, 255, 180))
        fm = p.fontMetrics()
        p.drawText(5, self.height()-5, "-1")
        p.drawText(quarter_x-10, self.height()-5, "-0.5")
        p.drawText(center_x-5, self.height()-5, "0")
        p.drawText(3*quarter_x-10, self.height()-5, "+0.5")
        p.drawText(self.width()-20, self.height()-5, "+1")

        p.drawText(5, 15,  "2.0")
        p.drawText(5, center_y+5, "1.0")
        p.drawText(5, self.height()-15, "0.5")

        # Crosshair and live indicator
        cx = int((self._b + 1) / 2 * self.width())
        cy = int((1 - (self._c - 0.5) / 1.5) * self.height())

        # Live lines
        p.setPen(QPen(QColor(0, 255, 0, 150), 2))
        p.drawLine(cx, 0, cx, self.height())
        p.setPen(QPen(QColor(0, 150, 255, 150), 2))
        p.drawLine(0, cy, self.width(), cy)

        # Crosshair
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawLine(cx-10, cy, cx+10, cy)
        p.drawLine(cx, cy-10, cx, cy+10)
        p.setPen(QPen(QColor(255, 0, 0), 1))
        p.drawLine(cx-8, cy, cx+8, cy)
        p.drawLine(cx, cy-8, cx, cy+8)

        # Center circle
        p.setBrush(QColor(255, 0, 0))
        p.drawEllipse(cx-2, cy-2, 4, 4)

        # Value tooltips
        p.setPen(QPen(QColor(255, 255, 255), 1))
        p.setBrush(QColor(0, 0, 0, 180))
        b_txt = f"B: {self._b:+.2f}"
        c_txt = f"C: {self._c:.2f}"
        b_rect = fm.boundingRect(b_txt)
        c_rect = fm.boundingRect(c_txt)
        
        # Brightness box (bottom)
        bx = cx - b_rect.width()//2
        by = self.height() - b_rect.height() - 4
        p.drawRect(bx-2, by-2, b_rect.width()+4, b_rect.height()+4)
        p.drawText(bx, by + b_rect.height(), b_txt)
        
        # Contrast box (right)
        cxr = self.width() - c_rect.width() - 6
        cyr = cy - c_rect.height()//2
        p.drawRect(cxr-2, cyr-2, c_rect.width()+4, c_rect.height()+4)
        p.drawText(cxr, cyr + c_rect.height(), c_txt)

        # Highlight on drag/hover
        if self._dragging:
            p.setPen(QPen(QColor(255, 255, 0, 200), 3))
            p.setBrush(QColor(255, 255, 0, 50))
            p.drawEllipse(cx-8, cy-8, 16, 16)
        elif self._hover:
            p.setPen(QPen(QColor(255, 255, 255, 150), 2))
            p.setBrush(QColor(255, 255, 255, 30))
            p.drawEllipse(cx-6, cy-6, 12, 12)


class BaseOpacitySlider(QWidget):
    """Reusable opacity slider with +/- buttons and percentage label."""
    valueChanged = Signal(int)  # Emits percentage (0-100)

    def __init__(self, label_text: str, initial_value: int = 50, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        
        # Label
        self.label = QLabel(label_text)
        layout.addWidget(self.label)
        
        # Slider row with +/- buttons
        slider_row = QHBoxLayout()
        slider_row.setSpacing(3)
        
        self.btn_minus = QPushButton("-")
        self.btn_minus.setFixedSize(30, 22)
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(initial_value)
        
        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(30, 22)
        
        self.lbl_value = QLabel(f"{initial_value} %")
        self.lbl_value.setFixedWidth(35)
        self.lbl_value.setAlignment(Qt.AlignRight)
        
        slider_row.addWidget(self.btn_minus)
        slider_row.addWidget(self.slider, 1)
        slider_row.addWidget(self.btn_plus)
        slider_row.addWidget(self.lbl_value)
        
        layout.addLayout(slider_row)
        
        # Connect signals
        self.slider.valueChanged.connect(self._on_value_changed)
        self.btn_minus.clicked.connect(lambda: self._adjust_value(-5))
        self.btn_plus.clicked.connect(lambda: self._adjust_value(5))

    def _on_value_changed(self, value: int):
        self.lbl_value.setText(f"{value} %")
        self.valueChanged.emit(value)

    def _adjust_value(self, step: int):
        current = self.slider.value()
        new_value = max(0, min(100, current + step))
        self.slider.setValue(new_value)

    def setValue(self, value: int):
        self.slider.setValue(value)

    def value(self) -> int:
        return self.slider.value()


class BaseCanvas(QGraphicsView):
    """Base canvas with core functionality: pan, zoom, drawing, history management."""

    def __init__(self, orig: np.ndarray, mask: np.ndarray, palette: list, parent=None):
        super().__init__(parent)
        self.palette = palette  # Store the palette for use

        # Rendering setup
        self.setRenderHints(
            QPainter.Antialiasing |
            QPainter.SmoothPixmapTransform |
            QPainter.TextAntialiasing
        )
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setMouseTracking(True)
        # Scene setup
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Store image dimensions
        self._img_height, self._img_width = orig.shape

        # Original grayscale layer
        self._orig_base = ((orig - orig.min()) / max(1, np.ptp(orig)) * 255).astype(np.uint8)
        gray_q = QImage(self._orig_base.data, self._img_width, self._img_height,
                        self._img_width, QImage.Format_Grayscale8).copy()
        self._item_gray = QGraphicsPixmapItem(QPixmap.fromImage(gray_q))
        self._item_gray.setOpacity(0.5)
        self._scene.addItem(self._item_gray)

        # Base mask array
        self._mask_arr = mask.astype(np.uint8)

        # ✅ FIX: Define the _layers attribute HERE, before it's ever used.
        # This creates a separate binary mask for each label in the palette.
        self._layers = {
            label_id: (self._mask_arr == label_id).astype(np.uint8)
            for label_id in range(len(self.palette))
        }

        # Create the pixmap item for the mask (subclass will populate it)
        self._item_mask = QGraphicsPixmapItem()
        self._scene.addItem(self._item_mask)

        # Drawing state
        self._cur_label = 1
        self._brush_radius = 5
        self._eraser = False
        self._show_all = False
        self._drawing = False
        self._pan_mode = False
        self._mouse_pos = QPointF()
        self._show_brush_cursor = True

        # Zoom tracking
        self._zoom_factor = 1.0
        self.setSceneRect(QRectF(self._item_gray.boundingRect()))

        # Info callback
        self._info_callback = None

        # History management (initialized at the very end)
        self._layer_history = {}
        self._max_history = 50
        # This call is now safe because self._layers exists
        self._init_history()

    def _init_history(self):
        """Initialize history - to be implemented by subclasses."""
        pass

    def set_info_callback(self, callback: Callable):
        """Set callback to update info display."""
        self._info_callback = callback
        self._update_info()

    def _update_info(self):
        """Update info display with current zoom and grid info."""
        if self._info_callback:
            grid_size = 1 if self._zoom_factor >= 4.0 else int(20 / self._zoom_factor)
            self._info_callback(self._img_width, self._img_height, self._zoom_factor, grid_size)

    # Opacity controls
    def set_gray_opacity(self, alpha: float):
        """Set opacity for grayscale layer (0-1)."""
        self._item_gray.setOpacity(alpha)

    def set_mask_opacity(self, alpha: float):
        """Set opacity for mask layer (0-1)."""
        if self._item_mask:
            self._item_mask.setOpacity(alpha)

    def set_bc(self, brightness: float, contrast: float):
        """Apply brightness/contrast adjustment."""
        arr = (self._orig_base.astype(np.float32) - 128) * contrast + 128 + brightness*128
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        q = QImage(arr.data, self._img_width, self._img_height,
                   self._img_width, QImage.Format_Grayscale8).copy()
        self._item_gray.setPixmap(QPixmap.fromImage(q))

    # Drawing controls
    def set_brush_size(self, radius: int):
        """Set brush radius (not diameter or pixel count)."""
        self._brush_radius = max(1, radius)
        self.viewport().update()
        
    def get_brush_radius(self) -> int:
        """Get current brush radius."""
        return self._brush_radius
    
    def set_brush_cursor_visible(self, visible: bool):
        """Toggle brush cursor visibility."""
        self._show_brush_cursor = visible
        self.viewport().update()

    def _get_brush_targets(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Get list of pixel coordinates affected by brush."""
        h, w = self._mask_arr.shape
        
        # ✅ FIX: Use the correct attribute name `_brush_radius`
        if self._brush_radius <= 1: 
            return [(x, y)]
        
        targets = []
        # ✅ FIX: Use the correct attribute name `_brush_radius`
        radius = self._brush_radius 
        radius_sq = radius * radius # Use squared radius for efficiency
        
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx*dx + dy*dy <= radius_sq:
                    px, py = x + dx, y + dy
                    if 0 <= px < w and 0 <= py < h:
                        targets.append((px, py))
        return targets

    def set_label(self, label: int):
        self._cur_label, self._eraser = int(label), False
        self._show_all = False
        self._refresh_mask()

    def set_eraser(self):
        self._eraser = True
        self._show_all = False
        self._refresh_mask()

    def toggle_show_all(self, on: bool):
        self._show_all = bool(on)
        self._refresh_mask()

    # Zoom controls
    def set_zoom(self, zoom_factor: float):
        """Set zoom to specific factor."""
        current_zoom = self.transform().m11()
        scale_factor = zoom_factor / current_zoom
        self._zoom_factor = zoom_factor
        self.scale(scale_factor, scale_factor)
        self._update_info()
        self.viewport().update()

    # Abstract methods for subclasses
    def _refresh_mask(self):
        """Refresh mask display - must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _refresh_mask")

    def _apply_brush(self, scene_pos: QPointF):
        """Apply brush at position - must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _apply_brush")

    def current_mask(self) -> np.ndarray:
        """Return current mask array."""
        return self._mask_arr

    # Common coordinate handling
    def _get_pixel_coordinates(self, scene_pos: QPointF) -> Tuple[int, int]:
        """Convert scene position to pixel coordinates."""
        x = max(0, min(self._img_width - 1, int(scene_pos.x() + 0.5)))
        y = max(0, min(self._img_height - 1, int(scene_pos.y() + 0.5)))
        return x, y

    def _get_brush_targets(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Get list of pixel coordinates affected by brush."""
        h, w = self._mask_arr.shape
        
        # ✅ FIX: Use the correct attribute name `_brush_radius`
        if self._brush_radius <= 1:
            return [(x, y)]
        
        targets = []
        # ✅ FIX: Use the correct attribute name `_brush_radius`
        radius = self._brush_radius
        radius_sq = radius * radius
        
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx*dx + dy*dy <= radius_sq:
                    px, py = x + dx, y + dy
                    if 0 <= px < w and 0 <= py < h:
                        targets.append((px, py))
        return targets
    # Mouse events
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and not self._pan_mode:
            self._drawing = True
            scene_pos = self.mapToScene(ev.position().toPoint())
            self._mouse_pos = scene_pos
            self._apply_brush(scene_pos)
            ev.accept()
        elif ev.button() == Qt.MiddleButton:
            self._pan_mode = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(QCursor(Qt.OpenHandCursor))
            super().mousePressEvent(ev)
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        scene_pos = self.mapToScene(ev.position().toPoint())
        self._mouse_pos = scene_pos # Store the current position

        if self._drawing and ev.buttons() & Qt.LeftButton and not self._pan_mode:
            self._apply_brush(scene_pos) # This is your fix from before
            ev.accept()
        else:
            super().mouseMoveEvent(ev)
        
        # ✅ FIX: Always update the viewport to redraw the cursor
        if not self._pan_mode:
            self.viewport().update()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._drawing:
            self._save_current_state()
            self._drawing = False
        elif ev.button() == Qt.MiddleButton:
            self._pan_mode = False
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(QCursor(Qt.CrossCursor))
        super().mouseReleaseEvent(ev)
    
    def enterEvent(self, ev):
        """Show brush cursor when mouse enters."""
        self._show_brush_cursor = True
        self.viewport().update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        """Hide brush cursor when mouse leaves."""
        self._show_brush_cursor = False
        self.viewport().update()
        super().leaveEvent(ev)

    def wheelEvent(self, ev: QWheelEvent):
        if ev.modifiers() & Qt.ControlModifier:
            factor = 1.15 if ev.angleDelta().y() > 0 else 1/1.15
            self._zoom_factor *= factor
            self.scale(factor, factor)
            self._update_info()
            self.viewport().update()
            ev.accept()
        else:
            super().wheelEvent(ev)

    # Grid overlay
    def drawForeground(self, painter: QPainter, rect: QRectF):
        if self._zoom_factor < 2.0:
            return
        else:
            step = 1 if self._zoom_factor >= 4.0 else max(1, int(10 / self._zoom_factor))
            alpha = min(100, int(20 * self._zoom_factor)) if step == 1 else 40
            
            pen = QPen(QColor(100, 100, 100, alpha))
            pen.setWidth(0)
            painter.setPen(pen)
            
            visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()
            
            left = math.floor(visible_rect.left() / step) * step
            top = math.floor(visible_rect.top() / step) * step
            right = math.ceil(visible_rect.right() / step) * step
            bottom = math.ceil(visible_rect.bottom() / step) * step
            
            # Vertical lines
            x = left
            while x <= right:
                if 0 <= x <= self._img_width:
                    painter.drawLine(x, max(0, top), x, min(self._img_height, bottom))
                x += step
            
            # Horizontal lines
            y = top
            while y <= bottom:
                if 0 <= y <= self._img_height:
                    painter.drawLine(max(0, left), y, min(self._img_width, right), y)
                y += step
        
        if self._show_brush_cursor and not self._pan_mode and self._brush_radius > 0:
            self._draw_brush_cursor(painter)
           
    def _draw_brush_cursor(self, painter: QPainter):
        """Draw circular brush cursor at mouse position."""
        # Get mouse position in scene coordinates
        cursor_center = self._mouse_pos
        
        # Check if cursor is within image bounds
        if (cursor_center.x() < 0 or cursor_center.x() >= self._img_width or
            cursor_center.y() < 0 or cursor_center.y() >= self._img_height):
            return
        
        # Calculate cursor appearance based on zoom and brush size
        cursor_radius = self._brush_radius
        
        # Set up cursor appearance
        if self._eraser:
            # Eraser cursor: red circle with crosshatch pattern
            pen_color = QColor(255, 100, 100, 180)  # Semi-transparent red
            brush_color = QColor(255, 100, 100, 30)
        else:
            # Paint cursor: blue circle
            pen_color = QColor(100, 150, 255, 180)  # Semi-transparent blue
            brush_color = QColor(100, 150, 255, 30)
        
        # Draw outer circle
        painter.setPen(QPen(pen_color, 1))
        painter.setBrush(QColor(brush_color))
        
        cursor_rect = QRectF(
            cursor_center.x() - cursor_radius,
            cursor_center.y() - cursor_radius,
            cursor_radius * 2,
            cursor_radius * 2
        )
        painter.drawEllipse(cursor_rect)
        
        # Draw center crosshair for precision
        painter.setPen(QPen(pen_color, 1))
        crosshair_size = min(3, cursor_radius // 2)
        painter.drawLine(
            cursor_center.x() - crosshair_size, cursor_center.y(),
            cursor_center.x() + crosshair_size, cursor_center.y()
        )
        painter.drawLine(
            cursor_center.x(), cursor_center.y() - crosshair_size,
            cursor_center.x(), cursor_center.y() + crosshair_size
        )
        
        # Add special pattern for eraser
        if self._eraser and cursor_radius > 3:
            painter.setPen(QPen(QColor(255, 0, 0, 120), 1))
            # Draw diagonal crosshatch pattern
            for i in range(-cursor_radius, cursor_radius, 3):
                # Diagonal lines
                painter.drawLine(
                    cursor_center.x() + i, cursor_center.y() - cursor_radius,
                    cursor_center.x() + i + cursor_radius, cursor_center.y()
                )
                painter.drawLine(
                    cursor_center.x() + i, cursor_center.y() + cursor_radius,
                    cursor_center.x() + i - cursor_radius, cursor_center.y()
                )

    # History methods (to be implemented by subclasses)
    def _save_current_state(self):
        """Save current state for undo - to be implemented by subclasses."""
        pass

    def undo(self, label_id: int):
        """Undo operation - to be implemented by subclasses."""
        pass

    def redo(self, label_id: int):
        """Redo operation - to be implemented by subclasses."""
        pass
    
class BaseBrushSizeControl(QWidget):
    """Reusable brush size control with 1px increments."""
    radiusChanged = Signal(int)  # Emits radius value
    
    def __init__(self, label_text: str = "Brush Size", 
                 initial_radius: int = 1, min_radius: int = 1, 
                 max_radius: int = 15, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        
        # Label
        self.label = QLabel(label_text)
        layout.addWidget(self.label)
        
        # Slider row with +/- buttons
        slider_row = QHBoxLayout()
        slider_row.setSpacing(3)
        
        self.btn_minus = QPushButton("-")
        self.btn_minus.setFixedSize(30, 22)
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(min_radius, max_radius)
        self.slider.setValue(initial_radius)
        
        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(30, 22)
        
        # Show pixel count instead of radius
        self.lbl_value = QLabel(f"{initial_radius}px")
        self.lbl_value.setFixedWidth(35)
        self.lbl_value.setAlignment(Qt.AlignRight)
        
        slider_row.addWidget(self.btn_minus)
        slider_row.addWidget(self.slider, 1)
        slider_row.addWidget(self.btn_plus)
        slider_row.addWidget(self.lbl_value)
        
        layout.addLayout(slider_row)
        
        # Connect signals
        self.slider.valueChanged.connect(self._on_value_changed)
        self.btn_minus.clicked.connect(lambda: self._adjust_value(-1))  # 1px increment
        self.btn_plus.clicked.connect(lambda: self._adjust_value(1))    # 1px increment

    def _on_value_changed(self, value: int):
        self.lbl_value.setText(f"r={value}")
        self.radiusChanged.emit(value)

    def _adjust_value(self, step: int):
        current = self.slider.value()
        new_value = max(self.slider.minimum(), min(self.slider.maximum(), current + step))
        self.slider.setValue(new_value)

    def setValue(self, radius: int):
        self.slider.setValue(radius)

    def value(self) -> int:
        return self.slider.value()

    def setRange(self, min_radius: int, max_radius: int):
        self.slider.setRange(min_radius, max_radius)

class BaseEditorDialog(QDialog):
    """Base dialog with common infrastructure for editors."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent, Qt.Window)
        from PySide6.QtGui import QGuiApplication
        
        self.setWindowTitle(title)
        geom = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(int(geom.width()*0.9), int(geom.height()*0.9))
        
        # Threading
        self._save_thread = None
        self._loading_dialog = None
        self._is_saving = False
        
        # Main layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setSpacing(5)
        
        # Create UI components
        self._create_toolbar()
        self._create_main_area()
        self._connect_signals()

    def _create_toolbar(self):
        """Create left toolbar - to be implemented by subclasses."""
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setMaximumWidth(250)
        self.toolbar_layout = QVBoxLayout(self.toolbar_widget)
        self.main_layout.addWidget(self.toolbar_widget)

    def _create_main_area(self):
        """Create main canvas area - to be implemented by subclasses."""
        self.main_area_layout = QVBoxLayout()
        self.main_layout.addLayout(self.main_area_layout, 1)

    def _connect_signals(self):
        """Connect signals - to be implemented by subclasses."""
        pass

    def _create_opacity_panel(self, opacity_configs: List[Tuple[str, int]]) -> QWidget:
        """Create a panel with multiple opacity sliders.
        
        Args:
            opacity_configs: List of (label, initial_value) tuples
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        self.opacity_sliders = {}
        for label, initial_value in opacity_configs:
            slider = BaseOpacitySlider(label, initial_value)
            self.opacity_sliders[label] = slider
            layout.addWidget(slider)
        
        return panel

    def _adjust_slider(self, slider: QSlider, step: int):
        """Helper to adjust slider value by step."""
        current = slider.value()
        new_value = max(slider.minimum(), min(slider.maximum(), current + step))
        slider.setValue(new_value)

    def _create_info_panel(self) -> QFrame:
        """Create info display panel."""
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Box)
        info_frame.setMaximumHeight(60)
        info_layout = QHBoxLayout(info_frame)
        
        self.lbl_image_info = QLabel("Image: 0×0")
        self.lbl_zoom_info = QLabel("Zoom: 1.0x")
        self.lbl_grid_info = QLabel("Grid: Off")
        
        info_layout.addWidget(QLabel("<b>Info:</b>"))
        info_layout.addWidget(self.lbl_image_info)
        info_layout.addWidget(QLabel("|"))
        info_layout.addWidget(self.lbl_zoom_info)
        info_layout.addWidget(QLabel("|"))
        info_layout.addWidget(self.lbl_grid_info)
        info_layout.addStretch()
        
        return info_frame

    def _update_info_display(self, width: int, height: int, zoom: float, grid_size: int):
        """Update info display with current stats."""
        self.lbl_image_info.setText(f"Image: {width}×{height}")
        self.lbl_zoom_info.setText(f"Zoom: {zoom:.1f}x")
        if zoom >= 2.0:
            if grid_size == 1:
                self.lbl_grid_info.setText("Grid: 1px")
            else:
                self.lbl_grid_info.setText(f"Grid: {grid_size}px")
        else:
            self.lbl_grid_info.setText("Grid: Off")

    def keyPressEvent(self, event):
        """Handle common keyboard shortcuts."""
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Z:
                self._perform_undo()
                event.accept()
                return
            elif event.key() == Qt.Key_Y:
                self._perform_redo()
                event.accept()
                return
        super().keyPressEvent(event)

    def _perform_undo(self):
        """Perform undo - to be implemented by subclasses."""
        pass

    def _perform_redo(self):
        """Perform redo - to be implemented by subclasses."""
        pass

    def _open_contrast_popup(self):
        """Open brightness/contrast adjustment dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Brightness / Contrast")
        dlg.setFixedSize(300, 400)
        lay = QVBoxLayout(dlg)

        pad = BaseBrightnessContrastPad()
        lbl = QLabel("B 0.00  C 1.00")
        lay.addWidget(QLabel("Drag crosshair – X = brightness, Y = contrast"))
        lay.addWidget(pad, 0, Qt.AlignCenter)
        
        # Reference labels
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel("Dark"))
        ref_layout.addStretch()
        ref_layout.addWidget(QLabel("Normal"))
        ref_layout.addStretch()
        ref_layout.addWidget(QLabel("Bright"))
        lay.addLayout(ref_layout)

        contrast_info = QLabel("↑ High Contrast\n↓ Low Contrast")
        contrast_info.setAlignment(Qt.AlignCenter)
        lay.addWidget(contrast_info)
        lay.addWidget(lbl, 0, Qt.AlignCenter)

        def _on_change(b, c):
            lbl.setText(f"B {b:+.2f}   C {c:.2f}")
            if hasattr(self, 'canvas'):
                self.canvas.set_bc(b, c)
        pad.valueChanged.connect(_on_change)

        dlg.exec()

    def _save_sc_dicom(self, img: np.ndarray, path: Path, desc: str):
        """Save as Secondary Capture DICOM."""
        rgb = img.ndim == 3
        rows, cols = img.shape[:2]
        meta = pydicom.Dataset()
        meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian

        ds = pydicom.FileDataset(str(path), {}, file_meta=meta, preamble=b"\0"*128)
        ds.Modality = "OT"
        ds.SeriesInstanceUID = generate_uid()
        ds.SeriesDescription = desc
        ds.Rows, ds.Columns = rows, cols
        ds.SamplesPerPixel = 3 if rgb else 1
        ds.PhotometricInterpretation = "RGB" if rgb else "MONOCHROME2"
        ds.BitsAllocated = ds.BitsStored = 8
        ds.HighBit = 7
        if rgb: 
            ds.PlanarConfiguration = 0
        ds.PixelRepresentation = 0
        ds.PixelData = img.astype(np.uint8).tobytes()
        ds.save_as(path, write_like_original=False)

    def _start_save_process(self, save_thread_class, *args):
        """Start threaded save process with loading dialog."""
        if self._is_saving:
            QMessageBox.warning(self, "Save in Progress", "Please wait for current save to complete.")
            return
        
        self._is_saving = True
        
        # Disable save button
        for widget in self.findChildren(QPushButton):
            if widget.text() == "Save":
                widget.setEnabled(False)
                widget.setText("Saving...")
        
        # Create loading dialog
        self._loading_dialog = LoadingDialog(
            title="Saving",
            message="Preparing to save...",
            show_progress=True,
            show_cancel=False,
            parent=self
        )
        self._loading_dialog.show()
        
        # Create and start save thread
        self._save_thread = save_thread_class(*args)
        self._save_thread.progress_updated.connect(self._on_save_progress)
        self._save_thread.save_completed.connect(self._on_save_completed)
        self._save_thread.start()

    def _on_save_progress(self, progress: int, message: str):
        """Handle save progress updates."""
        if self._loading_dialog:
            self._loading_dialog.set_progress(progress)
            self._loading_dialog.set_message(message)

    def _on_save_completed(self, success: bool, message: str):
        """Handle save completion."""
        if self._loading_dialog:
            self._loading_dialog.close()
            self._loading_dialog = None
        
        self._is_saving = False
        
        # Re-enable save button
        for widget in self.findChildren(QPushButton):
            if "Saving..." in widget.text():
                widget.setEnabled(True)
                widget.setText("Save")
        
        # Show result
        if success:
            QMessageBox.information(self, "Success", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Save Failed", message)
        
        # Clean up
        if self._save_thread:
            self._save_thread.deleteLater()
            self._save_thread = None


class BaseSaveThread(QThread):
    """Base save thread with progress reporting."""
    progress_updated = Signal(int, str)  # progress percentage, message
    save_completed = Signal(bool, str)   # success, message
    
    def __init__(self):
        super().__init__()
    
    def run(self):
        """Save process - to be implemented by subclasses."""
        try:
            self._perform_save()
            self.save_completed.emit(True, "Save completed successfully!")
        except Exception as e:
            error_msg = f"Save failed: {str(e)}"
            self.save_completed.emit(False, error_msg)
    
    def _perform_save(self):
        """Actual save logic - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _perform_save")