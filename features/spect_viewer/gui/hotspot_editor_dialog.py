# =====================================================================
# frontend/widgets/segmentation_editor_dialog.py  – v2.3-segmentation-integrated
# ---------------------------------------------------------------------
"""
Full-screen dialog untuk manual edit segmentasi dengan XML management dan segmentation layer.

Perbaikan v2.3:
- Integrasi fitur segmentation layer dari code pertama
- Pembatasan painting hanya pada area segmen (bukan background)
- Detection segment pada posisi cursor dan bounding box
- Segmentation opacity control
- Enhanced segment validation
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
import math
import xml.etree.ElementTree as ET
from datetime import datetime
import shutil
import os

from core.config.paths import (
    extract_study_date_from_dicom,
    generate_filename_stem,
)

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QThread
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QWheelEvent, QCursor, QLinearGradient, 
)
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSlider, QWidget, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QStyleOptionGraphicsItem, QFrame, QCheckBox
)

import pydicom
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from features.spect_viewer.logic.hotspot_processor import HotspotProcessor, parse_xml_annotations, create_hotspot_mask

from features.spect_viewer.logic.colorizer import label_mask_to_hotspot_rgb,label_new_mask_to_hotspot_rgb, _HOTSPOT_PALLETTE

# Import segmentation colorizer
from features.spect_viewer.logic.colorizer import _PALETTE

# ✅ ADD: Loading dialog import
from core.gui.loading_dialog import LoadingDialog

# ---------------------------------------------------------------- label names & desc
_LABEL_INFO: List[Tuple[str, str]] = [
    ("Background", "kosong"),
    ("Abnormal", "Terdeteksi anomali"),
    ("Normal", "Tidak terdeteksi anomali")
]

# Mapping dari label ID ke nama segment (sesuai colorizer.py)
_SEGMENT_NAMES = {
    0: "background",
    1: "skull", 
    2: "cervical_vertebrae",
    3: "thoracic_vertebrae", 
    4: "rib",
    5: "sternum",
    6: "collarbone",
    7: "scapula",
    8: "humerus",
    9: "lumbar_vertebrae",
    10: "sacrum",
    11: "pelvis", 
    12: "femur"
}


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
    """Interactive view: pan, zoom, brush / eraser dengan koordinat presisi tinggi dan segmentation support."""

    def __init__(self, orig: np.ndarray, mask: np.ndarray, parent=None):
        super().__init__(parent)
        
        # FIXED: Remove HighQualityAntialiasing - it doesn't exist in PySide6
        self.setRenderHints(
            QPainter.Antialiasing | 
            QPainter.SmoothPixmapTransform | 
            QPainter.TextAntialiasing
            # QPainter.HighQualityAntialiasing  # REMOVED - not available in PySide6
        )
        
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
        
        # Load segmentation layer
        self._segmentation_arr = self._load_segmentation_layer(orig)
        self._segmentation_img = None
        self._item_segmentation = None
        if self._segmentation_arr is not None:
            self._segmentation_img = self._segmentation_to_qimage()
            self._item_segmentation = QGraphicsPixmapItem(QPixmap.fromImage(self._segmentation_img))
            self._item_segmentation.setOpacity(0.3)  # Default 30% opacity
            self._scene.addItem(self._item_segmentation)
        
        # --- NEW: bank layer per-label ---------------------------------
        self._layers = {lbl: (self._mask_arr == lbl).astype(np.uint8)
                        for lbl in range(len(_HOTSPOT_PALLETTE))}
        self._bg_alpha = 0.0  # Opacity for background (label-0)
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
        print("Segmentation loaded  :", self._segmentation_arr is not None)
        print("Opacity gray image   :", self._item_gray.opacity())
        print("Mask QImage size     :", self._mask_img.size())
        print("QGraphicsScene items :", len(self._scene.items()))
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

    def _load_segmentation_layer(self, orig_frame: np.ndarray) -> np.ndarray:
        """Load segmentation colored PNG jika tersedia."""
        try:
            # Konstruksi path segmentation berdasarkan naming convention
            # Akan dicari di parent dialog nanti
            return None  # Placeholder, akan di-set dari dialog
        except Exception as e:
            print(f"[DEBUG] Could not load segmentation layer: {e}")
            return None
    
    def set_segmentation_layer(self, segmentation_path: Path):
        """Set segmentation layer dari path eksternal."""
        try:
            if segmentation_path and segmentation_path.exists():
                # Load RGB image dan convert ke label mask
                rgb_img = np.array(Image.open(segmentation_path).convert("RGB"))
                
                # Convert RGB ke label mask menggunakan palette
                label_mask = np.zeros(rgb_img.shape[:2], dtype=np.uint8)
                for label_id, color in enumerate(_PALETTE):
                    mask_matches = np.all(rgb_img == color, axis=-1)
                    label_mask[mask_matches] = label_id
                
                self._segmentation_arr = label_mask
                
                # Update graphics item
                if self._item_segmentation:
                    self._scene.removeItem(self._item_segmentation)
                
                self._segmentation_img = self._segmentation_to_qimage()
                self._item_segmentation = QGraphicsPixmapItem(QPixmap.fromImage(self._segmentation_img))
                self._item_segmentation.setOpacity(0.3)
                self._scene.addItem(self._item_segmentation)
                
                print(f"✓ Loaded segmentation layer: {segmentation_path}")
                return True
            else:
                print(f"✗ Segmentation file not found: {segmentation_path}")
                return False
        except Exception as e:
            print(f"✗ Failed to load segmentation: {e}")
            return False
    
    def _segmentation_to_qimage(self) -> QImage:
        """Convert segmentation array to QImage dengan transparency."""
        if self._segmentation_arr is None:
            return QImage()
        
        h, w = self._segmentation_arr.shape
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        alpha = np.zeros((h, w), dtype=np.uint8)
        
        # Apply colors from palette
        for label_id, color in enumerate(_PALETTE):
            mask = (self._segmentation_arr == label_id)
            if label_id == 0:  # Background transparent
                alpha[mask] = 0
            else:  # Segments visible
                rgb[mask] = color
                alpha[mask] = 255
        
        # Create RGBA
        rgba = np.dstack([rgb, alpha])
        return QImage(rgba.data, w, h, 4*w, QImage.Format_RGBA8888).copy()

    def get_segment_at_position(self, x: int, y: int) -> str:
        """Get segment name at given position."""
        if self._segmentation_arr is not None:
            if 0 <= x < self._segmentation_arr.shape[1] and 0 <= y < self._segmentation_arr.shape[0]:
                segment_label = self._segmentation_arr[y, x]
                return _SEGMENT_NAMES.get(segment_label, "unknown")
        return "manual_annotation"
    
    def set_segmentation_opacity(self, alpha: float):
        """Set opacity untuk segmentation layer."""
        if self._item_segmentation:
            self._item_segmentation.setOpacity(alpha)

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
        arr_f = (arr - arr.min()) / max(1, np.ptp(arr)) * 255.0
        u8 = arr_f.astype(np.uint8)
        h, w = u8.shape
        return QImage(u8.data, w, h, w, QImage.Format_Grayscale8).copy()
    
    def _mask_to_qimage(self, *, show_all: bool, label: int) -> QImage:
        rgb = label_mask_to_hotspot_rgb(self._mask_arr)      # (H, W, 3)
        h, w, _ = rgb.shape

        # Selalu tampilkan semua hotspot, mirip perilaku di kode lama.
        alpha = np.full((h, w), 255, np.uint8)
        
        # Atur transparansi untuk background (label 0) jika slider BG opacity digeser.
        alpha[self._mask_arr == 0] = int(self._bg_alpha * 255)

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

    # -------- FIXED: drawing helpers dengan koordinat yang presisi dan segmentation validation
    def _apply_brush(self, scene_pos: QPointF):
        """Apply brush dengan koordinat yang presisi dan validasi segmentasi."""
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

        # ---- NEW core: sentuh hanya layer aktif dengan validasi segmentasi ---------
        lay = self._layers[self._cur_label]
        for px, py in targets:
            # VALIDATION: Hanya izinkan edit di area yang bukan background
            if self._segmentation_arr is not None:
                segment_label = self._segmentation_arr[py, px]
                if segment_label == 0:  # Background segment
                    continue  # Skip painting on background
            
            # Original painting logic
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

# ================================================================= XML Utilities
def mask_to_bounding_boxes(mask: np.ndarray, segmentation_arr: np.ndarray = None, min_area: int = 10) -> List[Dict]:
    """Convert mask annotations to bounding boxes with proper segment detection."""
    bounding_boxes = []
    
    # Process Abnormal (label=1) and Normal (label=2) areas
    for label_value in [1, 2]:
        label_mask = (mask == label_value).astype(np.uint8)
        
        if not np.any(label_mask):
            continue
            
        # Find connected components
        labeled_regions = measure.label(label_mask)
        
        for region_id in range(1, labeled_regions.max() + 1):
            region = (labeled_regions == region_id)
            
            # Skip small regions
            if np.sum(region) < min_area:
                continue
                
            # Get bounding box coordinates
            coords = np.where(region)
            y_min, y_max = coords[0].min(), coords[0].max()
            x_min, x_max = coords[1].min(), coords[1].max()
            
            # Detect dominant segment in this region
            segment_name = "manual_annotation"
            if segmentation_arr is not None:
                # Get segment labels in this region
                region_segments = segmentation_arr[region]
                # Find most common non-background segment
                unique_segments, counts = np.unique(region_segments, return_counts=True)
                # Filter out background (label 0)
                non_bg_mask = unique_segments != 0
                if np.any(non_bg_mask):
                    dominant_segment_id = unique_segments[non_bg_mask][np.argmax(counts[non_bg_mask])]
                    segment_name = _SEGMENT_NAMES.get(dominant_segment_id, "unknown")
            
            # Convert to proper format
            bbox = {
                'x': int(x_min),
                'y': int(y_min),
                'width': int(x_max - x_min + 1),
                'height': int(y_max - y_min + 1),
                'label': 'abnormal' if label_value == 1 else 'normal',
                'confidence': 1.0,  # Manual annotation = high confidence
                'hotspot_pixels': int(np.sum(region)),
                'segment': segment_name
            }
            
            bounding_boxes.append(bbox)
    
    return bounding_boxes

def create_xml_from_bboxes(bounding_boxes: List[Dict], img_width: int, img_height: int, 
                          patient_id: str, view: str, filename_stem: str) -> str:
    """Create XML content from bounding boxes dengan format classification results."""
    
    # Create root element
    root = ET.Element('annotation')
    
    # Add metadata
    ET.SubElement(root, 'folder').text = 'classification_results'
    ET.SubElement(root, 'filename').text = f'{filename_stem}_{view}_classification.png'
    ET.SubElement(root, 'path').text = f'/path/to/{filename_stem}_{view}_classification.png'
    
    # Add source info
    source = ET.SubElement(root, 'source')
    ET.SubElement(source, 'database').text = 'Hotspot Classification Results'
    
    # Add image size
    size = ET.SubElement(root, 'size')
    ET.SubElement(size, 'width').text = str(img_width)
    ET.SubElement(size, 'height').text = str(img_height)
    ET.SubElement(size, 'depth').text = '1'
    
    ET.SubElement(root, 'segmented').text = '0'
    
    # Add bounding boxes
    for bbox in bounding_boxes:
        obj = ET.SubElement(root, 'object')
        # FIXED: Gunakan format dengan huruf kapital pertama
        label_name = bbox['label'].capitalize()  # 'abnormal' -> 'Abnormal'
        ET.SubElement(obj, 'name').text = label_name
        ET.SubElement(obj, 'pose').text = 'Unspecified'
        ET.SubElement(obj, 'truncated').text = '0'
        ET.SubElement(obj, 'difficult').text = '0'
        
        # Add bounding box coordinates
        bndbox = ET.SubElement(obj, 'bndbox')
        ET.SubElement(bndbox, 'xmin').text = str(bbox['x'])
        ET.SubElement(bndbox, 'ymin').text = str(bbox['y'])
        ET.SubElement(bndbox, 'xmax').text = str(bbox['x'] + bbox['width'])
        ET.SubElement(bndbox, 'ymax').text = str(bbox['y'] + bbox['height'])
    
    # Convert to string with proper formatting
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding='unicode')

def save_xml_file(xml_content: str, file_path: Path):
    """Save XML content to file with proper header."""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_content)

class SaveThread(QThread):
    """Thread untuk save process dengan progress reporting"""
    progress_updated = Signal(int, str)  # progress percentage, message
    save_completed = Signal(bool, str)   # success, message
    
    def __init__(self, canvas, classification_mask_edited, xml_edited, patient_id, view_short, filename_stem, dicom_path, study_date):
        super().__init__()
        self.canvas = canvas
        self.classification_mask_edited = classification_mask_edited
        self.xml_edited = xml_edited
        self.patient_id = patient_id
        self.view_short = view_short
        self.filename_stem = filename_stem
        
        # ✅ FIX: Simpan dengan nama yang benar
        self._dicom_path = dicom_path  # ← TAMBAHKAN INI
        self._study_date = study_date  # ← TAMBAHKAN INI
        
    def run(self):
        try:
            mask = self.canvas.current_mask()
            
            self.progress_updated.emit(10, "Preparing classification data...")
            
            # Save classification mask
            rgb_img = label_mask_to_hotspot_rgb(mask)
            
            self.progress_updated.emit(30, "Saving classification mask...")
            
            # Create parent directories
            self.classification_mask_edited.parent.mkdir(parents=True, exist_ok=True)
            
            # Save classification mask
            Image.fromarray(rgb_img).save(self.classification_mask_edited)
            print(f"✓ Saved edited classification mask: {self.classification_mask_edited}")
            
            self.progress_updated.emit(50, "Generating XML annotations...")
            
            # Generate and save XML
            xml_result = self._save_xml_with_backup(mask)
            
            self.progress_updated.emit(80, "Running quantification...")
            
            # Trigger quantification
            quant_success = self._trigger_quantification()
            
            self.progress_updated.emit(100, "Save completed!")
            
            # ✅ FIX: Update success message dengan info kuantifikasi
            success_msg = f"Classification edits saved successfully!\n\n"
            success_msg += f"Classification file saved:\n• {self.classification_mask_edited.name}\n\n"
            
            if xml_result:
                success_msg += f"XML annotation file:\n"
                for file_info in xml_result['saved_files']:
                    success_msg += file_info + "\n"
                success_msg += f"\nAnnotations: {xml_result['bbox_stats']}"
            
            # ✅ IMPROVED: Better quantification status
            if quant_success:
                success_msg += "\n\n✅ Quantification pipeline completed successfully"
            else:
                success_msg += "\n\n⚠️ Quantification pipeline failed (check logs for details)"
            
            self.save_completed.emit(True, success_msg)
            
        except Exception as error:
            error_msg = f"Failed to save classification edits:\n{str(error)}"
            print(f"✗ Save failed: {error}")
            self.save_completed.emit(False, error_msg)
    
    def _save_xml_with_backup(self, mask):
        """Save XML with backup logic"""
        try:
            # Generate bounding boxes with segment detection
            segmentation_arr = self.canvas._segmentation_arr
            bounding_boxes = mask_to_bounding_boxes(mask, segmentation_arr, min_area=10)
            
            # Get image dimensions
            img_height, img_width = mask.shape
            
            # Generate XML content - ALWAYS generate, even if empty
            xml_content = create_xml_from_bboxes(
                bounding_boxes, img_width, img_height, 
                self.patient_id, self.view_short, self.filename_stem
            )
            
            # Save XML file
            save_xml_file(xml_content, self.xml_edited)
            print(f"✓ Saved XML to: {self.xml_edited}")
            
            # Prepare result
            bbox_count = len(bounding_boxes)
            abnormal_count = len([b for b in bounding_boxes if b['label'] == 'abnormal'])
            normal_count = len([b for b in bounding_boxes if b['label'] == 'normal'])
            
            if bbox_count == 0:
                bbox_stats = "No annotations (empty but valid for quantification)"
            else:
                bbox_stats = f"{bbox_count} annotations ({abnormal_count} abnormal, {normal_count} normal)"
            
            return {
                'saved_files': [f"• {self.xml_edited.name} (created)"],
                'bbox_stats': bbox_stats,
                'action_type': "created"
            }
            
        except Exception as error:  # ✅ FIX: Use 'error' instead of 'e'
            print(f"✗ Failed to save XML: {error}")
            return None
    
    def _trigger_quantification(self):
        """Trigger quantification pipeline"""
        try:
            from features.spect_viewer.logic.processing_wrapper import (
                run_quantification_for_patient
            )
            
            # ✅ FIX: Gunakan atribut yang benar
            print("[SAVE-PIPELINE] Editor sudah menyimpan classification files.")
            print("[SAVE-PIPELINE] Langsung menjalankan kuantifikasi...")
            
            quant_success = run_quantification_for_patient(
                self._dicom_path,    # ✅ Sekarang ada
                self.patient_id,     # ✅ Sudah ada
                self._study_date     # ✅ Sekarang ada
            )
            
            if quant_success:
                print("[SAVE-PIPELINE] Kuantifikasi berhasil.")
            else:
                print("[SAVE-PIPELINE] Kuantifikasi gagal.")
                # ❌ HAPUS: Jangan panggil QMessageBox dari thread
                # QMessageBox.warning(self, "Analisis Gagal", 
                #                     "Proses kuantifikasi gagal. Periksa file input yang diperlukan.")

            return quant_success
                    
        except Exception as error:  
            print(f"[SAVE-PIPELINE ERROR] Gagal menjalankan kuantifikasi: {error}")
            import traceback
            print(f"[SAVE-PIPELINE] Full traceback: {traceback.format_exc()}")
            
            # ❌ HAPUS: Jangan panggil QMessageBox dari thread
            # QMessageBox.critical(self, "Error Kritis", 
            #                     f"Terjadi error saat menjalankan kuantifikasi:\n{error}")
            return False
    # ================================================================= Dialog
# ================================================================= Dialog
class HotspotEditorDialog(QDialog):
    def __init__(self, scan: Dict, view: str, parent=None):
        super().__init__(parent, Qt.Window)
        from PySide6.QtGui import QGuiApplication
        self.setWindowTitle(f"Hotspot Editor – {view}")
        geom = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(int(geom.width()*0.95), int(geom.height()*0.9))  # Make wider for side-by-side

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
        
        # ✅ FIXED: Use CLASSIFICATION naming convention only
        view_short = "ant" if "ant" in view.lower() else "post"

        # CLASSIFICATION files (only ones we use)
        self._classification_mask_original = base.parent / f"{filename_stem}_{view_full}_classification_mask.png"
        self._classification_mask_edited = base.parent / f"{filename_stem}_{view_full}_classification_mask_edited.png"

        # XML files
        self._xml_original = base.parent / f"{filename_stem}_{view_short}_classification.xml"
        self._xml_edited = base.parent / f"{filename_stem}_{view_short}_classification_edited.xml"

        # ✅ ADD MISSING ATTRIBUTES
        self._xml_loaded_from_edited = False  # Track source of loaded XML

        # Store data for XML generation
        self._patient_id = patient_id
        self._view_short = view_short
        self._filename_stem = filename_stem

        # Store untuk akses ke processing wrapper
        self._dicom_path = Path(scan["path"])
        self._study_date = study_date
        
        # Load segmentation layer
        segmentation_path = base.parent / f"{filename_stem}_{view_full}_colored.png"
        self._segmentation_path = segmentation_path
        
        # Original PNG path
        orig_png_path = base.with_name(f"{base.stem}_{vtag}.png")
        
        print(f"[DEBUG] Classification editor paths:")
        print(f"  Classification mask (original): {self._classification_mask_original}")
        print(f"  Classification mask (edited): {self._classification_mask_edited}")
        print(f"  XML original: {self._xml_original}")
        print(f"  XML edited: {self._xml_edited}")
        print(f"  Segmentation: {self._segmentation_path}")
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
        
        # ✅ FIXED: CLASSIFICATION ONLY - simple priority
        if self._classification_mask_edited.exists():
            # Priority 1: Load from edited classification mask
            print(f"✓ Found EDITED classification mask: {self._classification_mask_edited}")
            mask_arr = self._load_mask_from_classification_png(self._classification_mask_edited)
            self._xml_loaded_from_edited = True  # ✅ SET ATTRIBUTE
        elif self._classification_mask_original.exists():
            # Priority 2: Load from original classification mask
            print(f"✓ Found ORIGINAL classification mask: {self._classification_mask_original}")
            mask_arr = self._load_mask_from_classification_png(self._classification_mask_original)
            self._xml_loaded_from_edited = False  # ✅ SET ATTRIBUTE
        elif self._xml_edited.exists():
            # Priority 3: Load from edited XML
            print(f"✓ Found EDITED XML annotations: {self._xml_edited}")
            self._xml_loaded_from_edited = True  # ✅ SET ATTRIBUTE
            mask_arr = self._load_from_xml(self._xml_edited, orig_arr, filename_stem, view_short, base.parent)
        elif self._xml_original.exists():
            # Priority 4: Load from original XML
            print(f"✓ Found ORIGINAL XML annotations: {self._xml_original}")
            self._xml_loaded_from_edited = False  # ✅ SET ATTRIBUTE
            mask_arr = self._load_from_xml(self._xml_original, orig_arr, filename_stem, view_short, base.parent)
        else:
            # ✅ EMPTY START - no fallback to hotspot files
            print(f"✗ No classification data found. Creating empty mask.")
            mask_arr = np.zeros_like(orig_arr, np.uint8)
            self._xml_loaded_from_edited = False  # ✅ SET ATTRIBUTE

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

        # Store original non-inverted image for toggle functionality
        self._original_image_data = orig_png_arr.copy()
        
        # Apply default inversion (checkbox starts checked)
        from features.spect_viewer.logic.image_inverter import simple_invert_image
        orig_png_arr = simple_invert_image(orig_png_arr)
        print(f"✓ Applied default image inversion")

        print(f"✓ DEBUG Original image range: min={orig_png_arr.min()}, max={orig_png_arr.max()}, shape={orig_png_arr.shape}")

        # Store original mask for reference view
        self._original_mask_arr = mask_arr.copy() if mask_arr is not None else np.zeros_like(orig_arr, np.uint8)

        # ================= SIDE-BY-SIDE UI LAYOUT =================
        # Main container
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(5)

        # ---- LEFT SIDE: Toolbar ----
        toolbar_widget = QWidget()
        toolbar_widget.setMaximumWidth(250)  # Fixed width for toolbar
        toolbar_layout = QVBoxLayout(toolbar_widget)
        
        # Palette section
        toolbar_layout.addWidget(QLabel("<b>Palette / Layers</b>"))
        self.list_palette = QListWidget()
        for rgb, (nm, desc) in zip(_HOTSPOT_PALLETTE, _LABEL_INFO):
            item = QListWidgetItem()
            w = QWidget()
            h = QHBoxLayout(w)
            box = QLabel()
            box.setFixedSize(22, 22)
            box.setStyleSheet(f"background:rgb({rgb[0]},{rgb[1]},{rgb[2]});"
                              "border:1px solid #000;")
            h.addWidget(box)
            h.addWidget(QLabel(nm))
            h.addWidget(QLabel(f"({desc})"))
            h.addStretch()
            item.setSizeHint(w.sizeHint())
            self.list_palette.addItem(item)
            self.list_palette.setItemWidget(item, w)
        self.list_palette.setCurrentRow(1)
        toolbar_layout.addWidget(self.list_palette, 1)

        # Tool buttons
        tool_row = QHBoxLayout()
        self.btn_brush = QPushButton("Brush")
        self.btn_brush.setCheckable(True)
        self.btn_brush.setChecked(True)
        self.btn_eraser = QPushButton("Eraser")
        self.btn_eraser.setCheckable(True)
        self.btn_showall = QPushButton("Show All")
        self.btn_showall.setCheckable(True)
        tool_row.addWidget(self.btn_brush)
        tool_row.addWidget(self.btn_eraser)
        tool_row.addWidget(self.btn_showall)
        toolbar_layout.addLayout(tool_row)

        # Undo/Redo buttons
        undo_row = QHBoxLayout()
        self.btn_undo = QPushButton("Undo")
        self.btn_redo = QPushButton("Redo")
        undo_row.addWidget(self.btn_undo)
        undo_row.addWidget(self.btn_redo)
        toolbar_layout.addLayout(undo_row)

        # Brush Size
        toolbar_layout.addWidget(QLabel("Brush Size (pixels)"))
        self.slider_size = QSlider(Qt.Horizontal)
        self.slider_size.setRange(1, 15)
        self.slider_size.setValue(1)
        self.lbl_size = QLabel("1px")
        self.lbl_size.setFixedWidth(35)
        self.lbl_size.setAlignment(Qt.AlignRight)
        self.btn_size_minus = QPushButton("-")
        self.btn_size_minus.setFixedSize(30, 22)
        self.btn_size_plus = QPushButton("+")
        self.btn_size_plus.setFixedSize(30, 22)
        size_row = QHBoxLayout()
        size_row.setSpacing(3)
        size_row.addWidget(self.btn_size_minus)
        size_row.addWidget(self.slider_size, 1)
        size_row.addWidget(self.btn_size_plus)
        size_row.addWidget(self.lbl_size)
        toolbar_layout.addLayout(size_row)

        # Zoom
        toolbar_layout.addWidget(QLabel("Zoom"))
        self.slider_zoom = QSlider(Qt.Horizontal)
        self.slider_zoom.setRange(1, 1000)
        self.slider_zoom.setValue(10)
        self.lbl_zoom = QLabel("1.0x")
        self.lbl_zoom.setFixedWidth(35)
        self.lbl_zoom.setAlignment(Qt.AlignRight)
        self.btn_zoom_minus = QPushButton("-")
        self.btn_zoom_minus.setFixedSize(30, 22)
        self.btn_zoom_plus = QPushButton("+")
        self.btn_zoom_plus.setFixedSize(30, 22)
        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(3)
        zoom_row.addWidget(self.btn_zoom_minus)
        zoom_row.addWidget(self.slider_zoom, 1)
        zoom_row.addWidget(self.btn_zoom_plus)
        zoom_row.addWidget(self.lbl_zoom)
        toolbar_layout.addLayout(zoom_row)

        # Original Opacity
        toolbar_layout.addWidget(QLabel("Original Opacity"))
        self.slider_gray = QSlider(Qt.Horizontal)
        self.slider_gray.setRange(0, 100)
        self.slider_gray.setValue(50)
        self.lbl_gray = QLabel("50 %")
        self.lbl_gray.setFixedWidth(35)
        self.lbl_gray.setAlignment(Qt.AlignRight)
        self.btn_gray_minus = QPushButton("-")
        self.btn_gray_minus.setFixedSize(30, 22)
        self.btn_gray_plus = QPushButton("+")
        self.btn_gray_plus.setFixedSize(30, 22)
        gray_row = QHBoxLayout()
        gray_row.setSpacing(3)
        gray_row.addWidget(self.btn_gray_minus)
        gray_row.addWidget(self.slider_gray, 1)
        gray_row.addWidget(self.btn_gray_plus)
        gray_row.addWidget(self.lbl_gray)
        toolbar_layout.addLayout(gray_row)

        # Mask Opacity
        toolbar_layout.addWidget(QLabel("Mask Opacity"))
        self.slider_mask = QSlider(Qt.Horizontal)
        self.slider_mask.setRange(0, 100)
        self.slider_mask.setValue(100)
        self.lbl_mask = QLabel("100 %")
        self.lbl_mask.setFixedWidth(35)
        self.lbl_mask.setAlignment(Qt.AlignRight)
        self.btn_mask_minus = QPushButton("-")
        self.btn_mask_minus.setFixedSize(30, 22)
        self.btn_mask_plus = QPushButton("+")
        self.btn_mask_plus.setFixedSize(30, 22)
        mask_row = QHBoxLayout()
        mask_row.setSpacing(3)
        mask_row.addWidget(self.btn_mask_minus)
        mask_row.addWidget(self.slider_mask, 1)
        mask_row.addWidget(self.btn_mask_plus)
        mask_row.addWidget(self.lbl_mask)
        toolbar_layout.addLayout(mask_row)

        # BG Opacity
        toolbar_layout.addWidget(QLabel("BG Opacity"))
        self.slider_bg = QSlider(Qt.Horizontal)
        self.slider_bg.setRange(0, 100)
        self.slider_bg.setValue(0)
        self.lbl_bg = QLabel("0 %")
        self.lbl_bg.setFixedWidth(35)
        self.lbl_bg.setAlignment(Qt.AlignRight)
        self.btn_bg_minus = QPushButton("-")
        self.btn_bg_minus.setFixedSize(30, 22)
        self.btn_bg_plus = QPushButton("+")
        self.btn_bg_plus.setFixedSize(30, 22)
        bg_row = QHBoxLayout()
        bg_row.setSpacing(3)
        bg_row.addWidget(self.btn_bg_minus)
        bg_row.addWidget(self.slider_bg, 1)
        bg_row.addWidget(self.btn_bg_plus)
        bg_row.addWidget(self.lbl_bg)
        toolbar_layout.addLayout(bg_row)

        # Segmentation Opacity
        toolbar_layout.addWidget(QLabel("Segmentation Opacity"))
        self.slider_seg = QSlider(Qt.Horizontal)
        self.slider_seg.setRange(0, 100)
        self.slider_seg.setValue(30)
        self.lbl_seg = QLabel("30 %")
        self.lbl_seg.setFixedWidth(35)
        self.lbl_seg.setAlignment(Qt.AlignRight)
        self.btn_seg_minus = QPushButton("-")
        self.btn_seg_minus.setFixedSize(30, 22)
        self.btn_seg_plus = QPushButton("+")
        self.btn_seg_plus.setFixedSize(30, 22)
        seg_row = QHBoxLayout()
        seg_row.setSpacing(3)
        seg_row.addWidget(self.btn_seg_minus)
        seg_row.addWidget(self.slider_seg, 1)
        seg_row.addWidget(self.btn_seg_plus)
        seg_row.addWidget(self.lbl_seg)
        toolbar_layout.addLayout(seg_row)

        # Contrast button
        btn_contrast = QPushButton("Contrast…")
        toolbar_layout.addWidget(btn_contrast)

        # Invert Image checkbox (following main window pattern)
        self.invert_checkbox = QCheckBox("Invert Image Colors")
        self.invert_checkbox.setChecked(True)  # Default to inverted (checked)
        self.invert_checkbox.setStyleSheet("margin-top: 8px; font-weight: bold;")
        toolbar_layout.addWidget(self.invert_checkbox)

        # Setup segmentation layer status
        if self._segmentation_path.exists():
            segmentation_status = f"Segmentation loaded: {self._segmentation_path.name}"
        else:
            segmentation_status = f"No segmentation found: {self._segmentation_path.name}"
            self.slider_seg.setEnabled(False)

        # Instructions and data info
        data_source = "Original PNG loaded" if self._has_orig_png else "DICOM frames used"
        if mask_arr is not None and np.any(mask_arr):
            if self._xml_loaded_from_edited:
                mask_status = "Edited XML loaded"
            elif hasattr(self, '_xml_original') and self._xml_original.exists():
                mask_status = "Original XML loaded"
            else:
                mask_status = "Existing mask loaded"
        else:
            mask_status = "New mask created"

        instructions = QLabel(
            "<b>Controls:</b><br>"
            "• Left click/drag: Paint<br>"
            "• Middle click/drag: Pan<br>"
            "• Ctrl+scroll: Zoom<br>"
            "• Ctrl+Z: Undo edit<br>"
            "• Ctrl+Y: Redo Edit<br>"
            "• Grid appears at 2x+ zoom<br>"
            "• <b>Paint only on colored segments</b><br><br>"
            f"<b>Data Info:</b><br>"
            f"• Image: {data_source}<br>"
            f"• Mask: {mask_status}<br>"
            f"• Segmentation: {segmentation_status}<br>"
            f"• Size: {orig_png_arr.shape[1]}×{orig_png_arr.shape[0]}<br>"
            f"• XML: Save to '_edited' only"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("QLabel { background: #f0f0f0; padding: 8px; border-radius: 4px; }")
        toolbar_layout.addWidget(instructions)

        # Save/Cancel buttons
        btn_save = QPushButton("Save")
        btn_cancel = QPushButton("Cancel")
        toolbar_layout.addWidget(btn_save)
        toolbar_layout.addWidget(btn_cancel)
        toolbar_layout.addStretch()

        # Add toolbar to main layout
        main_layout.addWidget(toolbar_widget)

        # ---- MIDDLE: Original Scan Image (READ-ONLY with zoom sync) ----
        scan_layout = QVBoxLayout()
        
        # Header for scan image
        scan_header = QLabel("Scan Image")
        scan_header.setAlignment(Qt.AlignCenter)
        scan_header.setStyleSheet("QLabel { background: #e0e0e0; padding: 5px; font-weight: bold; }")
        scan_layout.addWidget(scan_header)

        # Original scan canvas (READ-ONLY but with zoom interaction)
        self.original_canvas = _Canvas(orig_png_arr, np.zeros_like(orig_png_arr, np.uint8))
        # Don't disable completely - we want zoom interaction but no painting
        self.original_canvas._painting_disabled = True  # Custom flag to disable painting only
        self.original_canvas.setStyleSheet("QGraphicsView { border: 1px solid #888; }")
        
        # Setup original canvas with segmentation if available
        if self._segmentation_path.exists():
            self.original_canvas.set_segmentation_layer(self._segmentation_path)
        
        scan_layout.addWidget(self.original_canvas)
        
        # Add scan layout to main layout
        main_layout.addLayout(scan_layout)

        # ---- RIGHT: Hotspot Editor (EDITABLE) ----
        editor_layout = QVBoxLayout()
        
        # Header for editor
        editor_header = QLabel("Hotspot Editor")
        editor_header.setAlignment(Qt.AlignCenter)
        editor_header.setStyleSheet("QLabel { background: #d0f0d0; padding: 5px; font-weight: bold; }")
        editor_layout.addWidget(editor_header)

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
        editor_layout.addWidget(info_frame)

        # Main editing canvas (EDITABLE)
        self.canvas = _Canvas(orig_png_arr, mask_arr)  # ← ENABLED FOR EDITING
        self.canvas.set_info_callback(self._update_info_display)
        self.canvas.setStyleSheet("QGraphicsView { border: 1px solid #4a90e2; }")
        
        # Setup segmentation layer
        if self._segmentation_path.exists():
            success = self.canvas.set_segmentation_layer(self._segmentation_path)
            if success:
                print(f"✓ Segmentation loaded: {self._segmentation_path.name}")
            else:
                print(f"✗ Segmentation load failed: {self._segmentation_path.name}")
        else:
            print(f"✗ No segmentation found: {self._segmentation_path.name}")
        
        editor_layout.addWidget(self.canvas)
        
        # Add editor layout to main layout
        main_layout.addLayout(editor_layout)

        # Set layout proportions: Toolbar(fixed) : Scan(50%) : Editor(50%)
        main_layout.setStretchFactor(main_layout.itemAt(0).widget(), 0)  # Toolbar - fixed
        main_layout.setStretchFactor(main_layout.itemAt(1).layout(), 2)  # Scan - flexible
        main_layout.setStretchFactor(main_layout.itemAt(2).layout(), 2)  # Editor - flexible

        # ===== CONNECT ALL SIGNALS =====
        self.list_palette.currentRowChanged.connect(self._change_label)
        self.slider_size.valueChanged.connect(self._size_changed)
        self.slider_zoom.valueChanged.connect(self._zoom_slider_changed)
        self.btn_showall.toggled.connect(self.canvas.toggle_show_all)
        self.btn_brush.clicked.connect(self._select_brush)
        self.btn_eraser.clicked.connect(self._select_eraser)
        self.slider_gray.valueChanged.connect(self._gray_alpha_changed)
        self.slider_mask.valueChanged.connect(self._mask_alpha_changed)
        self.slider_bg.valueChanged.connect(self._bg_alpha_changed)
        self.slider_seg.valueChanged.connect(self._seg_alpha_changed)
        btn_contrast.clicked.connect(self._open_contrast_popup)
        self.invert_checkbox.stateChanged.connect(self._on_invert_changed)
        btn_save.clicked.connect(self._save_all)
        btn_cancel.clicked.connect(self.reject)
        self.btn_undo.clicked.connect(self._perform_undo)
        self.btn_redo.clicked.connect(self._perform_redo)

        # All the +/- button connections
        self.btn_size_minus.clicked.connect(lambda: self._adjust_slider(self.slider_size, -1))
        self.btn_size_plus.clicked.connect(lambda: self._adjust_slider(self.slider_size, 1))
        self.btn_zoom_minus.clicked.connect(lambda: self._adjust_slider(self.slider_zoom, -5))
        self.btn_zoom_plus.clicked.connect(lambda: self._adjust_slider(self.slider_zoom, 5))
        self.btn_gray_minus.clicked.connect(lambda: self._adjust_slider(self.slider_gray, -5))
        self.btn_gray_plus.clicked.connect(lambda: self._adjust_slider(self.slider_gray, 5))
        self.btn_mask_minus.clicked.connect(lambda: self._adjust_slider(self.slider_mask, -5))
        self.btn_mask_plus.clicked.connect(lambda: self._adjust_slider(self.slider_mask, 5))
        self.btn_bg_minus.clicked.connect(lambda: self._adjust_slider(self.slider_bg, -5))
        self.btn_bg_plus.clicked.connect(lambda: self._adjust_slider(self.slider_bg, 5))
        self.btn_seg_minus.clicked.connect(lambda: self._adjust_slider(self.slider_seg, -5))
        self.btn_seg_plus.clicked.connect(lambda: self._adjust_slider(self.slider_seg, 5))
        
        # Set up zoom synchronization between canvases
        self._sync_zoom_in_progress = False  # Prevent infinite loop
        self._setup_zoom_sync()
        
        self._save_thread = None
        self._loading_dialog = None
        self._is_saving = False

    def _setup_zoom_sync(self):
        """Setup bidirectional zoom synchronization between original and editor canvases"""
        # Override wheel events for both canvases to enable sync
        original_wheel_event = self.original_canvas.wheelEvent
        editor_wheel_event = self.canvas.wheelEvent
        
        def sync_original_wheel(event):
            if not self._sync_zoom_in_progress and event.modifiers() & Qt.ControlModifier:
                self._sync_zoom_in_progress = True
                # Apply zoom to original canvas
                original_wheel_event(event)
                # Sync to editor canvas
                current_zoom = self.original_canvas._zoom_factor
                self.canvas.set_zoom(current_zoom)
                # Update slider
                slider_value = int(current_zoom * 10)
                self.slider_zoom.setValue(slider_value)
                self.lbl_zoom.setText(f"{current_zoom:.1f}x")
                self._sync_zoom_in_progress = False
            elif not (event.modifiers() & Qt.ControlModifier):
                # Pass through non-zoom wheel events
                original_wheel_event(event)
        
        def sync_editor_wheel(event):
            if not self._sync_zoom_in_progress and event.modifiers() & Qt.ControlModifier:
                self._sync_zoom_in_progress = True
                # Apply zoom to editor canvas
                editor_wheel_event(event)
                # Sync to original canvas
                current_zoom = self.canvas._zoom_factor
                self.original_canvas.set_zoom(current_zoom)
                # Update slider
                slider_value = int(current_zoom * 10)
                self.slider_zoom.setValue(slider_value)
                self.lbl_zoom.setText(f"{current_zoom:.1f}x")
                self._sync_zoom_in_progress = False
            elif not (event.modifiers() & Qt.ControlModifier):
                # Pass through non-zoom wheel events
                editor_wheel_event(event)
        
        # Replace wheel event handlers
        self.original_canvas.wheelEvent = sync_original_wheel
        self.canvas.wheelEvent = sync_editor_wheel

    def _load_from_xml(self, xml_path: Path, orig_arr: np.ndarray, filename_stem: str, 
                       view_short: str, base_dir: Path) -> np.ndarray:
        """Load mask from XML file."""
        try:
            # Determine image to use for processing
            orig_png_path = base_dir / f"{filename_stem}_{view_short}.png"
            if orig_png_path.exists():
                input_image_path = str(orig_png_path)
                print(f"✓ Using original PNG for XML processing: {orig_png_path}")
            else:
                # Save DICOM frame to temp PNG
                temp_png_path = base_dir / f"{filename_stem}_temp.png"
                Image.fromarray(orig_arr).save(temp_png_path)
                input_image_path = str(temp_png_path)
                print(f"✓ Saved DICOM frame to temp PNG for XML processing: {input_image_path}")

            # Parse and process
            boxes = parse_xml_annotations(str(xml_path))
            if boxes:
                mask_arr, overlayed_pil, _ = create_hotspot_mask(
                    input_image_path,
                    boxes,
                    self._patient_id,
                    view_short, str(base_dir)
                )
                # Convert to label format
                recolor = np.zeros_like(mask_arr, dtype=np.uint8)
                recolor[mask_arr > 200] = 1      # Abnormal
                recolor[(mask_arr > 50) & (mask_arr <= 200)] = 2  # Normal
                print(f"✓ Generated mask from XML: {xml_path}")
                return recolor
            else:
                print(f"✗ No bounding boxes in XML: {xml_path}")
                return np.zeros_like(orig_arr, np.uint8)
        except Exception as e:
            print(f"✗ Error processing XML {xml_path}: {e}")
            return np.zeros_like(orig_arr, np.uint8)

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
        """Handle zoom slider change with bidirectional synchronization"""
        if self._sync_zoom_in_progress:
            return  # Prevent feedback loop
            
        self._sync_zoom_in_progress = True
        zoom_factor = val / 10.0
        
        # Apply zoom to both canvases
        self.canvas.set_zoom(zoom_factor)
        self.original_canvas.set_zoom(zoom_factor)
        self.lbl_zoom.setText(f"{zoom_factor:.1f}x")
        
        self._sync_zoom_in_progress = False

    # -- Opacity handlers: update opacity label + send to EDITABLE canvas only ----
    def _gray_alpha_changed(self, val: int):
        alpha = val / 100.0
        self.canvas.set_gray_opacity(alpha)  # Only affects editable canvas
        self.original_canvas.set_gray_opacity(alpha)  # Sync with original view
        self.lbl_gray.setText(f"{val} %")

    def _mask_alpha_changed(self, val: int):
        alpha = val / 100.0
        self.canvas.set_mask_opacity(alpha)  # Only affects editable canvas
        self.lbl_mask.setText(f"{val} %")

    def _bg_alpha_changed(self, val: int):
        a = val / 100.0
        self.canvas.set_bg_opacity(a)  # Only affects editable canvas
        self.lbl_bg.setText(f"{val} %")

    def _seg_alpha_changed(self, val: int):
        """Handle segmentation opacity change."""
        alpha = val / 100.0
        self.canvas.set_segmentation_opacity(alpha)  # Only affects editable canvas
        self.original_canvas.set_segmentation_opacity(alpha)  # Sync with original view
        self.lbl_seg.setText(f"{val} %")
        
    # ---------- contrast mini-popup ------------------------------
    def _open_contrast_popup(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Brightness / Contrast")
        dlg.setFixedSize(300, 400)
        lay = QVBoxLayout(dlg)

        pad = _BCPad()
        lbl = QLabel("B 0.00  C 1.00")
        lay.addWidget(QLabel("Drag crosshair – X = brightness, Y = contrast"))
        lay.addWidget(pad, 0, Qt.AlignCenter)
        
        # Labels for reference
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel("Dark"))
        ref_layout.addStretch()
        ref_layout.addWidget(QLabel("Normal"))
        ref_layout.addStretch()
        ref_layout.addWidget(QLabel("Bright"))
        lay.addLayout(ref_layout)

        # Labels for contrast (vertical)
        contrast_info = QLabel("↑ High Contrast\n↓ Low Contrast")
        contrast_info.setAlignment(Qt.AlignCenter)
        lay.addWidget(contrast_info)
        lay.addWidget(lbl, 0, Qt.AlignCenter)

        def _on_change(b, c):
            lbl.setText(f"B {b:+.2f}   C {c:.2f}")
            self.canvas.set_bc(b, c)  # Only affects editable canvas
            self.original_canvas.set_bc(b, c)  # Sync with original view
        pad.valueChanged.connect(_on_change)

        dlg.exec()

    def _on_invert_changed(self, state: int):
        """Handle image inversion toggle for both canvases following main window pattern"""
        from features.spect_viewer.logic.image_inverter import simple_invert_image
        
        print(f"[DEBUG] === INVERT CHECKBOX CHANGED ===")
        
        actual_checked = self.invert_checkbox.isChecked()
        
        print(f"[DEBUG] Checkbox state: {state}, isChecked(): {actual_checked}")
        
        try:
            if actual_checked:
                inverted_data = simple_invert_image(self._original_image_data)
                print("✓ Applied image inversion (checked)")
            else:
                inverted_data = self._original_image_data.copy()
                print("✓ Removed image inversion (unchecked)")
            
            # This call will now work correctly
            self._update_canvas_images(inverted_data)
            
        except Exception as e:
            print(f"✗ Error during image inversion: {e}")
            self.invert_checkbox.setChecked(not actual_checked)

    def _update_canvas_images(self, new_image_data: np.ndarray):
            """Update both canvases with new image data - FIXED VERSION"""
            try:
                if new_image_data.dtype != np.uint8:
                    normalized_data = ((new_image_data - new_image_data.min()) /
                                    max(1, np.ptp(new_image_data)) * 255).astype(np.uint8)
                else:
                    normalized_data = new_image_data.copy()

                self.original_canvas._orig_base = normalized_data.copy()
                self.canvas._orig_base = normalized_data.copy()

                h, w = normalized_data.shape
                q_image = QImage(normalized_data.data, w, h, w, QImage.Format_Grayscale8)
                pixmap = QPixmap.fromImage(q_image.copy())

                self.original_canvas._item_gray.setPixmap(pixmap)
                self.canvas._item_gray.setPixmap(pixmap)

                current_brightness = getattr(self, '_current_brightness', 0.0)
                current_contrast = getattr(self, '_current_contrast', 1.0)

                if current_brightness != 0.0 or current_contrast != 1.0:
                    self.canvas.set_bc(current_brightness, current_contrast)
                    self.original_canvas.set_bc(current_brightness, current_contrast)

                self.original_canvas.viewport().update()
                self.canvas.viewport().update()
                
                print("✓ Successfully updated both canvas images with new inversion state")
                
            except Exception as e:
                print(f"✗ Error updating canvas images: {e}")
                import traceback
                traceback.print_exc()

    # ---------- palette & tools (only affect editable canvas)
    def _select_brush(self):
        self.btn_eraser.setChecked(False)
        self.canvas.set_label(self.list_palette.currentRow())  # Only affects editable canvas
    
    def _select_eraser(self):
        self.btn_brush.setChecked(False)
        self.canvas.set_eraser()  # Only affects editable canvas
    
    def _change_label(self, idx: int):
        self.btn_brush.setChecked(True)
        self.btn_eraser.setChecked(False)
        self.canvas.set_label(idx)  # Only affects editable canvas

    # ---------- I/O helpers
    def _load_mask_from_classification_png(self, classification_path: Path) -> np.ndarray:
        """Load mask from classification PNG file."""
        try:
            # Load classification mask
            rgb = np.array(Image.open(classification_path).convert("RGB"))
            mask = np.zeros(rgb.shape[:2], np.uint8)
            
            # Convert classification colors to hotspot labels
            # Red (255,0,0) -> Abnormal (1)
            red_mask = np.all(rgb == [255, 0, 0], axis=-1)
            mask[red_mask] = 1
            
            # Cream (255,241,188) -> Normal (2)  
            cream_mask = np.all(rgb == [255, 241, 188], axis=-1)
            mask[cream_mask] = 2
            
            print(f"✓ Successfully loaded classification mask from: {classification_path}")
            return mask
            
        except Exception as e:
            print(f"✗ Failed to load classification mask: {e}")
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

    def _save_xml_with_backup(self, mask: np.ndarray):
        """Always generate XML even if no annotations found"""
        try:
            print(f"[DEBUG-XML] Starting XML save for {self._patient_id}")
            print(f"[DEBUG-XML] View: {self._view_short}, Filename stem: {self._filename_stem}")
            print(f"[DEBUG-XML] Will save to: {self._xml_edited}")
            print(f"[DEBUG-XML] Mask shape: {mask.shape}, unique values: {np.unique(mask)}")
            
            # Generate bounding boxes with segment detection
            segmentation_arr = self.canvas._segmentation_arr
            bounding_boxes = mask_to_bounding_boxes(mask, segmentation_arr, min_area=10)
            print(f"[DEBUG-XML] Generated {len(bounding_boxes)} bounding boxes")
            
            # Always save XML - even if empty
            if not bounding_boxes:
                print("✓ Saving empty XML (no annotations found - but file will exist)")
                bounding_boxes = []  # Empty but valid list
            
            # Get image dimensions
            img_height, img_width = mask.shape
            
            # Generate XML content - always generate, even if empty
            xml_content = create_xml_from_bboxes(
                bounding_boxes, img_width, img_height, 
                self._patient_id, self._view_short, self._filename_stem
            )
            
            # Always save XML file - even empty ones
            save_xml_file(xml_content, self._xml_edited)
            print(f"✓ Saved XML to: {self._xml_edited}")
            
            # Check if we're overwriting an existing edited file
            is_overwrite = self._xml_edited.exists()
            
            # Prepare result
            saved_files = []
            if is_overwrite:
                saved_files.append(f"• {self._xml_edited.name} (updated)")
                action_type = "updated"
            else:
                saved_files.append(f"• {self._xml_edited.name} (created)")
                action_type = "created"
            
            # Show success message
            bbox_count = len(bounding_boxes)
            abnormal_count = len([b for b in bounding_boxes if b['label'] == 'abnormal'])
            normal_count = len([b for b in bounding_boxes if b['label'] == 'normal'])
            
            # Better message for empty case
            if bbox_count == 0:
                bbox_stats = "No annotations (empty but valid for quantification)"
            else:
                bbox_stats = f"{bbox_count} annotations ({abnormal_count} abnormal, {normal_count} normal)"
            
            return {
                'saved_files': saved_files,
                'bbox_stats': bbox_stats,
                'action_type': action_type
            }
            
        except Exception as e:
            print(f"✗ Failed to save XML: {e}")
            return None
    
    def _trigger_quantification(self):
        """
        Modified: Trigger complete analysis pipeline: Classification FIRST, then Quantification.
        """
        try:
            from features.spect_viewer.logic.processing_wrapper import (
                run_classification_for_patient,
                run_quantification_for_patient
            )

            # Step 1: Run classification again
            import inspect
            try:
                path_file = inspect.getfile(run_classification_for_patient)
                print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                print(f"!!! DEBUG: Function 'run_classification_for_patient' loaded from:")
                print(f"!!! {path_file}")
                print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            except TypeError:
                print("!!! DEBUG: Cannot find file path for 'run_classification_for_patient'.")

            print("[SAVE-PIPELINE] Triggering classification re-run (from editor)...")
            clf_success = run_classification_for_patient(
                self._dicom_path,
                self._patient_id,
                self._study_date,
                source_is_editor=True
            )

            # Step 2: Check classification results
            if not clf_success:
                print("[SAVE-PIPELINE] Classification re-run failed. Quantification process cancelled.")
                QMessageBox.warning(self, "Analysis Failed", 
                                    "Classification re-run failed. Quantification not executed.")
                return False

            print("[SAVE-PIPELINE] Classification re-run successful.")

            # Step 3: Run quantification (only if classification successful)
            print("[SAVE-PIPELINE] Triggering quantification re-run...")
            quant_success = run_quantification_for_patient(
                self._dicom_path,
                self._patient_id,
                self._study_date
            )
            
            if quant_success:
                print("[SAVE-PIPELINE] Quantification re-run successful.")
            else:
                print("[SAVE-PIPELINE] Quantification re-run failed.")
                QMessageBox.warning(self, "Analysis Failed", 
                                    "Quantification re-run failed after successful classification.")

            return quant_success

        except Exception as e:
            print(f"[SAVE-PIPELINE ERROR] Failed to run advanced analysis: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Critical Error", 
                                f"Error occurred during advanced analysis:\n{e}")
            return False
        
    def _save_all(self):
        """Save with threaded processing and loading dialog"""
        
        if self._is_saving:
            QMessageBox.warning(self, "Save in Progress", "Please wait for current save to complete.")
            return
        
        self._is_saving = True
        
        # Disable save button
        for widget in self.findChildren(QPushButton):
            if widget.text() == "Save":
                widget.setEnabled(False)
                widget.setText("Saving...")
        
        # Create and show loading dialog
        self._loading_dialog = LoadingDialog(
            title="Saving Classification",
            message="Preparing to save classification edits...",
            show_progress=True,
            show_cancel=False,
            parent=self
        )
        self._loading_dialog.show()
        
        # Create save thread
        self._save_thread = SaveThread(
            self.canvas,  # Only save from editable canvas
            self._classification_mask_edited,
            self._xml_edited,
            self._patient_id,
            self._view_short,
            self._filename_stem,
            self._dicom_path,
            self._study_date
        )
        
        # Connect signals
        self._save_thread.progress_updated.connect(self._on_save_progress)
        self._save_thread.save_completed.connect(self._on_save_completed)
        
        # Start save process
        self._save_thread.start()

    def _on_save_progress(self, progress: int, message: str):
        """Handle save progress updates"""
        if self._loading_dialog:
            self._loading_dialog.set_progress(progress)
            self._loading_dialog.set_message(message)

    def _on_save_completed(self, success: bool, message: str):
        """Handle save completion"""
        if self._loading_dialog:
            self._loading_dialog.close()
            self._loading_dialog = None
        
        self._is_saving = False
        
        # Re-enable save button
        for widget in self.findChildren(QPushButton):
            if "Saving..." in widget.text():
                widget.setEnabled(True)
                widget.setText("Save")
        
        # Safe to call QMessageBox from main thread
        if success:
            QMessageBox.information(self, "Success", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Save Failed", message)
        
        # Clean up thread
        if self._save_thread:
            self._save_thread.deleteLater()
            self._save_thread = None