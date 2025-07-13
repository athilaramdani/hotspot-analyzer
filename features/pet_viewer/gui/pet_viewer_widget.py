# frontend/widgets/pet_viewer_widget.py
"""
Widget untuk menampilkan PET data dalam 4 panel view (R, G, Y, P)
"""
from typing import Optional, Dict, Any
import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QGridLayout, QFrame, QSizePolicy, QPushButton
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor

from features.pet_viewer.logic.pet_loader import PETData, get_slice_data, normalize_image_for_display


class PETSliceViewer(QWidget):
    """Widget untuk menampilkan single slice dengan slider control"""
    
    def __init__(self, title: str, color: str, axis: int, slider_label: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.color = color
        self.axis = axis  # 0=sagittal, 1=coronal, 2=axial
        self.slider_label = slider_label
        
        self.image_data: Optional[np.ndarray] = None
        self.current_slice: int = 0
        self.max_slices: int = 0
        
        self._create_ui()
        self._setup_styling()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Title bar dengan warna
        title_frame = QFrame()
        title_frame.setFixedHeight(30)
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(10, 5, 10, 5)
        
        title_label = QLabel(self.title)
        title_label.setStyleSheet(f"font-weight: bold; color: {self.color};")
        title_layout.addWidget(title_label)
        
        # Slice info
        self.slice_info_label = QLabel("0/0")
        self.slice_info_label.setStyleSheet(f"color: {self.color};")
        title_layout.addWidget(self.slice_info_label)
        
        layout.addWidget(title_frame)
        
        # Slider control - DIPINDAH KE ATAS GAMBAR
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel(f"{self.slider_label}:"))
        
        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(0)
        self.slice_slider.setValue(0)
        self.slice_slider.valueChanged.connect(self._on_slice_changed)
        slider_layout.addWidget(self.slice_slider)
        
        layout.addLayout(slider_layout)
        
        # Image display area
        self.image_label = QLabel()
        self.image_label.setMinimumSize(200, 200)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(f"border: 2px solid {self.color}; background-color: black;")
        # IMPORTANT: Jangan gunakan setScaledContents untuk maintain aspect ratio
        self.image_label.setScaledContents(False)
        layout.addWidget(self.image_label)
        
        # Set stretch factors
        layout.setStretchFactor(title_frame, 0)
        layout.setStretchFactor(slider_layout, 0)
        layout.setStretchFactor(self.image_label, 1)
    
    def _setup_styling(self):
        """Setup styling untuk panel"""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(0, 0, 0, 0.1);
                border-radius: 5px;
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: #ddd;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {self.color};
                border: 1px solid #999;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::sub-page:horizontal {{
                background: {self.color};
                border-radius: 3px;
            }}
        """)
    
    def set_image_data(self, image_data: np.ndarray):
        """Set image data untuk ditampilkan"""
        print(f"[DEBUG] {self.title} - set_image_data called with data shape: {image_data.shape if image_data is not None else 'None'}")
        
        self.image_data = image_data
        
        if image_data is not None:
            # Update slider range
            self.max_slices = image_data.shape[self.axis]
            self.slice_slider.setMaximum(self.max_slices - 1)
            
            # Set to middle slice
            middle_slice = self.max_slices // 2
            self.slice_slider.setValue(middle_slice)
            self.current_slice = middle_slice
            
            print(f"[DEBUG] {self.title} - max_slices: {self.max_slices}, middle_slice: {middle_slice}")
            
            self._update_display()
        else:
            self.clear()
    
    def _on_slice_changed(self, value: int):
        """Handle slice slider change"""
        self.current_slice = value
        self._update_display()
    
    def _update_display(self):
        """Update tampilan slice PET"""
        if self.image_data is None:
            self.clear()
            return

        # Ambil slice berdasarkan axis dan posisi slider
        slice_data = get_slice_data(self.image_data, self.axis, self.current_slice)
        if slice_data is None:
            self.clear()
            return

        # Debug: Print slice info
        print(f"[DEBUG] Displaying {self.title} - axis: {self.axis}, slice: {self.current_slice}, shape: {slice_data.shape}")
        
        # Make a copy to avoid modifying original data
        slice_data = slice_data.copy()
        
        # PERBAIKAN ORIENTASI: Apply proper orientation for each view
        # Note: Orientasi ini mungkin perlu disesuaikan tergantung data source
        if self.axis == 0:  # Sagittal (Left-Right)
            slice_data = np.flipud(slice_data)
        elif self.axis == 1:  # Coronal (Anterior-Posterior)  
            slice_data = np.flipud(slice_data)
        elif self.axis == 2:  # Axial (Superior-Inferior)
            # For axial view, just transpose to get proper orientation
            slice_data = slice_data.T
            slice_data = np.flipud(slice_data)

        # Normalisasi dan pastikan buffer C-contiguous
        normalized = normalize_image_for_display(slice_data)
        if normalized is None:
            print(f"[ERROR] Failed to normalize image for {self.title}")
            self.clear()
            return
            
        normalized = np.ascontiguousarray(normalized)

        # Konversi ke QImage
        height, width = normalized.shape
        bytes_per_line = width
        
        # Debug print
        print(f"[DEBUG] Creating QImage: width={width}, height={height}, bytes_per_line={bytes_per_line}")
        
        q_image = QImage(
            normalized.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_Grayscale8
        )

        if q_image.isNull():
            print(f"[ERROR] QImage is null for {self.title}")
            self.clear()
            return

        # PERBAIKAN KUALITAS GAMBAR: Scale dengan maintain aspect ratio
        pixmap = QPixmap.fromImage(q_image)
        
        if pixmap.isNull():
            print(f"[ERROR] QPixmap is null for {self.title}")
            self.clear()
            return
        
        # Calculate proper scaling to fit the label while maintaining aspect ratio
        label_size = self.image_label.size()
        if label_size.width() > 0 and label_size.height() > 0:
            scaled_pixmap = pixmap.scaled(
                label_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation  # Gunakan smooth transformation untuk kualitas lebih baik
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            # If label size is not ready, just set the pixmap
            self.image_label.setPixmap(pixmap)

        # Update info slice
        self.slice_info_label.setText(f"{self.current_slice + 1}/{self.max_slices}")

    def clear(self):
        """Clear the display"""
        print(f"[DEBUG] {self.title}.clear() called")
        self.image_label.clear()
        self.image_label.setText("No data")
        self.slice_info_label.setText("0/0")
        self.slice_slider.setMaximum(0)
        self.slice_slider.setValue(0)
        self.image_data = None
    
    def resizeEvent(self, event):
        """Handle resize event"""
        super().resizeEvent(event)
        # Update display pada resize
        if self.image_data is not None:
            QTimer.singleShot(100, self._update_display)
    
    def showEvent(self, event):
        """Handle show event"""
        super().showEvent(event)
        # Force update display when widget is shown
        if self.image_data is not None:
            QTimer.singleShot(100, self._update_display)


class PETViewerWidget(QWidget):
    """Widget utama untuk menampilkan PET data dalam 4 panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        print("[DEBUG] PETViewerWidget.__init__ called")
        self.pet_data: Optional[PETData] = None
        self.current_image_type: str = "PET"  # PET, CT, SEG, SUV
        
        self._create_ui()
        self._setup_image_type_controls()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        
        # Control panel
        control_layout = QHBoxLayout()
        
        # Image type selector
        control_layout.addWidget(QLabel("Image Type:"))
        
        # Placeholder for image type selector (will be added later)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # Main viewer area - 2x2 grid dengan posisi yang BENAR
        viewer_layout = QGridLayout()
        viewer_layout.setSpacing(10)
        
        # PERBAIKAN POSISI PANEL:
        # Red panel (Axial) - KIRI ATAS (0, 0)
        self.red_panel = PETSliceViewer("Red (Axial)", "#FF0000", 2, "Superior-Inferior")
        viewer_layout.addWidget(self.red_panel, 0, 0)
        
        # Purple panel - KANAN ATAS (0, 1) 
        self.purple_panel = PETSliceViewer("Purple (3D/MIP)", "#800080", 2, "Slice")
        viewer_layout.addWidget(self.purple_panel, 0, 1)
        
        # Green panel (Coronal) - KIRI BAWAH (1, 0)
        self.green_panel = PETSliceViewer("Green (Coronal)", "#00FF00", 1, "Anterior-Posterior")
        viewer_layout.addWidget(self.green_panel, 1, 0)
        
        # Yellow panel (Sagittal) - KANAN BAWAH (1, 1)
        self.yellow_panel = PETSliceViewer("Yellow (Sagittal)", "#FFFF00", 0, "Left-Right")
        viewer_layout.addWidget(self.yellow_panel, 1, 1)
        
        # Set equal stretch factors
        for i in range(2):
            viewer_layout.setRowStretch(i, 1)
            viewer_layout.setColumnStretch(i, 1)
        
        layout.addLayout(viewer_layout)
        
        # Set stretch factors
        layout.setStretchFactor(control_layout, 0)
        layout.setStretchFactor(viewer_layout, 1)
        
        # Store panels for easy access
        self.panels = [self.red_panel, self.green_panel, self.yellow_panel, self.purple_panel]
        
        print("[DEBUG] PETViewerWidget._create_ui completed - created {} panels".format(len(self.panels)))
    
    def _setup_image_type_controls(self):
        """Setup controls untuk memilih tipe image"""
        # TODO: Implement image type selector
        pass
    
    def set_pet_data(self, pet_data: PETData):
        """Set PET data untuk ditampilkan"""
        print(f"[DEBUG] PETViewerWidget.set_pet_data called with patient_id: {pet_data.patient_id if pet_data else 'None'}")
        if pet_data:
            print(f"[DEBUG] Available images: PET={pet_data.pet_image is not None}, CT={pet_data.ct_image is not None}, SEG={pet_data.seg_image is not None}, SUV={pet_data.suv_image is not None}")
        self.pet_data = pet_data
        self._update_display()
        
        # Force a display update after a short delay to ensure everything is ready
        QTimer.singleShot(100, self._update_display)
    
    def _update_display(self):
        """Update display dengan data terbaru"""
        if not self.pet_data:
            self.clear()
            return

        # Ambil image 3-D sesuai tipe
        image_data = self._get_current_image_data()
        
        print(f"[DEBUG] PETViewerWidget._update_display - image_type: {self.current_image_type}, data shape: {image_data.shape if image_data is not None else 'None'}")

        if image_data is not None:
            # Kirim image yang sama ke semua panel slice-viewer
            for panel in self.panels:
                panel.set_image_data(image_data)
        else:
            print("[WARNING] No image data available to display")
            self.clear()
    
    def _get_current_image_data(self) -> Optional[np.ndarray]:
        """Get image data berdasarkan tipe yang dipilih"""
        if not self.pet_data:
            print("[DEBUG] _get_current_image_data: No pet_data available")
            return None

        print(f"[DEBUG] _get_current_image_data: Getting {self.current_image_type} data")
        
        if self.current_image_type == "PET":
            # Gunakan PET mentah; jika tidak ada, fallback ke PET korr
            pet_image = self.pet_data.pet_image
            pet_corr_image = self.pet_data.pet_corr_image
            
            print(f"[DEBUG] PET image shape: {pet_image.shape if pet_image is not None else 'None'}")
            print(f"[DEBUG] PET corr image shape: {pet_corr_image.shape if pet_corr_image is not None else 'None'}")
            
            return (
                pet_image
                if pet_image is not None
                else pet_corr_image
            )
        elif self.current_image_type == "CT":
            return self.pet_data.ct_image
        elif self.current_image_type == "SEG":
            return self.pet_data.seg_image
        elif self.current_image_type == "SUV":
            return self.pet_data.suv_image

        return None
    
    def set_image_type(self, image_type: str):
        """Set tipe image yang akan ditampilkan"""
        self.current_image_type = image_type
        self._update_display()
    
    def clear(self):
        """Clear semua panel"""
        for panel in self.panels:
            panel.clear()
    
    def cleanup(self):
        """Cleanup resources"""
        self.clear()
        self.pet_data = None
    
    def get_available_image_types(self) -> Dict[str, bool]:
        """Get available image types"""
        if not self.pet_data:
            return {}
        
        return {
            "PET": (self.pet_data.pet_image is not None or self.pet_data.pet_corr_image is not None),
            "CT": self.pet_data.ct_image is not None,
            "SEG": self.pet_data.seg_image is not None,
            "SUV": self.pet_data.suv_image is not None,
        }