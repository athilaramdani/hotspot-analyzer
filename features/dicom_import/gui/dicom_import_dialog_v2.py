# features/dicom_import/gui/dicom_import_dialog_v2.py - Updated with view selection workflow
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Dict

from PySide6.QtCore import Signal, QCoreApplication, QTimer, QThread
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QVBoxLayout, QHBoxLayout, QProgressBar, 
    QLabel, QListWidget, QListWidgetItem, QPushButton, QTextEdit,
    QSplitter, QWidget, QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, QSize

from features.dicom_import.logic.input_data import process_files_with_assignments, process_files
from core.gui.ui_constants import (
    DIALOG_IMPORT_BUTTON_STYLE,
    DIALOG_START_BUTTON_STYLE,
    DIALOG_CANCEL_BUTTON_STYLE,
    DIALOG_REMOVE_BUTTON_STYLE,
    DIALOG_TITLE_STYLE,
    DIALOG_SUBTITLE_STYLE,
    DIALOG_PANEL_HEADER_STYLE,
    DIALOG_FILE_LIST_STYLE,
    DIALOG_LOG_STYLE,
    DIALOG_PROGRESS_BAR_STYLE,
    DIALOG_FRAME_STYLE,
    FILE_ITEM_NAME_STYLE,
    FILE_ITEM_PATH_STYLE,
    PRIMARY_BUTTON_STYLE,
    truncate_text,
    Colors
)

# Import the new view selector dialog
from .dicom_view_selector_dialog import DicomViewSelectorDialog

# Import for cloud storage
try:
    from core.config.cloud_storage import sync_spect_data
    CLOUD_AVAILABLE = True
except ImportError:
    CLOUD_AVAILABLE = False

