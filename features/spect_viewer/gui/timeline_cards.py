# features/spect_viewer/gui/timeline_cards.py
"""
Card rendering UI components for timeline widget
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional, Callable
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)


class TimelineCard(QFrame):
    """Individual timeline card for displaying scan data"""
    
    # Signals
    selected = Signal(int)  # Emit index when card is selected
    
    def __init__(self, scan_data: Dict, scan_index: int, card_width: int, parent=None):
        super().__init__(parent)
        self.scan_data = scan_data
        self.scan_index = scan_index
        self.card_width = card_width
        self.is_active = False
        
        self._build_ui()
    
    def _build_ui(self):
        """Build card UI"""
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        self._update_card_style()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Header with scan info and select button
        header_layout = self._create_header()
        layout.addLayout(header_layout)
        
        # Image display area
        self.image_label = QLabel(alignment=Qt.AlignCenter)
        self.image_label.setMinimumHeight(200)
        layout.addWidget(self.image_label)
        
        # Status footer
        self.status_label = QLabel("No data")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #495057;
                padding: 4px;
                background: #e9ecef;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.status_label)
    
    def _create_header(self) -> QHBoxLayout:
        """Create header with scan info and select button"""
        meta = self.scan_data["meta"]
        date_raw = meta.get("study_date", "")
        
        try:   
            date_str = datetime.strptime(date_raw, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError: 
            date_str = "Unknown"
        
        bsi = meta.get("bsi_value", "N/A")
        
        header_layout = QHBoxLayout()
        
        # Header info
        header_label = QLabel(f"<b>{date_str}</b><br>BSI: {bsi}")
        header_label.setStyleSheet("font-size: 11px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        
        # Select button
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
        select_btn.clicked.connect(lambda: self.selected.emit(self.scan_index))
        header_layout.addWidget(select_btn)
        
        return header_layout
    
    def set_active(self, active: bool):
        """Set card active state"""
        self.is_active = active
        self._update_card_style()
    
    def _update_card_style(self):
        """Update card styling based on active state"""
        if self.is_active:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #4e73ff;
                    border-radius: 6px;
                    background-color: #f0f4ff;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    background-color: white;
                }
                QFrame:hover {
                    border: 1px solid #4e73ff;
                }
            """)
    
    def set_image(self, image: Optional[Image.Image]):
        """Set card image"""
        if image is None:
            self.image_label.setText("No layer data available")
            self.image_label.setStyleSheet("color:#888; font-size: 12px; padding: 20px;")
            return
        
        try:
            # Convert PIL image to QPixmap
            pixmap = self._pil_to_pixmap(image, self.card_width)
            self.image_label.setPixmap(pixmap)
            self.image_label.setStyleSheet("")  # Clear any text styling
        except Exception as e:
            print(f"[ERROR] Failed to set card image: {e}")
            self.image_label.setText("Error loading image")
            self.image_label.setStyleSheet("color:#dc3545; font-size: 12px; padding: 20px;")
    
    def set_status(self, current_view: str, active_layers: List[str] = None):
        """Set card status text"""
        if active_layers:
            layer_text = ", ".join(active_layers)
            tooltip_text = f"Active layers: {layer_text}"
        else:
            tooltip_text = "No active layers"
        
        self.status_label.setText(current_view)
        self.status_label.setToolTip(tooltip_text)
    
    def set_tooltip_info(self, active_layers: List[str], opacities: Dict[str, float]):
        """Set detailed tooltip with layer info"""
        if not active_layers:
            self.setToolTip("No active layers")
            return
        
        tooltip_parts = []
        for layer_name in active_layers:
            opacity_pct = int(opacities.get(layer_name, 1.0) * 100)
            tooltip_parts.append(f"{layer_name}: {opacity_pct}%")
        
        tooltip_text = "Active layers: " + " | ".join(tooltip_parts)
        self.setToolTip(tooltip_text)
    
    def _pil_to_pixmap(self, pil_image: Image.Image, width: int) -> QPixmap:
        """Convert PIL Image to QPixmap with scaling"""
        # Handle different PIL Image modes
        if pil_image.mode == 'RGBA':
            # Create white background for transparency display
            background = Image.new('RGB', pil_image.size, (255, 255, 255))
            display_image = Image.alpha_composite(background.convert('RGBA'), pil_image)
            display_image = display_image.convert('RGB')
        elif pil_image.mode == 'RGB':
            display_image = pil_image
        elif pil_image.mode == 'L':
            display_image = pil_image
        else:
            # Convert to RGB if other format
            display_image = pil_image.convert('RGB')
        
        # Convert to numpy array
        np_array = np.array(display_image)
        
        if len(np_array.shape) == 3:
            # RGB image
            height, width_orig, channels = np_array.shape
            bytes_per_line = channels * width_orig
            q_image = QImage(np_array.data, width_orig, height, bytes_per_line, QImage.Format_RGB888)
        else:
            # Grayscale image
            height, width_orig = np_array.shape
            q_image = QImage(np_array.data, width_orig, height, width_orig, QImage.Format_Grayscale8)
        
        return QPixmap.fromImage(q_image).scaledToWidth(width, Qt.SmoothTransformation)


class PlaceholderCard(QFrame):
    """Placeholder card for when no data is available"""
    
    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.message = message
        self._build_ui()
    
    def _build_ui(self):
        """Build placeholder UI"""
        layout = QVBoxLayout(self)
        
        label = QLabel(self.message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 14px;
                padding: 40px;
                background: #f8f9fa;
                border: 2px dashed #dee2e6;
                border-radius: 8px;
            }
        """)
        
        layout.addWidget(label)


class CardFactory:
    """Factory for creating different types of timeline cards"""
    
    @staticmethod
    def create_scan_card(scan_data: Dict, scan_index: int, card_width: int, 
                        select_callback: Callable[[int], None]) -> TimelineCard:
        """Create a scan card"""
        card = TimelineCard(scan_data, scan_index, card_width)
        card.selected.connect(select_callback)
        return card
    
    @staticmethod
    def create_placeholder_card(message: str) -> PlaceholderCard:
        """Create a placeholder card"""
        return PlaceholderCard(message)
    
    @staticmethod
    def create_no_scans_card() -> PlaceholderCard:
        """Create card for when no scans are available"""
        return CardFactory.create_placeholder_card("No scans available")
    
    @staticmethod
    def create_no_layers_card() -> PlaceholderCard:
        """Create card for when no layers are selected"""
        return CardFactory.create_placeholder_card("No layers selected\nPlease select layers to display")