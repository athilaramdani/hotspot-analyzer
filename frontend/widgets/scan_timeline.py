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
        self.active_scan_index = 0
        self._zoom_factor = 1.0
        self.card_width = 350   ## Keep track of the current zoom level

    def _clear_layout(self) -> None:
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def set_active_scan(self, index: int) -> None:
        self.active_scan_index = index
        self._rebuild()


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
    def display_timeline(self, scans: List[Dict], active_index: int = -1) -> None:

        """
        scans: list[{"meta":dict, "frames":dict[str,np.ndarray], "path":Path}]
        """
        self._scans_cache = scans
        self._zoom_factor = 1.0  # Reset zoom whenever a new patient is loaded
        self.active_scan_index = active_index
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
        self._clear_layout()

        if not self._scans_cache:
            self.main_layout.addWidget(QLabel("No scans to display"))
            return

        zoomed_width = int(self.card_width * self._zoom_factor)

        # --- Logika Baru Berdasarkan Mode ---
        
        if self.current_mode == "Original":
            # Tampilkan SEMUA gambar original dengan header
            for scan in self._scans_cache:
                # Buat widget vertikal untuk menampung header + gambar
                mini_card_widget = QWidget()
                mini_card_layout = QVBoxLayout(mini_card_widget)
                
                # 1. Buat Header
                meta = scan["meta"]
                date_raw = meta.get("study_date", "")
                try:
                    hdr_date = datetime.strptime(date_raw, "%Y%m%d").strftime("%b %d, %Y")
                except ValueError:
                    hdr_date = "Unknown"
                bsi = meta.get("bsi_value", "N/A")
                header_label = QLabel(f"<b>{hdr_date}</b>   BSI {bsi}")
                mini_card_layout.addWidget(header_label)

                # 2. Buat Gambar
                frame_map = scan["frames"]
                if self.current_view in frame_map:
                    pix = _array_to_pixmap(frame_map[self.current_view], zoomed_width)
                    img_label = QLabel()
                    img_label.setPixmap(pix)
                    mini_card_layout.addWidget(img_label)
                
                self.main_layout.addWidget(mini_card_widget)

        elif self.current_mode == "Segmentation":
            # Tampilkan SEMUA gambar segmentasi dengan header
            for scan in self._scans_cache:
                # Buat widget vertikal untuk menampung header + gambar
                mini_card_widget = QWidget()
                mini_card_layout = QVBoxLayout(mini_card_widget)
                
                # 1. Buat Header
                meta = scan["meta"]
                date_raw = meta.get("study_date", "")
                try:
                    hdr_date = datetime.strptime(date_raw, "%Y%m%d").strftime("%b %d, %Y")
                except ValueError:
                    hdr_date = "Unknown"
                bsi = meta.get("bsi_value", "N/A")
                header_label = QLabel(f"<b>{hdr_date}</b>   BSI {bsi}")
                mini_card_layout.addWidget(header_label)

                # 2. Buat Gambar
                dicom_path: Path = scan["path"]
                base = dicom_path.stem
                seg_path = dicom_path.with_name(f"{base}_{self.current_view.lower()}_colored.png")
                seg_pix = _png_to_pixmap(seg_path, zoomed_width)
                if seg_pix:
                    img_label = QLabel()
                    img_label.setPixmap(seg_pix)
                    mini_card_layout.addWidget(img_label)

                self.main_layout.addWidget(mini_card_widget)

        else:  # Mode "Both" (default)
            # Tampilkan HANYA SATU kartu untuk scan yang aktif
            if 0 <= self.active_scan_index < len(self._scans_cache):
                scan = self._scans_cache[self.active_scan_index]
                card = self._make_card(scan, zoomed_width)
                self.main_layout.addWidget(card)

        self.main_layout.addStretch()

    # KODE BARU (hanya 2 argumen)
    def _make_card(self, scan: Dict, image_width: int) -> QFrame:

        card = QFrame()
        card.setObjectName("ScanCard")
        lay = QVBoxLayout(card)

        meta = scan["meta"]
        date_raw = meta.get("study_date", "")
        try:
            hdr_date = datetime.strptime(date_raw, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError:
            hdr_date = "Unknown"
        bsi = meta.get("bsi_value", "N/A")
        lay.addWidget(QLabel(f"<b>{hdr_date}</b>     BSI {bsi}", alignment=Qt.AlignLeft))

        # Image row: Original + Segmentation
        image_row = QHBoxLayout()

        # --- Original ---
        orig_lbl = QLabel(alignment=Qt.AlignCenter)
        frame_map = scan["frames"]
        if self.current_view in frame_map:
            pix = _array_to_pixmap(frame_map[self.current_view], image_width)
            orig_lbl.setPixmap(pix)
        else:
            orig_lbl.setText(f"No {self.current_view} view")
            orig_lbl.setStyleSheet("color:#888;")
        image_row.addWidget(orig_lbl)

        # --- Segmentation ---
        seg_lbl = QLabel(alignment=Qt.AlignCenter)
        dicom_path: Path = scan["path"]
        base = dicom_path.stem
        seg_path = dicom_path.with_name(f"{base}_{self.current_view.lower()}_colored.png")
        seg_pix = _png_to_pixmap(seg_path, image_width)
        if seg_pix:
            seg_lbl.setPixmap(seg_pix)
        else:
            seg_lbl.setText("Segmentation not found")
            seg_lbl.setStyleSheet("color:#888;")
        image_row.addWidget(seg_lbl)

        lay.addLayout(image_row)

        # Footer: view name
        lay.addWidget(QLabel(self.current_view, alignment=Qt.AlignCenter))

        return card


    def _make_single_image(self, frame_map: Dict, seg_path: Path, image_width: int, mode: str) -> QLabel:
        lbl = QLabel(alignment=Qt.AlignCenter)

        if mode == "Original":
            if self.current_view in frame_map:
                pix = _array_to_pixmap(frame_map[self.current_view], image_width)
                lbl.setPixmap(pix)
            else:
                lbl.setText(f"No {self.current_view} view")
                lbl.setStyleSheet("color:#888;")
        elif mode == "Segmentation":
            pix = _png_to_pixmap(seg_path, image_width)
            if pix:
                lbl.setPixmap(pix)
            else:
                lbl.setText("Segmentation not found")
                lbl.setStyleSheet("color:#888;")

        return lbl
    def _make_dual_image_row(self, frame_map: Dict, seg_path: Path, image_width: int) -> QHBoxLayout:
        row = QHBoxLayout()

        # --- Original ---
        orig_lbl = QLabel(alignment=Qt.AlignCenter)
        if self.current_view in frame_map:
            pix = _array_to_pixmap(frame_map[self.current_view], image_width)
            orig_lbl.setPixmap(pix)
        else:
            orig_lbl.setText(f"No {self.current_view} view")
            orig_lbl.setStyleSheet("color:#888;")
        row.addWidget(orig_lbl)

        # --- Segmentation ---
        seg_lbl = QLabel(alignment=Qt.AlignCenter)
        seg_pix = _png_to_pixmap(seg_path, image_width)
        if seg_pix:
            seg_lbl.setPixmap(seg_pix)
        else:
            seg_lbl.setText("Segmentation not found")
            seg_lbl.setStyleSheet("color:#888;")
        row.addWidget(seg_lbl)

        return row