class ProcessingThread(QThread):
    """Thread untuk menjalankan proses import DICOM dengan view assignments"""
    progress_updated = Signal(int, int, str)
    log_updated = Signal(str)
    finished_processing = Signal()
    
    def __init__(self, file_view_assignments: Dict[Path, Dict[int, str]], data_root: Path, session_code: str):
        super().__init__()
        self.file_view_assignments = file_view_assignments
        self.data_root = data_root
        self.session_code = session_code
        
    def run(self):
        try:
            # Process files with view assignments
            process_files_with_assignments(
                file_view_assignments=self.file_view_assignments,
                data_root=self.data_root,
                session_code=self.session_code,
                progress_cb=self._progress_callback,
                log_cb=self._log_callback
            )
            
            self.log_updated.emit("## Processing completed. Original PNG files uploaded to cloud.")
            self.log_updated.emit("## All files processed with proper Anterior/Posterior naming.")
            
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
        self.setWindowTitle("Import DICOM Files - Enhanced Workflow")
        self.setModal(True)
        self.resize(1000, 700)
        
        self.data_root = data_root
        self.session_code = session_code
        self.selected_files: List[Path] = []
        self.view_assignments: Dict[Path, Dict[int, str]] = {}
        self.processing_thread: Optional[ProcessingThread] = None
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup UI components"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(8)
        
        # Title with enhanced workflow info
        title_text = "Import DICOM Files - Enhanced Workflow"
        if self.session_code:
            title_text += f" - Session: {self.session_code}"
        
        title_label = QLabel(title_text)
        title_label.setStyleSheet(DIALOG_TITLE_STYLE)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(title_label)
        
        # Enhanced workflow description
        if self.session_code:
            structure_info = QLabel(f"Files will be saved to: data/SPECT/{self.session_code}/[patient_id]/")
            structure_info.setStyleSheet(DIALOG_SUBTITLE_STYLE)
            structure_info.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(structure_info)
        
        # Workflow info
        workflow_info = QLabel(
            "✅ Enhanced Workflow: Add Files → Select Views → Confirm & Process\n"
            "• System auto-detects Anterior/Posterior views when possible\n" 
            "• Manual selection required when auto-detection fails\n"
            "• All files MUST have both Anterior and Posterior views assigned"
        )
        workflow_info.setStyleSheet(f"""
            QLabel {{
                background: {Colors.LIGHT_GRAY};
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 6px;
                padding: 12px;
                font-size: 11px;
                color: {Colors.DARK_GRAY};
                line-height: 1.4;
            }}
        """)
        main_layout.addWidget(workflow_info)
        
        # Main content area
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(6)
        
        # Left panel - File List
        left_panel = self._create_file_list_panel()
        content_splitter.addWidget(left_panel)
        
        # Right panel - Process Log  
        right_panel = self._create_process_log_panel()
        content_splitter.addWidget(right_panel)
        
        content_splitter.setStretchFactor(0, 2)
        content_splitter.setStretchFactor(1, 3)
        content_splitter.setSizes([300, 450])
        
        main_layout.addWidget(content_splitter, 1)
        
        # Bottom controls
        bottom_layout = self._create_bottom_controls()
        main_layout.addLayout(bottom_layout)
        
    def _create_file_list_panel(self) -> QWidget:
        """Create left panel with file list"""
        panel = QFrame()
        panel.setStyleSheet(DIALOG_FRAME_STYLE)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header_label = QLabel("DICOM Files to Import")
        header_label.setStyleSheet(DIALOG_PANEL_HEADER_STYLE)
        layout.addWidget(header_label)
        
        # File list widget
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(DIALOG_FILE_LIST_STYLE)
        layout.addWidget(self.file_list)
        
        return panel
        
    def _create_process_log_panel(self) -> QWidget:
        """Create right panel with process log"""
        panel = QFrame()
        panel.setStyleSheet(DIALOG_FRAME_STYLE)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header_label = QLabel("Process Log")
        header_label.setStyleSheet(DIALOG_PANEL_HEADER_STYLE)
        layout.addWidget(header_label)
        
        # Process log text area
        self.process_log = QTextEdit()
        self.process_log.setReadOnly(True)
        self.process_log.setStyleSheet(DIALOG_LOG_STYLE)
        
        # Enhanced initial message
        initial_msg = "🚀 Enhanced DICOM Import Workflow Ready\n"
        if self.session_code:
            initial_msg += f"Session: {self.session_code}\n"
            initial_msg += f"Target: data/SPECT/{self.session_code}/[patient_id]/\n"
        
        cloud_status = "✅ Available" if CLOUD_AVAILABLE else "❌ Not available"
        initial_msg += f"Cloud storage: {cloud_status}\n"
        
        if CLOUD_AVAILABLE:
            initial_msg += "Upload: Original PNG files only (*_original.png)\n"
        
        initial_msg += "\nWorkflow Steps:\n"
        initial_msg += "1️⃣ Add DICOM files\n"
        initial_msg += "2️⃣ Configure Anterior/Posterior views\n"
        initial_msg += "3️⃣ Confirm and process\n"
        
        self.process_log.setPlainText(initial_msg)
        layout.addWidget(self.process_log)
        
        return panel
        
    def _create_bottom_controls(self) -> QHBoxLayout:
        """Create bottom control buttons"""
        layout = QHBoxLayout()
        layout.setSpacing(10)
        
        # Add DICOM button
        self.add_dicom_btn = QPushButton("Add DICOM Files")
        self.add_dicom_btn.setStyleSheet(DIALOG_IMPORT_BUTTON_STYLE)
        layout.addWidget(self.add_dicom_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(DIALOG_PROGRESS_BAR_STYLE)
        layout.addWidget(self.progress_bar)
        
        # Progress label
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet(f"color: {Colors.DIALOG_TEXT}; font-size: 12px;")
        layout.addWidget(self.progress_label)
        
        layout.addStretch()
        
        # Configure Views button (new step)
        self.configure_views_btn = QPushButton("Configure Views")
        self.configure_views_btn.setEnabled(False)
        self.configure_views_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        layout.addWidget(self.configure_views_btn)
        
        # Start Import button (updated)
        self.start_import_btn = QPushButton("Start Import")
        self.start_import_btn.setEnabled(False)
        self.start_import_btn.setStyleSheet(DIALOG_START_BUTTON_STYLE)
        layout.addWidget(self.start_import_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(DIALOG_CANCEL_BUTTON_STYLE)
        layout.addWidget(self.cancel_btn)
        
        return layout
        
    def _connect_signals(self):
        """Connect all signals"""
        self.add_dicom_btn.clicked.connect(self._add_dicom_files)
        self.configure_views_btn.clicked.connect(self._configure_views)
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
            self._log_message("Next step: Configure Anterior/Posterior views")
            
    def _add_file_to_list(self, file_path: Path):
        """Add a file to the list widget with status"""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, file_path)
        
        # Create widget untuk item
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # File name label
        file_name = truncate_text(file_path.name, 30)
        file_label = QLabel(file_name)
        file_label.setStyleSheet(FILE_ITEM_NAME_STYLE)
        layout.addWidget(file_label)
        
        # Status label
        status_label = QLabel("⏳ Pending view configuration")
        status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.WARNING};
                font-size: 10px;
                font-style: italic;
            }}
        """)
        layout.addWidget(status_label)
        
        # File path label
        path_text = truncate_text(str(file_path.parent), 35)
        path_label = QLabel(path_text)
        path_label.setStyleSheet(FILE_ITEM_PATH_STYLE)
        layout.addWidget(path_label)
        
        layout.addStretch()
        
        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet(DIALOG_REMOVE_BUTTON_STYLE)
        remove_btn.clicked.connect(lambda: self._remove_file(item))
        layout.addWidget(remove_btn)

        widget.setMinimumHeight(40)
        item.setSizeHint(widget.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, widget)
        
    def _remove_file(self, item: QListWidgetItem):
        """Remove file from list"""
        file_path = item.data(Qt.UserRole)
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            
        # Remove from view assignments too
        if file_path in self.view_assignments:
            del self.view_assignments[file_path]
            
        row = self.file_list.row(item)
        self.file_list.takeItem(row)
        
        self._update_ui_state()
        file_name = truncate_text(file_path.name, 40)
        self._log_message(f"Removed {file_name} from import list")
        
    def _configure_views(self):
        """Open view configuration dialog"""
        if not self.selected_files:
            QMessageBox.warning(self, "Warning", "Please add DICOM files first!")
            return
            
        self._log_message("🔍 Opening view configuration dialog...")
        print(f"🔍 DEBUG: Opening view selector with {len(self.selected_files)} files")
        
        # Open view selector dialog
        view_dialog = DicomViewSelectorDialog(self.selected_files, self)
        
        # ✅ FIXED: Use lambda untuk debugging connection
        def on_views_confirmed_debug(view_assignments):
            print(f"🔍 DEBUG: Signal received! Processing {len(view_assignments)} assignments")
            self._on_views_configured(view_assignments)
        
        print("🔍 DEBUG: Connecting views_confirmed signal...")
        view_dialog.views_confirmed.connect(on_views_confirmed_debug)
        
        print("🔍 DEBUG: Executing dialog...")
        result = view_dialog.exec()
        
        print(f"🔍 DEBUG: View dialog result: {result}")
        print(f"🔍 DEBUG: Dialog accepted = {result == QDialog.Accepted}")
        print(f"🔍 DEBUG: Current view_assignments count: {len(self.view_assignments)}")
        
        if result == QDialog.Rejected:
            self._log_message("❌ View configuration cancelled")
        elif result == QDialog.Accepted:
            print("✅ Dialog accepted")
            # Double check assignments were received
            if len(self.view_assignments) == 0:
                print("❌ WARNING: No assignments received despite dialog acceptance!")
            else:
                print(f"✅ Assignments received: {len(self.view_assignments)} files")
        
        # Force UI refresh after dialog closes
        print("🔍 DEBUG: Final UI state refresh...")
        self._update_ui_state()
        QCoreApplication.processEvents()
        
        
    def _on_views_configured(self, view_assignments: Dict[Path, Dict[int, str]]):
        """Handle confirmed view assignments"""
        print(f"🔍 DEBUG: _on_views_configured called with {len(view_assignments)} assignments")

        # ✅ Normalisasi key agar pasti Path, bukan str
        normalized = {}
        for k, v in view_assignments.items():
            p = Path(k) if not isinstance(k, Path) else k
            normalized[p] = v

        self.view_assignments = normalized
        
        self._log_message("✅ View assignments configured successfully")
        self._log_message(f"Files with view assignments: {len(view_assignments)}")
        
        # ✅ FIXED: Update file list status immediately with detailed debugging
        try:
            print("🔍 DEBUG: Calling _update_file_list_status...")
            self._update_file_list_status()
            print("✅ _update_file_list_status completed")
        except Exception as e:
            print(f"❌ ERROR in _update_file_list_status: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            print("🔍 DEBUG: Calling _update_ui_state...")
            self._update_ui_state()
            print("✅ _update_ui_state completed")
        except Exception as e:
            print(f"❌ ERROR in _update_ui_state: {e}")
            import traceback
            traceback.print_exc()
        
        # Log summary with validation
        for file_path, assignments in self.view_assignments.items():
            views = list(set(assignments.values()))  # Get unique views
            file_name = truncate_text(file_path.name, 30)  # sudah Path karena dinormalisasi
            
            # ✅ FIXED: Validate assignments per file
            has_anterior = "Anterior" in assignments.values()
            has_posterior = "Posterior" in assignments.values()
            
            if has_anterior and has_posterior:
                status = "✅ Complete"
                self._log_message(f"  📄 {file_name}: {', '.join(views)} - {status}")
            else:
                status = "⚠️ Incomplete"  
                self._log_message(f"  📄 {file_name}: {', '.join(views)} - {status}")
        
        # ✅ FIXED: Check if all files are properly configured
        all_complete = all(
            "Anterior" in assignments.values() and "Posterior" in assignments.values()
            for assignments in self.view_assignments.values()
        )
        
        print(f"🔍 DEBUG: All files complete: {all_complete}")
        
        if all_complete:
            self._log_message("🎉 All files have complete view assignments!")
            self._log_message("Ready to start import process!")
        else:
            self._log_message("⚠️ Some files have incomplete assignments")
        
        # Force UI update
        QCoreApplication.processEvents()
        print("✅ _on_views_configured completed")
        
    def _update_file_list_status(self):
        """Update status labels in file list"""
        print(f"🔍 DEBUG: Updating file list status for {len(self.view_assignments)} assignments")
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            widget = self.file_list.itemWidget(item)
            file_path = item.data(Qt.UserRole)
            
            print(f"  Checking file: {file_path.name}")
            
            if widget and file_path in self.view_assignments:
                # ✅ FIXED: Find and update status label properly
                layout = widget.layout()
                
                # Status label should be at index 1
                if layout.count() > 1:
                    status_widget = layout.itemAt(1).widget()
                    if isinstance(status_widget, QLabel):
                        assignments = self.view_assignments[file_path]
                        
                        # Check if file has complete assignments
                        has_anterior = "Anterior" in assignments.values()
                        has_posterior = "Posterior" in assignments.values()
                        
                        print(f"    Assignments: {assignments}")
                        print(f"    Has Anterior: {has_anterior}, Has Posterior: {has_posterior}")
                        
                        if has_anterior and has_posterior:
                            status_widget.setText("✅ Views configured")
                            status_widget.setStyleSheet(f"""
                                QLabel {{
                                    color: {Colors.SUCCESS};
                                    font-size: 10px;
                                    font-style: italic;
                                    font-weight: bold;
                                }}
                            """)
                            print(f"    ✅ Status updated to: Views configured")
                        else:
                            status_widget.setText("⚠️ Incomplete assignment")
                            status_widget.setStyleSheet(f"""
                                QLabel {{
                                    color: {Colors.WARNING};
                                    font-size: 10px;
                                    font-style: italic;
                                    font-weight: bold;
                                }}
                            """)
                            print(f"    ⚠️ Status updated to: Incomplete assignment")
            else:
                if not widget:
                    print(f"    ⚠️ No widget for {file_path.name}")
                elif file_path not in self.view_assignments:
                    key_type = type(next(iter(self.view_assignments.keys()))) if self.view_assignments else None
                    print(f"    ❌ No assignments found for {file_path.name} (check key type; example: {key_type})")
                else:
                    print(f"    ⚠️ Unknown state for {file_path.name}")
            
        # ✅ FIXED: Use repaint() instead of update()
        self.file_list.repaint()
        QCoreApplication.processEvents()
        print("✅ File list status update completed")
        
    def _update_ui_state(self):
        """Update UI state based on files and assignments"""
        has_files = len(self.selected_files) > 0
        has_session = self.session_code is not None
        
        # ✅ FIXED: Check if ALL files have COMPLETE assignments  
        has_complete_assignments = (
            len(self.view_assignments) == len(self.selected_files) and 
            len(self.view_assignments) > 0 and
            all(
                "Anterior" in assignments.values() and "Posterior" in assignments.values()
                for assignments in self.view_assignments.values()
            )
        )
        
        # Update button states
        self.configure_views_btn.setEnabled(has_files)
        self.start_import_btn.setEnabled(has_files and has_complete_assignments and has_session)
        
        # Update tooltips
        if not has_files:
            self.start_import_btn.setToolTip("Add DICOM files first")
        elif not has_complete_assignments:
            self.start_import_btn.setToolTip("Configure complete view assignments first")
        elif not has_session:
            self.start_import_btn.setToolTip("Session code is required")
        else:
            self.start_import_btn.setToolTip("Start processing with configured views")
        
        # ✅ FIXED: Update button text based on state
        if has_complete_assignments:
            self.start_import_btn.setText("🚀 Start Import")
        else:
            self.start_import_btn.setText("Start Import")
        
    def _start_import(self):
        """Start the enhanced import process"""
        if not self.selected_files or not self.view_assignments or not self.session_code:
            QMessageBox.warning(self, "Warning", "Please complete view configuration first!")
            return
        
        # Final validation
        if len(self.view_assignments) != len(self.selected_files):
            QMessageBox.warning(self, "Warning", "Not all files have view assignments!")
            return
            
        self._log_message("🚀 Starting enhanced import process...")
        self._log_message(f"Processing {len(self.selected_files)} files with view assignments")
        self._log_message(f"Session: {self.session_code}")
        self._log_message(f"Target: data/SPECT/{self.session_code}/[patient_id]/")
        self._log_message("Enforced naming: Anterior/Posterior views only")
        
        # Update UI for processing mode
        self.add_dicom_btn.setEnabled(False)
        self.configure_views_btn.setEnabled(False)
        self.start_import_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setValue(0)
        
        # Start processing thread with view assignments
        self.processing_thread = ProcessingThread(
            self.view_assignments,
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
        
        file_name = truncate_text(Path(filename).name, 25)
        self.progress_label.setText(f"Processing: {file_name} ({current}/{total})")
        QCoreApplication.processEvents()
        
    def _on_log_updated(self, message: str):
        """Handle log update"""
        display_message = message
        if len(message) > 100 and not message.startswith("##"):
            display_message = truncate_text(message, 100)
            
        self.process_log.append(display_message)
        self.process_log.ensureCursorVisible()
        QCoreApplication.processEvents()
        
    def _on_processing_finished(self):
        """Handle processing completion"""
        self._log_message("🎉 Enhanced import workflow completed!")
        self._log_message("All files processed with proper Anterior/Posterior naming")
        self._log_message("Rescanning folder...")

        # Emit signal untuk rescan folder
        self.files_imported.emit()

        # Update UI
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.add_dicom_btn.setEnabled(True)
        self.configure_views_btn.setEnabled(True)

        # Success message
        processed_count = len(self.view_assignments)
        QMessageBox.information(
            self,
            "Import Successful",
            f"Successfully processed {processed_count} DICOM files!\n\n"
            "✅ All files have proper Anterior/Posterior view assignments\n"
            "✅ Original PNG files uploaded to cloud storage\n"
            "✅ Complete processing pipeline executed\n\n"
            "Files are now ready for viewing and analysis."
        )
        self.accept()
        
    def _cancel_import(self):
        """Cancel the import process"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.terminate()
            self.processing_thread.wait()
            
        self.reject()
        
    def _log_message(self, message: str):
        """Add message to process log"""
        display_message = truncate_text(message, 120) if len(message) > 120 else message
        self.process_log.append(display_message)
        self.process_log.ensureCursorVisible()
        QCoreApplication.processEvents()


