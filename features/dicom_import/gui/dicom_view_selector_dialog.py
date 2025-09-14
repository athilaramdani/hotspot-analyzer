# features/dicom_import/gui/dicom_view_selector_dialog.py - FIXED VERSION
"""
Dialog untuk memilih dan memverifikasi view Anterior/Posterior dari DICOM files
sebelum melakukan processing.

FIXES:
1. Proper image display orientation
2. Pan functionality with zoom
3. Auto-configuration status based on reliable detection
4. manual taggeduration for uncertain cases
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

import numpy as np
import pydicom
from PIL import Image
from PySide6.QtCore import Signal, Qt, QThread, QTimer, QPoint, QCoreApplication
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QWidget, QFrame, QCheckBox, QGridLayout,
    QGroupBox, QSplitter, QMessageBox, QProgressBar, QSlider,
    QRadioButton, QButtonGroup  # TAMBAHAN BARU
)
from PySide6.QtGui import QPixmap, QFont, QImage, QWheelEvent, QMouseEvent, QPainter

# Use centralized imports from core
from core.gui.ui_constants import (
    DIALOG_TITLE_STYLE, DIALOG_SUBTITLE_STYLE, DIALOG_FRAME_STYLE,
    PRIMARY_BUTTON_STYLE, GRAY_BUTTON_STYLE, SUCCESS_BUTTON_STYLE,
    DIALOG_CANCEL_BUTTON_STYLE, GROUP_BOX_STYLE, Colors,
    truncate_text
)
from core.gui.loading_dialog import LoadingDialog

# Use centralized DICOM processing
from features.dicom_import.logic.dicom_loader import load_frames_and_metadata, _extract_labels_enhanced

@dataclass
class FrameInfo:
    """Information about a single DICOM frame"""
    frame_index: int
    frame_data: np.ndarray
    detected_view: Optional[str]  # "Anterior", "Posterior", or None
    user_selected_view: Optional[str]  # User's selection
    is_anterior_checked: bool = False
    is_posterior_checked: bool = False
    detection_confidence: str = "none"  # "high", "low", "none"
    # TAMBAHAN BARU:
    selected_background: str = "black"  # "black" or "white"
    pixel_analysis: Optional[Dict[str, any]] = None  # Pixel analysis results

@dataclass
class DicomInfo:
    """Information about a single DICOM file"""
    file_path: Path
    patient_id: str
    study_date: str
    frames: List[FrameInfo]
    has_reliable_detection: bool  # True if confident auto-detection available
    needs_manual_config: bool     # True if manual taggeduration required


class ZoomableImageLabel(QLabel):
    """Custom QLabel with proper zoom and pan capabilities"""
    
    def __init__(self, frame_data: np.ndarray):
        super().__init__()
    
        #   FIXED: Validate frame_data first
        if frame_data is None:
            logging.info(" ERROR: ZoomableImageLabel received None frame_data")
            raise ValueError("Frame data cannot be None")
        
        if not isinstance(frame_data, np.ndarray):
            logging.info(f" ERROR: Frame data is not numpy array: {type(frame_data)}")
            raise ValueError("Frame data must be numpy array")
        
        if frame_data.size == 0:
            logging.info(" ERROR: Frame data is empty")
            raise ValueError("Frame data cannot be empty")
        
        logging.info(f"  DEBUG: ZoomableImageLabel init - shape: {frame_data.shape}, dtype: {frame_data.dtype}")
        
        #   FIXED: Detect if this is likely a medical image
        height, width = frame_data.shape[:2]
        
        # Heuristics for medical image detection
        is_medical = (
            frame_data.dtype in [np.uint16, np.int16] or  # Medical images often 16-bit
            (height >= 256 and width >= 256) or          # Reasonable medical scan size
            (height > width * 1.5) or                    # Tall narrow scans
            (width > height * 1.5)                       # Wide scans
        )
        
        self._is_medical_image = is_medical
        logging.info(f"  DEBUG: Medical image detected: {is_medical}")
        
        self.frame_data = frame_data
        self.zoom_factor = 1.0
        self.min_zoom = 0.3
        self.max_zoom = 8.0
        self.original_pixmap = None
        self.dragging = False
        self.last_pan_point = QPoint()
        self.pan_offset = QPoint(0, 0)
        
        # Set initial properties
        self.setMinimumSize(200, 200)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #dee2e6;
                border-radius: 8px;
                background: #f8f9fa;
            }
            QLabel:hover {
                border-color: #4e73ff;
            }
        """)
        
        # Enable mouse tracking for pan
        self.setMouseTracking(True)
        
        #   FIXED: Wrap image creation with error handling
        try:
            logging.info("  DEBUG: Creating pixmap...")
            self._create_pixmap()
            logging.info("  DEBUG: Updating display...")
            self._update_display()
            logging.info("  ZoomableImageLabel initialized successfully")
        except Exception as e:
            logging.info(f" ERROR in ZoomableImageLabel init: {e}")
            import traceback
            traceback.print_exc()
            self._create_error_pixmap()
    
    def _create_pixmap(self):
        """Create QPixmap from frame data with proper orientation"""
        try:
            logging.info(f"  DEBUG: Starting pixmap creation - shape: {self.frame_data.shape}")
            
            #   FIXED: Validate frame data shape
            if len(self.frame_data.shape) not in [2, 3]:
                logging.info(f" ERROR: Invalid frame data shape: {self.frame_data.shape}")
                raise ValueError(f"Frame data must be 2D or 3D, got {len(self.frame_data.shape)}D")
            
            frame_data = self.frame_data.copy()
            logging.info(f"  DEBUG: Frame data copied - dtype: {frame_data.dtype}")
            
            #   FIXED: Handle different data types more safely
            if frame_data.dtype != np.uint8:
                logging.info(f"  DEBUG: Converting from {frame_data.dtype} to uint8...")
                
                # Check for invalid values
                if np.any(np.isnan(frame_data)) or np.any(np.isinf(frame_data)):
                    logging.info("⚠️ WARNING: Found NaN or Inf values, cleaning...")
                    frame_data = np.nan_to_num(frame_data, nan=0.0, posinf=0.0, neginf=0.0)
                
                # Safe normalization
                data_min = frame_data.min()
                data_max = frame_data.max()
                logging.info(f"  DEBUG: Data range: {data_min} to {data_max}")
                
                if data_max > data_min:
                    frame_norm = (frame_data.astype(np.float32) - data_min) / (data_max - data_min)
                else:
                    logging.info("⚠️ WARNING: No data range, using zeros")
                    frame_norm = np.zeros_like(frame_data, dtype=np.float32)
                
                frame_data = (frame_norm * 255).astype(np.uint8)
                logging.info(f"  Normalization completed")
            
            #   FIXED: Handle 2D vs 3D data
            if len(frame_data.shape) == 3:
                logging.info(f"  DEBUG: 3D data detected, shape: {frame_data.shape}")
                if frame_data.shape[2] == 1:
                    frame_data = frame_data[:, :, 0]  # Remove single channel dimension
                    logging.info("  DEBUG: Removed single channel dimension")
                elif frame_data.shape[2] == 3:
                    # Convert RGB to grayscale
                    frame_data = np.dot(frame_data[...,:3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)
                    logging.info("  DEBUG: Converted RGB to grayscale")
            
            height, width = frame_data.shape
            logging.info(f"  DEBUG: Final frame dimensions: {width}x{height}")
            
            #   FIXED: Validate dimensions
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid dimensions: {width}x{height}")
            
            #   FIXED: Apply medical image enhancement if needed
            if hasattr(self, '_is_medical_image') and self._is_medical_image:
                frame_data = self._enhance_medical_image_display(frame_data)
                logging.info("  Medical image enhancement applied")
            
            # Convert to PIL Image with error handling
            try:
                logging.info("  DEBUG: Creating PIL Image...")
                image = Image.fromarray(frame_data, mode='L')
                logging.info("  PIL Image created")
            except Exception as pil_error:
                logging.info(f" ERROR creating PIL Image: {pil_error}")
                raise
            
            #   FIXED: For DICOM medical images, check if we need rotation
            # Medical scans are sometimes stored in different orientations
            if hasattr(self, '_is_medical_image') and self._is_medical_image and height > width and height > 512:
                # Likely a medical scan that might need orientation adjustment
                logging.info("  DEBUG: Detected potential medical scan")
                
                # Check if image seems to be rotated (very tall and narrow)
                aspect_ratio = height / width
                if aspect_ratio > 3.0:
                    logging.info(f"  DEBUG: High aspect ratio ({aspect_ratio:.1f}), checking for rotation...")
                    
                    # Try rotating and see if it looks more reasonable
                    rotated_90 = image.rotate(90, expand=True)
                    rotated_width, rotated_height = rotated_90.size  # PIL uses (width, height)
                    rotated_aspect = rotated_height / rotated_width
                    
                    if rotated_aspect < aspect_ratio and rotated_aspect > 0.5:
                        logging.info("  DEBUG: Rotation improved aspect ratio, applying 90° rotation")
                        image = rotated_90
                        width, height = rotated_width, rotated_height
                    else:
                        logging.info("  DEBUG: Rotation did not improve, keeping original orientation")
            
            logging.info(f"  PIL Image finalized - size: {image.size}")
            
            #   FIXED: Handle DICOM medical image orientation properly
            logging.info(f"  DEBUG: Original dimensions: {width}x{height}")

            # For medical images, often height > width (like bone scans)
            # We need to preserve aspect ratio and proper orientation
            if height > width:
                # Tall image (typical medical scan)
                display_height = 280
                display_width = max(1, int((width / height) * display_height))
                logging.info(f"  DEBUG: Tall image - resize to {display_width}x{display_height}")
            else:
                # Wide image 
                display_width = 280
                display_height = max(1, int((height / width) * display_width))
                logging.info(f"  DEBUG: Wide image - resize to {display_width}x{display_height}")

            #   FIXED: Ensure minimum dimensions
            display_width = max(50, min(400, display_width))  # Clamp between 50-400
            display_height = max(50, min(400, display_height))  # Clamp between 50-400

            logging.info(f"  DEBUG: Final resize dimensions: {display_width}x{display_height}")

            #   FIXED: Use different resampling for medical vs regular images
            # Medical images often need nearest neighbor to preserve sharp edges
            if hasattr(self, '_is_medical_image') and self._is_medical_image:
                # Medical scan - use nearest neighbor for sharp edges
                resampling_method = Image.Resampling.NEAREST
                logging.info("  DEBUG: Using NEAREST resampling for medical image")
            else:
                # Regular image - use LANCZOS for smooth scaling
                resampling_method = Image.Resampling.LANCZOS
                logging.info("  DEBUG: Using LANCZOS resampling for regular image")
            
            #   FIXED: Safe resize with error handling
            try:
                image_resized = image.resize((display_width, display_height), resampling_method)
                logging.info("  Image resized")
            except Exception as resize_error:
                logging.info(f" ERROR resizing image: {resize_error}")
                # Fallback to nearest neighbor
                image_resized = image.resize((display_width, display_height), Image.Resampling.NEAREST)
                logging.info("  Fallback resize completed")
            
            # Convert to QPixmap with error handling
            try:
                image_rgb = image_resized.convert('RGB')
                w, h = image_rgb.size
                buf = image_rgb.tobytes()           # panjang = w*h*3
                qimg = QImage(buf, w, h, w * 3, QImage.Format_RGB888)
                qimg = qimg.copy()                  #   deep copy, aman dari lifetime buffer
                self.original_pixmap = QPixmap.fromImage(qimg)
                
                if self.original_pixmap.isNull():
                    raise ValueError("QPixmap creation failed - pixmap is null")
                
                logging.info("  QPixmap created successfully")
                
            except Exception as qt_error:
                logging.info(f" ERROR in Qt conversion: {qt_error}")
                raise
            
        except Exception as e:
            logging.info(f" CRITICAL ERROR creating pixmap: {e}")
            import traceback
            traceback.print_exc()
            self._create_error_pixmap()

    def _create_error_pixmap(self):
        """Create error pixmap when image processing fails"""
        logging.info("🔄 Creating error pixmap...")
        self.original_pixmap = QPixmap(200, 200)
        self.original_pixmap.fill(Qt.red)
        
        # Add error text
        from PySide6.QtGui import QPainter, QFont
        painter = QPainter(self.original_pixmap)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(self.original_pixmap.rect(), Qt.AlignCenter, "ERROR\nLoading\nImage")
        painter.end()
        logging.info("  Error pixmap created")
    def _enhance_medical_image_display(self, frame_data: np.ndarray) -> np.ndarray:
        """Enhance medical image for better display"""
        try:
            logging.info("  DEBUG: Enhancing medical image display...")
            
            #   FIXED: Apply histogram equalization for better contrast
            if frame_data.dtype != np.uint8:
                # For 16-bit medical images, apply adaptive histogram equalization
                from scipy import ndimage
                
                # Normalize to 0-1 range first
                data_min, data_max = frame_data.min(), frame_data.max()
                if data_max > data_min:
                    normalized = (frame_data - data_min) / (data_max - data_min)
                else:
                    normalized = np.zeros_like(frame_data, dtype=np.float32)
                
                # Apply gentle contrast enhancement
                enhanced = np.power(normalized, 0.8)  # Gamma correction
                
                # Convert back to uint8
                result = (enhanced * 255).astype(np.uint8)
                logging.info("  Applied contrast enhancement for medical image")
                return result
            else:
                logging.info("  Image already uint8, no enhancement needed")
                return frame_data
                
        except Exception as e:
            logging.info(f"⚠️ WARNING: Medical image enhancement failed: {e}")
            return frame_data
        
    def _update_display(self):
        """Update display with current zoom and pan"""
        if not self.original_pixmap:
            return
            
        # Calculate zoomed size
        zoomed_size = self.original_pixmap.size() * self.zoom_factor

        #   FIXED: Use appropriate scaling for different image types
        if hasattr(self, '_is_medical_image') and self._is_medical_image:
            # Medical images need sharp edges preserved
            transformation = Qt.FastTransformation if self.zoom_factor < 1.0 else Qt.SmoothTransformation
            logging.info(f"  DEBUG: Using {'Fast' if transformation == Qt.FastTransformation else 'Smooth'} transformation for medical image")
        else:
            # Regular images always use smooth
            transformation = Qt.SmoothTransformation

        # Scale pixmap with appropriate transformation
        scaled_pixmap = self.original_pixmap.scaled(
            zoomed_size,
            Qt.KeepAspectRatio,
            transformation
        )
        
        #   FIX 2: Implement proper panning with offset
        if self.zoom_factor > 1.0 and not self.pan_offset.isNull():
            # Create a canvas for panning
            canvas_size = self.size()
            canvas = QPixmap(canvas_size)
            canvas.fill(Qt.transparent)
            
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            
            # Calculate position with pan offset
            x = (canvas_size.width() - scaled_pixmap.width()) // 2 + self.pan_offset.x()
            y = (canvas_size.height() - scaled_pixmap.height()) // 2 + self.pan_offset.y()
            
            painter.drawPixmap(x, y, scaled_pixmap)
            painter.end()
            
            self.setPixmap(canvas)
        else:
            self.setPixmap(scaled_pixmap)
        
        # Update cursor based on zoom level
        if self.zoom_factor > 1.0:
            if self.dragging:
                self.setCursor(Qt.ClosedHandCursor)
            else:
                self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        
        # Update tooltip with current info
        self.setToolTip(
            f"Zoom: {self.zoom_factor:.1f}x\n"
            f"Pan: ({self.pan_offset.x()}, {self.pan_offset.y()})\n"
            f"Mouse wheel: zoom\n"
            f"Drag: pan (when zoomed)\n"
            f"Double-click: reset"
        )
    
    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming"""
        # Get wheel delta
        delta = event.angleDelta().y()
        
        # Calculate zoom change
        zoom_in = delta > 0
        zoom_change = 1.15 if zoom_in else 1/1.15
        
        # Apply zoom with limits
        new_zoom = self.zoom_factor * zoom_change
        new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
        
        if new_zoom != self.zoom_factor:
            self.zoom_factor = new_zoom
            
            # Reset pan when zooming out to 1.0 or less
            if self.zoom_factor <= 1.0:
                self.pan_offset = QPoint(0, 0)
            
            self._update_display()
        
        event.accept()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Start dragging for pan"""
        if event.button() == Qt.LeftButton and self.zoom_factor > 1.0:
            self.dragging = True
            self.last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for panning"""
        if self.dragging and self.zoom_factor > 1.0:
            #   FIX 2: Implement actual panning
            delta = event.pos() - self.last_pan_point
            self.pan_offset += delta
            self.last_pan_point = event.pos()
            self._update_display()
        elif self.zoom_factor > 1.0:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Stop dragging"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            if self.zoom_factor > 1.0:
                self.setCursor(Qt.OpenHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Reset zoom and pan on double click"""
        self.zoom_factor = 1.0
        self.pan_offset = QPoint(0, 0)
        self._update_display()
        super().mouseDoubleClickEvent(event)

from features.dicom_import.logic.pixel_analyzer import analyze_pixel_distribution

class DicomPreviewThread(QThread):
    """Thread untuk load preview DICOM files dengan enhanced detection"""
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
                logging.info(f"Error loading {file_path}: {e}")
                # Emit None untuk menandakan error
                self.preview_loaded.emit(file_path, None)
            
            self.loading_progress.emit(i + 1, len(self.file_paths))
    
    def _load_dicom_info(self, file_path: Path) -> DicomInfo:
        """Load DICOM info dengan enhanced detection dan confidence scoring"""
        # Load frames and metadata
        frames_dict, metadata = load_frames_and_metadata(str(file_path))
        
        # Extract patient info
        patient_id = metadata.get("patient_id", "Unknown")
        study_date = metadata.get("study_date", "Unknown")
        
        # Process each frame dengan confidence scoring
        frame_infos = []
        reliable_detections = 0
        total_frames = len(frames_dict)
        
        logging.info(f"  DEBUG: Processing {total_frames} frames from {file_path.name}")
        
        for frame_index, (view_name, frame_data) in enumerate(frames_dict.items()):
            logging.info(f"  Frame {frame_index}: '{view_name}'")
            
            #   FIX 3: Enhanced view detection with confidence
            detected_view, confidence = self._enhanced_view_detection_with_confidence(view_name)
            logging.info(f"    Detected: {detected_view} (confidence: {confidence})")
            
            frame_info = FrameInfo(
                frame_index=frame_index,
                frame_data=frame_data,
                detected_view=detected_view,
                user_selected_view=None,  # Will be set based on confidence
                detection_confidence=confidence
            )
            
            #   FIX 3: Auto-set only for HIGH confidence detections
            if confidence == "high" and detected_view in ["Anterior", "Posterior"]:
                frame_info.user_selected_view = detected_view
                if detected_view == "Anterior":
                    frame_info.is_anterior_checked = True
                    frame_info.is_posterior_checked = False
                else:
                    frame_info.is_posterior_checked = True
                    frame_info.is_anterior_checked = False
                
                reliable_detections += 1
                logging.info(f"      auto-tagged: {detected_view} (high confidence)")
            else:
                frame_info.is_anterior_checked = False
                frame_info.is_posterior_checked = False
                frame_info.user_selected_view = None
            from features.dicom_import.logic.pixel_analyzer import analyze_background_type
        
            logging.info(f"\n  STARTING BACKGROUND ANALYSIS FOR FRAME {frame_index}...")
            background_analysis = analyze_background_type(frame_data)
            
            if background_analysis:
                frame_info.pixel_analysis = background_analysis
                frame_info.selected_background = background_analysis["background_type"]
                
                confidence = background_analysis["confidence"]
                bg_type = background_analysis["background_type"]
                bg_percentage = background_analysis["background_percentage"]
                
                logging.info(f"  BACKGROUND ANALYSIS RESULT:")
                logging.info(f"   Type: {bg_type}")
                logging.info(f"   Confidence: {confidence}%")
                logging.info(f"   Background area: {bg_percentage:.1f}%")
                logging.info(f"   Will auto-select: {bg_type} radio button")
                
                # Debug decision factors
                if "debug_info" in background_analysis:
                    debug = background_analysis["debug_info"]
                    logging.info(f"   Factors: {len(debug.get('decision_factors', []))}")
            else:
                logging.info(f" BACKGROUND ANALYSIS FAILED!")
                frame_info.pixel_analysis = None
                frame_info.selected_background = "black"  # Fallback

            logging.info(f"    ⚠️ manual tagged REQUIRED: {confidence} confidence")
            
            frame_infos.append(frame_info)
        
        # Determine if reliable detection is available
        has_reliable_detection = reliable_detections >= 2  # At least 2 reliable detections
        needs_manual_config = reliable_detections < total_frames  # Some frames need manual tagged
        
        # Special case: 2-frame bone scan with no reliable detections
        if total_frames == 2 and reliable_detections == 0:
            # Check if we can make educated guess
            if all(info.detection_confidence == "low" for info in frame_infos):
                # Apply bone scan convention but mark as needing confirmation
                frame_infos[0].detected_view = "Anterior"
                frame_infos[1].detected_view = "Posterior"
                logging.info(f"      Applied bone scan convention (needs manual confirmation)")
                needs_manual_config = True
                has_reliable_detection = False
        
        logging.info(f"Summary: {file_path.name}")
        logging.info(f"    Reliable detections: {reliable_detections}/{total_frames}")
        logging.info(f"    Has reliable detection: {has_reliable_detection}")
        logging.info(f"    Needs manual tagged: {needs_manual_config}")
        
        return DicomInfo(
            file_path=file_path,
            patient_id=patient_id,
            study_date=study_date,
            frames=frame_infos,
            has_reliable_detection=has_reliable_detection,
            needs_manual_config=needs_manual_config
        )
    
    def _enhanced_view_detection_with_confidence(self, view_name: str) -> Tuple[Optional[str], str]:
        """
        Enhanced view detection dengan confidence scoring
        
        Returns:
            Tuple of (detected_view, confidence)
            confidence: "high", "low", "none"
        """
        if not view_name:
            return None, "none"
        
        view_upper = view_name.upper()
        
        # HIGH CONFIDENCE: Clear, unambiguous indicators
        if "ANTERIOR" in view_upper:
            return "Anterior", "high"
        elif "POSTERIOR" in view_upper:
            return "Posterior", "high"
        elif view_upper == "ANT":
            return "Anterior", "high"
        elif view_upper == "POST":
            return "Posterior", "high"
        
        # LOW CONFIDENCE: Partial matches or assumptions
        elif view_upper.startswith("ANT") and len(view_upper) <= 6:
            return "Anterior", "low"
        elif view_upper.startswith("POST") and len(view_upper) <= 8:
            return "Posterior", "low"
        elif "ANT" in view_upper and len(view_upper) <= 10:
            return "Anterior", "low"
        elif "POST" in view_upper and len(view_upper) <= 12:
            return "Posterior", "low"
        
        
        return None, "none"


class FrameWidget(QWidget):
    """Widget untuk menampilkan single frame dengan enhanced controls"""
    selection_changed = Signal()
    
    def __init__(self, frame_info: FrameInfo, dicom_path: Path):
        super().__init__()
        
        #   FIXED: Validate frame_info
        if not frame_info:
            logging.info(" ERROR: FrameWidget received None frame_info")
            raise ValueError("FrameInfo cannot be None")
        
        if frame_info.frame_data is None:
            logging.info(f" ERROR: FrameWidget received None frame_data for frame {frame_info.frame_index}")
            raise ValueError("Frame data cannot be None")
        
        logging.info(f"  DEBUG: Initializing FrameWidget for frame {frame_info.frame_index} from {dicom_path.name}")
        
        self.frame_info = frame_info
        self.dicom_path = dicom_path
        
        try:
            logging.info(f"  DEBUG: Setting up UI for frame {frame_info.frame_index}...")
            self._setup_ui()
            logging.info(f"  DEBUG: Connecting signals for frame {frame_info.frame_index}...")
            self._connect_signals()
            logging.info(f"  FrameWidget setup completed for frame {frame_info.frame_index}")
        except Exception as e:
            logging.info(f" ERROR in FrameWidget.__init__ for frame {frame_info.frame_index}: {e}")
            import traceback
            traceback.print_exc()
            logging.info(f"🔄 Using fallback UI for frame {frame_info.frame_index}")
            self._setup_fallback_ui()
    
    def _setup_fallback_ui(self):
        """Fallback UI jika ada error"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        error_label = QLabel("Frame Load Error")
        error_label.setStyleSheet("""
            QLabel {
                color: #dc3545;
                font-weight: bold;
                padding: 8px;
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 4px;
                font-size: 11px;
                text-align: center;
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        #   FIX 1: Use enhanced ZoomableImageLabel
        self.preview_label = ZoomableImageLabel(self.frame_info.frame_data)
        self.preview_label.setMinimumSize(250, 250)
        layout.addWidget(self.preview_label)
        
        # Enhanced frame info with confidence indicator
        frame_data = self.frame_info.frame_data
        dimensions = f"{frame_data.shape[0]}×{frame_data.shape[1]}"
        
        info_text = f"Frame {self.frame_info.frame_index + 1}\nSize: {dimensions}"
        
        #   FIX 3: Show detection confidence
        if self.frame_info.detected_view:
            confidence_icon = {
                "high": " ",
                "low": "⚠️", 
                "none": "❌"
            }.get(self.frame_info.detection_confidence, "❓")
            
            info_text += f"\nDetected: {self.frame_info.detected_view}"
            # info_text += f"\nConfidence: {confidence_icon} {self.frame_info.detection_confidence.title()}"
        else:
            info_text += f"\nDetected: None\nConfidence:  None"
        
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
        
        # Enhanced zoom controls
        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(6)
        
        zoom_out_btn = QPushButton(" -")
        zoom_out_btn.setFixedSize(30, 25)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(lambda: self._zoom_control(-1))
        
        zoom_reset_btn = QPushButton("Reset")
        zoom_reset_btn.setFixedSize(35, 25)
        zoom_reset_btn.setToolTip("Reset Zoom & Pan")
        zoom_reset_btn.clicked.connect(lambda: self._zoom_control(0))
        
        zoom_in_btn = QPushButton(" +")
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
        
        #   FIX 3: Enhanced checkboxes with auto-config status
        checkbox_frame = QFrame()
        
        # Simple status determination
        if self.frame_info.detection_confidence == "high":
            status_text = "  auto-tagged"
            status_color = Colors.SUCCESS
        elif self.frame_info.detection_confidence == "low":
            status_text = "⚠️ Please confirm"
            status_color = Colors.WARNING
        else:
            status_text = "⚙️ Manual selection required"
            status_color = Colors.SECONDARY
        
        #   FIXED: Use consistent styling without variables
        checkbox_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(248, 249, 250, 0.9);
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        checkbox_layout = QVBoxLayout(checkbox_frame)
        checkbox_layout.setSpacing(8)
        
        # Status indicator for auto-configuration
        if self.frame_info.detection_confidence == "high":
            status_text = "  auto-tagged"
            status_color = Colors.SUCCESS
        elif self.frame_info.detection_confidence == "low":
            status_text = "⚠️ Please confirm"
            status_color = Colors.WARNING
        else:
            status_text = "⚙️ Manual selection required"
            status_color = Colors.SECONDARY
        
        status_label = QLabel(status_text)
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet(f"""
            QLabel {{
                color: {status_color};
                font-size: 10px;
                font-weight: bold;
                padding: 2px 4px;
                font-style: italic;
            }}
        """)
        checkbox_layout.addWidget(status_label)
        
        self.anterior_radio = QRadioButton("Anterior")
        self.posterior_radio = QRadioButton("Posterior")
        
        # --- PERUBAHAN: Kontrol Pemilihan View menggunakan RadioButton ---
        view_selection_frame = QFrame()
        view_selection_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(248, 249, 250, 0.9);
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        view_selection_layout = QVBoxLayout(view_selection_frame)
        view_selection_layout.setSpacing(8)

        # Status indicator for auto-configuration (Sama seperti sebelumnya)
        if self.frame_info.detection_confidence == "high":
            status_text = "✔ auto-tagged"
            status_color = Colors.SUCCESS
        elif self.frame_info.detection_confidence == "low":
            status_text = "⚠️ Please confirm"
            status_color = Colors.WARNING
        else:
            status_text = "⚙️ Manual selection required"
            status_color = Colors.SECONDARY
        
        status_label = QLabel(status_text)
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet(f"color: {status_color}; font-size: 10px; font-weight: bold; padding: 2px 4px; font-style: italic;")
        view_selection_layout.addWidget(status_label)

        # Buat RadioButton dan ButtonGroup
        self.view_button_group = QButtonGroup()
        self.anterior_radio = QRadioButton("Anterior")
        self.posterior_radio = QRadioButton("Posterior")
        
        # Gunakan style yang sama dengan radio button background
        radio_style = f"""
            QRadioButton {{ font-size: 11px; font-weight: bold; color: {Colors.DARK_GRAY}; padding: 2px; }}
            QRadioButton::indicator {{ width: 14px; height: 14px; }}
            QRadioButton::indicator:unchecked {{ border: 2px solid {Colors.BORDER_MEDIUM}; border-radius: 7px; background: white; }}
            QRadioButton::indicator:checked {{ border: 2px solid {Colors.PRIMARY}; border-radius: 7px; background: {Colors.PRIMARY}; }}
        """
        self.anterior_radio.setStyleSheet(radio_style)
        self.posterior_radio.setStyleSheet(radio_style)

        # Tambahkan ke group untuk mutual exclusivity
        self.view_button_group.addButton(self.anterior_radio)
        self.view_button_group.addButton(self.posterior_radio)
        self.view_button_group.setExclusive(True) # Pastikan hanya satu yang bisa dipilih

        # Atur status awal berdasarkan data
        self.anterior_radio.setChecked(self.frame_info.is_anterior_checked)
        self.posterior_radio.setChecked(self.frame_info.is_posterior_checked)

        # Tambahkan ke layout horizontal agar berdampingan
        radio_layout = QHBoxLayout()
        # radio_layout.addStretch()
        radio_layout.addWidget(self.anterior_radio)
        radio_layout.addWidget(self.posterior_radio)
        # radio_layout.addStretch()
        view_selection_layout.addLayout(radio_layout)
        
        layout.addWidget(view_selection_frame)
        # --- AKHIR PERUBAHAN ---
        
        # TAMBAHAN BARU: Background Selection Controls
        background_frame = QFrame()
        background_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(248, 249, 250, 0.9);
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 6px;
                padding: 8px;
                margin-top: 8px;
            }}
        """)
        background_layout = QVBoxLayout(background_frame)
        background_layout.setSpacing(6)
        bg_stats = "Background Analysis"
        # Background selection header with pixel stats
        if self.frame_info.pixel_analysis:
            analysis = self.frame_info.pixel_analysis
            bg_type = analysis.get("background_type", "unknown")
            confidence = analysis.get("confidence", 0)
            bg_percentage = analysis.get("background_percentage", 0)
            
            
        else:
            bg_stats = "Background Analysis"
        
        bg_header = QLabel(bg_stats)
        bg_header.setStyleSheet(f"""
            QLabel {{
                color: {Colors.SECONDARY};
                font-size: 10px;
                font-weight: bold;
                text-align: center;
                margin-bottom: 4px;
            }}
        """)
        background_layout.addWidget(bg_header)
        
        # Radio buttons for background selection
        self.background_group = QButtonGroup()
        
        bg_radio_layout = QHBoxLayout()
        bg_radio_layout.setSpacing(12)
        
        self.black_bg_radio = QRadioButton("Black Background")
        self.white_bg_radio = QRadioButton("White Background")
        
        # Set initial selection based on analysis
        detected_bg = self.frame_info.selected_background
        confidence = self.frame_info.pixel_analysis.get("confidence", 0) if self.frame_info.pixel_analysis else 0
        
        detected_bg = self.frame_info.selected_background
        pixel_analysis = self.frame_info.pixel_analysis
        
        logging.info(f"\n  FRAME {self.frame_info.frame_index} AUTO-SELECTION DEBUG:")
        logging.info(f"   detected_bg: '{detected_bg}'")
        logging.info(f"   pixel_analysis exists: {pixel_analysis is not None}")
        
        if pixel_analysis:
            confidence = pixel_analysis.get("confidence", 0)
            bg_type = pixel_analysis.get("background_type", "unknown")
            logging.info(f"   analysis.background_type: '{bg_type}'")
            logging.info(f"   analysis.confidence: {confidence}%")
            
            if "debug_info" in pixel_analysis:
                debug = pixel_analysis["debug_info"]
                logging.info(f"   corner_mean: {debug.get('corner_mean', 'N/A')}")
                logging.info(f"   edge_mean: {debug.get('edge_mean', 'N/A')}")
                logging.info(f"   image_mean: {debug.get('image_mean', 'N/A')}")
        else:
            confidence = 0
            logging.info(f"    NO PIXEL ANALYSIS DATA!")
        
        # Auto-selection logic with detailed logging
        if detected_bg == "black":
            self.black_bg_radio.setChecked(True)
            self.white_bg_radio.setChecked(False)
            logging.info(f"  AUTO-SELECTED: BLACK background radio button")
        elif detected_bg == "white":
            self.white_bg_radio.setChecked(True) 
            self.black_bg_radio.setChecked(False)
            logging.info(f"  AUTO-SELECTED: WHITE background radio button")
        else:
            # Fallback dengan logging
            self.black_bg_radio.setChecked(True)
            self.white_bg_radio.setChecked(False)
            logging.info(f"⚠️ FALLBACK: Unknown detected_bg '{detected_bg}' → defaulting to BLACK")
        
        logging.info(f"   Final state - Black checked: {self.black_bg_radio.isChecked()}")
        logging.info(f"   Final state - White checked: {self.white_bg_radio.isChecked()}")
        
        radio_style = f"""
            QRadioButton {{
                font-size: 10px;
                font-weight: bold;
                color: {Colors.DARK_GRAY};
                padding: 2px;
            }}
            QRadioButton::indicator {{
                width: 12px;
                height: 12px;
            }}
            QRadioButton::indicator:unchecked {{
                border: 2px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                background: white;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {Colors.PRIMARY};
                border-radius: 6px;
                background: {Colors.PRIMARY};
            }}
        """
        
        self.anterior_radio.setStyleSheet(radio_style)
        self.posterior_radio.setStyleSheet(radio_style)

        self.black_bg_radio.setStyleSheet(radio_style)
        self.white_bg_radio.setStyleSheet(radio_style)
        
        self.background_group.addButton(self.black_bg_radio, 0)
        self.background_group.addButton(self.white_bg_radio, 1)
        
        bg_radio_layout.addWidget(self.black_bg_radio)
        bg_radio_layout.addWidget(self.white_bg_radio)
        background_layout.addLayout(bg_radio_layout)
        
        layout.addWidget(background_frame)
    
    
    def _zoom_control(self, direction: int):
        """Control zoom via buttons with pan reset"""
        if hasattr(self.preview_label, 'zoom_factor'):
            current_zoom = self.preview_label.zoom_factor
            
            if direction == 1:  # Zoom in
                new_zoom = min(current_zoom * 1.2, self.preview_label.max_zoom)
            elif direction == -1:  # Zoom out
                new_zoom = max(current_zoom / 1.2, self.preview_label.min_zoom)
            else:  # Reset
                new_zoom = 1.0
                self.preview_label.pan_offset = QPoint(0, 0)
            
            if new_zoom != current_zoom:
                self.preview_label.zoom_factor = new_zoom
                
                # Reset pan when zooming out to normal
                if new_zoom <= 1.0:
                    self.preview_label.pan_offset = QPoint(0, 0)
                
                self.preview_label._update_display()
    
    def _connect_signals(self):
        # Connect with parent reference for mutual exclusivity
        self.view_button_group.buttonToggled.connect(self._on_view_changed)
        self.background_group.buttonToggled.connect(self._on_background_changed)
        
    def _on_view_changed(self, button: QRadioButton, checked: bool):
        """Handler baru untuk view radio buttons."""
        if not checked:
            # Hanya proses saat sebuah tombol menjadi checked
            # Saat tombol lain di-uncheck, jangan lakukan apa-apa
            # Ini mencegah sinyal ganda
            return
            
        selected_view = None
        if button == self.anterior_radio:
            selected_view = "Anterior"
            self.frame_info.is_anterior_checked = True
            self.frame_info.is_posterior_checked = False
        elif button == self.posterior_radio:
            selected_view = "Posterior"
            self.frame_info.is_posterior_checked = True
            self.frame_info.is_anterior_checked = False

        self.frame_info.user_selected_view = selected_view
        
        # Panggil parent untuk enforce exclusivity antar frame
        parent_widget = self.get_dicom_file_widget()
        if parent_widget and selected_view:
            parent_widget._enforce_mutual_exclusivity(selected_view, self)

        # Emit sinyal bahwa pilihan telah berubah
        self.selection_changed.emit()

    def get_selection(self) -> Optional[str]:
        """Get current selection"""
        return self.frame_info.user_selected_view
    
    def get_dicom_file_widget(self) -> Optional['DicomFileWidget']:
        """Get parent DicomFileWidget"""
        parent = self.parent()
        while parent:
            if isinstance(parent, DicomFileWidget):
                return parent
            parent = parent.parent()
        return None

    def _on_background_changed(self, button, checked):
        """Handle background selection change"""
        if not checked:
            return
            
        if button == self.black_bg_radio:
            self.frame_info.selected_background = "black"
            logging.info(f"🎨 Frame {self.frame_info.frame_index}: Selected black background")
        elif button == self.white_bg_radio:
            self.frame_info.selected_background = "white"
            logging.info(f"🎨 Frame {self.frame_info.frame_index}: Selected white background")
        
        # Emit selection changed to update parent
        QTimer.singleShot(0, self.selection_changed.emit)

    def get_background_selection(self) -> str:
        """Get current background selection"""
        return self.frame_info.selected_background

class DicomFileWidget(QWidget):
    """Widget untuk menampilkan single DICOM file dengan enhanced status"""
    selection_changed = Signal()
    
    def __init__(self, dicom_info: DicomInfo):
        super().__init__()
        
        #   FIXED: Validate input first
        if not dicom_info:
            logging.info(" ERROR: DicomFileWidget received None dicom_info")
            raise ValueError("DicomInfo cannot be None")
        
        if not dicom_info.frames:
            logging.info(f" ERROR: DicomFileWidget received empty frames for {dicom_info.file_path}")
            raise ValueError("DicomInfo must have frames")
        
        logging.info(f"  DEBUG: Initializing DicomFileWidget for {dicom_info.file_path.name} with {len(dicom_info.frames)} frames")
        
        self.dicom_info = dicom_info
        self.frame_widgets: List[FrameWidget] = []
        
        try:
            logging.info(f"  DEBUG: Setting up UI for {dicom_info.file_path.name}...")
            self._setup_ui()
            logging.info(f"  UI setup completed for {dicom_info.file_path.name}")
        except Exception as e:
            logging.info(f" ERROR in DicomFileWidget.__init__ for {dicom_info.file_path.name}: {e}")
            import traceback
            traceback.print_exc()
            logging.info(f"🔄 Falling back to minimal UI for {dicom_info.file_path.name}")
            try:
                self._setup_fallback_ui()
            except Exception as fallback_error:
                logging.info(f" CRITICAL: Fallback UI also failed: {fallback_error}")
                raise
        
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
        layout.setSpacing(15)
        
        #   FIX 3: Enhanced file header with detection status
        header_frame = QFrame()
        
        # Color-code header based on detection status
        if self.dicom_info.has_reliable_detection and not self.dicom_info.needs_manual_config:
            # Fully auto-tagged
            header_bg = "linear-gradient(135deg, #d4edda 0%, rgba(212, 237, 218, 0.8) 100%)"
            header_border = "#c3e6cb"
            status_icon = " "
            status_text = "auto-tagged"
            
        elif self.dicom_info.has_reliable_detection and self.dicom_info.needs_manual_config:
            # Partially auto-tagged
            header_bg = "linear-gradient(135deg, #fff3cd 0%, rgba(255, 243, 205, 0.8) 100%)"
            header_border = "#ffeeba"
            status_icon = "⚠️"
            status_text = "Partial - Needs Confirmation"
            
        else:
            # manual taggeduration required
            header_bg = "linear-gradient(135deg, #f8d7da 0%, rgba(248, 215, 218, 0.8) 100%)"
            header_border = "#f5c6cb"
            status_icon = "⚙️"
            status_text = "Manual Selection Required"
        
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: {header_bg};
                border: 1px solid {header_border};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        header_layout = QVBoxLayout(header_frame)
        
        # File name with status
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
        
        # Patient info with enhanced status
        info_text = f"Patient: {self.dicom_info.patient_id} | Study Date: {self.dicom_info.study_date}"
        info_text += f" | {status_icon} {status_text}"
        
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
            error_label = QLabel(" No frames found in DICOM file")
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
        
        # Frames container with enhanced layout
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
        frames_layout.setSpacing(20)
        frames_layout.setContentsMargins(15, 15, 15, 15)
        
        # Responsive grid calculation
        frame_count = len(self.dicom_info.frames)
        if frame_count <= 2:
            cols = frame_count
        elif frame_count <= 6:
            cols = min(3, frame_count)
        else:
            cols = 4
        
        # Add frame widgets
        for i, frame_info in enumerate(self.dicom_info.frames):
            try:
                frame_widget = FrameWidget(frame_info, self.dicom_info.file_path)
                frame_widget.selection_changed.connect(self.selection_changed.emit)
                
                row = i // cols
                col = i % cols
                frames_layout.addWidget(frame_widget, row, col)
                self.frame_widgets.append(frame_widget)
                
            except Exception as e:
                logging.info(f"ERROR creating FrameWidget {i}: {e}")
                continue
        
        # Set column stretch for proper spacing
        for col in range(cols):
            frames_layout.setColumnStretch(col, 1)
        
        layout.addWidget(frames_container)
    
    def _enforce_mutual_exclusivity(self, selected_view: str, selected_frame_widget: 'FrameWidget'):
        """Enforce mutual exclusivity: hanya satu Anterior dan satu Posterior per DICOM file."""
        logging.info(f"🔒 Enforcing mutual exclusivity: {selected_view} selected")
        
        for frame_widget in self.frame_widgets:
            if frame_widget == selected_frame_widget:
                continue

            # Gunakan QButtonGroup untuk me-reset pilihan di frame lain
            if selected_view == "Anterior" and frame_widget.anterior_radio.isChecked():
                frame_widget.view_button_group.setExclusive(False) # Matikan sementara
                frame_widget.anterior_radio.setChecked(False)
                frame_widget.view_button_group.setExclusive(True) # Nyalakan lagi
                frame_widget.frame_info.is_anterior_checked = False
                if frame_widget.frame_info.user_selected_view == "Anterior":
                    frame_widget.frame_info.user_selected_view = None
                logging.info(f"  Unchecked Anterior on frame {frame_widget.frame_info.frame_index}")

            elif selected_view == "Posterior" and frame_widget.posterior_radio.isChecked():
                frame_widget.view_button_group.setExclusive(False) # Matikan sementara
                frame_widget.posterior_radio.setChecked(False)
                frame_widget.view_button_group.setExclusive(True) # Nyalakan lagi
                frame_widget.frame_info.is_posterior_checked = False
                if frame_widget.frame_info.user_selected_view == "Posterior":
                    frame_widget.frame_info.user_selected_view = None
                logging.info(f"  Unchecked Posterior on frame {frame_widget.frame_info.frame_index}")
    
    
    def get_view_assignments(self) -> Dict[int, str]:
        """Get view assignments for all frames"""
        assignments = {}
        for frame_widget in self.frame_widgets:
            frame_index = frame_widget.frame_info.frame_index
            selection = frame_widget.get_selection()
            if selection:
                assignments[frame_index] = selection
        return assignments
    
    def get_view_assignments_with_background(self) -> Dict[int, Dict[str, str]]:
        """Get view assignments with background selection for all frames"""
        assignments = {}
        for frame_widget in self.frame_widgets:
            frame_index = frame_widget.frame_info.frame_index
            selection = frame_widget.get_selection()
            background = frame_widget.get_background_selection()
            
            if selection:  # Only include frames with view selections
                assignments[frame_index] = {
                    "view": selection,
                    "background": background
                }
        return assignments
    
    def has_complete_selection(self) -> Tuple[bool, List[str]]:
        """Check if file has exactly one Anterior and one Posterior frame selected"""
        assignments = self.get_view_assignments()
        
        if not assignments:
            return False, ["No frames selected"]
        
        views = list(assignments.values())
        anterior_count = views.count("Anterior")
        posterior_count = views.count("Posterior")
        
        missing = []
        if anterior_count == 0:
            missing.append("Anterior view")
        elif anterior_count > 1:
            missing.append(f"Too many Anterior views ({anterior_count}, should be 1)")
        
        if posterior_count == 0:
            missing.append("Posterior view")
        elif posterior_count > 1:
            missing.append(f"Too many Posterior views ({posterior_count}, should be 1)")
        background_selections = [
            self.frame_widgets[i].get_background_selection() 
            for i in range(len(self.frame_widgets))
            if self.frame_widgets[i].get_selection()  # Only for selected frames
        ]
        
        if not background_selections:
            missing.append("Background selection")
        return len(missing) == 0, missing
    
    def get_detection_status(self) -> Dict[str, any]:
        """Get detection status summary for this file"""
        return {
            "has_reliable_detection": self.dicom_info.has_reliable_detection,
            "needs_manual_config": self.dicom_info.needs_manual_config,
            "auto_configured_count": sum(1 for f in self.dicom_info.frames 
                                       if f.detection_confidence == "high"),
            "manual_required_count": sum(1 for f in self.dicom_info.frames 
                                       if f.detection_confidence in ["low", "none"]),
            "total_frames": len(self.dicom_info.frames)
        }


class DicomViewSelectorDialog(QDialog):
    """Enhanced main dialog untuk view selection dengan auto-configuration support"""
    views_confirmed = Signal(dict)  # {file_path: {frame_index: view_name}}
    def __init__(self, file_paths: List[Path], parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.dicom_infos: Dict[Path, DicomInfo] = {}
        self.dicom_widgets: List[DicomFileWidget] = []
        
        self.setWindowTitle("Select Anterior/Posterior Views ")
        self.setModal(True)
        self.resize(1400, 900)
        
        # Loading dialog
        self.loading_dialog: Optional[LoadingDialog] = None
        
        self._setup_ui()
        self._start_loading()

    def closeEvent(self, event):
        """Handle dialog close event with proper cleanup"""
        logging.info("  DEBUG: DicomViewSelectorDialog closing, cleaning up...")
        
        #   FIXED: Stop threads
        if hasattr(self, 'preview_thread') and self.preview_thread:
            if self.preview_thread.isRunning():
                logging.info("  DEBUG: Terminating preview thread...")
                self.preview_thread.terminate()
                self.preview_thread.wait(1000)  # Wait max 1 second
        
        #   FIXED: Close loading dialog
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
        
        #   FIXED: Clear widget references
        self.dicom_widgets.clear()
        self.dicom_infos.clear()
    
        logging.info("  DicomViewSelectorDialog cleanup completed")
        super().closeEvent(event)
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)
        
        # Enhanced title
        title_label = QLabel("  Select Anterior/Posterior Views")
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
        self.scroll_layout.setSpacing(20)
        
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
        
        # Enhanced validation status
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
        
        # Cancel button
        self.cancel_btn = QPushButton(" Cancel")
        self.cancel_btn.setStyleSheet(f"""
            {DIALOG_CANCEL_BUTTON_STYLE}
            font-size: 13px;
            padding: 10px 20px;
        """)
        button_layout.addWidget(self.cancel_btn)
        
        # Enhanced OK button
        self.ok_btn = QPushButton("  Confirm & Process")
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
            message="Analyzing DICOM files and detecting views with confidence scoring...",
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
            logging.info(f"  Loaded DICOM info for: {file_path.name}")
            logging.info(f"    Reliable detection: {dicom_info.has_reliable_detection}")
            logging.info(f"    Needs manual tagged: {dicom_info.needs_manual_config}")
        else:
            logging.info(f" Failed to load: {file_path}")
    
    def _on_loading_progress(self, current: int, total: int):
        """Update loading progress"""
        if self.loading_dialog:
            progress = int((current / total) * 100)
            self.loading_dialog.set_progress(progress)
            self.loading_dialog.set_message(f"Loading DICOM files... ({current}/{total})")
    
    def _on_loading_finished(self):
        """Finish loading and setup UI"""
        logging.info(f"  DEBUG: Loading finished. Loaded {len(self.dicom_infos)} DICOM info objects")
        
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
        
        #   FIXED: Added more robust error handling with step-by-step execution
        try:
            logging.info("  DEBUG: Starting widget setup...")
            self._setup_dicom_widgets()
            logging.info("  DEBUG: Widget setup completed, updating validation...")
            self._update_validation_status()
            logging.info("  DICOM widgets setup completed successfully")
            
        except Exception as e:
            logging.info(f" CRITICAL ERROR in _on_loading_finished: {e}")
            import traceback
            traceback.print_exc()
            
            #   FIXED: More detailed error recovery
            try:
                # Try to at least show some UI
                error_widget = self._create_critical_error_widget(str(e))
                self.scroll_layout.addWidget(error_widget)
                self._update_load_summary_status(0, len(self.file_paths), 0, 0)
            except Exception as recovery_error:
                logging.info(f" Recovery also failed: {recovery_error}")
            
            #   FIXED: Don't show error dialog that might cause another crash
            logging.info(" Setup failed - check console for details")
                
    
    def _setup_dicom_widgets(self):
        """Setup widgets for each loaded DICOM with enhanced status tracking"""
        success_count = 0
        error_count = 0
        auto_configured_count = 0
        manual_required_count = 0
        
        try:
            #   FIXED: Sort files by detection status to process auto-detected files first
            sorted_file_paths = sorted(
                [fp for fp in self.file_paths if fp in self.dicom_infos],
                key=lambda fp: (
                    not self.dicom_infos[fp].has_reliable_detection,  # Auto-detected first (False sorts before True)
                    self.dicom_infos[fp].needs_manual_config,         # Then by manual tagged needed
                    fp.name                                          # Finally by name for consistency
                )
            )

            logging.info(f"  DEBUG: Processing {len(sorted_file_paths)} files in optimized order...")
            for fp in sorted_file_paths:
                info = self.dicom_infos[fp]
                status = "auto" if info.has_reliable_detection and not info.needs_manual_config else "manual"
                logging.info(f"  {fp.name}: {status}")

            for i, file_path in enumerate(sorted_file_paths):
                try:
                    logging.info(f"  DEBUG: Creating widget {i+1}/{len(sorted_file_paths)} for {file_path.name}...")
                    
                    #   FIXED: Check if widget already exists (prevent duplicates)
                    if any(w.dicom_info.file_path == file_path for w in self.dicom_widgets):
                        logging.info(f"⚠️ WARNING: Widget for {file_path.name} already exists, skipping...")
                        continue
                    
                    dicom_info = self.dicom_infos[file_path]
                    
                    #   FIXED: Validate dicom_info before creating widget
                    if not dicom_info or not dicom_info.frames:
                        logging.info(f" ERROR: Invalid dicom_info for {file_path.name}")
                        error_count += 1
                        continue
                    
                    logging.info(f"  DEBUG: Creating DicomFileWidget with {len(dicom_info.frames)} frames...")
                    
                    #   FIXED: Wrap widget creation with specific error handling
                    try:
                        dicom_widget = DicomFileWidget(dicom_info)
                    except Exception as widget_error:
                        logging.info(f" ERROR creating DicomFileWidget for {file_path.name}: {widget_error}")
                        import traceback
                        traceback.print_exc()
                        error_count += 1
                        
                        # Create enhanced error placeholder
                        error_widget = self._create_error_widget(file_path, str(widget_error))
                        self.scroll_layout.addWidget(error_widget)
                        continue
                    
                    logging.info(f"  DEBUG: Widget created successfully, connecting signals...")
                    
                    #   FIXED: Wrap signal connection with error handling
                    try:
                        # Use queued connection to prevent order dependency crashes
                        dicom_widget.selection_changed.connect(
                            lambda: QTimer.singleShot(0, self._safe_update_validation_status)
                        )
                    except Exception as signal_error:
                        logging.info(f" ERROR connecting signals for {file_path.name}: {signal_error}")
                        error_count += 1
                        continue
                    
                    logging.info(f"  DEBUG: Signals connected, adding to layout...")
                    
                    #   FIXED: Wrap layout addition with error handling
                    try:
                        self.scroll_layout.addWidget(dicom_widget)
                        self.dicom_widgets.append(dicom_widget)
                        success_count += 1
                    except Exception as layout_error:
                        logging.info(f" ERROR adding widget to layout for {file_path.name}: {layout_error}")
                        error_count += 1
                        continue
                    
                    # Track configuration status
                    if dicom_info.has_reliable_detection and not dicom_info.needs_manual_config:
                        auto_configured_count += 1
                    elif dicom_info.needs_manual_config:
                        manual_required_count += 1
                    
                    logging.info(f"  Successfully created widget for {file_path.name}")
                    
                    #   FIXED: Process events more carefully
                    try:
                        QCoreApplication.processEvents()
                    except Exception as process_error:
                        logging.info(f"⚠️ WARNING: processEvents failed: {process_error}")
                        
                except Exception as e:
                    logging.info(f" ERROR creating widget for {file_path.name}: {e}")
                    import traceback
                    traceback.print_exc()
                    error_count += 1
                    
                    # Create enhanced error placeholder
                    try:
                        error_widget = self._create_error_widget(file_path, str(e))
                        self.scroll_layout.addWidget(error_widget)
                    except Exception as error_widget_error:
                        logging.info(f" ERROR creating error widget: {error_widget_error}")
            
            # Add stretch to push content to top
            self.scroll_layout.addStretch()
            
            # Update status with detailed summary
            self._update_load_summary_status(success_count, error_count, auto_configured_count, manual_required_count)
            
            logging.info(f"📊 Widget creation summary:")
            logging.info(f"  Success: {success_count}")
            logging.info(f"  Errors: {error_count}")
            logging.info(f"  auto-tagged: {auto_configured_count}")
            logging.info(f"  Manual required: {manual_required_count}")
            
        except Exception as e:
            logging.info(f" CRITICAL ERROR in _setup_dicom_widgets: {e}")
            import traceback
            traceback.print_exc()
            
            # Show critical error message
            try:
                critical_error_widget = self._create_critical_error_widget(str(e))
                self.scroll_layout.addWidget(critical_error_widget)
            except Exception as critical_error:
                logging.info(f" Critical error widget creation also failed: {critical_error}")

    def _safe_update_validation_status(self):
        """Safe wrapper for validation status update with crash recovery"""
        try:
            self._update_validation_status()
        except Exception as e:
            logging.info(f" ERROR in validation status update: {e}")
            import traceback
            traceback.print_exc()
            
            #   Recovery: Set default state
            try:
                self.ok_btn.setEnabled(False)
                self.status_label.setText("⚠️ Validation error - please retry")
                self.status_label.setStyleSheet(f"""
                    QLabel {{
                        color: #dc3545;
                        font-size: 13px;
                        font-weight: bold;
                        padding: 8px 12px;
                        background: #f8d7da;
                        border: 1px solid #f5c6cb;
                        border-radius: 6px;
                    }}
                """)
            except Exception as recovery_error:
                logging.info(f" Recovery also failed: {recovery_error}")
    
    def _create_error_widget(self, file_path: Path, error_msg: str) -> QFrame:
        """Create enhanced error widget for failed files"""
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
        
        error_title = QLabel(f" Error Loading: {file_path.name}")
        error_title.setStyleSheet("""
            QLabel {
                color: #721c24;
                font-weight: bold;
                font-size: 14px;
                margin-bottom: 5px;
            }
        """)
        error_layout.addWidget(error_title)
        
        error_detail = QLabel(f"Technical details: {truncate_text(error_msg, 100)}")
        error_detail.setStyleSheet("""
            QLabel {
                color: #721c24;
                font-size: 11px;
                font-style: italic;
            }
        """)
        error_layout.addWidget(error_detail)
        
        return error_widget
    
    def _create_critical_error_widget(self, error_msg: str) -> QFrame:
        """Create critical error widget"""
        error_frame = QFrame()
        error_layout = QVBoxLayout(error_frame)
        
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
        error_layout.addWidget(error_label)
        
        detail_label = QLabel(f"Technical details: {truncate_text(error_msg, 200)}\n\nThis may be due to corrupted DICOM files or missing dependencies.")
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
        error_layout.addWidget(detail_label)
        
        return error_frame
    
    def _update_load_summary_status(self, success: int, error: int, auto_config: int, manual_req: int):
        """Update status with detailed load summary"""
        total = len(self.file_paths)
        
        if error > 0:
            self.status_label.setText(f"⚠️ Loaded {success}/{total} files ({error} errors)")
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
            status_text = f"  Loaded {success} files"
            if auto_config > 0:
                status_text += f" • {auto_config} auto-tagged"
            if manual_req > 0:
                status_text += f" • {manual_req} need manual tagged"
            
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.SUCCESS};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px 12px;
                    background: #d4edda;
                    border: 1px solid #c3e6cb;
                    border-radius: 6px;
                }}
            """)
    
    def _update_validation_status(self):
        """Enhanced validation status with detailed breakdown - FIXED to only require minimum views"""
        #   FIXED: Add safety checks to prevent crashes
        try:
            if not self.dicom_widgets:
                logging.info("  DEBUG: No dicom widgets to validate")
                return
            
            logging.info(f"  DEBUG: Validating {len(self.dicom_widgets)} widgets...")
            
            total_files = len(self.dicom_widgets)
            files_with_both_views = 0
            auto_configured_files = 0
            files_missing_views = []
            
        except Exception as e:
            logging.info(f" ERROR in validation start: {e}")
            return
        
        for i, dicom_widget in enumerate(self.dicom_widgets):
            try:
                logging.info(f"  DEBUG: Validating widget {i+1}/{total_files}...")
                
                #   FIXED: More comprehensive widget validation
                if not dicom_widget:
                    logging.info(f"⚠️ WARNING: Widget {i} is None")
                    continue
                
                #   FIXED: Check if widget is still valid (not deleted)
                if not dicom_widget.isVisible() or dicom_widget.parent() is None:
                    logging.info(f"⚠️ WARNING: Widget {i} is not valid/visible")
                    continue
                    
                #   FIXED: Safe method calls with try-catch
                try:
                    detection_status = dicom_widget.get_detection_status()
                except Exception as status_error:
                    logging.info(f"⚠️ WARNING: Error getting detection status for widget {i}: {status_error}")
                    continue
                    
                if not detection_status:
                    logging.info(f"⚠️ WARNING: No detection status for widget {i}")
                    continue
                
                try:
                    assignments = dicom_widget.get_view_assignments()
                except Exception as assign_error:
                    logging.info(f"⚠️ WARNING: Error getting assignments for widget {i}: {assign_error}")
                    assignments = {}
                    
                if assignments is None:
                    logging.info(f"⚠️ WARNING: No assignments for widget {i}")
                    assignments = {}
                    
                #   FIXED: Safe set creation
                try:
                    views = set(assignments.values()) if assignments else set()
                    has_minimum_views = "Anterior" in views and "Posterior" in views
                except Exception as views_error:
                    logging.info(f"⚠️ WARNING: Error processing views for widget {i}: {views_error}")
                    has_minimum_views = False
                
            except Exception as widget_error:
                logging.info(f" ERROR validating widget {i}: {widget_error}")
                continue
            
            if has_minimum_views:
                files_with_both_views += 1
            else:
                # Track which views are missing for this file
                missing_views = []
                if "Anterior" not in views:
                    missing_views.append("Anterior")
                if "Posterior" not in views:
                    missing_views.append("Posterior")
                files_missing_views.append({
                    'file': dicom_widget.dicom_info.file_path.name,
                    'missing': missing_views
                })
            
            # Track auto-tagged files
            if detection_status["has_reliable_detection"] and not detection_status["needs_manual_config"]:
                auto_configured_files += 1
        
        #   FIXED: Simplified validation logic
        ready_to_process = (files_with_both_views == total_files)
        
        if ready_to_process:
            if auto_configured_files == total_files:
                status_text = f"🎉 All {total_files} files auto-tagged and ready!"
            elif auto_configured_files > 0:
                manual_configured = total_files - auto_configured_files
                status_text = f"🎉 Ready! {auto_configured_files} auto + {manual_configured} manual tagged"
            else:
                status_text = f"🎉 All {total_files} files manually configured and ready!"
            
            self.status_label.setText(status_text)
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
        else:
            #   FIXED: More specific error messages
            files_missing_count = total_files - files_with_both_views
            if files_missing_count == 1:
                missing_file = files_missing_views[0]
                missing_text = " & ".join(missing_file['missing'])
                status_text = f"⚠️ {missing_file['file']} missing {missing_text} view(s)"
            else:
                status_text = f"⚠️ {files_missing_count} files missing required Anterior/Posterior views"
            
            if auto_configured_files > 0:
                status_text += f" • {auto_configured_files} auto-tagged"
            
            self.status_label.setText(status_text)
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
    
    def _confirm_selections(self):
        """Confirm selections and emit signal"""
        logging.info("  DEBUG: Confirming selections...")
        
        # Collect all view assignments
        view_assignments = {}
        background_assignments = {}
        
        for dicom_widget in self.dicom_widgets:
            file_path = dicom_widget.dicom_info.file_path
            assignments = dicom_widget.get_view_assignments()  # Keep original for compatibility
            assignments_with_bg = dicom_widget.get_view_assignments_with_background()
            
            view_assignments[file_path] = assignments
            background_assignments[file_path] = assignments_with_bg
            
            logging.info(f"📄 {file_path.name}: {assignments}")
            logging.info(f"🎨 Background selections: {assignments_with_bg}")
        
        # Final validation
        if not self._validate_assignments(view_assignments):
            logging.info(" Validation failed!")
            return
        
        logging.info("  Validation passed - emitting signal")
        logging.info(f"  DEBUG: About to emit views_confirmed signal with {len(view_assignments)} files")
        
        # Emit signal dengan path sebagai string (lebih aman)
        payload = {str(fp): assign for fp, assign in view_assignments.items()}
        background_payload = {str(fp): assign for fp, assign in background_assignments.items()}
        
        # Create combined payload
        combined_payload = {
            "view_assignments": payload,
            "background_assignments": background_payload
        }
        logging.info("  DEBUG: Emitting views_confirmed signal (string paths)...")
        logging.info("  DEBUG: Emitting views_confirmed signal with background data...")
        self.views_confirmed.emit(combined_payload)
        logging.info("  DEBUG: Signal emitted, closing dialog...")
        
        self.accept()
        logging.info("  DEBUG: Dialog accepted and closed")
    
    def _validate_assignments(self, assignments: dict) -> bool:
        """Enhanced final validation - only need 1 Anterior + 1 Posterior frame minimum"""
        for file_path, frame_assignments in assignments.items():
            if not frame_assignments:
                QMessageBox.warning(
                    self, 
                    "Incomplete Selection",
                    f"No frames selected for:\n{file_path.name}\n\nPlease select at least 1 Anterior and 1 Posterior frame."
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
    
    def _safe_update_validation_status(self):
        """Safe wrapper for validation status update with crash recovery"""
        try:
            self._update_validation_status()
        except Exception as e:
            logging.info(f" ERROR in validation status update: {e}")
            import traceback
            traceback.print_exc()
            
            #   Recovery: Set default state
            try:
                self.ok_btn.setEnabled(False)
                self.status_label.setText("⚠️ Validation error - please retry")
                self.status_label.setStyleSheet(f"""
                    QLabel {{
                        color: #dc3545;
                        font-size: 13px;
                        font-weight: bold;
                        padding: 8px 12px;
                        background: #f8d7da;
                        border: 1px solid #f5c6cb;
                        border-radius: 6px;
                    }}
                """)
            except Exception as recovery_error:
                logging.info(f" Recovery also failed: {recovery_error}")