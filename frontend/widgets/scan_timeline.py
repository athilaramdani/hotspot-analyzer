from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QFrame
from typing import List, Dict
from datetime import datetime
import numpy as np
from PySide6.QtGui import QPixmap, QImage

def _array_to_pixmap(arr: np.ndarray, width: int) -> QPixmap:
    img_float = arr.astype(np.float32); min_val, max_val = img_float.min(), img_float.max()
    if max_val > min_val: img_float = (img_float - min_val) / (max_val - min_val) * 255
    img_uint8 = img_float.astype(np.uint8); height, width_orig = img_uint8.shape
    q_image = QImage(img_uint8.data, width_orig, height, width_orig, QImage.Format_Grayscale8)
    return QPixmap.fromImage(q_image).scaledToWidth(width, Qt.SmoothTransformation)

class ScanTimelineWidget(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded); self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.container = QWidget(); self.main_layout = QHBoxLayout(self.container)
        self.main_layout.setAlignment(Qt.AlignLeft); self.setWidget(self.container)
        self.current_view = "Anterior"; self.scans_data_cache: List[Dict] = []

    def _clear_timeline(self):
        while self.main_layout.count():
            child = self.main_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

    def display_timeline(self, scans: List[Dict]):
        self.scans_data_cache = scans; self._clear_timeline()
        if not scans: self.main_layout.addWidget(QLabel("No scans to display.", alignment=Qt.AlignCenter)); return
        for scan_data in self.scans_data_cache: self.main_layout.addWidget(self._create_scan_card(scan_data))
        self.main_layout.addStretch()

    def set_active_view(self, view_name: str):
        self.current_view = view_name; self.display_timeline(self.scans_data_cache)
    
    def scroll_to_scan(self, index: int):
        if 0 <= index < self.main_layout.count():
            widget_item = self.main_layout.itemAt(index)
            if widget_item and widget_item.widget(): self.horizontalScrollBar().setValue(widget_item.widget().pos().x())

    def _create_scan_card(self, scan_data: Dict) -> QWidget:
        card = QFrame(); card.setObjectName("ScanCard"); card_layout = QVBoxLayout(card)
        meta = scan_data["meta"]; study_date_str = meta.get("study_date", "")
        try: formatted_date = datetime.strptime(study_date_str, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError: formatted_date = "Unknown Date"
        bsi_value = meta.get("bsi_value", "N/A%")
        header_label = QLabel(f"<b>{formatted_date}</b> &nbsp;&nbsp; BSI {bsi_value}")
        image_label = QLabel(alignment=Qt.AlignCenter); image_label.setMinimumSize(220, 500)
        frames = scan_data["frames"]
        if self.current_view in frames: image_label.setPixmap(_array_to_pixmap(frames[self.current_view], width=220))
        else: image_label.setText(f"'{self.current_view}' view not available"); image_label.setStyleSheet("color: #888;")
        footer_label = QLabel(self.current_view, alignment=Qt.AlignCenter)
        card_layout.addWidget(header_label); card_layout.addWidget(image_label); card_layout.addWidget(footer_label)
        return card