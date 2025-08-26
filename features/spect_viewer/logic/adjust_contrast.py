# C:\hotspot\hotspot-analyzer\features\spect_viewer\logic\adjust_contrast.py

from __future__ import annotations
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QPen, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)

def apply_brightness_contrast(
    pil_image: Image.Image, 
    brightness: float, 
    contrast: float
) -> Image.Image:
    """
    Apply brightness and contrast adjustment to a PIL Image.
    
    Args:
        pil_image: The input PIL Image (must be in 'L' or 'RGB' mode).
        brightness: Brightness adjustment factor (-1.0 to +1.0).
        contrast: Contrast adjustment factor (0.5 to 2.0).
        
    Returns:
        A new PIL Image with adjustments applied.
    """
    if pil_image.mode not in ['L', 'RGB']:
        pil_image = pil_image.convert('RGB')

    # Convert image to numpy array for fast processing
    arr = np.array(pil_image, dtype=np.float32)
    
    # Apply the formula: new = (orig - 128) * contrast + 128 + brightness * 128
    arr = (arr - 128.0) * contrast + 128.0 + (brightness * 128.0)
    
    # Clip values to the valid 0-255 range
    arr = np.clip(arr, 0, 255)
    
    # Convert back to uint8 and then to a PIL Image
    return Image.fromarray(arr.astype(np.uint8))


class BCPad(QWidget):
    """
    A reusable 2D pad for adjusting Brightness and Contrast.
    X-axis = Brightness (−1 to +1)
    Y-axis = Contrast   (0.5 to 2.0)
    """
    valueChanged = Signal(float, float)  # Emits (brightness, contrast)

    def __init__(self, size: int = 200, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._b = 0.0  # brightness
        self._c = 1.0  # contrast
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
        self._b = (x / w) * 2.0 - 1.0
        self._c = 0.5 + (1.0 - y / h) * 1.5
        self._emit()
        self.update()

    def mousePressEvent(self, ev):
        if ev.buttons() & Qt.LeftButton:
            self._dragging = True
            self._update_from_pos(ev)

    def mouseMoveEvent(self, ev):
        self._hover = True
        if self._dragging:
            self._update_from_pos(ev)
        self.update()

    def mouseReleaseEvent(self, ev):
        self._dragging = False
        self.update()

    def leaveEvent(self, ev):
        self._hover = False
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        grad_h = QLinearGradient(0, 0, self.width(), 0)
        grad_h.setColorAt(0.0, QColor("#404040"))
        grad_h.setColorAt(0.5, QColor("#808080"))
        grad_h.setColorAt(1.0, QColor("#c0c0c0"))

        grad_v = QLinearGradient(0, 0, 0, self.height())
        grad_v.setColorAt(0.0, QColor("#ffffff"))
        grad_v.setColorAt(0.5, QColor("#808080"))
        grad_v.setColorAt(1.0, QColor("#404040"))

        p.fillRect(self.rect(), grad_h)
        p.setCompositionMode(QPainter.CompositionMode_Multiply)
        p.fillRect(self.rect(), grad_v)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)

        center_x = self.width() // 2
        center_y = int(self.height() * (1 - (1.0 - 0.5) / 1.5))

        p.setPen(QPen(QColor(255, 255, 255, 80), 1))
        p.drawLine(center_x, 0, center_x, self.height())
        p.drawLine(0, center_y, self.width(), center_y)

        quarter_x = self.width() // 4
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawLine(quarter_x, 0, quarter_x, self.height())
        p.drawLine(3 * quarter_x, 0, 3 * quarter_x, self.height())

        cx = int((self._b + 1) / 2 * self.width())
        cy = int((1 - (self._c - 0.5) / 1.5) * self.height())

        p.setPen(QPen(QColor(0, 255, 0, 150), 2))
        p.drawLine(cx, 0, cx, self.height())
        p.setPen(QPen(QColor(0, 150, 255, 150), 2))
        p.drawLine(0, cy, self.width(), cy)
        
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawLine(cx - 10, cy, cx + 10, cy)
        p.drawLine(cx, cy - 10, cx, cy + 10)
        p.setPen(QPen(QColor(255, 0, 0), 1))
        p.drawLine(cx - 8, cy, cx + 8, cy)
        p.drawLine(cx, cy - 8, cx, cy + 8)
        p.setBrush(QColor(255, 0, 0))
        p.drawEllipse(cx - 2, cy - 2, 4, 4)

        if self._dragging:
            p.setPen(QPen(QColor(255, 255, 0, 200), 3))
            p.setBrush(QColor(255, 255, 0, 50))
            p.drawEllipse(cx - 8, cy - 8, 16, 16)
        elif self._hover:
            p.setPen(QPen(QColor(255, 255, 255, 150), 2))
            p.setBrush(QColor(255, 255, 255, 30))
            p.drawEllipse(cx - 6, cy - 6, 12, 12)


class ContrastDialog(QDialog):
    """A dialog that hosts the BCPad for interactive adjustment."""
    adjustment_changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adjust Brightness / Contrast")
        self.setFixedSize(300, 320)
        
        self._current_b = 0.0
        self._current_c = 1.0

        layout = QVBoxLayout(self)
        self.info_label = QLabel("Drag crosshair to adjust")
        self.value_label = QLabel("B: +0.00  |  C: 1.00")
        self.value_label.setAlignment(Qt.AlignCenter)

        self.pad = BCPad() # Make pad an instance variable
        self.pad.valueChanged.connect(self._on_pad_change)
        
        #   2. CONNECT the pad's signal to our new live preview signal
        self.pad.valueChanged.connect(self.adjustment_changed)

        btn_ok = QPushButton("Apply")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)

        layout.addWidget(self.info_label, 0, Qt.AlignCenter)
        layout.addWidget(self.pad, 0, Qt.AlignCenter)
        layout.addWidget(self.value_label, 0, Qt.AlignCenter)
        layout.addLayout(btn_layout)

    def set_initial_values(self, b: float, c: float):
        """Sets the initial position of the control pad."""
        self.pad._b = b
        self.pad._c = c
        self.pad.update() # Redraw the pad
        self._on_pad_change(b, c) # Update the label
        
    def _on_pad_change(self, b: float, c: float):
        self._current_b = b
        self._current_c = c
        self.value_label.setText(f"B: {b:+.2f}  |  C: {c:.2f}")

    def get_values(self) -> tuple[float, float] | None:
        """Returns (brightness, contrast) if accepted, otherwise None."""
        if self.result() == QDialog.Accepted:
            return self._current_b, self._current_c
        return None