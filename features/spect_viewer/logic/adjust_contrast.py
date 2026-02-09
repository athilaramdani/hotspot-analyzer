# C:\hotspot\hotspot-analyzer\features\spect_viewer\logic\adjust_contrast.py

from __future__ import annotations
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QPen
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)

def apply_gamma_mid(
    pil_image: Image.Image, 
    gamma: float, 
    mid: float
) -> Image.Image:
    """
    Apply Gamma and Mid adjustment to a PIL Image.
    Logic ported from matplotlib example:
      x = x ** gamma
      x = (x - mid) / (1 - mid)
    
    Args:
        pil_image: The input PIL Image (must be in 'L' or 'RGB' mode).
        gamma: Gamma value (0.1 to 3.0).
        mid: Mid (threshold) value (0.0 to 0.9).
        
    Returns:
        A new PIL Image with adjustments applied.
    """
    if pil_image.mode not in ['L', 'RGB']:
        pil_image = pil_image.convert('RGB')

    # Convert image to numpy float array (0.0 - 1.0)
    arr = np.array(pil_image, dtype=np.float32) / 255.0
    
    # 1. Apply Gamma
    # Protect against extremely small negative numbers just in case, though usually 0-1
    arr = np.maximum(arr, 0) 
    arr = np.power(arr, gamma)
    
    # 2. Apply Mid adjustment
    # Use user's formula: (x - mid) / (1 - mid)
    # Clamp mid to max 0.99 to avoid division by zero
    safe_mid = min(mid, 0.99)
    denom = 1.0 - safe_mid
    arr = (arr - safe_mid) / denom
    
    # 3. Clip to 0-1
    arr = np.clip(arr, 0.0, 1.0)
    
    # 4. Convert back to uint8
    arr = (arr * 255).astype(np.uint8)
    return Image.fromarray(arr)


class BCPad(QWidget):
    """
    A reusable 2D pad for adjusting Gamma and Mid.
    X-axis = Gamma (0.1 to 3.0)
    Y-axis = Mid   (0.0 to 0.9)
    """
    valueChanged = Signal(float, float)  # Emits (gamma, mid)

    def __init__(self, size: int = 200, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        
        # Internal state
        self._gamma = 1.0
        self._mid = 0.0  # Default 0.5 in user script, but 0.0 is 'neutral' for this formula
        
        self._dragging = False
        self._hover = False
        self.setMouseTracking(True)

    def _emit(self):
        self.valueChanged.emit(self._gamma, self._mid)

    def _update_from_pos(self, ev):
        x = ev.position().x()
        y = ev.position().y()
        w, h = self.width(), self.height()
        
        # Clamp coordinates
        x = max(0, min(w, x))
        y = max(0, min(h, y))
        
        # Map X to Gamma [0.1, 3.0]
        # x_ratio goes from 0.0 to 1.0
        x_ratio = x / w
        self._gamma = 0.1 + (x_ratio * 2.9)
        
        # Map Y to Mid [0.0, 0.9]
        # y_ratio goes from 0.0 (top) to 1.0 (bottom)
        # Usually UI sliders: bottom is low, top is high.
        # Let's make Bottom=0.0, Top=0.9
        y_ratio = 1.0 - (y / h)
        self._mid = y_ratio * 0.9
        
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

        # Background Gradient (Horizontal for Gamma)
        grad_h = QLinearGradient(0, 0, self.width(), 0)
        grad_h.setColorAt(0.0, QColor("#222222"))   # Low Gamma
        grad_h.setColorAt(1.0, QColor("#aaaaaa"))   # High Gamma

        p.fillRect(self.rect(), grad_h)
        
        # Overlay Gradient (Vertical for Mid)
        grad_v = QLinearGradient(0, self.height(), 0, 0) # Bottom to Top
        grad_v.setColorAt(0.0, QColor(0, 0, 0, 0))       # Mid 0 (Transparent)
        grad_v.setColorAt(1.0, QColor(0, 0, 0, 200))     # Mid 0.9 (Darker/Blacking out)
        
        p.fillRect(self.rect(), grad_v)

        # Draw Grids
        # Center X (Gamma ~ 1.55? No, we want to mark Gamma 1.0)
        # Gamma 1.0 is at (1.0 - 0.1)/2.9 = 0.9/2.9 = 0.31 of width
        gamma_1_x = int(((1.0 - 0.1) / 2.9) * self.width())
        
        p.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.DashLine))
        p.drawLine(gamma_1_x, 0, gamma_1_x, self.height())
        
        # Mid 0.0 is at bottom, Mid 0.5 is at y_ratio = 0.5/0.9 = 0.55
        mid_05_y = int(self.height() * (1.0 - (0.5 / 0.9)))
        
        p.drawLine(0, mid_05_y, self.width(), mid_05_y)

        # Calculate cursor position
        curr_x_ratio = (self._gamma - 0.1) / 2.9
        cx = int(curr_x_ratio * self.width())
        
        curr_y_ratio = self._mid / 0.9
        cy = int(self.height() * (1.0 - curr_y_ratio))

        # Draw Crosshair
        p.setPen(QPen(QColor(0, 255, 0, 200), 2))
        p.drawLine(cx, 0, cx, self.height())
        p.setPen(QPen(QColor(0, 150, 255, 200), 2))
        p.drawLine(0, cy, self.width(), cy)
        
        # Draw Point
        if self._dragging:
            p.setPen(QPen(QColor(255, 255, 0, 255), 3))
            p.setBrush(QColor(255, 255, 0, 100))
            p.drawEllipse(cx - 8, cy - 8, 16, 16)
        else:
            p.setPen(QPen(QColor(255, 255, 255, 200), 2))
            p.setBrush(QColor(255, 255, 255, 50))
            p.drawEllipse(cx - 6, cy - 6, 12, 12)


