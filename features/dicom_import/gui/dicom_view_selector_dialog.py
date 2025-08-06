# features/dicom_import/gui/dicom_view_selector_dialog.py
"""
Dialog untuk memilih dan memverifikasi view Anterior/Posterior dari DICOM files
sebelum melakukan processing.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import pydicom
from PIL import Image
from PySide6.QtCore import Signal, Qt, QThread, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QWidget, QFrame, QCheckBox, QGridLayout,
    QGroupBox, QSplitter, QMessageBox, QProgressBar, QSlider
)
from PySide6.QtGui import QPixmap, QFont, QImage, QWheelEvent, QMouseEvent

# Use centralized imports from core
from core.gui.ui_constants import (
    DIALOG_TITLE_STYLE, DIALOG_SUBTITLE_STYLE, DIALOG_FRAME_STYLE,
    PRIMARY_BUTTON_STYLE, GRAY_BUTTON_STYLE, SUCCESS_BUTTON_STYLE,
    DIALOG_CANCEL_BUTTON_STYLE, GROUP_BOX_STYLE, Colors,
    truncate_text
)
from core.gui.loading_dialog import LoadingDialog

# Use centralized DICOM processing
from features.dicom_import.logic.dicom_loader import load_frames_and_metadata, _extract_labels

@dataclass
class FrameInfo:
    """Information about a single DICOM frame"""
    frame_index: int
    frame_data: np.ndarray
    detected_view: Optional[str]  # "Anterior", "Posterior", or None
    user_selected_view: Optional[str]  # User's selection
    is_anterior_checked: bool = False
    is_posterior_checked: bool = False

@dataclass
class DicomInfo:
    """Information about a single DICOM file"""
    file_path: Path
    patient_id: str
    study_date: str
    frames: List[FrameInfo]
    has_auto_detection: bool


class ZoomableImageLabel(QLabel):
    """Custom QLabel with zoom capabilities"""
    
    def __init__(self, frame_data: np.ndarray):
        super().__init__()
        self.frame_data = frame_data
        self.zoom_factor = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 5.0
        self.original_pixmap = None
        self.dragging = False
        self.last_pan_point = None
        self.image_offset = (0, 0)
        
        # Set initial properties
        self.setMinimumSize(200, 200)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #dee2e6;
                border-radius: 8px;
                background: #f8f9fa;
            }
        """)
        
        # Enable mouse tracking for pan
        self.setMouseTracking(True)
        
        # Load and display image
        self._create_pixmap()
        self._update_display()
    
    def _create_pixmap(self):
        """Create QPixmap from frame data"""
        try:
            frame_data = self.frame_data
            
            # Normalize to 0-255
            if frame_data.dtype != np.uint8:
                frame_norm = (frame_data.astype(np.float32) - frame_data.min())
                if frame_norm.max() > frame_norm.min():
                    frame_norm /= (frame_norm.max() - frame_norm.min())
                frame_data = (frame_norm * 255).astype(np.uint8)
            
            height, width = frame_data.shape
            
            # Convert to PIL Image
            image = Image.fromarray(frame_data, mode='L')
            
            # Resize for better initial display (larger base size)
            base_size = 300  # Increased from 120
            if width > height:
                new_width = base_size
                new_height = int((height / width) * base_size)
            else:
                new_height = base_size
                new_width = int((width / height) * base_size)
            
            # Resize with proper resampling
            image_resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert PIL image to QPixmap
            image_rgb = image_resized.convert('RGB')
            width_final, height_final = image_rgb.size
            
            # Create QImage from PIL image bytes
            img_bytes = image_rgb.tobytes('raw', 'RGB')
            q_image = QImage(img_bytes, width_final, height_final, QImage.Format_RGB888)
            
            # Convert to QPixmap
            self.original_pixmap = QPixmap.fromImage(q_image)
            
        except Exception as e:
            print(f"Error creating pixmap: {e}")
            # Create error pixmap
            error_pixmap = QPixmap(200, 200)
            error_pixmap.fill(Qt.red)
            self.original_pixmap = error_pixmap
    
    def _update_display(self):
        """Update display with current zoom and pan"""
        if not self.original_pixmap:
            return
            
        # Calculate zoomed size
        zoomed_size = self.original_pixmap.size() * self.zoom_factor
        
        # Scale pixmap
        scaled_pixmap = self.original_pixmap.scaled(
            zoomed_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Apply offset for panning (simple version)
        self.setPixmap(scaled_pixmap)
        
        # Update tooltip with zoom info
        self.setToolTip(f"Zoom: {self.zoom_factor:.1f}x\nScroll to zoom, drag to pan")
    
    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming"""
        # Get wheel delta
        delta = event.angleDelta().y()
        
        # Calculate zoom change
        zoom_in = delta > 0
        zoom_change = 1.2 if zoom_in else 1/1.2
        
        # Apply zoom with limits
        new_zoom = self.zoom_factor * zoom_change
        new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
        
        if new_zoom != self.zoom_factor:
            self.zoom_factor = new_zoom
            self._update_display()
        
        event.accept()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Start dragging for pan"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for panning"""
        if self.dragging and self.last_pan_point:
            # Simple panning - could be enhanced
            self.setCursor(Qt.ClosedHandCursor)
        elif not self.dragging:
            self.setCursor(Qt.OpenHandCursor if self.zoom_factor > 1.0 else Qt.ArrowCursor)
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Stop dragging"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.setCursor(Qt.OpenHandCursor if self.zoom_factor > 1.0 else Qt.ArrowCursor)
        super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Reset zoom on double click"""
        self.zoom_factor = 1.0
        self.image_offset = (0, 0)
        self._update_display()
        super().mouseDoubleClickEvent(event)


class DicomPreviewThread(QThread):
    """Thread untuk load preview DICOM files"""
    preview_loaded = Signal(Path, object)  # file_path, DicomInfo
    loading_progress = Signal(int, int)  # current, total
    
    def __init__(self, file_paths: List[Path]):
        super().__init__()
        self.file_paths = file_paths
    
    def run(self):
        for i, file_path in enumerate(self.file_paths):
            try:
                dicom_info = self._load_dicom_info(file_path)
                self.preview_loaded.emit(file_path, dicom_info)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                # Emit None untuk menandakan error
                self.preview_loaded.emit(file_path, None)
            
            self.loading_progress.emit(i + 1, len(self.file_paths))
    
    def _load_dicom_info(self, file_path: Path) -> DicomInfo:
        """Load DICOM info dengan enhanced detection"""
        # Load frames and metadata
        frames_dict, metadata = load_frames_and_metadata(str(file_path))
        
        # Extract patient info
        patient_id = metadata.get("patient_id", "Unknown")
        study_date = metadata.get("study_date", "Unknown")
        
        # Process each frame
        frame_infos = []
        has_auto_detection = False
        
        print(f"🔍 DEBUG: Processing {len(frames_dict)} frames from {file_path.name}")
        
        for frame_index, (view_name, frame_data) in enumerate(frames_dict.items()):
            print(f"  Frame {frame_index}: '{view_name}'")
            
            # Enhanced view detection
            detected_view = self._enhanced_view_detection(view_name)
            print(f"    Detected: {detected_view}")
            
            if detected_view in ["Anterior", "Posterior"]:
                has_auto_detection = True
                print(f"    ✅ Auto-detected as {detected_view}")
            else:
                print(f"    ⚠️ No confident detection - user must select")
            
            frame_info = FrameInfo(
                frame_index=frame_index,
                frame_data=frame_data,
                detected_view=detected_view,
                user_selected_view=detected_view if detected_view in ["Anterior", "Posterior"] else None
            )
            
            # Only auto-check if view is properly detected
            if detected_view == "Anterior":
                frame_info.is_anterior_checked = True
                frame_info.user_selected_view = "Anterior"
                print(f"    ✅ Auto-checked Anterior")
            elif detected_view == "Posterior":
                frame_info.is_posterior_checked = True
                frame_info.user_selected_view = "Posterior"
                print(f"    ✅ Auto-checked Posterior")
            else:
                frame_info.is_anterior_checked = False
                frame_info.is_posterior_checked = False
                frame_info.user_selected_view = None
                print(f"    ❌ Left unchecked - manual selection required")
            
            frame_infos.append(frame_info)
        
        print(f"📊 Summary: {file_path.name} - Auto-detection: {has_auto_detection}")
        return DicomInfo(
            file_path=file_path,
            patient_id=patient_id,
            study_date=study_date,
            frames=frame_infos,
            has_auto_detection=has_auto_detection
        )
    
    def _enhanced_view_detection(self, view_name: str) -> Optional[str]:
        """Enhanced view detection dengan multiple methods - ONLY return if confident"""
        if not view_name:
            return None
        
        view_upper = view_name.upper()
        
        # Only return confident detections
        # Method 1: Direct detection - most reliable
        if "ANTERIOR" in view_upper:
            return "Anterior"
        elif "POSTERIOR" in view_upper:
            return "Posterior"
        elif view_upper.startswith("ANT") and len(view_upper) <= 8:  # "ANT", "ANTERIOR"
            return "Anterior"  
        elif view_upper.startswith("POST") and len(view_upper) <= 10:  # "POST", "POSTERIOR"
            return "Posterior"
        
        return None  # Return None for uncertain cases


class FrameWidget(QWidget):
    """Widget untuk menampilkan single frame dengan checkbox controls dan zoom"""
    selection_changed = Signal()
    
    def __init__(self, frame_info: FrameInfo, dicom_path: Path):
        super().__init__()
        self.frame_info = frame_info
        self.dicom_path = dicom_path
        
        try:
            self._setup_ui()
            self._connect_signals()
        except Exception as e:
            print(f"ERROR in FrameWidget.__init__: {e}")
            import traceback
            traceback.print_exc()
            self._setup_fallback_ui()
    
    def _setup_fallback_ui(self):
        """Fallback UI jika ada error"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        error_label = QLabel("Frame Error")
        error_label.setStyleSheet("""
            QLabel {
                color: #dc3545;
                font-weight: bold;
                padding: 4px;
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 4px;
                font-size: 10px;
            }
        """)
        layout.addWidget(error_label)
        
        # Still add checkboxes for functionality
        self.anterior_checkbox = QCheckBox("Anterior")
        self.posterior_checkbox = QCheckBox("Posterior")
        layout.addWidget(self.anterior_checkbox)
        layout.addWidget(self.posterior_checkbox)
        
        # Connect minimal signals
        self.anterior_checkbox.toggled.connect(self._on_anterior_toggled)
        self.posterior_checkbox.toggled.connect(self._on_posterior_toggled)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)  # Increased margins
        layout.setSpacing(12)  # Increased spacing
        
        # ✅ FIXED: Use ZoomableImageLabel instead of regular QLabel
        self.preview_label = ZoomableImageLabel(self.frame_info.frame_data)
        self.preview_label.setMinimumSize(250, 250)  # Larger minimum size
        layout.addWidget(self.preview_label)
        
        # Enhanced frame info with better formatting
        frame_data = self.frame_info.frame_data
        dimensions = f"{frame_data.shape[0]}×{frame_data.shape[1]}"
        
        info_text = f"Frame {self.frame_info.frame_index + 1}\nSize: {dimensions}"
        if self.frame_info.detected_view:
            info_text += f"\nDetected: {self.frame_info.detected_view}"
        else:
            info_text += "\nDetected: None"
        
        info_label = QLabel(info_text)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.DARK_GRAY};
                font-size: 11px;
                font-weight: bold;
                background: rgba(248, 249, 250, 0.9);
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 6px;
                padding: 8px;
                line-height: 1.3;
            }}
        """)
        layout.addWidget(info_label)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(6)
        
        zoom_out_btn = QPushButton("🔍-")
        zoom_out_btn.setFixedSize(30, 25)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(lambda: self._zoom_control(-1))
        
        zoom_reset_btn = QPushButton("1:1")
        zoom_reset_btn.setFixedSize(35, 25)
        zoom_reset_btn.setToolTip("Reset Zoom")
        zoom_reset_btn.clicked.connect(lambda: self._zoom_control(0))
        
        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setFixedSize(30, 25)
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(lambda: self._zoom_control(1))
        
        button_style = f"""
            QPushButton {{
                background: {Colors.LIGHT_GRAY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {Colors.BORDER_MEDIUM};
            }}
            QPushButton:pressed {{
                background: {Colors.DARK_GRAY};
                color: white;
            }}
        """
        
        zoom_out_btn.setStyleSheet(button_style)
        zoom_reset_btn.setStyleSheet(button_style)
        zoom_in_btn.setStyleSheet(button_style)
        
        zoom_layout.addStretch()
        zoom_layout.addWidget(zoom_out_btn)
        zoom_layout.addWidget(zoom_reset_btn)
        zoom_layout.addWidget(zoom_in_btn)
        zoom_layout.addStretch()
        
        layout.addLayout(zoom_layout)
        
        # Checkboxes with better styling
        checkbox_frame = QFrame()
        checkbox_frame.setStyleSheet(f"""
            QFrame {{
                background: {Colors.LIGHT_GRAY};
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        checkbox_layout = QVBoxLayout(checkbox_frame)
        checkbox_layout.setSpacing(8)
        
        self.anterior_checkbox = QCheckBox("Anterior")
        self.posterior_checkbox = QCheckBox("Posterior")
        
        checkbox_style = f"""
            QCheckBox {{
                font-size: 12px;
                font-weight: bold;
                color: {Colors.DARK_GRAY};
                padding: 4px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
            }}
            QCheckBox::indicator:unchecked {{
                border: 2px solid {Colors.BORDER_MEDIUM};
                border-radius: 4px;
                background: white;
            }}
            QCheckBox::indicator:checked {{
                border: 2px solid {Colors.PRIMARY};
                border-radius: 4px;
                background: {Colors.PRIMARY};
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iMTAiIHZpZXdCb3g9IjAgMCAxMCAxMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTggMkw0IDZMMiA0IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }}
            QCheckBox::indicator:checked:hover {{
                background: {Colors.PRIMARY};
            }}
        """
        
        self.anterior_checkbox.setStyleSheet(checkbox_style)
        self.posterior_checkbox.setStyleSheet(checkbox_style)
        
        # Set initial state properly
        self.anterior_checkbox.setChecked(self.frame_info.is_anterior_checked)
        self.posterior_checkbox.setChecked(self.frame_info.is_posterior_checked)
        
        checkbox_layout.addWidget(self.anterior_checkbox)
        checkbox_layout.addWidget(self.posterior_checkbox)
        layout.addWidget(checkbox_frame)
    
    def _zoom_control(self, direction: int):
        """Control zoom via buttons"""
        if hasattr(self.preview_label, 'zoom_factor'):
            current_zoom = self.preview_label.zoom_factor
            
            if direction == 1:  # Zoom in
                new_zoom = min(current_zoom * 1.2, self.preview_label.max_zoom)
            elif direction == -1:  # Zoom out
                new_zoom = max(current_zoom / 1.2, self.preview_label.min_zoom)
            else:  # Reset
                new_zoom = 1.0
            
            if new_zoom != current_zoom:
                self.preview_label.zoom_factor = new_zoom
                self.preview_label._update_display()
    
    def _connect_signals(self):
        self.anterior_checkbox.toggled.connect(self._on_anterior_toggled)
        self.posterior_checkbox.toggled.connect(self._on_posterior_toggled)
    
    def _on_anterior_toggled(self, checked: bool):
        if checked:
            # Uncheck posterior (mutual exclusive)
            self.posterior_checkbox.setChecked(False)
            self.frame_info.is_anterior_checked = True
            self.frame_info.is_posterior_checked = False
            self.frame_info.user_selected_view = "Anterior"
        else:
            self.frame_info.is_anterior_checked = False
            if not self.posterior_checkbox.isChecked():
                self.frame_info.user_selected_view = None
        
        self.selection_changed.emit()
    
    def _on_posterior_toggled(self, checked: bool):
        if checked:
            # Uncheck anterior (mutual exclusive)
            self.anterior_checkbox.setChecked(False)
            self.frame_info.is_posterior_checked = True
            self.frame_info.is_anterior_checked = False
            self.frame_info.user_selected_view = "Posterior"
        else:
            self.frame_info.is_posterior_checked = False
            if not self.anterior_checkbox.isChecked():
                self.frame_info.user_selected_view = None
        
        self.selection_changed.emit()
    
    def get_selection(self) -> Optional[str]:
        """Get current selection"""
        return self.frame_info.user_selected_view


class DicomFileWidget(QWidget):
    """Widget untuk menampilkan single DICOM file dengan all frames"""
    selection_changed = Signal()
    
    def __init__(self, dicom_info: DicomInfo):
        super().__init__()
        self.dicom_info = dicom_info
        self.frame_widgets: List[FrameWidget] = []
        
        try:
            self._setup_ui()
        except Exception as e:
            print(f"ERROR in DicomFileWidget.__init__: {e}")
            import traceback
            traceback.print_exc()
            self._setup_fallback_ui()
    
    def _setup_fallback_ui(self):
        """Fallback UI jika ada error"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        error_label = QLabel(f"Error loading: {self.dicom_info.file_path.name}")
        error_label.setStyleSheet(f"""
            QLabel {{
                color: #dc3545;
                font-weight: bold;
                padding: 8px;
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 4px;
            }}
        """)
        layout.addWidget(error_label)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)  # Increased spacing
        
        # File header with enhanced styling
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: linear-gradient(135deg, {Colors.LIGHT_GRAY} 0%, rgba(248, 249, 250, 0.8) 100%);
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        header_layout = QVBoxLayout(header_frame)
        
        # File name with better formatting
        file_name = truncate_text(self.dicom_info.file_path.name, 60)
        file_label = QLabel(f"📄 {file_name}")
        file_label.setStyleSheet(f"""
            QLabel {{
                font-size: 15px;
                font-weight: bold;
                color: {Colors.DARK_GRAY};
                padding: 10px;
            }}
        """)
        header_layout.addWidget(file_label)
        
        # Patient info with status
        info_text = f"Patient: {self.dicom_info.patient_id} | Study Date: {self.dicom_info.study_date}"
        if self.dicom_info.has_auto_detection:
            info_text += " | ✅ Auto-detected views available"
        else:
            info_text += " | ⚠️ Manual selection required"
        
        info_label = QLabel(info_text)
        info_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {Colors.SECONDARY};
                padding: 0px 10px 10px 10px;
                font-style: italic;
            }}
        """)
        header_layout.addWidget(info_label)
        
        layout.addWidget(header_frame)
        
        # Check if we have valid frames
        if not self.dicom_info.frames:
            error_label = QLabel("❌ No frames found in DICOM file")
            error_label.setStyleSheet(f"""
                QLabel {{
                    color: #dc3545;
                    background: #f8d7da;
                    border: 1px solid #f5c6cb;
                    padding: 15px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 13px;
                }}
            """)
            layout.addWidget(error_label)
            return
        
        # ✅ FIXED: Better frames layout with proper spacing
        frames_container = QFrame()
        frames_container.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        frames_layout = QGridLayout(frames_container)
        frames_layout.setSpacing(20)  # Increased spacing between frames
        frames_layout.setContentsMargins(15, 15, 15, 15)
        
        # ✅ FIXED: Better responsive grid calculation
        frame_count = len(self.dicom_info.frames)
        if frame_count <= 2:
            cols = frame_count  # 1 or 2 columns for small counts
        elif frame_count <= 6:
            cols = min(3, frame_count)  # Up to 3 columns for medium counts
        else:
            cols = 4  # 4 columns for large counts
        
        # Add frame widgets with proper spacing
        for i, frame_info in enumerate(self.dicom_info.frames):
            try:
                frame_widget = FrameWidget(frame_info, self.dicom_info.file_path)
                frame_widget.selection_changed.connect(self.selection_changed.emit)
                
                row = i // cols
                col = i % cols
                frames_layout.addWidget(frame_widget, row, col)
                self.frame_widgets.append(frame_widget)
                
            except Exception as e:
                print(f"ERROR creating FrameWidget {i}: {e}")
                continue
        
        # Set column stretch to ensure proper spacing
        for col in range(cols):
            frames_layout.setColumnStretch(col, 1)
        
        layout.addWidget(frames_container)
    
    def get_view_assignments(self) -> Dict[int, str]:
        """Get view assignments for all frames"""
        assignments = {}
        for frame_widget in self.frame_widgets:
            frame_index = frame_widget.frame_info.frame_index
            selection = frame_widget.get_selection()
            if selection:
                assignments[frame_index] = selection
        return assignments
    
    def has_complete_selection(self) -> Tuple[bool, List[str]]:
        """Check if all frames have view assignments"""
        missing_frames = []
        for frame_widget in self.frame_widgets:
            if not frame_widget.get_selection():
                frame_num = frame_widget.frame_info.frame_index + 1
                missing_frames.append(f"Frame {frame_num}")
        
        return len(missing_frames) == 0, missing_frames


class DicomViewSelectorDialog(QDialog):
    """Main dialog untuk memilih view assignments"""
    views_confirmed = Signal(dict)  # {file_path: {frame_index: view_name}}
    
    def __init__(self, file_paths: List[Path], parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.dicom_infos: Dict[Path, DicomInfo] = {}
        self.dicom_widgets: List[DicomFileWidget] = []
        
        self.setWindowTitle("Select Anterior/Posterior Views - Enhanced")
        self.setModal(True)
        self.resize(1400, 900)  # Larger default size
        
        # Loading dialog
        self.loading_dialog: Optional[LoadingDialog] = None
        
        self._setup_ui()
        self._start_loading()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)  # Increased margins
        main_layout.setSpacing(12)
        
        # Title with enhanced styling
        title_label = QLabel("🔍 Select Anterior/Posterior Views - Enhanced")
        title_label.setStyleSheet(f"""
            {DIALOG_TITLE_STYLE}
            font-size: 18px;
            padding: 10px;
            background: linear-gradient(135deg, {Colors.PRIMARY} 0%, {Colors.SECONDARY} 100%);
            color: white;
            border-radius: 8px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Enhanced subtitle with zoom info
        subtitle_label = QLabel("Review and confirm view assignments • Scroll to zoom • Drag to pan • Double-click to reset")
        subtitle_label.setStyleSheet(f"""
            {DIALOG_SUBTITLE_STYLE}
            font-size: 13px;
            padding: 8px;
        """)
        subtitle_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle_label)
        
        # Enhanced instructions with zoom controls info
        instructions = QLabel(
            "🎯 Instructions:\n"
            "• Green checkmark (✅) = Views automatically detected\n"
            "• Warning (⚠️) = Manual selection required\n" 
            "• Each frame must be assigned to either Anterior or Posterior view\n"
            "• Use mouse wheel or zoom buttons to zoom in/out on images\n"
            "• Drag to pan zoomed images • Double-click to reset zoom"
        )
        instructions.setStyleSheet(f"""
            QLabel {{
                background: linear-gradient(135deg, {Colors.LIGHT_GRAY} 0%, rgba(240, 248, 255, 0.8) 100%);
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 8px;
                padding: 12px;
                font-size: 11px;
                color: {Colors.DARK_GRAY};
                line-height: 1.4;
            }}
        """)
        main_layout.addWidget(instructions)
        
        # Enhanced scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 2px solid {Colors.BORDER_LIGHT};
                border-radius: 8px;
                background: #fafbfc;
            }}
            QScrollArea QScrollBar:vertical {{
                background: {Colors.LIGHT_GRAY};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollArea QScrollBar::handle:vertical {{
                background: {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollArea QScrollBar::handle:vertical:hover {{
                background: {Colors.PRIMARY};
            }}
        """)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(15, 15, 15, 15)
        self.scroll_layout.setSpacing(20)  # Increased spacing between files
        
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)
        
        # Enhanced bottom controls
        button_frame = QFrame()
        button_frame.setStyleSheet(f"""
            QFrame {{
                background: {Colors.LIGHT_GRAY};
                border-top: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 0 0 8px 8px;
                padding: 8px;
            }}
        """)
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(15)
        
        # Validation status with enhanced styling
        self.status_label = QLabel("🔄 Loading DICOM files...")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.SECONDARY};
                font-size: 13px;
                font-weight: bold;
                padding: 8px 12px;
                background: white;
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 6px;
            }}
        """)
        button_layout.addWidget(self.status_label)
        
        button_layout.addStretch()
        
        # Cancel button with enhanced styling
        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.setStyleSheet(f"""
            {DIALOG_CANCEL_BUTTON_STYLE}
            font-size: 13px;
            padding: 10px 20px;
        """)
        button_layout.addWidget(self.cancel_btn)
        
        # OK button with enhanced styling
        self.ok_btn = QPushButton("✅ Confirm & Process")
        self.ok_btn.setEnabled(False)
        self.ok_btn.setStyleSheet(f"""
            {SUCCESS_BUTTON_STYLE}
            font-size: 13px;
            font-weight: bold;
            padding: 10px 25px;
        """)
        button_layout.addWidget(self.ok_btn)
        
        main_layout.addWidget(button_frame)
        
        # Connect signals
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn.clicked.connect(self._confirm_selections)
    
    def _start_loading(self):
        """Start loading DICOM previews"""
        self.loading_dialog = LoadingDialog(
            title="Loading DICOM Files",
            message="Analyzing DICOM files and detecting views...",
            show_progress=True,
            show_cancel=False,
            parent=self
        )
        self.loading_dialog.show()
        
        # Start preview thread
        self.preview_thread = DicomPreviewThread(self.file_paths)
        self.preview_thread.preview_loaded.connect(self._on_preview_loaded)
        self.preview_thread.loading_progress.connect(self._on_loading_progress)
        self.preview_thread.finished.connect(self._on_loading_finished)
        self.preview_thread.start()
    
    def _on_preview_loaded(self, file_path: Path, dicom_info: Optional[DicomInfo]):
        """Handle loaded DICOM info"""
        if dicom_info:
            self.dicom_infos[file_path] = dicom_info
            print(f"✅ Loaded DICOM info for: {file_path.name}")
        else:
            print(f"❌ Failed to load: {file_path}")
    
    def _on_loading_progress(self, current: int, total: int):
        """Update loading progress"""
        if self.loading_dialog:
            progress = int((current / total) * 100)
            self.loading_dialog.set_progress(progress)
            self.loading_dialog.set_message(f"Loading DICOM files... ({current}/{total})")
    
    def _on_loading_finished(self):
        """Finish loading and setup UI"""
        print(f"🔍 DEBUG: Loading finished. Loaded {len(self.dicom_infos)} DICOM info objects")
        
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
        
        try:
            self._setup_dicom_widgets()
            self._update_validation_status()
            print("✅ DICOM widgets setup completed successfully")
        except Exception as e:
            print(f"❌ ERROR in _on_loading_finished: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error dialog
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to setup view selector interface:\n{str(e)}\n\nCheck console for details."
            )
    
    def _setup_dicom_widgets(self):
        """Setup widgets for each loaded DICOM"""
        success_count = 0
        error_count = 0
        
        try:
            for file_path in self.file_paths:
                if file_path in self.dicom_infos:
                    try:
                        dicom_widget = DicomFileWidget(self.dicom_infos[file_path])
                        dicom_widget.selection_changed.connect(self._update_validation_status)
                        
                        self.scroll_layout.addWidget(dicom_widget)
                        self.dicom_widgets.append(dicom_widget)
                        success_count += 1
                        print(f"✅ Successfully created widget for {file_path.name}")
                        
                    except Exception as e:
                        print(f"ERROR creating widget for {file_path.name}: {e}")
                        import traceback
                        traceback.print_exc()
                        
                        # Create enhanced error placeholder
                        error_widget = QFrame()
                        error_widget.setStyleSheet(f"""
                            QFrame {{
                                background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
                                border: 2px solid #dc3545;
                                border-radius: 8px;
                                padding: 15px;
                            }}
                        """)
                        error_layout = QVBoxLayout(error_widget)
                        
                        error_title = QLabel(f"❌ Error Loading: {file_path.name}")
                        error_title.setStyleSheet("""
                            QLabel {
                                color: #721c24;
                                font-weight: bold;
                                font-size: 14px;
                                margin-bottom: 5px;
                            }
                        """)
                        error_layout.addWidget(error_title)
                        
                        error_detail = QLabel(f"Technical details: {str(e)[:100]}...")
                        error_detail.setStyleSheet("""
                            QLabel {
                                color: #721c24;
                                font-size: 11px;
                                font-style: italic;
                            }
                        """)
                        error_layout.addWidget(error_detail)
                        
                        self.scroll_layout.addWidget(error_widget)
                        error_count += 1
                else:
                    print(f"WARNING: No DICOM info found for {file_path.name}")
                    error_count += 1
            
            # Add stretch to push content to top
            self.scroll_layout.addStretch()
            
            # Update status with load summary
            if error_count > 0:
                self.status_label.setText(f"⚠️ Loaded {success_count}/{len(self.file_paths)} files ({error_count} errors)")
                self.status_label.setStyleSheet(f"""
                    QLabel {{
                        color: {Colors.WARNING};
                        font-size: 13px;
                        font-weight: bold;
                        padding: 8px 12px;
                        background: #fff3cd;
                        border: 1px solid #ffeeba;
                        border-radius: 6px;
                    }}
                """)
            else:
                self.status_label.setText(f"✅ Successfully loaded all {success_count} files")
            
        except Exception as e:
            print(f"CRITICAL ERROR in _setup_dicom_widgets: {e}")
            import traceback
            traceback.print_exc()
            
            # Show critical error message
            error_label = QLabel("💥 Critical Error Setting Up Interface")
            error_label.setStyleSheet(f"""
                QLabel {{
                    color: white;
                    background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                    border: 3px solid #dc3545;
                    border-radius: 10px;
                    padding: 25px;
                    font-weight: bold;
                    font-size: 16px;
                    text-align: center;
                }}
            """)
            self.scroll_layout.addWidget(error_label)
            
            detail_label = QLabel("Check console for technical details. This may be due to corrupted DICOM files or missing dependencies.")
            detail_label.setStyleSheet("""
                QLabel {
                    color: #721c24;
                    background: #f8d7da;
                    border: 1px solid #f5c6cb;
                    border-radius: 6px;
                    padding: 15px;
                    font-size: 12px;
                    margin-top: 10px;
                }
            """)
            self.scroll_layout.addWidget(detail_label)
    
    def _update_validation_status(self):
        """Update validation status and OK button state"""
        if not self.dicom_widgets:
            return
        
        total_files = len(self.dicom_widgets)
        complete_files = 0
        total_missing = 0
        files_with_both_views = 0
        
        for dicom_widget in self.dicom_widgets:
            is_complete, missing_frames = dicom_widget.has_complete_selection()
            if is_complete:
                complete_files += 1
                
                # Check if this file has both Anterior and Posterior views
                assignments = dicom_widget.get_view_assignments()
                views = set(assignments.values())
                if "Anterior" in views and "Posterior" in views:
                    files_with_both_views += 1
            else:
                total_missing += len(missing_frames)
        
        # Enhanced validation logic
        all_complete = (complete_files == total_files)
        all_have_both_views = (files_with_both_views == total_files)
        ready_to_process = all_complete and all_have_both_views
        
        if ready_to_process:
            self.status_label.setText("🎉 All views assigned and validated - ready to process!")
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.SUCCESS};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px 12px;
                    background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
                    border: 1px solid #28a745;
                    border-radius: 6px;
                }}
            """)
            self.ok_btn.setEnabled(True)
            self.ok_btn.setStyleSheet(f"""
                {SUCCESS_BUTTON_STYLE}
                font-size: 13px;
                font-weight: bold;
                padding: 10px 25px;
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            """)
        elif all_complete and not all_have_both_views:
            missing_both_views = total_files - files_with_both_views
            self.status_label.setText(f"⚠️ {missing_both_views} files missing both Anterior & Posterior views")
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.WARNING};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px 12px;
                    background: #fff3cd;
                    border: 1px solid #ffeeba;
                    border-radius: 6px;
                }}
            """)
            self.ok_btn.setEnabled(False)
        else:
            missing_files = total_files - complete_files
            self.status_label.setText(f"📋 {missing_files} files incomplete, {total_missing} frames need assignment")
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.SECONDARY};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px 12px;
                    background: white;
                    border: 1px solid {Colors.BORDER_LIGHT};
                    border-radius: 6px;
                }}
            """)
            self.ok_btn.setEnabled(False)
    
    def _confirm_selections(self):
        """Confirm selections and emit signal"""
        print("🔍 DEBUG: Confirming selections...")
        
        # Collect all view assignments
        view_assignments = {}
        
        for dicom_widget in self.dicom_widgets:
            file_path = dicom_widget.dicom_info.file_path
            assignments = dicom_widget.get_view_assignments()
            view_assignments[file_path] = assignments
            
            print(f"📄 {file_path.name}: {assignments}")
        
        # Final validation
        if not self._validate_assignments(view_assignments):
            print("❌ Validation failed!")
            return
        
        print("✅ Validation passed - emitting signal")
        print(f"🔍 DEBUG: About to emit views_confirmed signal with {len(view_assignments)} files")
        
        # Emit signal dengan path sebagai string (lebih aman)
        payload = {str(fp): assign for fp, assign in view_assignments.items()}

        print("🔍 DEBUG: Emitting views_confirmed signal (string paths)...")
        self.views_confirmed.emit(payload)
        print("🔍 DEBUG: Signal emitted, closing dialog...")
        
        self.accept()
        print("🔍 DEBUG: Dialog accepted and closed")
    
    def _validate_assignments(self, assignments: dict) -> bool:
        """Final validation of assignments with enhanced checking"""
        for file_path, frame_assignments in assignments.items():
            if not frame_assignments:
                QMessageBox.warning(
                    self, 
                    "Incomplete Selection",
                    f"No frames selected for:\n{file_path.name}\n\nPlease assign views to all frames."
                )
                return False
            
            # Check for both anterior and posterior
            views = set(frame_assignments.values())
            missing_views = []
            
            if "Anterior" not in views:
                missing_views.append("Anterior")
            if "Posterior" not in views:
                missing_views.append("Posterior")
            
            if missing_views:
                missing_text = " and ".join(missing_views)
                QMessageBox.warning(
                    self,
                    "Missing Required Views", 
                    f"Missing {missing_text} view(s) for:\n{file_path.name}\n\n"
                    f"Each DICOM file must have at least one frame assigned to both "
                    f"Anterior and Posterior views for proper processing."
                )
                return False
        
        return True