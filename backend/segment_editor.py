# backend/segment_editor.py
import traceback
import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QSlider, QToolButton, QButtonGroup
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.colors import ListedColormap
import matplotlib.pyplot as plt

class SegmentEditor(QWidget):
    saved = Signal(np.ndarray)  # Signal to emit when saved

    def __init__(self, original_img, nnunet_mask, palette):
        super().__init__()
        self.original = original_img
        self.mask = nnunet_mask.copy()
        self.backup_mask = nnunet_mask.copy()
        self.palette = palette
        self.current_label = 1  # Default: skull
        self.brush_size = 5
        self.current_mode = "draw"  # 'draw' or 'erase'
        self.zoom_factor = 1.0
        self.setWindowTitle("Segment Editor")
        self.setMinimumSize(800, 600)
        
        # Create colormap from palette
        self.cmap = ListedColormap([np.array(color)/255 for color in palette])
        
        self._setup_ui()
        self._update_display()

    def _setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        # Label selection
        self.label_combo = QComboBox()
        self.label_combo.addItems([
            "Background", "Skull", "Cervical Vertebrae", 
            "Thoracic Vertebrae", "Rib", "Sternum", "Collarbone",
            "Scapula", "Humerus", "Lumbar Vertebrae", "Sacrum",
            "Pelvis", "Femur"
        ])
        self.label_combo.setCurrentIndex(1)  # Set default to Skull
        self.label_combo.currentIndexChanged.connect(self._on_label_changed)
        
        # Brush size
        size_slider = QSlider(Qt.Horizontal)
        size_slider.setRange(1, 20)
        size_slider.setValue(self.brush_size)
        size_slider.valueChanged.connect(self._on_brush_size_changed)
        
        # Mode buttons (draw/erase)
        self.mode_group = QButtonGroup(self)
        self.btn_draw = QToolButton()
        self.btn_draw.setText("Draw")
        self.btn_draw.setCheckable(True)
        self.btn_draw.setChecked(True)
        self.btn_draw.clicked.connect(lambda: self._set_mode("draw"))
        
        self.btn_erase = QToolButton()
        self.btn_erase.setText("Erase")
        self.btn_erase.setCheckable(True)
        self.btn_erase.clicked.connect(lambda: self._set_mode("erase"))
        
        self.mode_group.addButton(self.btn_draw)
        self.mode_group.addButton(self.btn_erase)
        
        # Zoom buttons
        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText("Zoom In")
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        
        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText("Zoom Out")
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        
        # Action buttons
        btn_undo = QPushButton("Undo")
        btn_undo.clicked.connect(self._undo)
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self._emit_save)
        
        # Add widgets to toolbar
        toolbar.addWidget(QLabel("Edit Part:"))
        toolbar.addWidget(self.label_combo)
        toolbar.addWidget(QLabel("Brush Size:"))
        toolbar.addWidget(size_slider)
        toolbar.addWidget(self.btn_draw)
        toolbar.addWidget(self.btn_erase)
        toolbar.addWidget(self.btn_zoom_in)
        toolbar.addWidget(self.btn_zoom_out)
        toolbar.addWidget(btn_undo)
        toolbar.addWidget(btn_save)
        
        # Canvas
        self.canvas = FigureCanvasQTAgg(Figure())
        self.ax = self.canvas.figure.subplots()
        self.canvas.mpl_connect('button_press_event', self._on_click)
        self.canvas.mpl_connect('motion_notify_event', self._on_drag)
        self.canvas.mpl_connect('scroll_event', self._on_scroll)
        
        main_layout.addLayout(toolbar)
        main_layout.addWidget(self.canvas)
        self.setLayout(main_layout)

    def _update_display(self):
        """Render gambar dengan overlay segmentasi berwarna"""
        self.ax.clear()
        
        try:
            # Pastikan gambar original 2D
            if self.original.ndim == 3:
                if self.original.shape[2] == 1:  # Jika format (H,W,1)
                    display_img = self.original[:,:,0]
                else:  # Jika format RGB
                    display_img = cv2.cvtColor(self.original, cv2.COLOR_RGB2GRAY)
            else:
                display_img = self.original
                
            # Tampilkan gambar original
            self.ax.imshow(display_img, cmap='gray', extent=[0, display_img.shape[1], display_img.shape[0], 0])
            
            # Pastikan mask dalam format yang benar
            if self.mask.ndim == 3:
                if self.mask.shape[2] == 1:  # Jika format (H,W,1)
                    mask_display = self.mask[:,:,0]
                else:  # Jika format RGB, konversi ke label mask
                    mask_display = self._rgb_to_label_mask(self.mask)
            else:
                mask_display = self.mask
            
            # Pastikan mask memiliki nilai yang valid (0-12)
            mask_display = np.clip(mask_display, 0, 12)
            
            # Tampilkan mask dengan colormap khusus dan transparansi
            # Buat mask untuk area yang tidak kosong (bukan background)
            non_zero_mask = mask_display > 0
            if np.any(non_zero_mask):
                self.ax.imshow(mask_display, cmap=self.cmap, alpha=0.6, vmin=0, vmax=12, 
                              extent=[0, mask_display.shape[1], mask_display.shape[0], 0])
            
            # Highlight label yang sedang aktif dengan contour
            if self.current_label > 0:
                contour_mask = (mask_display == self.current_label).astype(np.uint8)
                if np.any(contour_mask):
                    contours, _ = cv2.findContours(
                        contour_mask,
                        cv2.RETR_EXTERNAL, 
                        cv2.CHAIN_APPROX_SIMPLE
                    )
                    for cnt in contours:
                        if len(cnt) > 2:
                            cnt = cnt.squeeze()
                            if cnt.ndim == 2:
                                self.ax.plot(cnt[:, 0], cnt[:, 1], 'r-', linewidth=2)
            
            # Apply zoom
            h, w = mask_display.shape
            x_center, y_center = w/2, h/2
            x_width = w / (2 * self.zoom_factor)
            y_width = h / (2 * self.zoom_factor)
            
            self.ax.set_xlim(x_center - x_width, x_center + x_width)
            self.ax.set_ylim(y_center + y_width, y_center - y_width)  # Note: inverted y-axis
            
            # Set title to show current label
            label_names = [
                "Background", "Skull", "Cervical Vertebrae", 
                "Thoracic Vertebrae", "Rib", "Sternum", "Collarbone",
                "Scapula", "Humerus", "Lumbar Vertebrae", "Sacrum",
                "Pelvis", "Femur"
            ]
            current_label_name = label_names[self.current_label] if self.current_label < len(label_names) else f"Label {self.current_label}"
            self.ax.set_title(f"Editing: {current_label_name} (Mode: {self.current_mode.title()})")
            
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error updating display: {e}")
            traceback.print_exc()

    def _rgb_to_label_mask(self, rgb_mask):
        """Convert RGB colored mask back to label mask"""
        if rgb_mask.ndim != 3 or rgb_mask.shape[2] != 3:
            return rgb_mask
            
        label_mask = np.zeros(rgb_mask.shape[:2], dtype=np.uint8)
        
        # Convert palette colors to match
        for i, color in enumerate(self.palette):
            if i == 0:  # Skip background
                continue
            color_normalized = np.array(color, dtype=np.uint8)
            
            # Find pixels that match this color (with some tolerance)
            mask = np.all(np.abs(rgb_mask.astype(int) - color_normalized.astype(int)) < 10, axis=2)
            label_mask[mask] = i
            
        return label_mask

    def _on_label_changed(self, index):
        self.current_label = index
        self._update_display()

    def _on_brush_size_changed(self, size):
        self.brush_size = size

    def _set_mode(self, mode):
        self.current_mode = mode
        if mode == "draw":
            self.btn_draw.setChecked(True)
            self.btn_erase.setChecked(False)
        else:
            self.btn_draw.setChecked(False)
            self.btn_erase.setChecked(True)
        self._update_display()

    def _on_click(self, event):
        if event.inaxes != self.ax:
            return
            
        x, y = int(event.xdata), int(event.ydata)
        if event.button == 1:  # Left click
            self._apply_brush(x, y)

    def _on_drag(self, event):
        if event.button != 1 or event.inaxes != self.ax:
            return
            
        x, y = int(event.xdata), int(event.ydata)
        self._apply_brush(x, y)

    def _apply_brush(self, x, y):
        """Apply brush operation at given coordinates"""
        try:
            # Get current mask (ensure it's 2D)
            if self.mask.ndim == 3:
                if self.mask.shape[2] == 1:
                    current_mask = self.mask[:,:,0]
                else:
                    current_mask = self._rgb_to_label_mask(self.mask)
            else:
                current_mask = self.mask.copy()
                
            # Apply brush
            if self.current_mode == "draw":
                cv2.circle(current_mask, (x, y), self.brush_size, self.current_label, -1)
            else:  # erase
                cv2.circle(current_mask, (x, y), self.brush_size, 0, -1)
            
            # Update mask
            if self.mask.ndim == 3:
                if self.mask.shape[2] == 1:
                    self.mask[:,:,0] = current_mask
                else:
                    # Convert back to RGB if needed
                    self.mask = self._label_to_rgb_mask(current_mask)
            else:
                self.mask = current_mask
                
            self._update_display()
            
        except Exception as e:
            print(f"Error applying brush: {e}")
            traceback.print_exc()

    def _label_to_rgb_mask(self, label_mask):
        """Convert label mask to RGB colored mask"""
        h, w = label_mask.shape
        rgb_mask = np.zeros((h, w, 3), dtype=np.uint8)
        
        for i, color in enumerate(self.palette):
            if i < len(self.palette):
                mask = (label_mask == i)
                rgb_mask[mask] = color
                
        return rgb_mask

    def _on_scroll(self, event):
        if event.button == 'up':
            self._zoom_in()
        elif event.button == 'down':
            self._zoom_out()

    def _zoom_in(self):
        self.zoom_factor *= 1.2
        if self.zoom_factor > 10:  # Max zoom limit
            self.zoom_factor = 10
        self._update_display()

    def _zoom_out(self):
        self.zoom_factor /= 1.2
        if self.zoom_factor < 1:  # Min zoom limit (original size)
            self.zoom_factor = 1
        self._update_display()

    def _undo(self):
        self.mask = self.backup_mask.copy()
        self._update_display()

    def _emit_save(self):
        # Ensure mask is in correct format for saving
        if self.mask.ndim == 3:
            if self.mask.shape[2] == 3:
                # Convert RGB to label mask for saving
                save_mask = self._rgb_to_label_mask(self.mask)
            else:
                save_mask = self.mask[:,:,0]
        else:
            save_mask = self.mask
            
        self.saved.emit(save_mask)
        self.close()

    def get_edited_mask(self):
        if self.mask.ndim == 3:
            if self.mask.shape[2] == 3:
                return self._rgb_to_label_mask(self.mask)
            else:
                return self.mask[:,:,0]
        else:
            return self.mask