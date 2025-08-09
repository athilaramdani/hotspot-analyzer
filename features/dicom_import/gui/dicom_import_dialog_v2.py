# features/dicom_import/gui/dicom_import_dialog_v2.py - CLEAN FINAL VERSION
"""
Enhanced DICOM Import Dialog dengan improved auto-configuration status handling.

FIXES:
1. Proper status display for auto-configured vs manual configuration required
2. Immediate status update based on detection confidence
3. Enhanced workflow with better user feedback
"""
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
from features.dicom_import.logic.dicom_loader import load_frames_and_metadata, _extract_labels_enhanced
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

# Import the enhanced view selector dialog
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


class QuickDetectionThread(QThread):
    """Thread untuk quick detection check tanpa loading full UI"""
    detection_completed = Signal(Path, dict)  # file_path, detection_info
    
    def __init__(self, file_paths: List[Path]):
        super().__init__()
        self.file_paths = file_paths
    
    def run(self):
        for file_path in self.file_paths:
            try:
                detection_info = self._quick_detection_check(file_path)
                self.detection_completed.emit(file_path, detection_info)
            except Exception as e:
                print(f"Quick detection failed for {file_path}: {e}")
                # Emit default info on error
                self.detection_completed.emit(file_path, {
                    "has_reliable_detection": False,
                    "needs_manual_config": True,
                    "auto_configured_count": 0,
                    "manual_required_count": 1,
                    "total_frames": 1,
                    "error": str(e)
                })
    
    def _quick_detection_check(self, file_path: Path) -> dict:
        """Quick detection check untuk immediate status display"""
        frames_dict, metadata = load_frames_and_metadata(str(file_path))
        
        reliable_detections = 0
        total_frames = len(frames_dict)
        
        for view_name, frame_data in frames_dict.items():
            detected_view, confidence = self._enhanced_view_detection_with_confidence(view_name)
            if confidence == "high" and detected_view in ["Anterior", "Posterior"]:
                reliable_detections += 1
        
        has_reliable_detection = reliable_detections >= 2
        needs_manual_config = reliable_detections < total_frames
        
        return {
            "has_reliable_detection": has_reliable_detection,
            "needs_manual_config": needs_manual_config,
            "auto_configured_count": reliable_detections,
            "manual_required_count": total_frames - reliable_detections,
            "total_frames": total_frames,
            "patient_id": metadata.get("patient_id", "Unknown")
        }
    
    def _enhanced_view_detection_with_confidence(self, view_name: str) -> tuple:
        """Same detection logic as view selector"""
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
        self.file_detection_status: Dict[Path, dict] = {}  # Store detection status per file
        self.processing_thread: Optional[ProcessingThread] = None
        self.quick_detection_thread: Optional[QuickDetectionThread] = None
        
        # ✅ FIXED: Add dialog reference tracking
        self._view_dialog: Optional[DicomViewSelectorDialog] = None
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup UI components"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(8)
        
        # Title with enhanced workflow info
        title_text = "Import DICOM Files - Enhanced Auto-Detection Workflow"
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
        
        # Enhanced workflow info
        workflow_info = QLabel(
            "✅ Enhanced Auto-Detection Workflow:\n"
            "• Add Files → System instantly analyzes DICOM tags for view detection\n" 
            "• ✅ Auto-configured: High confidence detection from clear DICOM tags\n"
            "• ⚠️ Manual required: Low/no confidence detection, needs user verification\n"
            "• Configure Views → Manual adjustment if needed → Confirm & Process"
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
        
        initial_msg += "\nAuto-Detection Features:\n"
        initial_msg += "• ✅ High confidence: Clear DICOM tags (auto-configured)\n"
        initial_msg += "• ⚠️ Low confidence: Partial tags (manual verification)\n"
        initial_msg += "• ❌ No detection: Missing tags (manual selection)\n"
        initial_msg += "\nWorkflow Steps:\n"
        initial_msg += "1️⃣ Add DICOM files (instant analysis)\n"
        initial_msg += "2️⃣ Configure views (if needed)\n"
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
        
        # Configure Views button
        self.configure_views_btn = QPushButton("Configure Views")
        self.configure_views_btn.setEnabled(False)
        self.configure_views_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        layout.addWidget(self.configure_views_btn)
        
        # Start Import button
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
        """Add DICOM files to the list dengan instant detection analysis"""
        # ✅ FIXED: Close any open view dialog first
        if hasattr(self, '_view_dialog') and self._view_dialog:
            print("🔍 DEBUG: Closing existing view dialog before adding files...")
            try:
                self._view_dialog.close()
            except:
                pass
            self._view_dialog = None
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select DICOM Files", 
            "", 
            "DICOM Files (*.dcm);;All Files (*)"
        )
        
        if file_paths:
            # ✅ FIXED: Clear existing view assignments if adding to existing list
            if self.selected_files and self.view_assignments:
                print("🔍 DEBUG: Clearing existing view assignments due to file list change...")
                self.view_assignments.clear()
                self._log_message("⚠️ View assignments cleared - files list changed")
            
            new_files = []
            for file_path in file_paths:
                path = Path(file_path)
                if path not in self.selected_files:
                    self.selected_files.append(path)
                    new_files.append(path)
                    self._add_file_to_list(path)
            
            # ✅ FIXED: Reset detection status for consistency
            if new_files:
                print(f"🔍 DEBUG: Added {len(new_files)} new files to existing {len(self.selected_files) - len(new_files)} files")
                # Clear detection status that might be inconsistent
                for existing_file in list(self.file_detection_status.keys()):
                    if existing_file not in self.selected_files:
                        del self.file_detection_status[existing_file]
            
            self._update_ui_state()
            self._log_message(f"Added {len(new_files)} new file(s) to import list")
            self._log_message("🔍 Starting instant view detection analysis...")
            
            # Start quick detection for immediate status update
            if new_files:
                self._start_quick_detection(new_files)
    
    def _start_quick_detection(self, file_paths: List[Path]):
        """Start quick detection analysis untuk immediate feedback"""
        # ✅ FIXED: More thorough thread cleanup
        if hasattr(self, 'quick_detection_thread') and self.quick_detection_thread:
            if self.quick_detection_thread.isRunning():
                print("🔍 DEBUG: Terminating existing quick detection thread...")
                self.quick_detection_thread.terminate()
                self.quick_detection_thread.wait(2000)  # Wait max 2 seconds
                if self.quick_detection_thread.isRunning():
                    print("⚠️ WARNING: Thread did not terminate, forcing...")
            
            # Disconnect old signals
            try:
                self.quick_detection_thread.detection_completed.disconnect()
                self.quick_detection_thread.finished.disconnect()
            except:
                pass
            
            self.quick_detection_thread = None
        
        print(f"🔍 DEBUG: Starting quick detection for {len(file_paths)} files...")
        
        try:
            self.quick_detection_thread = QuickDetectionThread(file_paths)
            self.quick_detection_thread.detection_completed.connect(self._on_quick_detection_completed)
            self.quick_detection_thread.finished.connect(self._on_quick_detection_finished)
            self.quick_detection_thread.start()
        except Exception as e:
            print(f"❌ ERROR starting quick detection: {e}")
            self._log_message(f"❌ Error starting file analysis: {str(e)}")
        
    def _on_quick_detection_completed(self, file_path: Path, detection_info: dict):
        """Handle completed quick detection for single file"""
        # ✅ FIXED: Check if file still exists in selected files
        if file_path not in self.selected_files:
            print(f"⚠️ WARNING: File {file_path.name} no longer in selected files, skipping detection update")
            return
        
        # ✅ FIXED: Prevent duplicate detection processing
        if file_path in self.file_detection_status:
            existing_info = self.file_detection_status[file_path]
            if existing_info.get("total_frames") == detection_info.get("total_frames"):
                print(f"🔍 DEBUG: Detection for {file_path.name} already exists and unchanged, skipping...")
                return
        
        print(f"🔍 DEBUG: Processing detection result for {file_path.name}")
        self.file_detection_status[file_path] = detection_info
        
        # Update file status immediately
        try:
            self._update_single_file_status(file_path, detection_info)
        except Exception as e:
            print(f"❌ ERROR updating file status for {file_path.name}: {e}")
        
        # Log detection result
        patient_id = detection_info.get("patient_id", "Unknown")
        auto_count = detection_info.get("auto_configured_count", 0)
        manual_count = detection_info.get("manual_required_count", 0)
        
        if detection_info.get("has_reliable_detection", False):
            if not detection_info.get("needs_manual_config", True):
                self._log_message(f"✅ {truncate_text(file_path.name, 30)}: Fully auto-configured ({auto_count} frames)")
            else:
                self._log_message(f"⚠️ {truncate_text(file_path.name, 30)}: Partially auto-configured ({auto_count} auto, {manual_count} manual)")
        else:
            self._log_message(f"❌ {truncate_text(file_path.name, 30)}: Manual configuration required ({manual_count} frames)")
    
    def _on_quick_detection_finished(self):
        """Handle completion of all quick detections"""
        self._update_ui_state()
        
        # Summary of detection results
        total_files = len(self.file_detection_status)
        fully_auto = sum(1 for info in self.file_detection_status.values() 
                        if info.get("has_reliable_detection", False) and not info.get("needs_manual_config", True))
        partially_auto = sum(1 for info in self.file_detection_status.values() 
                           if info.get("has_reliable_detection", False) and info.get("needs_manual_config", True))
        manual_only = total_files - fully_auto - partially_auto
        
        self._log_message("📊 Detection Analysis Complete:")
        if fully_auto > 0:
            self._log_message(f"   ✅ {fully_auto} files fully auto-configured")
        if partially_auto > 0:
            self._log_message(f"   ⚠️ {partially_auto} files partially auto-configured")
        if manual_only > 0:
            self._log_message(f"   ❌ {manual_only} files need manual configuration")
        
        if fully_auto == total_files:
            self._log_message("🎉 All files auto-configured! You can proceed directly to import.")
        elif manual_only == 0:
            self._log_message("⚠️ Some files need verification. Please review in Configure Views.")
        else:
            self._log_message("⚙️ Manual configuration required for some files.")
        
        self._log_message("Next step: Configure Views (or proceed if all auto-configured)")
    
    def _update_single_file_status(self, file_path: Path, detection_info: dict):
        """Update status for single file in the list"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            widget = self.file_list.itemWidget(item)
            if item.data(Qt.UserRole) == file_path and widget:
                layout = widget.layout()
                
                # Update status label (should be at index 1)
                if layout.count() > 1:
                    status_widget = layout.itemAt(1).widget()
                    if isinstance(status_widget, QLabel):
                        if detection_info.get("has_reliable_detection", False):
                            if not detection_info.get("needs_manual_config", True):
                                status_widget.setText("✅ Auto-configured")
                                status_widget.setStyleSheet(f"""
                                    QLabel {{
                                        color: {Colors.SUCCESS};
                                        font-size: 10px;
                                        font-style: italic;
                                        font-weight: bold;
                                    }}
                                """)
                            else:
                                auto_count = detection_info.get("auto_configured_count", 0)
                                manual_count = detection_info.get("manual_required_count", 0)
                                status_widget.setText(f"⚠️ Partial auto ({auto_count}/{auto_count + manual_count})")
                                status_widget.setStyleSheet(f"""
                                    QLabel {{
                                        color: {Colors.WARNING};
                                        font-size: 10px;
                                        font-style: italic;
                                        font-weight: bold;
                                    }}
                                """)
                        else:
                            status_widget.setText("❌ Manual config required")
                            status_widget.setStyleSheet(f"""
                                QLabel {{
                                    color: #dc3545;
                                    font-size: 10px;
                                    font-style: italic;
                                    font-weight: bold;
                                }}
                            """)
                
                # Force widget repaint
                widget.repaint()
                break
        
        # Force list widget update
        self.file_list.repaint()
        QCoreApplication.processEvents()
        
    def _add_file_to_list(self, file_path: Path):
        """Add a file to the list widget with initial status"""
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
        
        # Status label (will be updated by quick detection)
        status_label = QLabel("🔍 Analyzing...")
        status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.SECONDARY};
                font-size: 10px;
                font-style: italic;
                font-weight: bold;
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
            
        # Remove from view assignments and detection status
        if file_path in self.view_assignments:
            del self.view_assignments[file_path]
        if file_path in self.file_detection_status:
            del self.file_detection_status[file_path]
            
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
        
        # ✅ FIXED: Check if dialog is already open
        if hasattr(self, '_view_dialog') and self._view_dialog:
            print("⚠️ WARNING: View dialog already open, bringing to front...")
            self._view_dialog.raise_()
            self._view_dialog.activateWindow()
            return
        
        # ✅ FIXED: Validate that all files have detection status
        missing_detection = []
        for file_path in self.selected_files:
            if file_path not in self.file_detection_status:
                missing_detection.append(file_path)
        
        if missing_detection:
            print(f"⚠️ WARNING: {len(missing_detection)} files missing detection status, starting analysis...")
            self._log_message(f"⚠️ Analyzing {len(missing_detection)} files without detection status...")
            
            # Start detection for missing files
            self._start_quick_detection(missing_detection)
            
            # Show message and return
            QMessageBox.information(
                self,
                "Analysis in Progress", 
                f"Please wait for analysis to complete for {len(missing_detection)} files, then try again."
            )
            return
            
        self._log_message("🔍 Opening enhanced view configuration dialog...")
        print(f"🔍 DEBUG: Opening view selector with {len(self.selected_files)} files")
        
        # ✅ FIXED: Create dialog and store reference
        try:
            self._view_dialog = DicomViewSelectorDialog(self.selected_files, self)
            
            def on_views_confirmed_debug(view_assignments):
                print(f"🔍 DEBUG: Signal received! Processing {len(view_assignments)} assignments")
                self._on_views_configured(view_assignments)
                # ✅ FIXED: Clear dialog reference after use
                self._view_dialog = None
            
            def on_dialog_finished():
                print("🔍 DEBUG: Dialog finished, cleaning up...")
                # ✅ FIXED: Clear dialog reference when closed
                self._view_dialog = None
                self._update_ui_state()
                QCoreApplication.processEvents()
            
            print("🔍 DEBUG: Connecting signals...")
            self._view_dialog.views_confirmed.connect(on_views_confirmed_debug)
            self._view_dialog.finished.connect(on_dialog_finished)
            
            print("🔍 DEBUG: Executing dialog...")
            result = self._view_dialog.exec()
            
            print(f"🔍 DEBUG: View dialog result: {result}")
            if result == QDialog.Rejected:
                self._log_message("❌ View configuration cancelled")
            elif result == QDialog.Accepted:
                print("✅ Dialog accepted")
            
        except Exception as e:
            print(f"❌ ERROR creating view dialog: {e}")
            import traceback
            traceback.print_exc()
            self._log_message(f"❌ Error opening view configuration: {str(e)}")
            
            # ✅ FIXED: Clear dialog reference on error
            self._view_dialog = None
        
        # ✅ FIXED: Force cleanup and UI refresh
        self._view_dialog = None
        self._update_ui_state()
        QCoreApplication.processEvents()
        
    def _on_views_configured(self, view_assignments: Dict[Path, Dict[int, str]]):
        """Handle confirmed view assignments"""
        print(f"🔍 DEBUG: _on_views_configured called with {len(view_assignments)} assignments")

        # Normalize key agar pasti Path, bukan str
        normalized = {}
        for k, v in view_assignments.items():
            p = Path(k) if not isinstance(k, Path) else k
            normalized[p] = v

        self.view_assignments = normalized
        
        self._log_message("✅ View assignments configured successfully")
        self._log_message(f"Files with view assignments: {len(view_assignments)}")
        
        # Update file list status with confirmed assignments
        try:
            self._update_file_list_with_assignments()
        except Exception as e:
            print(f"❌ ERROR in _update_file_list_with_assignments: {e}")
        
        try:
            self._update_ui_state()
        except Exception as e:
            print(f"❌ ERROR in _update_ui_state: {e}")
        
        # Log summary with validation
        auto_configured_count = 0
        manually_configured_count = 0
        
        for file_path, assignments in self.view_assignments.items():
            views = list(set(assignments.values()))
            file_name = truncate_text(file_path.name, 30)
            
            # Check if this was auto-configured or manually configured
            detection_info = self.file_detection_status.get(file_path, {})
            was_auto_configured = detection_info.get("has_reliable_detection", False)
            
            # Validate assignments per file
            has_anterior = "Anterior" in assignments.values()
            has_posterior = "Posterior" in assignments.values()
            
            if has_anterior and has_posterior:
                if was_auto_configured:
                    status = "✅ Auto-configured"
                    auto_configured_count += 1
                else:
                    status = "⚙️ Manually configured"
                    manually_configured_count += 1
                self._log_message(f"  📄 {file_name}: {', '.join(views)} - {status}")
            else:
                status = "⚠️ Incomplete"
                self._log_message(f"  📄 {file_name}: {', '.join(views)} - {status}")
        
        # Final summary
        total_configured = auto_configured_count + manually_configured_count
        if total_configured == len(self.view_assignments):
            self._log_message(f"🎉 All {total_configured} files configured!")
            if auto_configured_count > 0 and manually_configured_count > 0:
                self._log_message(f"   {auto_configured_count} auto + {manually_configured_count} manual")
            elif auto_configured_count == total_configured:
                self._log_message(f"   All {auto_configured_count} files auto-configured")
            else:
                self._log_message(f"   All {manually_configured_count} files manually configured")
            self._log_message("Ready to start import process!")
        else:
            self._log_message("⚠️ Some files have incomplete assignments")
        
        # Force UI update
        QCoreApplication.processEvents()
        
    def _update_file_list_with_assignments(self):
        """Update file list status based on final assignments"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            widget = self.file_list.itemWidget(item)
            file_path = item.data(Qt.UserRole)
            
            if widget and file_path in self.view_assignments:
                layout = widget.layout()
                
                # Status label should be at index 1
                if layout.count() > 1:
                    status_widget = layout.itemAt(1).widget()
                    if isinstance(status_widget, QLabel):
                        assignments = self.view_assignments[file_path]
                        
                        # Check if file has complete assignments
                        has_anterior = "Anterior" in assignments.values()
                        has_posterior = "Posterior" in assignments.values()
                        
                        # Check if this was originally auto-configured
                        detection_info = self.file_detection_status.get(file_path, {})
                        was_auto_configured = detection_info.get("has_reliable_detection", False) and not detection_info.get("needs_manual_config", True)
                        
                        if has_anterior and has_posterior:
                            if was_auto_configured:
                                status_widget.setText("✅ Auto-configured")
                                status_widget.setStyleSheet(f"""
                                    QLabel {{
                                        color: {Colors.SUCCESS};
                                        font-size: 10px;
                                        font-style: italic;
                                        font-weight: bold;
                                    }}
                                """)
                            else:
                                status_widget.setText("⚙️ Manually configured")
                                status_widget.setStyleSheet(f"""
                                    QLabel {{
                                        color: {Colors.PRIMARY};
                                        font-size: 10px;
                                        font-style: italic;
                                        font-weight: bold;
                                    }}
                                """)
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
        
        # Force UI update
        self.file_list.repaint()
        QCoreApplication.processEvents()
        
    def _update_ui_state(self):
        """Update UI state based on files, detection status, and assignments"""
        has_files = len(self.selected_files) > 0
        has_session = self.session_code is not None
        
        # Check if ALL files have COMPLETE assignments  
        has_complete_assignments = (
            len(self.view_assignments) == len(self.selected_files) and 
            len(self.view_assignments) > 0 and
            all(
                "Anterior" in assignments.values() and "Posterior" in assignments.values()
                for assignments in self.view_assignments.values()
            )
        )
        
        # Check detection status for button text updates
        auto_configured_files = 0
        manual_required_files = 0
        
        for file_path in self.selected_files:
            detection_info = self.file_detection_status.get(file_path, {})
            if detection_info.get("has_reliable_detection", False) and not detection_info.get("needs_manual_config", True):
                auto_configured_files += 1
            elif detection_info.get("needs_manual_config", True):
                manual_required_files += 1
        
        # Update button states
        self.configure_views_btn.setEnabled(has_files)
        self.start_import_btn.setEnabled(has_files and has_complete_assignments and has_session)
        
        # Enhanced button text and tooltips based on detection status
        if has_files:
            if auto_configured_files == len(self.selected_files):
                self.configure_views_btn.setText("✅ Review Auto-Config")
                self.configure_views_btn.setToolTip("All files auto-configured. Click to review and confirm.")
            elif manual_required_files == len(self.selected_files):
                self.configure_views_btn.setText("⚙️ Configure Views")
                self.configure_views_btn.setToolTip("Manual configuration required for all files.")
            else:
                self.configure_views_btn.setText("⚠️ Review & Configure")
                self.configure_views_btn.setToolTip(f"{auto_configured_files} auto-configured, {manual_required_files} need manual config.")
        else:
            self.configure_views_btn.setText("Configure Views")
            self.configure_views_btn.setToolTip("Add DICOM files first")
        
        # Update start button
        if not has_files:
            self.start_import_btn.setToolTip("Add DICOM files first")
        elif not has_complete_assignments:
            self.start_import_btn.setToolTip("Configure complete view assignments first")
        elif not has_session:
            self.start_import_btn.setToolTip("Session code is required")
        else:
            self.start_import_btn.setToolTip("Start processing with configured views")
        
        # Enhanced start button text
        if has_complete_assignments:
            auto_count = sum(1 for fp in self.view_assignments.keys() 
                           if self.file_detection_status.get(fp, {}).get("has_reliable_detection", False) 
                           and not self.file_detection_status.get(fp, {}).get("needs_manual_config", True))
            if auto_count == len(self.view_assignments):
                self.start_import_btn.setText("🚀 Start Import (Auto)")
            elif auto_count > 0:
                self.start_import_btn.setText("🚀 Start Import (Mixed)")
            else:
                self.start_import_btn.setText("🚀 Start Import (Manual)")
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
        
        # Count configuration types for logging
        auto_configured_count = 0
        manual_configured_count = 0
        
        for file_path in self.view_assignments.keys():
            detection_info = self.file_detection_status.get(file_path, {})
            if detection_info.get("has_reliable_detection", False) and not detection_info.get("needs_manual_config", True):
                auto_configured_count += 1
            else:
                manual_configured_count += 1
        
        self._log_message("🚀 Starting enhanced import process...")
        self._log_message(f"Processing {len(self.selected_files)} files with view assignments")
        self._log_message(f"Session: {self.session_code}")
        self._log_message(f"Target: data/SPECT/{self.session_code}/[patient_id]/")
        
        if auto_configured_count > 0 and manual_configured_count > 0:
            self._log_message(f"Configuration: {auto_configured_count} auto + {manual_configured_count} manual")
        elif auto_configured_count == len(self.selected_files):
            self._log_message(f"Configuration: All {auto_configured_count} files auto-configured")
        else:
            self._log_message(f"Configuration: All {manual_configured_count} files manually configured")
        
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
        """Handle processing completion with enhanced summary"""
        auto_configured_count = sum(1 for fp in self.view_assignments.keys() 
                                  if self.file_detection_status.get(fp, {}).get("has_reliable_detection", False) 
                                  and not self.file_detection_status.get(fp, {}).get("needs_manual_config", True))
        manual_configured_count = len(self.view_assignments) - auto_configured_count
        
        self._log_message("🎉 Enhanced import workflow completed!")
        self._log_message("All files processed with proper Anterior/Posterior naming")
        
        if auto_configured_count > 0 and manual_configured_count > 0:
            self._log_message(f"✅ Successfully processed: {auto_configured_count} auto + {manual_configured_count} manual files")
        elif auto_configured_count == len(self.view_assignments):
            self._log_message(f"✅ Successfully processed: All {auto_configured_count} auto-configured files")
        else:
            self._log_message(f"✅ Successfully processed: All {manual_configured_count} manually configured files")
        
        self._log_message("Rescanning folder...")

        # Emit signal untuk rescan folder
        self.files_imported.emit()

        # Update UI
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.add_dicom_btn.setEnabled(True)
        self.configure_views_btn.setEnabled(True)

        # Enhanced success message
        processed_count = len(self.view_assignments)
        config_summary = ""
        if auto_configured_count > 0 and manual_configured_count > 0:
            config_summary = f"({auto_configured_count} auto + {manual_configured_count} manual)"
        elif auto_configured_count == processed_count:
            config_summary = f"(all {auto_configured_count} auto-configured)"
        else:
            config_summary = f"(all {manual_configured_count} manually configured)"
        
        QMessageBox.information(
            self,
            "Import Successful",
            f"Successfully processed {processed_count} DICOM files! {config_summary}\n\n"
            "✅ All files have proper Anterior/Posterior view assignments\n"
            "✅ Original PNG files uploaded to cloud storage\n"
            "✅ Complete processing pipeline executed\n"
            "✅ Enhanced auto-detection workflow completed\n\n"
            "Files are now ready for viewing and analysis."
        )
        self.accept()
        
    def _cancel_import(self):
        """Cancel the import process"""
        # ✅ FIXED: Clean up view dialog if open
        if hasattr(self, '_view_dialog') and self._view_dialog:
            try:
                self._view_dialog.close()
            except:
                pass
            self._view_dialog = None
        
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.terminate()
            self.processing_thread.wait()
        
        if self.quick_detection_thread and self.quick_detection_thread.isRunning():
            self.quick_detection_thread.terminate()
            self.quick_detection_thread.wait()
            
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
    Legacy version without enhanced auto-detection for backward compatibility
    Uses basic auto-detection only
    """
    
    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        super().__init__(data_root, parent, session_code)
        self.setWindowTitle("Import DICOM Files - Legacy Mode")
        
        # Hide enhanced features
        self.configure_views_btn.setVisible(False)
        self._setup_legacy_mode()
        
    def _setup_legacy_mode(self):
        """Setup for legacy mode without enhanced detection"""
        # Update workflow info
        workflow_info = self.findChild(QLabel)
        if workflow_info:
            workflow_info.setText(
                "⚠️ Legacy Mode: Basic auto-detection only\n"
                "• System will attempt to auto-detect Anterior/Posterior views\n" 
                "• May fail if DICOM tags are missing or incorrect\n"
                "• Consider using Enhanced Mode for better control and reliability"
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
    
    def _add_dicom_files(self):
        """Override to skip enhanced detection in legacy mode"""
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
                    self._add_legacy_file_to_list(path)
            
            self._update_ui_state()
            self._log_message(f"Added {len(file_paths)} file(s) to import list")
            self._log_message("⚠️ Legacy mode: Basic auto-detection will be used during processing")
    
    def _add_legacy_file_to_list(self, file_path: Path):
        """Add file to list with legacy status"""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, file_path)
        
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # File name label
        file_name = truncate_text(file_path.name, 30)
        file_label = QLabel(file_name)
        file_label.setStyleSheet(FILE_ITEM_NAME_STYLE)
        layout.addWidget(file_label)
        
        # Legacy status
        status_label = QLabel("⚠️ Legacy auto-detection")
        status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.WARNING};
                font-size: 10px;
                font-style: italic;
                font-weight: bold;
            }}
        """)
        layout.addWidget(status_label)
        
        # File path
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
    
    def _update_ui_state(self):
        """Override to skip enhanced view configuration step"""
        has_files = len(self.selected_files) > 0
        has_session = self.session_code is not None
        
        self.start_import_btn.setEnabled(has_files and has_session)
        
        if has_files and not has_session:
            self.start_import_btn.setToolTip("Session code is required")
        else:
            self.start_import_btn.setToolTip("Will use legacy auto-detection during processing")
    
    def _start_import(self):
        """Start legacy import with basic auto-detection"""
        if not self.selected_files or not self.session_code:
            QMessageBox.warning(self, "Warning", "Session code is required for import!")
            return
            
        self._log_message("⚠️ Starting LEGACY import process...")
        self._log_message("Using BASIC AUTO-DETECTION for Anterior/Posterior views")
        self._log_message(f"Processing {len(self.selected_files)} file(s)")
        self._log_message("Warning: May fail if DICOM view tags are missing or unclear")
        
        # Update UI for processing mode
        self.add_dicom_btn.setEnabled(False)
        self.start_import_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setValue(0)
        
        # Use legacy processing (basic auto-detection only)
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
        use_enhanced_mode: True untuk enhanced mode dengan auto-detection
        
    Returns:
        DicomImportDialog instance
    """
    if use_enhanced_mode:
        return DicomImportDialog(data_root, parent, session_code)
    else:
        return DicomImportDialogLegacy(data_root, parent, session_code)


# Utility functions for dialog management
def show_enhanced_import_dialog(data_root: Path, parent=None, session_code: str = None) -> bool:
    """
    Show enhanced import dialog and return success status
    
    Args:
        data_root: Root data directory
        parent: Parent widget
        session_code: Session code for the import
        
    Returns:
        True if files were imported, False if cancelled
    """
    dialog = create_dicom_import_dialog(
        data_root=data_root,
        parent=parent,
        session_code=session_code,
        use_enhanced_mode=True
    )
    
    result = dialog.exec()
    return result == QDialog.Accepted


def show_legacy_import_dialog(data_root: Path, parent=None, session_code: str = None) -> bool:
    """
    Show legacy import dialog and return success status
    
    Args:
        data_root: Root data directory
        parent: Parent widget
        session_code: Session code for the import
        
    Returns:
        True if files were imported, False if cancelled
    """
    dialog = create_dicom_import_dialog(
        data_root=data_root,
        parent=parent,
        session_code=session_code,
        use_enhanced_mode=False
    )
    
    result = dialog.exec()
    return result == QDialog.Accepted


# Configuration and validation functions
def validate_import_requirements(data_root: Path, session_code: str = None) -> tuple[bool, str]:
    """
    Validate requirements for DICOM import
    
    Args:
        data_root: Root data directory
        session_code: Session code
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check if data root exists and is writable
        if not data_root.exists():
            return False, f"Data directory does not exist: {data_root}"
        
        if not os.access(data_root, os.W_OK):
            return False, f"No write permission to data directory: {data_root}"
        
        # Check session code if provided
        if session_code:
            # Validate session code format (should be alphanumeric)
            if not session_code.replace("_", "").isalnum():
                return False, f"Invalid session code format: {session_code}"
            
            # Check if session directory can be created
            session_path = data_root / "SPECT" / session_code
            try:
                session_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return False, f"Cannot create session directory: {e}"
        
        # Check cloud storage if available
        if CLOUD_AVAILABLE:
            try:
                from core.config.paths import is_cloud_enabled
                if is_cloud_enabled():
                    print("[IMPORT] Cloud storage is enabled and configured")
                else:
                    print("[IMPORT] Cloud storage is available but not configured")
            except Exception as e:
                print(f"[IMPORT] Cloud storage check failed: {e}")
        
        return True, ""
        
    except Exception as e:
        return False, f"Validation failed: {str(e)}"


