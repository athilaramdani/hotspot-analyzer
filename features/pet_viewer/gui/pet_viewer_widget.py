# features/pet_viewer/gui/pet_viewer_widget.py
"""
Widget untuk menampilkan PET data dalam 4 panel view (R, G, Y, Plot)
"""
from typing import Optional, Dict, Any
import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QGridLayout, QFrame, QSizePolicy, QPushButton, QTextEdit
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont

from features.pet_viewer.logic.pet_loader import PETData, get_slice_data, normalize_image_for_display


class PETSliceViewer(QWidget):
    """Widget untuk menampilkan single slice dengan slider control"""
    
    # Signal untuk fullscreen toggle
    fullscreen_toggled = Signal(object)  # Mengirim referensi ke widget ini
    
    def __init__(self, title: str, color: str, axis: int, slider_label: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.color = color
        self.axis = axis  # 0=sagittal, 1=coronal, 2=axial
        self.slider_label = slider_label
        self.is_fullscreen = False
        
        self.image_data: Optional[np.ndarray] = None
        self.current_slice: int = 0
        self.max_slices: int = 0
        
        self._create_ui()
        self._setup_styling()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Title bar dengan warna dan tombol fullscreen
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
        
        # Spacer
        title_layout.addStretch()
        
        # Fullscreen button
        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setFixedSize(20, 20)
        self.fullscreen_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color};
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.2);
            }}
        """)
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        title_layout.addWidget(self.fullscreen_btn)
        
        layout.addWidget(title_frame)
        
        # Slider control
        self.slider_layout = QHBoxLayout()
        self.slider_layout.addWidget(QLabel(f"{self.slider_label}:"))
        
        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(0)
        self.slice_slider.setValue(0)
        self.slice_slider.valueChanged.connect(self._on_slice_changed)
        self.slider_layout.addWidget(self.slice_slider)
        
        layout.addLayout(self.slider_layout)
        
        # Image display area
        self.image_label = QLabel()
        self.image_label.setMinimumSize(200, 200)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(f"border: 2px solid {self.color}; background-color: black;")
        self.image_label.setScaledContents(False)
        layout.addWidget(self.image_label)
        
        # Set stretch factors
        layout.setStretchFactor(title_frame, 0)
        layout.setStretchFactor(self.slider_layout, 0)
        layout.setStretchFactor(self.image_label, 1)
    
    def _toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.is_fullscreen = not self.is_fullscreen
        
        # Update button text
        if self.is_fullscreen:
            self.fullscreen_btn.setText("⛶")  # Minimize icon
        else:
            self.fullscreen_btn.setText("⛶")  # Maximize icon
            
        # Emit signal ke parent widget
        self.fullscreen_toggled.emit(self)
    
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
        """Update tampilan slice PET dengan orientasi yang benar sesuai 3D Slicer"""
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
        
        # ORIENTASI STANDAR MEDIS (RADIOLOGICAL CONVENTION):
        # Following 3D Slicer's standard orientations
        if self.axis == 0:  # Sagittal (Left-Right view) - YELLOW
            # Standard: Anterior on left, Superior on top
            # Rotate 90 degrees LEFT (counterclockwise) and flip as requested
            slice_data = np.rot90(slice_data, k=1)  # 90 degrees counterclockwise (left)
            slice_data = np.fliplr(slice_data)      # Flip vertically
            
        elif self.axis == 1:  # Coronal (Anterior-Posterior view) - GREEN
            # Standard: Left on right (radiological), Superior on top
            # Rotate 90 degrees RIGHT (clockwise) as requested
            slice_data = np.rot90(slice_data, k=1)  # 90 degrees clockwise (right)
            
        elif self.axis == 2:  # Axial (Superior-Inferior view) - RED
            # Standard: Anterior on top, Left on right (radiological)
            # Rotate 90 degrees counterclockwise and flip horizontally
            slice_data = np.rot90(slice_data, k=1)
            slice_data = np.fliplr(slice_data)

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

        # Scale dengan maintain aspect ratio untuk kualitas terbaik
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
                Qt.SmoothTransformation
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


class PlotViewer(QWidget):
    """Widget untuk menampilkan plot/statistics panel seperti di 3D Slicer"""
    
    # Signal untuk fullscreen toggle
    fullscreen_toggled = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_fullscreen = False
        self._create_ui()
        self._setup_styling()
    
    def _toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.is_fullscreen = not self.is_fullscreen
        
        # Update button text
        if self.is_fullscreen:
            self.fullscreen_btn.setText("⛶")
        else:
            self.fullscreen_btn.setText("⛶")
            
        # Emit signal ke parent widget
        self.fullscreen_toggled.emit(self)
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Title bar dengan tombol fullscreen
        title_frame = QFrame()
        title_frame.setFixedHeight(30)
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(10, 5, 10, 5)
        
        title_label = QLabel("Plot")
        title_label.setStyleSheet("font-weight: bold; color: #808080;")  # Gray color for Plot
        title_layout.addWidget(title_label)
        
        # Spacer
        title_layout.addStretch()
        
        # Fullscreen button
        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setFixedSize(20, 20)
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: #808080;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        title_layout.addWidget(self.fullscreen_btn)
        
        layout.addWidget(title_frame)
        
        # Plot area - for now, show statistics or placeholder
        self.plot_area = QTextEdit()
        self.plot_area.setReadOnly(True)
        self.plot_area.setStyleSheet("""
            QTextEdit {
                border: 2px solid #808080;
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: monospace;
                font-size: 10pt;
            }
        """)
        self.plot_area.setPlainText("Plot view\n\nNo data loaded")
        
        layout.addWidget(self.plot_area)
        
    def _setup_styling(self):
        """Setup styling untuk plot panel"""
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.1);
                border-radius: 5px;
            }
        """)
    
    def update_statistics(self, pet_data: Optional[PETData], image_type: str):
        """Update plot area with statistics from current data"""
        if not pet_data:
            self.plot_area.setPlainText("Plot view\n\nNo data loaded")
            return
            
        stats_text = f"Plot view - {image_type} Statistics\n"
        stats_text += "="*40 + "\n\n"
        
        # Get current image data
        image_data = None
        if image_type == "PET":
            image_data = pet_data.pet_image if pet_data.pet_image is not None else pet_data.pet_corr_image
        elif image_type == "CT":
            image_data = pet_data.ct_image
        elif image_type == "SEG":
            image_data = pet_data.seg_image
        elif image_type == "SUV":
            image_data = pet_data.suv_image
            
        if image_data is not None:
            stats_text += f"Image shape: {image_data.shape}\n"
            stats_text += f"Data type: {image_data.dtype}\n\n"
            
            # Calculate statistics
            non_zero_data = image_data[image_data > 0]
            if len(non_zero_data) > 0:
                stats_text += "Intensity Statistics (non-zero voxels):\n"
                stats_text += f"  Min: {non_zero_data.min():.2f}\n"
                stats_text += f"  Max: {non_zero_data.max():.2f}\n"
                stats_text += f"  Mean: {non_zero_data.mean():.2f}\n"
                stats_text += f"  Std Dev: {non_zero_data.std():.2f}\n"
                stats_text += f"  Median: {np.median(non_zero_data):.2f}\n"
                stats_text += f"\nTotal voxels: {image_data.size:,}\n"
                stats_text += f"Non-zero voxels: {len(non_zero_data):,} ({100*len(non_zero_data)/image_data.size:.1f}%)\n"
            else:
                stats_text += "No non-zero voxels found\n"
                
            # Add metadata if available
            if hasattr(pet_data, f'{image_type.lower()}_metadata') and getattr(pet_data, f'{image_type.lower()}_metadata'):
                metadata = getattr(pet_data, f'{image_type.lower()}_metadata')
                if 'voxel_size' in metadata:
                    stats_text += f"\nVoxel size: {metadata['voxel_size']}\n"
        else:
            stats_text += f"No {image_type} data available\n"
            
        self.plot_area.setPlainText(stats_text)
    
    def clear(self):
        """Clear the plot display"""
        self.plot_area.setPlainText("Plot view\n\nNo data loaded")


