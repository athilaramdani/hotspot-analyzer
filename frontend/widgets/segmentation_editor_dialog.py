# =====================================================================
# frontend/widgets/segmentation_editor_dialog.py  – v2.1-precision-fixed
# ---------------------------------------------------------------------
"""
Full-screen dialog untuk manual edit segmentasi.

Perbaikan v2.1:
- Fix koordinat brush yang miss/meleset
- Fix loading PNG dari DICOM frames yang benar
- Improve pixel precision untuk drawing
- Better handling untuk DICOM dengan multiple frames
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
import math

import numpy as np
from PIL import Image

from PySide6.QtCore    import Qt, QRectF, QPointF, Signal
from PySide6.QtGui     import (
    QPixmap, QImage, QPainter, QColor, QPen, QWheelEvent, QCursor, QLinearGradient
)
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSlider, QWidget, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QStyleOptionGraphicsItem, QFrame
)

import pydicom
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

from backend.colorizer import label_mask_to_rgb, _PALETTE

# ---------------------------------------------------------------- label names & desc
_LABEL_INFO: List[Tuple[str, str]] = [
    ("Background", "kosong"),
    ("Skull", "Tulang tengkorak"),
    ("Cervical", "Vertebra servikal"),
    ("Thoracic", "Vertebra torakal"),
    ("Rib", "Tulang rusuk"),
    ("Sternum", "Tulang dada"),
    ("Clavicle", "Klavikula"),
    ("Scapula", "Belikat"),
    ("Humerus", "Lengan atas"),
    ("Lumbar", "Vertebra lumbal"),
    ("Sacrum", "Sakrum"),
    ("Pelvis", "Pelvis"),
    ("Femur", "Paha"),
]

class _BCPad(QWidget):
    """Pad 2-D:  X  = brightness (−1 … +1)
                Y  = contrast   (0.5 … 2.0)"""
    valueChanged = Signal(float, float)          # (brightness, contrast)

    def __init__(self, size: int = 200, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._b = 0.0          # brightness
        self._c = 1.0          # contrast
        self._dragging = False
        self._hover     = False
        self.setMouseTracking(True)              # enable hover feedback

    # ---------- helpers -------------------------------------------------
    def _emit(self):
        self.valueChanged.emit(self._b, self._c)

    def _update_from_pos(self, ev):
        # ambil posisi kursor lalu konversi → nilai B & C
        x = ev.position().x()
        y = ev.position().y()
        w, h = self.width(), self.height()
        # clamp agar tidak keluar kotak
        x = max(0, min(w, x))
        y = max(0, min(h, y))
        # map ke rentang
        self._b = (x / w) * 2.0 - 1.0            # −1 … +1
        self._c = 0.5 + (1.0 - y / h) * 1.5      # 2.0 (atas) … 0.5 (bawah)
        self._emit()
        self.update()

    # ---------- mouse events -------------------------------------------
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

    # ---------- paint ---------------------------------------------------
    def paintEvent(self, ev):
        p = QPainter(self)

        # --- background: kombinasi 2 gradient (brightness & contrast) ---
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

        # --- grid & label garis referensi ------------------------------
        center_x = self.width() // 2
        center_y = int(self.height() * (1 - (1.0 - 0.5) / 1.5))  # C=1.0 pos-Y

        # garis utama
        p.setPen(QPen(QColor(255, 255, 255, 80), 1))
        p.drawLine(center_x, 0, center_x, self.height())   # B = 0
        p.drawLine(0, center_y, self.width(), center_y)    # C = 1

        # garis kuartil
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        quarter_x = self.width() // 4
        p.drawLine(quarter_x, 0, quarter_x, self.height())
        p.drawLine(3*quarter_x, 0, 3*quarter_x, self.height())

        # label teks sederhana
        p.setPen(QColor(255, 255, 255, 180))
        fm = p.fontMetrics()
        p.drawText(5, self.height()-5, "-1")
        p.drawText(quarter_x-10, self.height()-5, "-0.5")
        p.drawText(center_x-5, self.height()-5, "0")
        p.drawText(3*quarter_x-10, self.height()-5, "+0.5")
        p.drawText(self.width()-20, self.height()-5, "+1")

        p.drawText(5, 15,  "2.0")        # contrast top
        p.drawText(5, center_y+5, "1.0") # contrast mid
        p.drawText(5, self.height()-15, "0.5")  # contrast bottom

        # --- crosshair & live indicator --------------------------------
        cx = int((self._b + 1) / 2 * self.width())
        cy = int((1 - (self._c - 0.5) / 1.5) * self.height())

        # garis live (green brightness, blue contrast)
        p.setPen(QPen(QColor(0, 255, 0, 150), 2))
        p.drawLine(cx, 0, cx, self.height())
        p.setPen(QPen(QColor(0, 150, 255, 150), 2))
        p.drawLine(0, cy, self.width(), cy)

        # crosshair dengan outline
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawLine(cx-10, cy, cx+10, cy)
        p.drawLine(cx, cy-10, cx, cy+10)
        p.setPen(QPen(QColor(255, 0, 0), 1))
        p.drawLine(cx-8, cy, cx+8, cy)
        p.drawLine(cx, cy-8, cx, cy+8)

        # lingkaran pusat
        p.setBrush(QColor(255, 0, 0))
        p.drawEllipse(cx-2, cy-2, 4, 4)

        # value tooltip di tepi
        p.setPen(QPen(QColor(255, 255, 255), 1))
        p.setBrush(QColor(0, 0, 0, 180))
        b_txt = f"B: {self._b:+.2f}"
        c_txt = f"C: {self._c:.2f}"
        b_rect = fm.boundingRect(b_txt)
        c_rect = fm.boundingRect(c_txt)
        # brightness box (bottom)
        bx = cx - b_rect.width()//2
        by = self.height() - b_rect.height() - 4
        p.drawRect(bx-2, by-2, b_rect.width()+4, b_rect.height()+4)
        p.drawText(bx, by + b_rect.height(), b_txt)
        # contrast box (right)
        cxr = self.width() - c_rect.width() - 6
        cyr = cy - c_rect.height()//2
        p.drawRect(cxr-2, cyr-2, c_rect.width()+4, c_rect.height()+4)
        p.drawText(cxr, cyr + c_rect.height(), c_txt)

        # highlight saat drag / hover
        if self._dragging:
            p.setPen(QPen(QColor(255, 255, 0, 200), 3))
            p.setBrush(QColor(255, 255, 0, 50))
            p.drawEllipse(cx-8, cy-8, 16, 16)
        elif self._hover:
            p.setPen(QPen(QColor(255, 255, 255, 150), 2))
            p.setBrush(QColor(255, 255, 255, 30))
            p.drawEllipse(cx-6, cy-6, 12, 12)

# ==================================================================== Canvas
class _Canvas(QGraphicsView):
    """Interactive view: pan, zoom, brush / eraser dengan koordinat presisi tinggi."""

    def __init__(self, orig: np.ndarray, mask: np.ndarray, parent=None):
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Default mode: drawing (no drag)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setCursor(QCursor(Qt.CrossCursor))

        # scene
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Store original dimensions
        self._img_height, self._img_width = orig.shape

        # original grayscale (opacity 0.5)
        self._orig_base = ((orig - orig.min()) / max(1, orig.ptp()) * 255).astype(np.uint8)
        gray_q = QImage(self._orig_base.data, self._img_width, self._img_height,
                        self._img_width, QImage.Format_Grayscale8).copy()
        self._item_gray = QGraphicsPixmapItem(QPixmap.fromImage(gray_q))
        self._item_gray.setOpacity(0.5)
        self._scene.addItem(self._item_gray)

        # mask layer
        self._mask_arr = mask.astype(np.uint8)
        # --- NEW: bank layer per-label ---------------------------------
        self._layers = {lbl: (self._mask_arr == lbl).astype(np.uint8)
                        for lbl in range(len(_PALETTE))}
        # ---------------------------------------------------------------
        self._mask_img = self._mask_to_qimage(show_all=False, label=1)
        self._item_mask = QGraphicsPixmapItem(QPixmap.fromImage(self._mask_img))
        self._scene.addItem(self._item_mask)

        # [OPSI] Tambah ini buat atur transparansi mask biar layer bawah kelihatan:
        self._item_mask.setOpacity(1.0)
        # -------- opacity states ---------------------------------
        self._bg_alpha = 0.0    # label-0 (background) opacity (0-1)

        
        print("===== DEBUG _Canvas =====")
        print("Shape original image:", orig.shape)
        print("Shape mask array     :", mask.shape)
        print("Unique mask values   :", np.unique(self._mask_arr))
        print("Opacity gray image   :", self._item_gray.opacity())
        print("Mask QImage size     :", self._mask_img.size())
        print("QGraphicsScene items :", self._scene.items())
        print("=========================\n")

        self._cur_label = 1
        self._brush_sz  = 1     # radius in pixels (true 1 pixel)
        self._eraser    = False
        self._show_all  = False
        self._drawing   = False
        self._pan_mode  = False

        # Zoom tracking
        self._zoom_factor = 1.0
        self.setSceneRect(QRectF(self._item_gray.boundingRect()))

        # Info callback
        self._info_callback = None

    def set_info_callback(self, callback):
        """Set callback to update info display"""
        self._info_callback = callback
        self._update_info()

    def _update_info(self):
        """Update info display with current zoom and grid info"""
        if self._info_callback:
            grid_size = 1 if self._zoom_factor >= 4.0 else int(20 / self._zoom_factor)
            self._info_callback(self._img_width, self._img_height, self._zoom_factor, grid_size)

    # -------- ndarray <-> QImage helpers
    @staticmethod
    def _nd_gray_to_qimage(arr: np.ndarray) -> QImage:
        arr_f = (arr - arr.min()) / max(1, arr.ptp()) * 255.0
        u8 = arr_f.astype(np.uint8)
        h, w = u8.shape
        return QImage(u8.data, w, h, w, QImage.Format_Grayscale8).copy()

    def _mask_to_qimage(self, *, show_all: bool, label: int) -> QImage:
        rgb = label_mask_to_rgb(self._mask_arr)          # (H, W, 3)
        h, w, _ = rgb.shape

        # build an alpha channel: fully opaque where we want to show,
        #  fully transparent everywhere else
        if show_all:
            alpha = np.full((h, w), 255, np.uint8)
            # label-0 transparency:
            alpha[self._mask_arr == 0] = int(self._bg_alpha * 255)
        else:
            sel = (self._layers[label] == 1)   
            rgb[sel] = np.array(_PALETTE[label], dtype=np.uint8)# ← inilah baris baru
            alpha = np.zeros((h, w), np.uint8)
            alpha[sel] = 255

        # stack RGB + alpha → RGBA image
        rgba = np.dstack([rgb, alpha])

        # create QImage from the raw data
        return QImage(rgba.data, w, h, 4*w, QImage.Format_RGBA8888).copy()


    # -------- public setters
    def set_brush_size(self, sz: int):        
        self._brush_sz = max(1, sz)
    
    def set_label(self, lbl: int):
        self._cur_label, self._eraser = int(lbl), False
        self._show_all = False
        self._refresh_mask()
    
    def set_eraser(self):
        self._eraser = True
        self._show_all = False
        self._refresh_mask()
    
    def toggle_show_all(self, on: bool):
        self._show_all = bool(on)
        self._refresh_mask()

    # ---- new: opacity setters ---------------------------------
    def set_gray_opacity(self, alpha: float):
        """alpha 0-1 untuk layer grayscale"""
        self._item_gray.setOpacity(alpha)

    def set_mask_opacity(self, alpha: float):
        """alpha 0-1 untuk layer mask/segmen"""
        self._item_mask.setOpacity(alpha)
        
    def set_bc(self, brightness: float, contrast: float):
        """
        brightness –1..+1, contrast 0.5..2
        simple formula: new = (orig-128)*contrast + 128 + brightness*128
        """
        arr = (self._orig_base.astype(np.float32) - 128) * contrast + 128 + brightness*128
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        q = QImage(arr.data, self._img_width, self._img_height,
                   self._img_width, QImage.Format_Grayscale8).copy()
        self._item_gray.setPixmap(QPixmap.fromImage(q))

        
    # -- background (label-0) opacity -----------------------------
    def set_bg_opacity(self, alpha: float):
        """alpha 0-1 hanya untuk label-0 (background)."""
        self._bg_alpha = alpha
        self._refresh_mask()      
        # rebuild RGBA so change is visible
    # -- contrast -------------------------------------------------
    def set_contrast(self, factor: float):
        """factor 0.5–2.0 : adjust brightness-contrast layer original"""
        arr = (self._orig_base * factor).clip(0, 255).astype(np.uint8)
        q   = QImage(arr.data, self._img_width, self._img_height,
                     self._img_width, QImage.Format_Grayscale8).copy()
        self._item_gray.setPixmap(QPixmap.fromImage(q))


    
    def current_mask(self) -> np.ndarray:     
        return self._mask_arr

    # -------- refresh mask pixmap
    # -------- NEW: rebuild gabungan dari semua layer ------------
    def _rebuild_combined(self):
        """Merge self._layers → self._mask_arr (prioritas label kecil→besar)."""
        combined = np.zeros_like(self._mask_arr)
        for lbl in range(len(_PALETTE)):              # 0 … 12
            layer = self._layers[lbl]
            combined[layer == 1] = lbl
        self._mask_arr = combined
    # ------------------------------------------------------------
    def _refresh_mask(self):
        self._mask_img = self._mask_to_qimage(
            show_all=self._show_all, label=self._cur_label)
        self._item_mask.setPixmap(QPixmap.fromImage(self._mask_img))
        self.viewport().update()

    # -------- FIXED: drawing helpers dengan koordinat yang presisi
    def _apply_brush(self, scene_pos: QPointF):
        """Apply brush dengan koordinat yang presisi, tidak miss lagi."""
        # Pastikan koordinat tepat pada pixel center
        x = max(0, min(self._img_width - 1, int(scene_pos.x() + 0.5)))
        y = max(0, min(self._img_height - 1, int(scene_pos.y() + 0.5)))
        
        h, w = self._mask_arr.shape
        
        if self._brush_sz == 1:
            targets = [(x, y)]
        else:
            targets = []
            radius = self._brush_sz
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx*dx + dy*dy <= radius*radius:
                        px, py = x + dx, y + dy
                        if 0 <= px < w and 0 <= py < h:
                            targets.append((px, py))

        # ---- NEW core: sentuh hanya layer aktif -----------------------
        lay = self._layers[self._cur_label]
        for px, py in targets:
            if self._eraser:
                lay[py, px] = 0            # hapus hanya label aktif
            else:
                lay[py, px] = 1            # warnai label aktif
        # --------------------------------------------------------------

        # selesai → re-compose lalu refresh
        self._rebuild_combined()
        self._refresh_mask()


    # -------- Qt events dengan koordinat yang diperbaiki
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and not self._pan_mode:
            self._drawing = True
            # FIXED: Gunakan koordinat yang tepat
            scene_pos = self.mapToScene(ev.position().toPoint())
            self._apply_brush(scene_pos)
            ev.accept()
        elif ev.button() == Qt.MiddleButton:
            # Enable pan mode temporarily
            self._pan_mode = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(QCursor(Qt.OpenHandCursor))
            super().mousePressEvent(ev)
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drawing and ev.buttons() & Qt.LeftButton and not self._pan_mode:
            # FIXED: Gunakan koordinat yang tepat
            scene_pos = self.mapToScene(ev.position().toPoint())
            self._apply_brush(scene_pos)
            ev.accept()
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._drawing = False
        elif ev.button() == Qt.MiddleButton:
            # Disable pan mode
            self._pan_mode = False
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(QCursor(Qt.CrossCursor))
        super().mouseReleaseEvent(ev)

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

    def set_zoom(self, zoom_factor: float):
        """Set zoom to specific factor"""
        current_zoom = self.transform().m11()
        scale_factor = zoom_factor / current_zoom
        self._zoom_factor = zoom_factor
        self.scale(scale_factor, scale_factor)
        self._update_info()
        self.viewport().update()

    # -------- improved grid overlay
    def drawForeground(self, painter: QPainter, rect: QRectF):
        # Only draw grid if zoomed in enough
        if self._zoom_factor < 2.0:
            return
        
        # Pixel-perfect grid
        if self._zoom_factor >= 4.0:
            step = 1  # 1 pixel grid
            alpha = min(100, int(20 * self._zoom_factor))  # More visible when zoomed
        else:
            step = max(1, int(10 / self._zoom_factor))  # Adaptive grid
            alpha = 40
        
        pen = QPen(QColor(100, 100, 100, alpha))
        pen.setWidth(0)  # Cosmetic pen (always 1 pixel wide)
        painter.setPen(pen)
        
        # Get visible area in scene coordinates
        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        
        # Align grid to pixel boundaries
        left = math.floor(visible_rect.left() / step) * step
        top = math.floor(visible_rect.top() / step) * step
        right = math.ceil(visible_rect.right() / step) * step
        bottom = math.ceil(visible_rect.bottom() / step) * step
        
        # Draw vertical lines
        x = left
        while x <= right:
            if 0 <= x <= self._img_width:
                painter.drawLine(x, max(0, top), x, min(self._img_height, bottom))
            x += step
        
        # Draw horizontal lines
        y = top
        while y <= bottom:
            if 0 <= y <= self._img_height:
                painter.drawLine(max(0, left), y, min(self._img_width, right), y)
            y += step

# ================================================================= Dialog
class SegmentationEditorDialog(QDialog):
    def __init__(self, scan: Dict, view: str, parent=None):
        super().__init__(parent, Qt.Window)
        from PySide6.QtGui import QGuiApplication
        self.setWindowTitle(f"Manual Edit – {view}")
        geom = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(int(geom.width()*0.9), int(geom.height()*0.9))

        # ----- FIXED: file paths dengan handling DICOM yang benar
        base = Path(scan["path"]).with_suffix("")
        vtag = view.lower()
        self._png_mask  = base.with_name(f"{base.stem}_{vtag}_mask.png")
        self._png_color = base.with_name(f"{base.stem}_{vtag}_colored.png")
        self._dcm_mask  = base.with_name(f"{base.stem}_{vtag}_mask.dcm")
        self._dcm_color = base.with_name(f"{base.stem}_{vtag}_colored.dcm")
        
        # ===== DEBUG: cek isi frame & view =====
        print("\n======================")
        print(">>> DEBUG: SegmentationEditorDialog")
        print(f"View diminta        : '{view}'")
        print(f"Keys di scan[frames]: {list(scan['frames'].keys())}")
        print("======================\n")

        # Load original array dari DICOM frames
        orig_arr = scan["frames"][view]
        
        # FIXED: Load mask dari PNG jika ada, atau buat mask kosong
        if self._png_color.exists():
            mask_arr = self._load_mask_from_png()
        else:
            mask_arr = np.zeros_like(orig_arr, np.uint8)

        # FIXED: Cek PNG original yang sudah ada untuk reference yang lebih akurat
        orig_png_path = base.with_name(f"{base.stem}_{vtag}.png")
        self._has_orig_png = orig_png_path.exists()
        
        if self._has_orig_png:
            try:
                orig_png_arr = np.array(Image.open(orig_png_path).convert('L'))
                print(f"✓ Loaded original PNG: {orig_png_path}")
            except Exception as e:
                print(f"✗ Failed to load PNG {orig_png_path}: {e}")
                orig_png_arr = orig_arr
                print(f"✓ DEBUG Original image range: min={orig_png_arr.min()}, max={orig_png_arr.max()}, shape={orig_png_arr.shape}")
        else:
            # Gunakan data dari DICOM frame langsung
            orig_png_arr = orig_arr
            print(f"✓ Using DICOM frame data for {view}")
            print(f"✓ DEBUG Original DICOM image range: min={orig_png_arr.min()}, max={orig_png_arr.max()}, shape={orig_png_arr.shape}")

        # ================= UI =================
        root = QHBoxLayout(self)

        # ---- left toolbar
        bar = QVBoxLayout(); root.addLayout(bar, 0)
        bar.addWidget(QLabel("<b>Palette / Layers</b>"))
        self.list_palette = QListWidget()
        for rgb, (nm, desc) in zip(_PALETTE, _LABEL_INFO):
            item = QListWidgetItem()
            w    = QWidget(); h = QHBoxLayout(w)
            box  = QLabel(); box.setFixedSize(22,22)
            box.setStyleSheet(f"background:rgb({rgb[0]},{rgb[1]},{rgb[2]});"
                              "border:1px solid #000;")
            h.addWidget(box); h.addWidget(QLabel(nm)); h.addWidget(QLabel(f"({desc})")); h.addStretch()
            item.setSizeHint(w.sizeHint())
            self.list_palette.addItem(item)
            self.list_palette.setItemWidget(item, w)
        self.list_palette.setCurrentRow(1)
        bar.addWidget(self.list_palette, 1)

        row = QHBoxLayout()
        self.btn_brush   = QPushButton("Brush");  self.btn_brush.setCheckable(True); self.btn_brush.setChecked(True)
        self.btn_eraser  = QPushButton("Eraser"); self.btn_eraser.setCheckable(True)
        self.btn_showall = QPushButton("Show All"); self.btn_showall.setCheckable(True)
        row.addWidget(self.btn_brush); row.addWidget(self.btn_eraser); row.addWidget(self.btn_showall)
        bar.addLayout(row)

        # ===== BRUSH SIZE SLIDER DENGAN TOMBOL +/- =====
        bar.addWidget(QLabel("Brush Size (pixels)"))
        self.slider_size = QSlider(Qt.Horizontal); self.slider_size.setRange(1,15); self.slider_size.setValue(1)
        self.lbl_size = QLabel("1px"); self.lbl_size.setFixedWidth(35); self.lbl_size.setAlignment(Qt.AlignRight)
        self.btn_size_minus = QPushButton("-"); self.btn_size_minus.setFixedSize(30, 22)
        self.btn_size_plus = QPushButton("+"); self.btn_size_plus.setFixedSize(30, 22)
        size_row = QHBoxLayout()
        size_row.setSpacing(3)
        size_row.addWidget(self.btn_size_minus)
        size_row.addWidget(self.slider_size, 1)
        size_row.addWidget(self.btn_size_plus)
        size_row.addWidget(self.lbl_size)
        bar.addLayout(size_row)

        # ===== ZOOM SLIDER DENGAN TOMBOL +/- =====
        bar.addWidget(QLabel("Zoom"))
        self.slider_zoom = QSlider(Qt.Horizontal); self.slider_zoom.setRange(1,1000); self.slider_zoom.setValue(10)
        self.lbl_zoom = QLabel("1.0x"); self.lbl_zoom.setFixedWidth(35); self.lbl_zoom.setAlignment(Qt.AlignRight)
        self.btn_zoom_minus = QPushButton("-"); self.btn_zoom_minus.setFixedSize(30, 22)
        self.btn_zoom_plus = QPushButton("+"); self.btn_zoom_plus.setFixedSize(30, 22)
        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(3)
        zoom_row.addWidget(self.btn_zoom_minus)
        zoom_row.addWidget(self.slider_zoom, 1)
        zoom_row.addWidget(self.btn_zoom_plus)
        zoom_row.addWidget(self.lbl_zoom)
        bar.addLayout(zoom_row)
        
        # ===== ORIGINAL OPACITY SLIDER DENGAN TOMBOL +/- =====
        bar.addWidget(QLabel("Original Opacity"))
        self.slider_gray = QSlider(Qt.Horizontal)
        self.slider_gray.setRange(0, 100)
        self.slider_gray.setValue(50)           # default 50 %
        self.lbl_gray = QLabel("50 %"); self.lbl_gray.setFixedWidth(35); self.lbl_gray.setAlignment(Qt.AlignRight)
        self.btn_gray_minus = QPushButton("-"); self.btn_gray_minus.setFixedSize(30, 22)
        self.btn_gray_plus = QPushButton("+"); self.btn_gray_plus.setFixedSize(30, 22)
        g_row = QHBoxLayout()
        g_row.setSpacing(3)
        g_row.addWidget(self.btn_gray_minus)
        g_row.addWidget(self.slider_gray, 1)
        g_row.addWidget(self.btn_gray_plus)
        g_row.addWidget(self.lbl_gray)
        bar.addLayout(g_row)

        # ===== MASK OPACITY SLIDER DENGAN TOMBOL +/- =====
        bar.addWidget(QLabel("Mask Opacity"))
        self.slider_mask = QSlider(Qt.Horizontal)
        self.slider_mask.setRange(0, 100)
        self.slider_mask.setValue(100)          # default 100 %
        self.lbl_mask = QLabel("100 %"); self.lbl_mask.setFixedWidth(35); self.lbl_mask.setAlignment(Qt.AlignRight)
        self.btn_mask_minus = QPushButton("-"); self.btn_mask_minus.setFixedSize(30, 22)
        self.btn_mask_plus = QPushButton("+"); self.btn_mask_plus.setFixedSize(30, 22)
        m_row = QHBoxLayout()
        m_row.setSpacing(3)
        m_row.addWidget(self.btn_mask_minus)
        m_row.addWidget(self.slider_mask, 1)
        m_row.addWidget(self.btn_mask_plus)
        m_row.addWidget(self.lbl_mask)
        bar.addLayout(m_row)

        # ===== BACKGROUND OPACITY SLIDER DENGAN TOMBOL +/- =====
        bar.addWidget(QLabel("BG Opacity"))
        self.slider_bg = QSlider(Qt.Horizontal)
        self.slider_bg.setRange(0, 100)
        self.slider_bg.setValue(0)           # start invisible
        self.lbl_bg = QLabel("0 %"); self.lbl_bg.setFixedWidth(35); self.lbl_bg.setAlignment(Qt.AlignRight)
        self.btn_bg_minus = QPushButton("-"); self.btn_bg_minus.setFixedSize(30, 22)
        self.btn_bg_plus = QPushButton("+"); self.btn_bg_plus.setFixedSize(30, 22)
        bg_row = QHBoxLayout()
        bg_row.setSpacing(3)
        bg_row.addWidget(self.btn_bg_minus)
        bg_row.addWidget(self.slider_bg, 1)
        bg_row.addWidget(self.btn_bg_plus)
        bg_row.addWidget(self.lbl_bg)
        bar.addLayout(bg_row)
        
        # --- Contrast button ---
        btn_contrast = QPushButton("Contrast…")
        bar.addWidget(btn_contrast)

        # Instructions dengan info yang lebih jelas
        data_source = "Original PNG loaded" if self._has_orig_png else "DICOM frames used"
        mask_status = "Existing mask loaded" if self._png_color.exists() else "New mask created"
        
        instructions = QLabel(
            "<b>Controls:</b><br>"
            "• Left click/drag: Paint<br>"
            "• Middle click/drag: Pan<br>"
            "• Ctrl+scroll: Zoom<br>"
            "• Grid appears at 2x+ zoom<br><br>"
            f"<b>Data Info:</b><br>"
            f"• Image: {data_source}<br>"
            f"• Mask: {mask_status}<br>"
            f"• Size: {orig_png_arr.shape[1]}×{orig_png_arr.shape[0]}"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("QLabel { background: #f0f0f0; padding: 8px; border-radius: 4px; }")
        bar.addWidget(instructions)

        btn_save, btn_cancel = QPushButton("Save"), QPushButton("Cancel")
        bar.addWidget(btn_save); bar.addWidget(btn_cancel)
        bar.addStretch()

        # ---- right side: canvas + info
        right_layout = QVBoxLayout()
        root.addLayout(right_layout, 1)

        # Info panel
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
        right_layout.addWidget(info_frame)

        # Canvas
        self.canvas = _Canvas(orig_png_arr, mask_arr)
        self.canvas.set_info_callback(self._update_info_display)
        right_layout.addWidget(self.canvas)

        # ===== SIGNALS =====
        self.list_palette.currentRowChanged.connect(self._change_label)
        self.slider_size.valueChanged.connect(self._size_changed)
        self.slider_zoom.valueChanged.connect(self._zoom_slider_changed)
        self.btn_showall.toggled.connect(self.canvas.toggle_show_all)
        self.btn_brush.clicked.connect(self._select_brush)
        self.btn_eraser.clicked.connect(self._select_eraser)
        self.slider_gray.valueChanged.connect(self._gray_alpha_changed)
        self.slider_mask.valueChanged.connect(self._mask_alpha_changed)
        self.slider_bg.valueChanged.connect(self._bg_alpha_changed)
        btn_contrast.clicked.connect(self._open_contrast_popup)
        btn_save.clicked.connect(self._save_all)
        btn_cancel.clicked.connect(self.reject)
        
        # Brush size buttons
        self.btn_size_minus.clicked.connect(lambda: self._adjust_slider(self.slider_size, -1))
        self.btn_size_plus.clicked.connect(lambda: self._adjust_slider(self.slider_size, 1))
        
        # Zoom buttons
        self.btn_zoom_minus.clicked.connect(lambda: self._adjust_slider(self.slider_zoom, -5))
        self.btn_zoom_plus.clicked.connect(lambda: self._adjust_slider(self.slider_zoom, 5))
        
        # Original opacity buttons
        self.btn_gray_minus.clicked.connect(lambda: self._adjust_slider(self.slider_gray, -5))
        self.btn_gray_plus.clicked.connect(lambda: self._adjust_slider(self.slider_gray, 5))
        
        # Mask opacity buttons
        self.btn_mask_minus.clicked.connect(lambda: self._adjust_slider(self.slider_mask, -5))
        self.btn_mask_plus.clicked.connect(lambda: self._adjust_slider(self.slider_mask, 5))
        
        # Background opacity buttons
        self.btn_bg_minus.clicked.connect(lambda: self._adjust_slider(self.slider_bg, -5))
        self.btn_bg_plus.clicked.connect(lambda: self._adjust_slider(self.slider_bg, 5))

    def _adjust_slider(self, slider, step):
        """Helper method untuk mengubah nilai slider dengan step tertentu"""
        current_value = slider.value()
        new_value = current_value + step
        
        # Pastikan nilai tidak melampaui range
        min_val = slider.minimum()
        max_val = slider.maximum()
        new_value = max(min_val, min(max_val, new_value))
        
        slider.setValue(new_value)

    def _update_info_display(self, width, height, zoom, grid_size):
        """Update the info display"""
        self.lbl_image_info.setText(f"Image: {width}×{height}")
        self.lbl_zoom_info.setText(f"Zoom: {zoom:.1f}x")
        if zoom >= 2.0:
            if grid_size == 1:
                self.lbl_grid_info.setText("Grid: 1px")
            else:
                self.lbl_grid_info.setText(f"Grid: {grid_size}px")
        else:
            self.lbl_grid_info.setText("Grid: Off")

    def _size_changed(self, size):
        """Handle brush size change dengan info yang lebih akurat"""
        self.canvas.set_brush_size(size)
        if size == 1:
            self.lbl_size.setText("1px")
        else:
            # Circular brush area calculation
            area_pixels = int(math.pi * size * size)
            self.lbl_size.setText(f"{area_pixels}px")
            self.lbl_size.styleSheet("font-size: 10pt;")
            
    def _zoom_slider_changed(self, val: int):
        """Handle zoom slider change"""
        zoom_factor = val / 10.0   # 0.1 – 100.0x
        self.canvas.set_zoom(zoom_factor)
        self.lbl_zoom.setText(f"{zoom_factor:.1f}x")

    # -- new handlers: update opacity label + kirim ke canvas ----
    def _gray_alpha_changed(self, val: int):
        alpha = val / 100.0
        self.canvas.set_gray_opacity(alpha)
        self.lbl_gray.setText(f"{val} %")

    def _mask_alpha_changed(self, val: int):
        alpha = val / 100.0
        self.canvas.set_mask_opacity(alpha)
        self.lbl_mask.setText(f"{val} %")

    def _bg_alpha_changed(self, val: int):
        a = val / 100.0
        self.canvas.set_bg_opacity(a)
        self.lbl_bg.setText(f"{val} %")
        
    # ---------- contrast mini-popup ------------------------------
    def _open_contrast_popup(self):
        dlg = QDialog(self); dlg.setWindowTitle("Brightness / Contrast")
        dlg.setFixedSize(300, 400)  # TAMBAHKAN: Fixed size untuk konsistensi
        lay = QVBoxLayout(dlg)

        pad = _BCPad()
        lbl = QLabel("B 0.00  C 1.00")
        lay.addWidget(QLabel("Drag crosshair – X = brightness, Y = contrast"))
        lay.addWidget(pad, 0, Qt.AlignCenter)
        # TAMBAHKAN: Labels untuk reference
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel("Dark"))
        ref_layout.addStretch()
        ref_layout.addWidget(QLabel("Normal"))
        ref_layout.addStretch()
        ref_layout.addWidget(QLabel("Bright"))
        lay.addLayout(ref_layout)

        # Labels untuk contrast (vertikal)
        contrast_info = QLabel("↑ High Contrast\n↓ Low Contrast")
        contrast_info.setAlignment(Qt.AlignCenter)
        lay.addWidget(contrast_info)
        lay.addWidget(lbl, 0, Qt.AlignCenter)

        def _on_change(b, c):
            lbl.setText(f"B {b:+.2f}   C {c:.2f}")
            self.canvas.set_bc(b, c)
        pad.valueChanged.connect(_on_change)

        dlg.exec()



    # ---------- palette & tools
    def _select_brush(self):
        self.btn_eraser.setChecked(False)
        self.canvas.set_label(self.list_palette.currentRow())
    
    def _select_eraser(self):
        self.btn_brush.setChecked(False)
        self.canvas.set_eraser()
    
    def _change_label(self, idx: int):
        self.btn_brush.setChecked(True); self.btn_eraser.setChecked(False)
        self.canvas.set_label(idx)

    # ---------- FIXED: I/O helpers dengan error handling yang lebih baik
    def _load_mask_from_png(self) -> np.ndarray:
        """Load mask dari PNG colored dengan error handling."""
        try:
            rgb = np.array(Image.open(self._png_color).convert("RGB"))
            mask = np.zeros(rgb.shape[:2], np.uint8)
            for lbl, col in enumerate(_PALETTE):
                mask[(rgb == col).all(-1)] = lbl
            print(f"✓ Loaded existing mask from: {self._png_color}")
            return mask
        except Exception as e:
            print(f"✗ Failed to load mask from {self._png_color}: {e}")
            # Return empty mask instead of crashing
            return np.zeros((1024, 256), np.uint8)  # Default DICOM size

    def _save_sc_dicom(self, img: np.ndarray, path: Path, desc: str):
        """Simple 8-bit Secondary-Capture DICOM."""
        rgb = img.ndim == 3
        rows, cols = img.shape[:2]
        meta = pydicom.Dataset()
        meta.MediaStorageSOPClassUID    = SecondaryCaptureImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID          = ExplicitVRLittleEndian

        ds = pydicom.FileDataset(str(path), {}, file_meta=meta, preamble=b"\0"*128)
        ds.Modality = "OT"
        ds.SeriesInstanceUID = generate_uid()
        ds.SeriesDescription = desc
        ds.Rows, ds.Columns  = rows, cols
        ds.SamplesPerPixel   = 3 if rgb else 1
        ds.PhotometricInterpretation = "RGB" if rgb else "MONOCHROME2"
        ds.BitsAllocated = ds.BitsStored = 8
        ds.HighBit = 7
        if rgb: ds.PlanarConfiguration = 0
        ds.PixelRepresentation = 0
        ds.PixelData = img.astype(np.uint8).tobytes()
        ds.save_as(path, write_like_original=False)

    def _save_all(self):
        mask = self.canvas.current_mask()
        try:
            # --- PNG (mask & colored)
            bin_img = (mask > 0).astype(np.uint8) * 255
            Image.fromarray(bin_img, mode="L").save(self._png_mask)
            print(f"✓ Saved mask PNG: {self._png_mask}")

            rgb_img = label_mask_to_rgb(mask)
            Image.fromarray(rgb_img).save(self._png_color)
            print(f"✓ Saved colored PNG: {self._png_color}")

            # --- DICOM SC
            self._save_sc_dicom(bin_img, self._dcm_mask , desc="Mask")
            print(f"✓ Saved mask DICOM: {self._dcm_mask}")
            
            self._save_sc_dicom(rgb_img, self._dcm_color, desc="Colored")
            print(f"✓ Saved colored DICOM: {self._dcm_color}")

            QMessageBox.information(self, "Success", 
                f"Segmentation saved successfully!\n\n"
                f"Files saved:\n"
                f"• {self._png_mask.name}\n"
                f"• {self._png_color.name}\n"
                f"• {self._dcm_mask.name}\n"
                f"• {self._dcm_color.name}")
            
            self.accept()
        except Exception as e:
            print(f"✗ Save failed: {e}")
            QMessageBox.critical(self, "Save failed", 
                f"Failed to save segmentation:\n{str(e)}\n\n"
                f"Please check file permissions and disk space.")