def get_import_dialog_config() -> dict:
    """
    Get configuration for import dialog
    
    Returns:
        Dictionary with configuration options
    """
    return {
        "enhanced_mode_available": True,
        "legacy_mode_available": True,
        "cloud_storage_available": CLOUD_AVAILABLE,
        "supported_extensions": [".dcm", ".dicom"],
        "max_files_per_import": 50,  # Reasonable limit
        "auto_detection_confidence_levels": ["high", "low", "none"],
        "required_views": ["Anterior", "Posterior"],
        "default_mode": "enhanced"
    }


# Helper functions for testing and debugging
def test_import_dialog(session_code: str = "TEST", mode: str = "enhanced"):
    """
    Test function for import dialog - for development use only
    
    Args:
        session_code: Test session code
        mode: "enhanced" or "legacy"
    """
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create test data directory
    test_data_root = Path("./test_data")
    test_data_root.mkdir(exist_ok=True)
    
    # Validate requirements
    is_valid, error_msg = validate_import_requirements(test_data_root, session_code)
    if not is_valid:
        print(f"Validation failed: {error_msg}")
        return
    
    # Show dialog
    use_enhanced = mode.lower() == "enhanced"
    dialog = create_dicom_import_dialog(
        data_root=test_data_root,
        session_code=session_code,
        use_enhanced_mode=use_enhanced
    )
    
    print(f"Testing {mode} mode import dialog...")
    result = dialog.exec()
    
    if result == QDialog.Accepted:
        print("✅ Import completed successfully")
    else:
        print("❌ Import cancelled")
    
    if app and not QApplication.instance():
        app.quit()


