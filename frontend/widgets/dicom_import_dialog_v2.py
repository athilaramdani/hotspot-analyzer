from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Signal, QCoreApplication, QTimer, QThread
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QVBoxLayout, QHBoxLayout, QProgressBar, 
    QLabel, QListWidget, QListWidgetItem, QPushButton, QTextEdit,
    QSplitter, QWidget, QFrame, QSizePolicy, QMessageBox   # <-- ditambah
)

from PySide6.QtCore import Qt, QSize

from backend.input_data import process_files


class ProcessingThread(QThread):
    """Thread untuk menjalankan proses import DICOM di background"""
    progress_updated = Signal(int, int, str)
    log_updated = Signal(str)
    finished_processing = Signal()
    
    def __init__(self, file_paths: List[Path], data_root: Path, session_code: str):
        super().__init__()
        self.file_paths = file_paths
        self.data_root = data_root
        self.session_code = session_code
        
    def run(self):
        try:
            process_files(
                paths=self.file_paths,
                data_root=self.data_root,
                session_code=self.session_code,
                progress_cb=self._progress_callback,
                log_cb=self._log_callback        # kirim log via callback
            )
        except Exception as e:
            self.log_updated.emit(f"[ERROR] Processing failed: {e}")
        finally:
            self.finished_processing.emit()
    
    def _progress_callback(self, current: int, total: int, filename: str):
        """Callback untuk update progress"""
        self.progress_updated.emit(current, total, filename)
    
            
    def _log_callback(self, msg: str):
        self.log_updated.emit(msg)


