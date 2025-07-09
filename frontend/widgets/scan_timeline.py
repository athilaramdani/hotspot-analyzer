# =====================================================================
# frontend/widgets/scan_timeline.py   – v3 (with Hotspot support)
# ---------------------------------------------------------------------
from __future__ import annotations
from pathlib import Path
from typing  import List, Dict
from datetime import datetime

import numpy as np
from PIL import Image
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton
)

from .segmentation_editor_dialog import SegmentationEditorDialog
from .hotspot_editor_dialog import HotspotEditorDialog
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


def _pil_to_pixmap(pil_image: Image.Image, width: int) -> QPixmap:
    """Convert PIL Image to QPixmap with scaling."""
    # Convert PIL Image to numpy array
    if pil_image.mode == 'RGB':
        # RGB image
        np_array = np.array(pil_image)
        height, width_orig, channels = np_array.shape
        bytes_per_line = channels * width_orig
        q_image = QImage(np_array.data, width_orig, height, bytes_per_line, QImage.Format_RGB888)
    elif pil_image.mode == 'L':
        # Grayscale image
        np_array = np.array(pil_image)
        height, width_orig = np_array.shape
        q_image = QImage(np_array.data, width_orig, height, width_orig, QImage.Format_Grayscale8)
    else:
        # Convert to RGB if other format
        pil_image = pil_image.convert('RGB')
        np_array = np.array(pil_image)
        height, width_orig, channels = np_array.shape
        bytes_per_line = channels * width_orig
        q_image = QImage(np_array.data, width_orig, height, bytes_per_line, QImage.Format_RGB888)
    
    return QPixmap.fromImage(q_image).scaledToWidth(width, Qt.SmoothTransformation)