def debug_detection_system(file_paths: List[Path]) -> dict:
    """
    Debug function to test detection system on files
    
    Args:
        file_paths: List of DICOM file paths to test
        
    Returns:
        Dictionary with detection results
    """
    results = {}
    
    for file_path in file_paths:
        try:
            print(f"🔍 Testing detection on: {file_path.name}")
            
            # Create quick detection thread for testing
            thread = QuickDetectionThread([file_path])
            detection_info = thread._quick_detection_check(file_path)
            
            results[str(file_path)] = {
                "detection_info": detection_info,
                "file_exists": file_path.exists(),
                "file_size": file_path.stat().st_size if file_path.exists() else 0
            }
            
            # Print results
            has_reliable = detection_info.get("has_reliable_detection", False)
            needs_manual = detection_info.get("needs_manual_config", True)
            auto_count = detection_info.get("auto_configured_count", 0)
            manual_count = detection_info.get("manual_required_count", 0)
            
            print(f"  Reliable detection: {has_reliable}")
            print(f"  Needs manual config: {needs_manual}")
            print(f"  Auto configured: {auto_count}")
            print(f"  Manual required: {manual_count}")
            
            if has_reliable and not needs_manual:
                print(f"  ✅ Status: Fully auto-configured")
            elif has_reliable and needs_manual:
                print(f"  ⚠️ Status: Partially auto-configured")
            else:
                print(f"  ❌ Status: Manual configuration required")
            
        except Exception as e:
            print(f"  ❌ Error testing {file_path.name}: {e}")
            results[str(file_path)] = {"error": str(e)}
    
    return results