class PETViewerWidget(QWidget):
    """Widget utama untuk menampilkan PET data dalam 4 panel (R, G, Y, Plot)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        print("[DEBUG] PETViewerWidget.__init__ called")
        self.pet_data: Optional[PETData] = None
        self.current_image_type: str = "PET"  # PET, CT, SEG, SUV
        self.fullscreen_widget: Optional[QWidget] = None  # Widget yang sedang fullscreen
        
        self._create_ui()
    
    def _create_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)
        
        # Main viewer area - 2x2 grid
        self.viewer_layout = QGridLayout()
        self.viewer_layout.setSpacing(10)
        
        # Red panel (Axial) - TOP LEFT (0, 0)
        self.red_panel = PETSliceViewer("Red (Axial)", "#FF0000", 2, "Superior-Inferior")
        self.red_panel.fullscreen_toggled.connect(self._handle_fullscreen_toggle)
        self.viewer_layout.addWidget(self.red_panel, 0, 0)
        
        # Green panel (Coronal) - BOTTOM LEFT (1, 0)
        self.green_panel = PETSliceViewer("Green (Coronal)", "#00FF00", 1, "Anterior-Posterior")
        self.green_panel.fullscreen_toggled.connect(self._handle_fullscreen_toggle)
        self.viewer_layout.addWidget(self.green_panel, 1, 0)
        
        # Yellow panel (Sagittal) - BOTTOM RIGHT (1, 1)
        self.yellow_panel = PETSliceViewer("Yellow (Sagittal)", "#FFFF00", 0, "Left-Right")
        self.yellow_panel.fullscreen_toggled.connect(self._handle_fullscreen_toggle)
        self.viewer_layout.addWidget(self.yellow_panel, 1, 1)
        
        # Plot panel - TOP RIGHT (0, 1)
        self.plot_panel = PlotViewer()
        self.plot_panel.fullscreen_toggled.connect(self._handle_fullscreen_toggle)
        self.viewer_layout.addWidget(self.plot_panel, 0, 1)
        
        # Set equal stretch factors
        for i in range(2):
            self.viewer_layout.setRowStretch(i, 1)
            self.viewer_layout.setColumnStretch(i, 1)
        
        self.main_layout.addLayout(self.viewer_layout)
        
        # Store slice panels for easy access
        self.slice_panels = [self.red_panel, self.green_panel, self.yellow_panel]
        self.all_panels = [self.red_panel, self.green_panel, self.yellow_panel, self.plot_panel]
        
        print("[DEBUG] PETViewerWidget._create_ui completed")
    
    def _handle_fullscreen_toggle(self, widget):
        """Handle fullscreen toggle from any panel"""
        if self.fullscreen_widget is None:
            # Enter fullscreen mode
            self._enter_fullscreen(widget)
        else:
            # Exit fullscreen mode
            self._exit_fullscreen()
    
    def _enter_fullscreen(self, widget):
        """Enter fullscreen mode for specified widget"""
        self.fullscreen_widget = widget
        
        # Hide all other panels
        for panel in self.all_panels:
            if panel != widget:
                panel.hide()
        
        # Clear the grid layout
        self._clear_layout(self.viewer_layout)
        
        # Add only the fullscreen widget to fill the entire area
        self.viewer_layout.addWidget(widget, 0, 0, 2, 2)  # Span 2 rows and 2 columns
        
        # Update stretch factors to make it fill completely
        self.viewer_layout.setRowStretch(0, 1)
        self.viewer_layout.setRowStretch(1, 1)
        self.viewer_layout.setColumnStretch(0, 1)
        self.viewer_layout.setColumnStretch(1, 1)
        
        # Show the widget
        widget.show()
        
        print(f"[DEBUG] Entered fullscreen mode for {widget.title if hasattr(widget, 'title') else 'Plot'}")
    
    def _exit_fullscreen(self):
        """Exit fullscreen mode and restore 2x2 grid layout"""
        if self.fullscreen_widget is None:
            return
        
        # Clear the layout
        self._clear_layout(self.viewer_layout)
        
        # Restore original 2x2 grid layout
        self.viewer_layout.addWidget(self.red_panel, 0, 0)
        self.viewer_layout.addWidget(self.green_panel, 1, 0)
        self.viewer_layout.addWidget(self.yellow_panel, 1, 1)
        self.viewer_layout.addWidget(self.plot_panel, 0, 1)
        
        # Set equal stretch factors
        for i in range(2):
            self.viewer_layout.setRowStretch(i, 1)
            self.viewer_layout.setColumnStretch(i, 1)
        
        # Show all panels
        for panel in self.all_panels:
            panel.show()
        
        # Reset fullscreen widget
        self.fullscreen_widget = None
        
        print("[DEBUG] Exited fullscreen mode")
    
    def _clear_layout(self, layout):
        """Clear all items from layout without deleting widgets"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                # Don't delete the widget, just remove from layout
                child.widget().setParent(None)
    
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
            # Kirim image ke semua slice viewer panels
            for panel in self.slice_panels:
                panel.set_image_data(image_data)
            
            # Update plot panel with statistics
            self.plot_panel.update_statistics(self.pet_data, self.current_image_type)
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
        for panel in self.slice_panels:
            panel.clear()
        self.plot_panel.clear()
    
    def cleanup(self):
        """Cleanup resources"""
        # Exit fullscreen if active
        if self.fullscreen_widget:
            self._exit_fullscreen()
        
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