# --------------------------- main widget -------------------------------------
class ScanTimelineWidget(QScrollArea):
    """
    Timeline horizontal berisi kartu tiap scan.
    current_view : "Anterior" | "Posterior"
    current_mode : "Original" | "Segmentation" | "Hotspot" | "Both"
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
        if self.current_mode in ("Original", "Segmentation", "Hotspot"):
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
    
   



    def _get_hotspot_frame(self, scan: Dict, view: str) -> np.ndarray | None:
        """Get hotspot frame for a specific view."""
        if view == "Anterior":
            hotspot_frames = scan.get("hotspot_frames_ant", [])
        elif view == "Posterior":
            hotspot_frames = scan.get("hotspot_frames_post", [])
        else:
            hotspot_frames = scan.get("hotspot_frames", [])
        
        # Get the frame index for this view
        frame_map = scan["frames"]
        if view in frame_map and hotspot_frames:
            frame_idx = list(frame_map.keys()).index(view) if view in frame_map else 0
            if frame_idx < len(hotspot_frames):
                return hotspot_frames[frame_idx]
        return None

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
        
        elif self.current_mode == "Segmentation":
            pix = _png_to_pixmap(seg_png, w)
            lbl.setPixmap(pix) if pix else lbl.setText("Seg not found")
        
        elif self.current_mode == "Hotspot":
            patient_id = base.parent.name
            v = "ant" if "ant" in self.current_view.lower() else "post"
            hotspot_png = Path(f"data/{patient_id}/{patient_id}_{v}_hotspot_colored.png")

            if hotspot_png.exists() and self.current_view in frame_map:
                try:
                    raw_arr = frame_map[self.current_view]
                    raw_pil = Image.fromarray(((raw_arr - raw_arr.min()) / max(1, raw_arr.ptp()) * 255).astype(np.uint8)).convert("RGB")
                    overlay_pil = Image.open(hotspot_png).convert("RGB")

                    # Resize if mismatch (safety)
                    if overlay_pil.size != raw_pil.size:
                        overlay_pil = overlay_pil.resize(raw_pil.size)

                    # Blend with fixed alpha (e.g. 0.5)
                    blended = Image.blend(raw_pil, overlay_pil, alpha=0.5)
                    lbl.setPixmap(_pil_to_pixmap(blended, w))
                except Exception as e:
                    lbl.setText("Error overlaying")
                    lbl.setToolTip(str(e))
                    lbl.setStyleSheet("color:#888;")
            else:
                # Fallback to hotspot frame logic
                hotspot_frame = self._get_hotspot_frame(scan, self.current_view)
                if hotspot_frame is not None:
                    if isinstance(hotspot_frame, Image.Image):
                        lbl.setPixmap(_pil_to_pixmap(hotspot_frame, w))
                    elif isinstance(hotspot_frame, np.ndarray):
                        lbl.setPixmap(_array_to_pixmap(hotspot_frame, w))
                elif self.current_view in frame_map:
                    lbl.setPixmap(_array_to_pixmap(frame_map[self.current_view], w))
                    lbl.setToolTip("Hotspot PNG not available - showing original")
                else:
                    lbl.setText("No hotspot data")
                    lbl.setStyleSheet("color:#888;")
        
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

        # Right side - depends on what mode we're comparing with
        s = QLabel(alignment=Qt.AlignCenter)
        
        # For "Both" mode, show segmentation and hotspot side by side
        if self.current_mode == "Both":
            # Create a container for segmentation and hotspot
            both_container = QWidget()
            both_layout = QVBoxLayout(both_container)
            
            # Segmentation
            seg_label = QLabel("Segmentation", alignment=Qt.AlignCenter)
            seg_label.setStyleSheet("font-size: 10px; color: #666;")
            seg_img = QLabel(alignment=Qt.AlignCenter)
            pix_s = _png_to_pixmap(seg_png, w//2)
            seg_img.setPixmap(pix_s) if pix_s else seg_img.setText("Seg N/A")
            
            # Hotspot
            hotspot_label = QLabel("Hotspot", alignment=Qt.AlignCenter)
            hotspot_label.setStyleSheet("font-size: 10px; color: #666;")
            hotspot_img = QLabel(alignment=Qt.AlignCenter)

            patient_id = base.parent.name
            v = "ant" if "ant" in self.current_view.lower() else "post"
            hotspot_png = Path(f"data/{patient_id}/{patient_id}_{v}_hotspot_colored.png")

            if hotspot_png.exists() and self.current_view in frame_map:
                try:
                    raw_arr = frame_map[self.current_view]
                    raw_pil = Image.fromarray(((raw_arr - raw_arr.min()) / max(1, raw_arr.ptp()) * 255).astype(np.uint8)).convert("RGB")
                    overlay_pil = Image.open(hotspot_png).convert("RGB")

                    if overlay_pil.size != raw_pil.size:
                        overlay_pil = overlay_pil.resize(raw_pil.size)

                    blended = Image.blend(raw_pil, overlay_pil, alpha=0.5)
                    hotspot_img.setPixmap(_pil_to_pixmap(blended, w // 2))
                except Exception as e:
                    hotspot_img.setText("Error overlaying")
                    hotspot_img.setToolTip(str(e))
                    hotspot_img.setStyleSheet("color:#888;")
            else:
                hotspot_frame = self._get_hotspot_frame(scan, self.current_view)
                if hotspot_frame is not None:
                    if isinstance(hotspot_frame, Image.Image):
                        hotspot_img.setPixmap(_pil_to_pixmap(hotspot_frame, w // 2))
                    elif isinstance(hotspot_frame, np.ndarray):
                        hotspot_img.setPixmap(_array_to_pixmap(hotspot_frame, w // 2))
                elif self.current_view in frame_map:
                    hotspot_img.setPixmap(_array_to_pixmap(frame_map[self.current_view], w // 2))
                    hotspot_img.setToolTip("Hotspot PNG not available - showing original")
                else:
                    hotspot_img.setText("Hotspot N/A")
            
            both_layout.addWidget(seg_label)
            both_layout.addWidget(seg_img)
            both_layout.addWidget(hotspot_label)
            both_layout.addWidget(hotspot_img)
            
            row.addWidget(both_container)
        else:
            # Original "Both" behavior - show segmentation
            pix_s = _png_to_pixmap(seg_png, w)
            s.setPixmap(pix_s) if pix_s else s.setText("Seg not found")
            row.addWidget(s)

        lay.addLayout(row)
        lay.addWidget(QLabel(self.current_view, alignment=Qt.AlignCenter))
        return card

    # ------------------------------------------------------ editor popup
    def _open_editor(self, idx: int):
        if not (0 <= idx < len(self._scans_cache)): return
        scan = self._scans_cache[idx]
        if self.current_mode == "Hotspot":
            dlg = HotspotEditorDialog(scan, self.current_view, parent=self)
        else:
            dlg = SegmentationEditorDialog(scan, self.current_view, parent=self)
        if dlg.exec():   # on save success → refresh
            self._rebuild()