# Import validation and error handling
class ImportValidationError(Exception):
    """Custom exception for import validation errors"""
    pass


class ImportProcessingError(Exception):
    """Custom exception for import processing errors"""
    pass


def safe_import_with_validation(
    file_paths: List[Path], 
    data_root: Path, 
    session_code: str,
    use_enhanced_mode: bool = True,
    parent=None
) -> tuple[bool, str, List[Path]]:
    """
    Safely import DICOM files with full validation and error handling
    
    Args:
        file_paths: List of DICOM file paths
        data_root: Root data directory
        session_code: Session code
        use_enhanced_mode: Whether to use enhanced mode
        parent: Parent widget for dialogs
        
    Returns:
        Tuple of (success, message, processed_files)
    """
    processed_files = []
    
    try:
        # Step 1: Validate requirements
        is_valid, error_msg = validate_import_requirements(data_root, session_code)
        if not is_valid:
            raise ImportValidationError(f"Requirements validation failed: {error_msg}")
        
        # Step 2: Validate files
        valid_files = []
        for file_path in file_paths:
            if not file_path.exists():
                print(f"⚠️ File not found: {file_path}")
                continue
            
            if not file_path.suffix.lower() in ['.dcm', '.dicom']:
                print(f"⚠️ Invalid file extension: {file_path}")
                continue
            
            try:
                # Quick DICOM validation
                import pydicom
                ds = pydicom.dcmread(file_path, stop_before_pixels=True)
                if not hasattr(ds, 'PatientID'):
                    print(f"⚠️ Invalid DICOM (no PatientID): {file_path}")
                    continue
                
                valid_files.append(file_path)
                
            except Exception as e:
                print(f"⚠️ DICOM validation failed for {file_path}: {e}")
                continue
        
        if not valid_files:
            raise ImportValidationError("No valid DICOM files found")
        
        print(f"✅ Validated {len(valid_files)} of {len(file_paths)} files")
        
        # Step 3: Create and show dialog
        dialog = create_dicom_import_dialog(
            data_root=data_root,
            parent=parent,
            session_code=session_code,
            use_enhanced_mode=use_enhanced_mode
        )
        
        # Pre-populate dialog with validated files
        for file_path in valid_files:
            dialog.selected_files.append(file_path)
            dialog._add_file_to_list(file_path)
        
        # Start quick detection if enhanced mode
        if use_enhanced_mode:
            dialog._start_quick_detection(valid_files)
        
        # Show dialog
        result = dialog.exec()
        
        if result == QDialog.Accepted:
            processed_files = list(dialog.view_assignments.keys()) if dialog.view_assignments else valid_files
            return True, f"Successfully imported {len(processed_files)} files", processed_files
        else:
            return False, "Import cancelled by user", []
        
    except ImportValidationError as e:
        return False, str(e), []
    except ImportProcessingError as e:
        return False, f"Processing error: {str(e)}", processed_files
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", processed_files