class ContrastDialog(QDialog):
    """A dialog that hosts the BCPad for interactive adjustment."""
    adjustment_changed = Signal(float, float) # Gamma, Mid

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adjust Contrast (Gamma/Mid)")
        self.setFixedSize(320, 360) # Slightly larger
        
        self._current_gamma = 1.0
        self._current_mid = 0.0

        layout = QVBoxLayout(self)
        self.info_label = QLabel("X: Gamma (Correction)\nY: Mid (Threshold)")
        self.info_label.setAlignment(Qt.AlignCenter)
        
        self.value_label = QLabel("Gamma: 1.00  |  Mid: 0.00")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("font-weight: bold; font-size: 12px; margin: 5px;")

        self.pad = BCPad()
        # Connect internal update
        self.pad.valueChanged.connect(self._on_pad_change)
        # Connect external signal
        self.pad.valueChanged.connect(self.adjustment_changed)

        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self._reset_values)
        
        btn_ok = QPushButton("Apply")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)

        layout.addWidget(self.info_label)
        layout.addWidget(self.pad, 0, Qt.AlignCenter)
        layout.addWidget(self.value_label)
        layout.addLayout(btn_layout)

    def set_initial_values(self, gamma: float, mid: float):
        """Sets the initial position."""
        # Validate ranges
        gamma = max(0.1, min(3.0, gamma))
        mid = max(0.0, min(0.9, mid))
        
        self.pad._gamma = gamma
        self.pad._mid = mid
        self.pad.update()
        self._on_pad_change(gamma, mid)
        
    def _reset_values(self):
        """Reset to default"""
        self.set_initial_values(1.0, 0.0)
        self.adjustment_changed.emit(1.0, 0.0)
        
    def _on_pad_change(self, gamma: float, mid: float):
        self._current_gamma = gamma
        self._current_mid = mid
        self.value_label.setText(f"Gamma: {gamma:.2f}  |  Mid: {mid:.2f}")

    def get_values(self) -> tuple[float, float] | None:
        """Returns (gamma, mid) if accepted."""
        if self.result() == QDialog.Accepted:
            return self._current_gamma, self._current_mid
        return None