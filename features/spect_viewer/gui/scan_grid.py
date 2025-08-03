# features\spect_viewer\gui\scan_grid.py
from pathlib import Path
from typing import List
from PySide6.QtCore   import Qt
from PySide6.QtGui    import QPixmap
from PySide6.QtWidgets import (
    QWidget, QTabWidget, QScrollArea, QGridLayout,
    QVBoxLayout, QLabel
)


class ScanGridWidget(QWidget):
    """Scrollable grid 2-column (anterior/posterior) for a single scan."""

    def __init__(self, image_paths: List[Path], parent: QWidget | None = None) -> None:
        super().__init__(parent)

        scroll    = QScrollArea(widgetResizable=True)
        container = QWidget()
        grid      = QGridLayout(container, spacing=16, contentsMargins=(12, 12, 12, 12))

        for col, path in enumerate(image_paths):
            pix = QPixmap(str(path)).scaledToWidth(260, Qt.SmoothTransformation)
            img_lbl = QLabel(alignment=Qt.AlignCenter, pixmap=pix)
            txt_lbl = QLabel(path.stem, alignment=Qt.AlignCenter)

            grid.addWidget(img_lbl, 0, col)
            grid.addWidget(txt_lbl, 1, col)

        scroll.setWidget(container)
        QVBoxLayout(self).addWidget(scroll)


class ScanTabs(QTabWidget):
    """Dynamic set of tabs: Scan 1 | Scan 2 | …"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabPosition(QTabWidget.North)
        self.setMovable(True)

    def add_scan(self, title: str, image_paths: List[Path]) -> None:
        idx = self.addTab(ScanGridWidget(image_paths), title)
        self.setCurrentIndex(idx)