# Export all public functions and classes
__all__ = [
    # Main classes
    "DicomImportDialog",
    "DicomImportDialogLegacy", 
    "ProcessingThread",
    "QuickDetectionThread",
    
    # Factory functions
    "create_dicom_import_dialog",
    "show_enhanced_import_dialog",
    "show_legacy_import_dialog",
    
    # Validation and utilities
    "validate_import_requirements",
    "get_import_dialog_config",
    "safe_import_with_validation",
    
    # Testing and debugging
    "test_import_dialog",
    "debug_detection_system",
    
    # Exceptions
    "ImportValidationError",
    "ImportProcessingError"
]


# Module level constants
DIALOG_VERSION = "2.0.0"
SUPPORTED_DICOM_EXTENSIONS = [".dcm", ".dicom"]
DEFAULT_SESSION_CODE = "DEFAULT"
MAX_FILES_PER_IMPORT = 50

# Configuration for different deployment environments
DEPLOYMENT_CONFIG = {
    "development": {
        "enable_debug_logging": True,
        "show_test_functions": True,
        "validate_strictly": False
    },
    "testing": {
        "enable_debug_logging": True,
        "show_test_functions": True,
        "validate_strictly": True
    },
    "production": {
        "enable_debug_logging": False,
        "show_test_functions": False,
        "validate_strictly": True
    }
}

