# frontend/widgets/scan_timeline.py
from __future__ import annotations
from pathlib import Path
from typing  import List, Dict

from datetime import datetime
import numpy as np

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QScrollArea, QFrame
)


# --------------------------- helpers -----------------------------------------
def _array_to_pixmap(arr: np.ndarray, width: int) -> QPixmap:
    """
    Convert ndarray (H×W, uint16/uint8/float) ke QPixmap ter-scale.
    """
    arr_f = arr.astype(np.float32)
    mn, mx = float(arr_f.min()), float(arr_f.max())
    if mx > mn:
        arr_f = (arr_f - mn) / (mx - mn) * 255.0
    img_u8 = arr_f.astype(np.uint8)

    h, w = img_u8.shape
    qim   = QImage(img_u8.data, w, h, w, QImage.Format_Grayscale8)
    return QPixmap.fromImage(qim).scaledToWidth(width, Qt.SmoothTransformation)


def _png_to_pixmap(png: Path, width: int) -> QPixmap | None:
    if not png.exists():
        return None
    return QPixmap(str(png)).scaledToWidth(width, Qt.SmoothTransformation)


# --------------------------- main widget -------------------------------------
class ScanTimelineWidget(QScrollArea):
    """
    Timeline horizontal berisi kartu tiap scan.
    • current_view : "Anterior" | "Posterior"
    • current_mode : "Original" | "Segmentation"
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.container    = QWidget()
        self.main_layout  = QHBoxLayout(self.container)
        self.main_layout.setAlignment(Qt.AlignLeft)

        self.setWidget(self.container)

        # state
        self.current_view = "Anterior"
        self.current_mode = "Original"
        self._scans_cache: List[Dict] = []
        self._zoom_factor = 1.0  ## Keep track of the current zoom level

    ## --- NEW: Corrected Zoom Logic --- ##
    def zoom_in(self):
        """Zooms in by increasing the zoom factor and rebuilding the UI."""
        self._zoom_factor *= 1.2
        self._rebuild() # Rebuild the cards at the new size

    def zoom_out(self):
        """Zooms out by decreasing the zoom factor and rebuilding the UI."""
        self._zoom_factor *= 0.8
        self._rebuild() # Rebuild the cards at the new size
    ## --- End of Corrected Zoom Logic --- ##

    # ---------------------------------------------------------------- public
    def display_timeline(self, scans: List[Dict]) -> None:
        """
        scans: list[{"meta":dict, "frames":dict[str,np.ndarray], "path":Path}]
        """
        self._scans_cache = scans
        self._zoom_factor = 1.0  # Reset zoom whenever a new patient is loaded
        self._rebuild()

    def set_active_view(self, view: str) -> None:
        self.current_view = view
        self._rebuild()

    def set_image_mode(self, mode: str) -> None:
        self.current_mode = mode
        self._rebuild()

    def scroll_to_scan(self, idx: int) -> None:
        if 0 <= idx < self.main_layout.count():
            item = self.main_layout.itemAt(idx)
            if item and item.widget():
                self.horizontalScrollBar().setValue(item.widget().pos().x())

    # ---------------------------------------------------------------- private
    def _clear(self) -> None:
        while self.main_layout.count():
            child = self.main_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _rebuild(self) -> None:
        self._clear()
        if not self._scans_cache:
            self.main_layout.addWidget(
                QLabel("No scans to display.", alignment=Qt.AlignCenter)
            )
            return

        ## --- CHANGE: Calculate the zoomed width here --- ##
        # We use the zoom factor to determine the width for the images.
        zoomed_width = int(220 * self._zoom_factor)

        for scan in self._scans_cache:
            ## Pass the calculated width to the card maker ##
            self.main_layout.addWidget(self._make_card(scan, zoomed_width))

        self.main_layout.addStretch()

    def _make_card(self, scan: Dict, image_width: int) -> QFrame: ## <-- CHANGED: Added image_width parameter
        card = QFrame()
        card.setObjectName("ScanCard")
        lay  = QVBoxLayout(card)

        # -------- header ----------------------------------------------------
        meta = scan["meta"]
        date_raw = meta.get("study_date", "")
        try:
            hdr_date = datetime.strptime(date_raw, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError:
            hdr_date = "Unknown"

        bsi = meta.get("bsi_value", "N/A")
        lay.addWidget(QLabel(f"<b>{hdr_date}</b>     BSI {bsi}", alignment=Qt.AlignLeft))

        # -------- image -----------------------------------------------------
        img_lbl = QLabel(alignment=Qt.AlignCenter)
        # img_lbl.setMinimumSize(220, 500) # We don't need this anymore as size is controlled by the pixmap

        if self.current_mode == "Original":
            frame_map = scan["frames"]
            if self.current_view in frame_map:
                ## Use the new image_width parameter instead of a fixed value ##
                pix = _array_to_pixmap(frame_map[self.current_view], image_width)
                img_lbl.setPixmap(pix)
            else:
                img_lbl.setText(f"'{self.current_view}' view not available")
                img_lbl.setStyleSheet("color:#888;")
        else:  # "Segmentation"
            dicom_path: Path = scan["path"]
            base = dicom_path.stem
            png  = dicom_path.with_name(
                f"{base}_{self.current_view.lower()}_colored.png"
            )
            ## Use the new image_width parameter instead of a fixed value ##
            pix = _png_to_pixmap(png, image_width)
            if pix:
                img_lbl.setPixmap(pix)
            else:
                img_lbl.setText("Segmentation not found")
                img_lbl.setStyleSheet("color:#888;")

        lay.addWidget(img_lbl)

        # -------- footer label ---------------------------------------------
        lay.addWidget(QLabel(self.current_view, alignment=Qt.AlignCenter))
        return card