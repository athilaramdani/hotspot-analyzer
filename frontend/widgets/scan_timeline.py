# =====================================================================
# frontend/widgets/scan_timeline.py   – v2 (with SegmentationEditorDialog)
# ---------------------------------------------------------------------
from __future__ import annotations
from pathlib import Path
from typing  import List, Dict
from datetime import datetime

import numpy as np
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton
)

from .segmentation_editor_dialog import SegmentationEditorDialog
from pydicom import dcmread


# --------------------------- helpers -----------------------------------------
def _array_to_pixmap(arr: np.ndarray, width: int) -> QPixmap:
    arr_f = arr.astype(np.float32)
    arr_f = (arr_f - arr_f.min()) / max(1, np.ptp(arr_f)) * 255.0
    img_u8 = arr_f.astype(np.uint8)
    h, w = img_u8.shape
    qim   = QImage(img_u8.data, w, h, w, QImage.Format_Grayscale8)
    return QPixmap.fromImage(qim).scaledToWidth(width, Qt.SmoothTransformation)



def _png_to_pixmap(png: Path, width: int) -> QPixmap | None:
    return (QPixmap(str(png)).scaledToWidth(width, Qt.SmoothTransformation)
            if png.exists() else None)


# --------------------------- main widget -------------------------------------
class ScanTimelineWidget(QScrollArea):
    """
    Timeline horizontal berisi kartu tiap scan.
    current_view : "Anterior" | "Posterior"
    current_mode : "Original" | "Segmentation" | "Both"
    """
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.container   = QWidget()
        self.main_layout = QHBoxLayout(self.container)
        self.main_layout.setAlignment(Qt.AlignLeft)
        self.setWidget(self.container)

        # state
        self.current_view  = "Anterior"
        self.current_mode  = "Original"
        self._scans_cache: List[Dict] = []
        self.active_scan_index = 0
        self._zoom_factor = 1.0
        self.card_width   = 350
        

    # ------------------------------------------------------ zoom
    def zoom_in(self):  self._zoom_factor *= 1.2; self._rebuild()
    def zoom_out(self): self._zoom_factor *= 0.8; self._rebuild()

    # ------------------------------------------------------ public API
    def display_timeline(self, scans: List[Dict], active_index: int = -1):
        print(f"[DEBUG] display_timeline dipanggil dengan {len(scans)} scan(s), active_index = {active_index}")
        self._scans_cache      = scans
        self.active_scan_index = active_index
        self._zoom_factor      = 1.0
        self._rebuild()

    def set_active_view(self, v: str): self.current_view = v; self._rebuild()
    def set_image_mode (self, m: str): self.current_mode = m; self._rebuild()

    # ------------------------------------------------------ rebuild
    def _clear(self):
        while self.main_layout.count():
            w = self.main_layout.takeAt(0).widget()
            if w: w.deleteLater()

    def _rebuild(self):
        self._clear()
        if not self._scans_cache:
            self.main_layout.addWidget(QLabel("No scans"))
            return

        w = int(self.card_width * self._zoom_factor)
        if self.current_mode in ("Original", "Segmentation"):
            for i, scan in enumerate(self._scans_cache):
                self.main_layout.addWidget(self._make_single(scan, w, i))
        else:   # Both
            idx = self.active_scan_index
            if 0 <= idx < len(self._scans_cache):
                self.main_layout.addWidget(self._make_dual(
                    self._scans_cache[idx], w, idx))

        self.main_layout.addStretch()

    # ------------------------------------------------------ card builders
    def _make_header(self, scan: Dict, idx: int) -> QHBoxLayout:
        meta = scan["meta"]
        date_raw = meta.get("study_date","")
        try:   hdr = datetime.strptime(date_raw,"%Y%m%d").strftime("%b %d, %Y")
        except ValueError: hdr = "Unknown"
        bsi = meta.get("bsi_value", "N/A")

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel(f"<b>{hdr}</b>   BSI {bsi}"))
        hbox.addStretch()
        btn = QPushButton("Edit"); btn.setFixedSize(60,24)
        btn.clicked.connect(lambda *_: self._open_editor(idx))
        hbox.addWidget(btn)
        return hbox
    
   

    
    def _make_single(self, scan: Dict, w: int, idx: int) -> QFrame:
        card, lay = QFrame(), QVBoxLayout()
        card.setLayout(lay)
        lay.addLayout(self._make_header(scan, idx))

        frame_map = scan["frames"]
        dicom = scan["path"]
        filename = dicom.stem  # contoh: '11'
        seg_png = dicom.parent / f"{filename}_{self.current_view.lower()}_colored.png"


        print(f"[DEBUG] Looking for segmentation PNG: {seg_png}")
        print(f"        Exists? {seg_png.exists()}")

        lbl = QLabel(alignment=Qt.AlignCenter)
        if self.current_mode == "Original":
            if self.current_view in frame_map:
                lbl.setPixmap(_array_to_pixmap(frame_map[self.current_view], w))
            else:
                lbl.setText("No view"); lbl.setStyleSheet("color:#888;")
        else:
            pix = _png_to_pixmap(seg_png, w)
            lbl.setPixmap(pix) if pix else lbl.setText("Seg not found")
        lay.addWidget(lbl)
        lay.addWidget(QLabel(self.current_view, alignment=Qt.AlignCenter))
        return card

    def _make_dual(self, scan: Dict, w: int, idx: int) -> QFrame:
        card, lay = QFrame(), QVBoxLayout()
        card.setLayout(lay)
        lay.addLayout(self._make_header(scan, idx))

        row = QHBoxLayout()
        frame_map = scan["frames"]
        dicom = scan["path"]
        base  = dicom.with_suffix("")
        seg_png = base.with_name(f"{base.stem}_{self.current_view.lower()}_colored.png")


        print(f"[DEBUG] Looking for segmentation PNG: {seg_png}")
        print(f"        Exists? {seg_png.exists()}")
        
        # original
        o = QLabel(alignment=Qt.AlignCenter)
        pix_o = ( _array_to_pixmap(frame_map[self.current_view], w)
                  if self.current_view in frame_map else None )
        o.setPixmap(pix_o) if pix_o else o.setText("No view")
        row.addWidget(o)

        # segmentation
        s = QLabel(alignment=Qt.AlignCenter)
        pix_s = _png_to_pixmap(seg_png, w)
        s.setPixmap(pix_s) if pix_s else s.setText("Seg not found")
        row.addWidget(s)

        lay.addLayout(row)
        lay.addWidget(QLabel(self.current_view, alignment=Qt.AlignCenter))
        return card

    # ------------------------------------------------------ editor popup
    def _open_editor(self, idx: int):
        if not (0 <= idx < len(self._scans_cache)): return
        dlg = SegmentationEditorDialog(self._scans_cache[idx],
                                       self.current_view,
                                       parent=self)
        if dlg.exec():   # on save success → refresh
            self._rebuild()