def get_deployment_config(environment: str = "production") -> dict:
    """Get configuration for specific deployment environment"""
    return DEPLOYMENT_CONFIG.get(environment, DEPLOYMENT_CONFIG["production"])


# Version and compatibility information
def get_version_info() -> dict:
    """Get version and compatibility information"""
    return {
        "dialog_version": DIALOG_VERSION,
        "compatible_python": ">=3.8",
        "required_pyside": ">=6.0",
        "features": {
            "enhanced_auto_detection": True,
            "confidence_based_detection": True,
            "instant_analysis": True,
            "zoom_and_pan": True,
            "cloud_integration": CLOUD_AVAILABLE,
            "legacy_compatibility": True
        },
        "supported_formats": SUPPORTED_DICOM_EXTENSIONS
    }

def _reset_import_state(self):
    """Reset import state when file list changes"""
    print("🔍 DEBUG: Resetting import state...")
    
    # Clear view assignments
    self.view_assignments.clear()
    
    # Clear detection status for files not in selected_files
    for file_path in list(self.file_detection_status.keys()):
        if file_path not in self.selected_files:
            del self.file_detection_status[file_path]
    
    # Close view dialog if open
    if hasattr(self, '_view_dialog') and self._view_dialog:
        try:
            self._view_dialog.close()
        except:
            pass
        self._view_dialog = None
    
    # Stop detection threads
    if hasattr(self, 'quick_detection_thread') and self.quick_detection_thread:
        if self.quick_detection_thread.isRunning():
            self.quick_detection_thread.terminate()
            self.quick_detection_thread.wait(1000)
        self.quick_detection_thread = None
    
    print("✅ Import state reset completed")