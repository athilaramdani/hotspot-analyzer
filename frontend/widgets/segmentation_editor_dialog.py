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

from PySide6.QtCore    import Qt, QRectF, QPointF
from PySide6.QtGui     import (
    QPixmap, QImage, QPainter, QColor, QPen, QWheelEvent, QCursor
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
        gray_q = self._nd_gray_to_qimage(orig)
        self._item_gray = QGraphicsPixmapItem(QPixmap.fromImage(gray_q))
        self._item_gray.setOpacity(0.5)
        self._scene.addItem(self._item_gray)

        # mask layer
        self._mask_arr = mask.astype(np.uint8)
        self._mask_img = self._mask_to_qimage(show_all=False, label=1)
        self._item_mask = QGraphicsPixmapItem(QPixmap.fromImage(self._mask_img))
        self._scene.addItem(self._item_mask)

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
        rgb = label_mask_to_rgb(self._mask_arr)
        if not show_all:
            sel = self._mask_arr == label
            rgb[~sel] = (0, 0, 0)
        h, w, _ = rgb.shape
        rgba = np.concatenate([rgb, np.full((h, w, 1), 255, np.uint8)], axis=-1)
        return QImage(rgba.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()

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
    
    def current_mask(self) -> np.ndarray:     
        return self._mask_arr

    # -------- refresh mask pixmap
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
            # Single pixel brush - langsung apply
            if 0 <= x < w and 0 <= y < h:
                if self._eraser:
                    self._mask_arr[y, x] = 0
                else:
                    self._mask_arr[y, x] = self._cur_label
        else:
            # Multi-pixel brush dengan area yang konsisten
            radius = self._brush_sz
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    # Circular brush untuk hasil yang lebih smooth
                    if dx*dx + dy*dy <= radius*radius:
                        px = x + dx
                        py = y + dy
                        if 0 <= px < w and 0 <= py < h:
                            if self._eraser:
                                self._mask_arr[py, px] = 0
                            else:
                                self._mask_arr[py, px] = self._cur_label
        
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
        else:
            # Gunakan data dari DICOM frame langsung
            orig_png_arr = orig_arr
            print(f"✓ Using DICOM frame data for {view}")

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

        bar.addWidget(QLabel("Brush Size (pixels)"))
        self.slider_size = QSlider(Qt.Horizontal); self.slider_size.setRange(1,15); self.slider_size.setValue(1)
        self.lbl_size = QLabel("1px")
        size_row = QHBoxLayout()
        size_row.addWidget(self.slider_size)
        size_row.addWidget(self.lbl_size)
        bar.addLayout(size_row)

        bar.addWidget(QLabel("Zoom"))
        self.slider_zoom = QSlider(Qt.Horizontal); self.slider_zoom.setRange(1,1000); self.slider_zoom.setValue(10)
        self.lbl_zoom = QLabel("1.0x")
        zoom_row = QHBoxLayout()
        zoom_row.addWidget(self.slider_zoom)
        zoom_row.addWidget(self.lbl_zoom)
        bar.addLayout(zoom_row)

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

        # ===== signals =====
        self.list_palette.currentRowChanged.connect(self._change_label)
        self.slider_size.valueChanged.connect(self._size_changed)
        self.slider_zoom.valueChanged.connect(self._zoom_slider_changed)
        self.btn_showall.toggled.connect(self.canvas.toggle_show_all)
        self.btn_brush.clicked.connect(self._select_brush)
        self.btn_eraser.clicked.connect(self._select_eraser)
        btn_save.clicked.connect(self._save_all)
        btn_cancel.clicked.connect(self.reject)

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
            self.lbl_size.setText(f"R{size} (~{area_pixels}px)")

    def _zoom_slider_changed(self, val: int):
        """Handle zoom slider change"""
        zoom_factor = val / 10.0   # 0.1 – 100.0x
        self.canvas.set_zoom(zoom_factor)
        self.lbl_zoom.setText(f"{zoom_factor:.1f}x")

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