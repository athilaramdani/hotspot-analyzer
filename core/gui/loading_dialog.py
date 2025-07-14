# core/gui/loading_dialog.py
"""
Loading dialog untuk menampilkan progress saat loading data
"""
from typing import Optional
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QFrame
)
from PySide6.QtGui import QFont, QMovie, QPixmap
import os


class LoadingDialog(QDialog):
    """Dialog untuk menampilkan loading progress"""
    
    # Signal untuk cancel loading
    cancel_requested = Signal()
    
    def __init__(self, title: str = "Loading", message: str = "Please wait...", 
                 show_progress: bool = True, show_cancel: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.resize(400, 150)
        
        self.show_progress = show_progress
        self.show_cancel = show_cancel
        self._cancelled = False
        
        self._create_ui()
        self._setup_styling()
        self.set_message(message)
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Loading icon/animation area
        icon_layout = QHBoxLayout()
        icon_layout.addStretch()
        
        # Simple loading label (you can replace with animated GIF later)
        self.loading_icon = QLabel("⟳")
        self.loading_icon.setAlignment(Qt.AlignCenter)
        self.loading_icon.setStyleSheet("""
            QLabel {
                font-size: 24px;
                color: #2196F3;
                background-color: rgba(33, 150, 243, 0.1);
                border-radius: 25px;
                width: 50px;
                height: 50px;
            }
        """)
        self.loading_icon.setFixedSize(50, 50)
        icon_layout.addWidget(self.loading_icon)
        icon_layout.addStretch()
        
        layout.addLayout(icon_layout)
        
        # Message label
        self.message_label = QLabel()
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #333333;
                margin: 5px;
            }
        """)
        layout.addWidget(self.message_label)
        
        # Progress bar (optional)
        if self.show_progress:
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #CCCCCC;
                    border-radius: 5px;
                    text-align: center;
                    font-weight: bold;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: #2196F3;
                    border-radius: 3px;
                }
            """)
            layout.addWidget(self.progress_bar)
        
        # Cancel button (optional)
        if self.show_cancel:
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            self.cancel_button = QPushButton("Cancel")
            self.cancel_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                }
            """)
            self.cancel_button.clicked.connect(self._on_cancel)
            button_layout.addWidget(self.cancel_button)
            button_layout.addStretch()
            
            layout.addLayout(button_layout)
        
        # Animation timer for loading icon
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_loading_icon)
        self.animation_timer.start(200)  # Rotate every 200ms
        self._rotation_angle = 0
    
    def _setup_styling(self):
        """Setup dialog styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border: 2px solid #CCCCCC;
                border-radius: 8px;
            }
        """)
    
    def _animate_loading_icon(self):
        """Animate the loading icon"""
        self._rotation_angle += 45
        if self._rotation_angle >= 360:
            self._rotation_angle = 0
        
        # Simple text animation (can be improved with actual rotation)
        animations = ["⟳", "⟲", "⟳", "⟲"]
        current = (self._rotation_angle // 90) % len(animations)
        self.loading_icon.setText(animations[current])
    
    def set_message(self, message: str):
        """Update loading message"""
        self.message_label.setText(message)
    
    def set_progress(self, value: int):
        """Update progress bar value (0-100)"""
        if self.show_progress and hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(value)
    
    def _on_cancel(self):
        """Handle cancel button click"""
        self._cancelled = True
        self.cancel_requested.emit()
        self.reject()
    
    def is_cancelled(self) -> bool:
        """Check if loading was cancelled"""
        return self._cancelled
    
    def closeEvent(self, event):
        """Handle dialog close"""
        self.animation_timer.stop()
        super().closeEvent(event)


class SPECTLoadingDialog(LoadingDialog):
    """Specialized loading dialog for SPECT data loading"""
    
    def __init__(self, patient_id: str, parent=None):
        super().__init__(
            title="Loading SPECT Data",
            message=f"Loading SPECT data for patient {patient_id}...",
            show_progress=True,
            show_cancel=True,
            parent=parent
        )
        self.patient_id = patient_id
    
    def update_loading_step(self, step: str, progress: int = None):
        """Update loading step and progress"""
        self.set_message(f"Loading SPECT data for patient {self.patient_id}\n{step}")
        if progress is not None:
            self.set_progress(progress)


class PETLoadingDialog(LoadingDialog):
    """Specialized loading dialog for PET data loading"""
    
    def __init__(self, patient_id: str, parent=None):
        super().__init__(
            title="Loading PET Data",
            message=f"Loading PET data for patient {patient_id}...",
            show_progress=True,
            show_cancel=True,
            parent=parent
        )
        self.patient_id = patient_id
    
    def update_loading_step(self, step: str, progress: int = None):
        """Update loading step and progress"""
        self.set_message(f"Loading PET data for patient {self.patient_id}\n{step}")
        if progress is not None:
            self.set_progress(progress)


# Convenience functions for quick usage
def show_loading_dialog(parent=None, title: str = "Loading", message: str = "Please wait...") -> LoadingDialog:
    """Show a simple loading dialog"""
    dialog = LoadingDialog(title, message, show_progress=False, show_cancel=False, parent=parent)
    dialog.show()
    return dialog


def show_spect_loading_dialog(patient_id: str, parent=None) -> SPECTLoadingDialog:
    """Show SPECT loading dialog"""
    dialog = SPECTLoadingDialog(patient_id, parent)
    dialog.show()
    return dialog


def show_pet_loading_dialog(patient_id: str, parent=None) -> PETLoadingDialog:
    """Show PET loading dialog"""
    dialog = PETLoadingDialog(patient_id, parent)
    dialog.show()
    return dialog