# Legacy compatibility class
class DicomImportDialogLegacy(DicomImportDialog):
    """
    Legacy version without view selection for backward compatibility
    Uses auto-detection only
    """
    
    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        super().__init__(data_root, parent, session_code)
        self.setWindowTitle("Import DICOM Files - Legacy Mode")
        
        # Hide view configuration step
        self.configure_views_btn.setVisible(False)
        self._setup_legacy_mode()
        
    def _setup_legacy_mode(self):
        """Setup for legacy mode without view selection"""
        # Update workflow info
        workflow_info = self.findChild(QLabel)
        if workflow_info:
            workflow_info.setText(
                "⚠️ Legacy Mode: Auto-detection only\n"
                "• System will attempt to auto-detect Anterior/Posterior views\n" 
                "• May fail if DICOM tags are missing or incorrect\n"
                "• Consider using Enhanced Mode for better control"
            )
            workflow_info.setStyleSheet(f"""
                QLabel {{
                    background: {Colors.WARNING};
                    border: 1px solid #ffeeba;
                    border-radius: 6px;
                    padding: 12px;
                    font-size: 11px;
                    color: #856404;
                    line-height: 1.4;
                }}
            """)
    
    def _update_ui_state(self):
        """Override to skip view configuration step"""
        has_files = len(self.selected_files) > 0
        has_session = self.session_code is not None
        
        self.start_import_btn.setEnabled(has_files and has_session)
        
        if has_files and not has_session:
            self.start_import_btn.setToolTip("Session code is required")
        else:
            self.start_import_btn.setToolTip("")
    
    def _start_import(self):
        """Start legacy import with auto-detection"""
        if not self.selected_files or not self.session_code:
            QMessageBox.warning(self, "Warning", "Session code is required for import!")
            return
            
        self._log_message("⚠️ Starting LEGACY import process...")
        self._log_message("Using AUTO-DETECTION for Anterior/Posterior views")
        self._log_message(f"Processing {len(self.selected_files)} file(s)")
        self._log_message("Warning: May fail if DICOM view tags are missing")
        
        # Update UI for processing mode
        self.add_dicom_btn.setEnabled(False)
        self.start_import_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setValue(0)
        
        # Use legacy processing (auto-detection only)
        class LegacyProcessingThread(QThread):
            progress_updated = Signal(int, int, str)
            log_updated = Signal(str)
            finished_processing = Signal()
            
            def __init__(self, file_paths, data_root, session_code):
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
                        log_cb=self._log_callback
                    )
                    self.log_updated.emit("## Legacy processing completed.")
                except Exception as e:
                    self.log_updated.emit(f"[ERROR] Legacy processing failed: {e}")
                finally:
                    self.finished_processing.emit()
                    
            def _progress_callback(self, current: int, total: int, filename: str):
                self.progress_updated.emit(current, total, filename)
            
            def _log_callback(self, msg: str):
                self.log_updated.emit(msg)
        
        self.processing_thread = LegacyProcessingThread(
            self.selected_files,
            self.data_root,
            self.session_code
        )
        self.processing_thread.progress_updated.connect(self._on_progress_updated)
        self.processing_thread.log_updated.connect(self._on_log_updated)
        self.processing_thread.finished_processing.connect(self._on_processing_finished)
        self.processing_thread.start()


# Factory function untuk memilih mode
def create_dicom_import_dialog(
    data_root: Path, 
    parent=None, 
    session_code: str | None = None,
    use_enhanced_mode: bool = True
) -> DicomImportDialog:
    """
    Factory function untuk membuat dialog import
    
    Args:
        data_root: Root data directory
        parent: Parent widget
        session_code: Session code
        use_enhanced_mode: True untuk enhanced mode dengan view selection
        
    Returns:
        DicomImportDialog instance
    """
    if use_enhanced_mode:
        return DicomImportDialog(data_root, parent, session_code)
    else:
        return DicomImportDialogLegacy(data_root, parent, session_code)


# For testing
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Test enhanced mode
    data_root = Path("./test_data")
    session_code = "NSY"
    
    dialog = create_dicom_import_dialog(
        data_root, 
        session_code=session_code,
        use_enhanced_mode=True  # Test enhanced mode
    )
    dialog.show()
    
    sys.exit(app.exec())