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

from core.config.paths import (
    extract_study_date_from_dicom,
    generate_filename_stem,
)


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
from features.spect_viewer.logic.hotspot_processor import HotspotProcessor, parse_xml_annotations, create_hotspot_mask

from features.spect_viewer.logic.colorizer import label_mask_to_hotspot_rgb,label_new_mask_to_hotspot_rgb, _HOTSPOT_PALLETTE

# ---------------------------------------------------------------- label names & desc
_LABEL_INFO: List[Tuple[str, str]] = [
    ("Background", "kosong"),
    ("Abnormal", "Terdeteksi anomali"),
    ("Normal", "Tidak terdeteksi anomali")
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
        self._orig_base = ((orig - orig.min()) / max(1, np.ptp(orig)) * 255).astype(np.uint8)

        gray_q = QImage(self._orig_base.data, self._img_width, self._img_height,
                        self._img_width, QImage.Format_Grayscale8).copy()
        self._item_gray = QGraphicsPixmapItem(QPixmap.fromImage(gray_q))
        self._item_gray.setOpacity(0.5)
        self._scene.addItem(self._item_gray)

        # mask layer
        self._mask_arr = mask.astype(np.uint8)
        # --- NEW: bank layer per-label ---------------------------------
        self._layers = {lbl: (self._mask_arr == lbl).astype(np.uint8)
                        for lbl in range(len(_HOTSPOT_PALLETTE))}
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

        # State management per layer
        self._layer_history = {}  # {label_id: {'undo': [], 'redo': []}}
        self._max_history = 50  # Batas maksimal history per layer
        
        # Inisialisasi history untuk setiap layer
        for label_id in range(len(_HOTSPOT_PALLETTE)):
            self._init_layer_history(label_id)
            
        # Simpan state awal untuk semua layer
        self._save_all_states()

    def _init_layer_history(self, label_id: int):
        """Inisialisasi struktur history untuk layer tertentu"""
        self._layer_history[label_id] = {
            'undo': [],
            'redo': []
        }

    def _save_layer_state(self, label_id: int):
        """Simpan state layer tertentu ke undo stack"""
        history = self._layer_history[label_id]
        
        # Salinan array layer saat ini
        state = self._layers[label_id].copy()
        
        # Batasi jumlah history
        if len(history['undo']) >= self._max_history:
            history['undo'].pop(0)
        
        history['undo'].append(state)
        history['redo'].clear()  # Reset redo setelah perubahan baru

    def _save_all_states(self):
        """Simpan state semua layer (digunakan saat inisialisasi)"""
        for label_id in range(len(_HOTSPOT_PALLETTE)):
            self._save_layer_state(label_id)

    def _restore_layer_state(self, label_id: int, state: np.ndarray):
        """Kembalikan state untuk layer tertentu"""
        self._layers[label_id] = state.copy()
        self._rebuild_combined()
        self._refresh_mask()

    def undo(self, label_id: int):
        """Kembalikan ke state sebelumnya untuk layer tertentu"""
        history = self._layer_history.get(label_id)
        if not history or len(history['undo']) < 2:
            return  # Tidak ada history yang cukup
        
        # Pindahkan state saat ini ke redo stack
        current_state = history['undo'].pop()
        history['redo'].append(current_state)
        
        # Kembalikan ke state sebelumnya
        prev_state = history['undo'][-1]
        self._restore_layer_state(label_id, prev_state)

    def redo(self, label_id: int):
        """Kembalikan perubahan yang di-undo untuk layer tertentu"""
        history = self._layer_history.get(label_id)
        if not history or not history['redo']:
            return
        
        state = history['redo'].pop()
        history['undo'].append(state)
        self._restore_layer_state(label_id, state)

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
        rgb = label_mask_to_hotspot_rgb(self._mask_arr)          # (H, W, 3)
        h, w, _ = rgb.shape

        # build an alpha channel: fully opaque where we want to show,
        #  fully transparent everywhere else
        if show_all:
            alpha = np.full((h, w), 255, np.uint8)
            # label-0 transparency:
            alpha[self._mask_arr == 0] = int(self._bg_alpha * 255)
        else:
            sel = (self._layers[label] == 1)   
            rgb[sel] = np.array(_HOTSPOT_PALLETTE[label], dtype=np.uint8)# ← inilah baris baru
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
        for lbl in range(len(_HOTSPOT_PALLETTE)):              # 0 … 12
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
        if ev.button() == Qt.LeftButton and self._drawing:
            # Simpan state layer yang sedang diedit
            self._save_layer_state(self._cur_label)
            self._drawing = False

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
class HotspotEditorDialog(QDialog):
    def __init__(self, scan: Dict, view: str, parent=None):
        super().__init__(parent, Qt.Window)
        from PySide6.QtGui import QGuiApplication
        self.setWindowTitle(f"Hotspot Editor – {view}")
        geom = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(int(geom.width()*0.9), int(geom.height()*0.9))

        # ----- FIXED: Use consistent naming convention
        base = Path(scan["path"]).with_suffix("")
        patient_id = base.parent.name
        
        # FIXED: Always use full view names (anterior/posterior) consistently
        view_full = "anterior" if "ant" in view.lower() else "posterior"
        vtag = view.lower()  # FIXED: Define vtag for backward compatibility
        
        # Extract study date from DICOM
        try:
            study_date = extract_study_date_from_dicom(scan["path"])
            filename_stem = generate_filename_stem(patient_id, study_date)
        except Exception as e:
            print(f"[WARN] Could not extract study date: {e}")
            filename_stem = base.stem
        
        # FIXED: Define all possible file paths
        # EDITED versions (for saving)
        self._png_color = base.parent / f"{filename_stem}_{view_full}_hotspot_edited_colored.png"
        self._png_mask = base.parent / f"{filename_stem}_{view_full}_hotspot_edited_mask.png"
        
        # ORIGINAL versions (for loading fallback)
        self._png_color_original = base.parent / f"{filename_stem}_{view_full}_hotspot_colored.png"
        self._png_mask_original = base.parent / f"{filename_stem}_{view_full}_hotspot_mask.png"
        
        # LEGACY versions (for loading fallback)
        view_short = "ant" if "ant" in view.lower() else "post"
        self._png_color_legacy = base.parent / f"{filename_stem}_{view_short}_hotspot_colored.png"
        self._png_mask_legacy = base.parent / f"{filename_stem}_{view_short}_hotspot_mask.png"
        
        # XML paths
        xml_path = base.parent / f"{filename_stem}_{view_short}.xml"
        
        # Original PNG path
        orig_png_path = base.with_name(f"{base.stem}_{vtag}.png")
        
        print(f"[DEBUG] Hotspot editor paths:")
        print(f"  Save to (edited): {self._png_color}")
        print(f"  Original hotspot: {self._png_color_original}")
        print(f"  Legacy hotspot: {self._png_color_legacy}")
        print(f"  XML: {xml_path}")
        print(f"  Original PNG: {orig_png_path}")

        orig_png_arr = None
        mask_arr = None

        # ===== DEBUG: cek isi frame & view =====
        print("\n======================")
        print(">>> DEBUG: HotspotEditorDialog")
        print(f"View diminta        : '{view}'")
        print(f"View full           : '{view_full}'")
        print(f"Keys di scan[frames]: {list(scan['frames'].keys())}")
        print("======================\n")

        # Load original array dari DICOM frames
        orig_arr = scan["frames"][view]
        
        # FIXED: Check for existing hotspot data with proper priority
        if self._png_color.exists():
            # Priority 1: Edited version exists
            print(f"✓ Found existing EDITED hotspot: {self._png_color}")
            mask_arr = self._load_mask_from_png()
        elif self._png_color_original.exists():
            # Priority 2: Original version exists
            print(f"✓ Found existing ORIGINAL hotspot: {self._png_color_original}")
            mask_arr = self._load_mask_from_png()
        elif self._png_color_legacy.exists():
            # Priority 3: Legacy version exists
            print(f"✓ Found existing LEGACY hotspot: {self._png_color_legacy}")
            mask_arr = self._load_mask_from_png()
        elif xml_path.exists():
            # Priority 4: Generate from XML
            print(f"✓ Found XML annotations: {xml_path}")
            try:
                # Determine image to use for processing
                if orig_png_path.exists():
                    input_image_path = str(orig_png_path)
                    print(f"✓ Using original PNG for processing: {orig_png_path}")
                else:
                    # Save DICOM frame to temp PNG so hotspot_processor can read it
                    temp_png_path = base.parent / f"{filename_stem}_temp.png"
                    Image.fromarray(orig_arr).save(temp_png_path)
                    input_image_path = str(temp_png_path)
                    print(f"✓ Saved DICOM frame to temp PNG for processing: {input_image_path}")

                # Parse and process
                boxes = parse_xml_annotations(str(xml_path))
                if boxes:
                    mask_arr, overlayed_pil = create_hotspot_mask(
                        input_image_path,
                        boxes,
                        patient_id,
                        view_short, str(base.parent)
                    )
                    print(mask_arr.shape, mask_arr.dtype)
                    recolor = np.zeros_like(mask_arr, dtype=np.uint8)
                    recolor[mask_arr > 200] = 1      # Abnormal
                    recolor[(mask_arr > 50) & (mask_arr <= 200)] = 2  # Normal
                    mask_arr = recolor
                    orig_png_arr = np.array(overlayed_pil.convert('L'))
                    print(f"✓ Generated mask and overlayed image from XML.")
                else:
                    print(f"✗ No bounding boxes in XML, using empty mask.")
                    mask_arr = np.zeros_like(orig_arr, np.uint8)
            except Exception as e:
                print(f"✗ Error processing XML: {e}")
                mask_arr = np.zeros_like(orig_arr, np.uint8)
        else:
            print(f"✗ No existing hotspot data found. Creating empty mask.")
            mask_arr = np.zeros_like(orig_arr, np.uint8)

        # Load original PNG if exists
        self._has_orig_png = orig_png_path.exists()
        
        if self._has_orig_png:
            try:
                orig_png_arr = np.array(Image.open(orig_png_path).convert('L'))
                print(f"✓ Loaded original PNG: {orig_png_path}")
            except Exception as e:
                print(f"✗ Failed to load PNG {orig_png_path}: {e}")
                orig_png_arr = orig_arr
        else:
            # Use DICOM frame data directly
            orig_png_arr = orig_arr
            print(f"✓ Using DICOM frame data for {view}")

        print(f"✓ DEBUG Original image range: min={orig_png_arr.min()}, max={orig_png_arr.max()}, shape={orig_png_arr.shape}")

        # ================= UI =================
        root = QHBoxLayout(self)

        # ---- left toolbar
        bar = QVBoxLayout(); root.addLayout(bar, 0)
        bar.addWidget(QLabel("<b>Palette / Layers</b>"))
        self.list_palette = QListWidget()
        for rgb, (nm, desc) in zip(_HOTSPOT_PALLETTE, _LABEL_INFO):
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

        # Tambahkan tombol undo/redo
        btn_row = QHBoxLayout()
        self.btn_undo = QPushButton("Undo")
        self.btn_redo = QPushButton("Redo")
        btn_row.addWidget(self.btn_undo)
        btn_row.addWidget(self.btn_redo)
        bar.addLayout(btn_row)

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
            "• Ctrl+Z: Undo edit<br>"
            "• Ctrl+Y: Redo Edit<br>"
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
        self.btn_undo.clicked.connect(self._perform_undo)
        self.btn_redo.clicked.connect(self._perform_redo)

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

    def _perform_undo(self):
        """Undo untuk layer yang sedang aktif"""
        current_label = self.list_palette.currentRow()
        self.canvas.undo(current_label)

    def _perform_redo(self):
        """Redo untuk layer yang sedang aktif"""
        current_label = self.list_palette.currentRow()
        self.canvas.redo(current_label)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.modifiers() & Qt.ControlModifier:
            current_label = self.list_palette.currentRow()
            
            if event.key() == Qt.Key_Z:
                self.canvas.undo(current_label)
                event.accept()
                return
            elif event.key() == Qt.Key_Y:
                self.canvas.redo(current_label)
                event.accept()
                return
        super().keyPressEvent(event)

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
        """FIXED: Load from highest priority available file"""
        try:
            # Priority 1: Try edited version first
            if self._png_color.exists():
                load_path = self._png_color
                print(f"✓ Loading EDITED hotspot from: {load_path}")
            # Priority 2: Try original version
            elif self._png_color_original.exists():
                load_path = self._png_color_original
                print(f"✓ Loading ORIGINAL hotspot from: {load_path}")
            # Priority 3: Try legacy version
            elif self._png_color_legacy.exists():
                load_path = self._png_color_legacy
                print(f"✓ Loading LEGACY hotspot from: {load_path}")
            else:
                print(f"✗ No hotspot file found in any location")
                return np.zeros((256, 256), np.uint8)
            
            # Load the mask
            rgb = np.array(Image.open(load_path).convert("RGB"))
            mask = np.zeros(rgb.shape[:2], np.uint8)
            for lbl, col in enumerate(_HOTSPOT_PALLETTE):
                mask[(rgb == col).all(-1)] = lbl
            print(f"✓ Successfully loaded hotspot mask from: {load_path}")
            return mask
            
        except Exception as e:
            print(f"✗ Failed to load hotspot mask: {e}")
            return np.zeros((256, 256), np.uint8)
    
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
        """FIXED: Always save to EDITED versions"""
        mask = self.canvas.current_mask()
        try:
            # Save to EDITED file paths (never overwrite originals)
            bin_img = (mask > 0).astype(np.uint8) * 255
            Image.fromarray(bin_img, mode="L").save(self._png_mask)
            print(f"✓ Saved edited mask PNG: {self._png_mask}")

            rgb_img = label_mask_to_hotspot_rgb(mask)
            Image.fromarray(rgb_img).save(self._png_color)
            print(f"✓ Saved edited colored PNG: {self._png_color}")

            QMessageBox.information(self, "Success", 
                f"Hotspot edits saved successfully!\n\n"
                f"Edited files saved:\n"
                f"• {self._png_mask.name}\n"
                f"• {self._png_color.name}\n\n"
                f"Original files preserved.")
            
            self.accept()
        except Exception as e:
            print(f"✗ Save failed: {e}")
            QMessageBox.critical(self, "Save failed", 
                f"Failed to save hotspot edits:\n{str(e)}")
            """FIXED: Save dengan nama file yang konsisten"""
            mask = self.canvas.current_mask()
            try:
                # FIXED: Save with consistent naming
                bin_img = (mask > 0).astype(np.uint8) * 255
                Image.fromarray(bin_img, mode="L").save(self._png_mask)
                print(f"✓ Saved mask PNG: {self._png_mask}")

                rgb_img = label_mask_to_hotspot_rgb(mask)
                Image.fromarray(rgb_img).save(self._png_color)
                print(f"✓ Saved colored PNG: {self._png_color}")

                QMessageBox.information(self, "Success", 
                    f"Hotspot saved successfully!\n\n"
                    f"Files saved:\n"
                    f"• {self._png_mask.name}\n"
                    f"• {self._png_color.name}")
                
                self.accept()
            except Exception as e:
                print(f"✗ Save failed: {e}")
                QMessageBox.critical(self, "Save failed", 
                    f"Failed to save hotspot:\n{str(e)}\n\n"
                    f"Please check file permissions and disk space.")