class DicomImportDialog(QDialog):
    files_imported = Signal()
    
    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Import DICOM Files")
        self.setModal(True)
        self.resize(1000, 700)
        
        self.data_root = data_root
        self.session_code = session_code
        self.selected_files: List[Path] = []
        self.processing_thread: Optional[ProcessingThread] = None
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup UI components"""
        main_layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Import DICOM Files")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        title_label.setAlignment(Qt.AlignCenter)                               # baru
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)    # baru
        main_layout.addWidget(title_label)
        
        # Main content area dengan splitter
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - File List
        left_panel = self._create_file_list_panel()
        content_splitter.addWidget(left_panel)
        
        # Right panel - Process Log
        right_panel = self._create_process_log_panel()
        content_splitter.addWidget(right_panel)
        
        # Set splitter proportions
        content_splitter.setStretchFactor(0, 1)  # File list
        content_splitter.setStretchFactor(1, 2)  # Process log (lebih besar)
        
        main_layout.addWidget(content_splitter)
        
        # Bottom controls
        bottom_layout = self._create_bottom_controls()
        main_layout.addLayout(bottom_layout)
        
    def _create_file_list_panel(self) -> QWidget:
        """Create left panel with file list"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Box)
        layout = QVBoxLayout(panel)
        
        # Header
        header_label = QLabel("Files to Import")
        header_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(header_label)
        
        # File list widget
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        layout.addWidget(self.file_list)
        
        return panel
        
    def _create_process_log_panel(self) -> QWidget:
        """Create right panel with process log"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Box)
        layout = QVBoxLayout(panel)
        
        # Header
        header_label = QLabel("Process Log")
        header_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(header_label)
        
        # Process log text area
        self.process_log = QTextEdit()
        self.process_log.setReadOnly(True)
        self.process_log.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        self.process_log.setPlainText("Ready to import DICOM files...\n")
        layout.addWidget(self.process_log)
        
        return panel
        
    def _create_bottom_controls(self) -> QHBoxLayout:
        """Create bottom control buttons and progress bar"""
        layout = QHBoxLayout()
        
        # Add DICOM button
        self.add_dicom_btn = QPushButton("Add DICOM Files")
        self.add_dicom_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        layout.addWidget(self.add_dicom_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Progress label
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        
        layout.addStretch()
        
        # Start Import button
        self.start_import_btn = QPushButton("Start Import")
        self.start_import_btn.setEnabled(False)
        self.start_import_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background-color: #45a049;
            }
            QPushButton:pressed:enabled {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        layout.addWidget(self.start_import_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """)
        layout.addWidget(self.cancel_btn)
        
        return layout
        
    def _connect_signals(self):
        """Connect all signals"""
        self.add_dicom_btn.clicked.connect(self._add_dicom_files)
        self.start_import_btn.clicked.connect(self._start_import)
        self.cancel_btn.clicked.connect(self._cancel_import)
        
    def _add_dicom_files(self):
        """Add DICOM files to the list"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select DICOM Files", 
            "", 
            "DICOM Files (*.dcm);;All Files (*)"
        )
        
        if file_paths:
            for file_path in file_paths:
                path = Path(file_path)
                if path not in self.selected_files:
                    self.selected_files.append(path)
                    self._add_file_to_list(path)
            
            self._update_ui_state()
            self._log_message(f"Added {len(file_paths)} file(s) to import list")
            
    def _add_file_to_list(self, file_path: Path):
        """Add a file to the list widget with remove button"""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, file_path)
        
        # Create widget untuk item
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # File name label
        file_label = QLabel(file_path.name)
        file_label.setStyleSheet("color: #333; font-weight: bold;")
        layout.addWidget(file_label)
        
        # File path label
        path_label = QLabel(str(file_path.parent))
        path_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(path_label)
        
        layout.addStretch()
        
        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        # Remove button
        remove_btn.clicked.connect(lambda: self._remove_file(item))
        layout.addWidget(remove_btn)

        # ---- tambahkan perbaikan tinggi baris ----
        widget.setMinimumHeight(36)   # atur tinggi minimal (boleh 36 kalau mau lebih besar)
        widget.adjustSize()           # pastikan sizeHint akurat
        # -----------------------------------------

        item.setSizeHint(widget.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, widget)
        
    def _remove_file(self, item: QListWidgetItem):
        """Remove file from list"""
        file_path = item.data(Qt.UserRole)
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            
        row = self.file_list.row(item)
        self.file_list.takeItem(row)
        
        self._update_ui_state()
        self._log_message(f"Removed {file_path.name} from import list")
        
    def _update_ui_state(self):
        """Update UI state based on selected files"""
        has_files = len(self.selected_files) > 0
        self.start_import_btn.setEnabled(has_files)
        
    def _start_import(self):
        """Start the import process"""
        if not self.selected_files:
            return
            
        self._log_message("## Starting batch import process...")
        self._log_message(f"## Processing {len(self.selected_files)} file(s)")
        
        # Update UI untuk mode processing
        self.add_dicom_btn.setEnabled(False)
        self.start_import_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setValue(0)
        
        # Start processing thread
        self.processing_thread = ProcessingThread(
            self.selected_files, 
            self.data_root, 
            self.session_code
        )
        self.processing_thread.progress_updated.connect(self._on_progress_updated)
        self.processing_thread.log_updated.connect(self._on_log_updated)
        self.processing_thread.finished_processing.connect(self._on_processing_finished)
        self.processing_thread.start()
        
    def _on_progress_updated(self, current: int, total: int, filename: str):
        """Handle progress update"""
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Processing: {Path(filename).name} ({current}/{total})")
        QCoreApplication.processEvents()
        
    def _on_log_updated(self, message: str):
        """Handle log update"""
        self.process_log.append(message)
        self.process_log.ensureCursorVisible()
        QCoreApplication.processEvents()
        
    def _on_processing_finished(self):
        """Handle processing completion"""
        self._log_message("## Batch import finished!")
        self._log_message("## Rescanning folder...")

        # Emit signal untuk rescan folder
        self.files_imported.emit()

        # Update UI
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.add_dicom_btn.setEnabled(True)

        # --- popup sukses ---
        QMessageBox.information(
            self,
            "Import Successful",
            "All selected DICOM files have been imported successfully."
        )
        # Tutup dialog utama setelah user menekan OK
        self.accept()
        
    def _cancel_import(self):
        """Cancel the import process"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.terminate()
            self.processing_thread.wait()
            
        self.reject()
        
    def _log_message(self, message: str):
        """Add message to process log"""
        self.process_log.append(message)
        self.process_log.ensureCursorVisible()
        QCoreApplication.processEvents()


# Untuk testing
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Test data
    data_root = Path("./test_data")
    session_code = "TEST"
    
    dialog = DicomImportDialog(data_root, session_code=session_code)
    dialog.show()
    
    sys.exit(app.exec())