# features/dicom_import/gui/dicom_import_dialog_v2.py - CLEAN FINAL VERSION
"""
Enhanced DICOM Import Dialog dengan improved auto-configuration status handling.

FIXES:
1. Proper status display for auto-tagged vs manual configuration required
2. Immediate status update based on detection confidence
3. Enhanced workflow with better user feedback
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Dict
import os
import pydicom
import logging

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
    DIALOG_DISABLED_BUTTON_STYLE,
    truncate_text,
    Colors
)

# Import the enhanced view selector dialog
from .dicom_view_selector_dialog import DicomViewSelectorDialog
from core.config.paths import extract_study_date_from_dicom
# Import for cloud storage
CLOUD_AVAILABLE = False

class ProcessingThread(QThread):
    progress_and_status_updated = Signal(int, int, str, str, float) # current, total, filename, step_message, step_progress
    log_updated = Signal(str)
    finished_processing = Signal()
    
    def __init__(self, file_view_assignments: Dict[Path, Dict[int, str]], 
                background_assignments: Dict[Path, Dict[int, Dict[str, str]]],
                data_root: Path, session_code: str): 
        super().__init__()
        self.file_view_assignments = file_view_assignments
        self.background_assignments = background_assignments
        self.data_root = data_root
        self.session_code = session_code  #   ADD this line
        
    def run(self):
        try:
            def combined_progress_callback_wrapper(current: int, total: int, filename: str, step_message: str, step_progress: float):
                self.progress_and_status_updated.emit(current, total, filename, step_message, step_progress)

            process_files_with_assignments(
                file_view_assignments=self.file_view_assignments,
                background_assignments=self.background_assignments,
                data_root=self.data_root,
                session_code=self.session_code,
                combined_progress_cb=combined_progress_callback_wrapper,
                log_cb=self._log_callback
            )
            
            self.log_updated.emit("## Processing completed.")
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
                logging.info(f"Quick detection failed for {file_path}: {e}")
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
        self.logger = logging.getLogger(__name__) # Use module-specific logger
        self.setModal(True)
        self.resize(1000, 700)
        
        self.data_root = data_root
        self.session_code = session_code
        self.selected_files: List[Path] = []
        self.view_assignments: Dict[Path, Dict[int, str]] = {}
        self.file_detection_status: Dict[Path, dict] = {}
        # Track kombinasi (patient_id, study_date) yang SUDAH ada di UI list:
        self._present_patient_study_keys = set()    # Set[Tuple[str, str]]
        # Map file -> key (untuk cleanup saat remove)
        self._file_key_map: Dict[Path, tuple] = {}
        self.processing_thread: Optional[ProcessingThread] = None
        self.quick_detection_thread: Optional[QuickDetectionThread] = None
        
        #   FIXED: Add dialog reference tracking
        self._view_dialog: Optional[DicomViewSelectorDialog] = None
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup UI components"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(8)
        
        # Title with enhanced workflow info
        title_text = "Import DICOM Files"
        if self.session_code:
            title_text += f" - Session: {self.session_code}"
            
        title_label = QLabel(title_text)
        title_label.setStyleSheet(DIALOG_TITLE_STYLE)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(title_label)
        
        # Enhanced workflow description
        if self.session_code:
            structure_info = QLabel(f"Files will be saved to: data/PLANAR/{self.session_code}/[patient_id]/")
            structure_info.setStyleSheet(DIALOG_SUBTITLE_STYLE)
            structure_info.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(structure_info)
        
        # Main content area - NOW ONLY THE FILE LIST
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(6)
        
        # Left panel - File List (expanded to full width)
        left_panel = self._create_file_list_panel()
        content_splitter.addWidget(left_panel)
        
        # REMOVED: Right panel - Process Log
        # right_panel = self._create_process_log_panel()
        # content_splitter.addWidget(right_panel)
        
        # Set stretch factor for a single widget
        content_splitter.setStretchFactor(0, 1) # Make file list panel expand
        content_splitter.setSizes([750]) # Set initial width
        
        main_layout.addWidget(content_splitter, 1)
        
        # Bottom controls
        bottom_layout = self._create_bottom_controls()
        main_layout.addLayout(bottom_layout)

    # DELETED: _create_process_log_panel function
    # The entire function is removed
    
    
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
        
        
    def _create_bottom_controls(self) -> QHBoxLayout:
        """Create bottom control buttons"""
        layout = QHBoxLayout()
        layout.setSpacing(10)
        

        file_folder_layout = QHBoxLayout()

        # Tombol Cancel SEKARANG DI SINI
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(DIALOG_CANCEL_BUTTON_STYLE)
        file_folder_layout.addWidget(self.cancel_btn) # Ditambahkan ke layout kiri
        
        self.add_dicom_btn = QPushButton("Add Files")
        self.add_dicom_btn.setStyleSheet(DIALOG_IMPORT_BUTTON_STYLE)
        file_folder_layout.addWidget(self.add_dicom_btn)

        self.add_folders_btn = QPushButton("Add Folders")
        self.add_folders_btn.setStyleSheet(DIALOG_IMPORT_BUTTON_STYLE)
        file_folder_layout.addWidget(self.add_folders_btn)

        

        layout.addLayout(file_folder_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(DIALOG_PROGRESS_BAR_STYLE)
        self.progress_bar.setFormat(" %p% ") # Tambahkan ini untuk menampilkan persentase di dalam bar
        self.progress_bar.setAlignment(Qt.AlignCenter) # Agar teksnya di tengah
        layout.addWidget(self.progress_bar)

        # Progress label (sekarang hanya untuk pesan status)
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet(f"color: {Colors.DIALOG_TEXT}; font-size: 12px;")
        layout.addWidget(self.progress_label)
        
        layout.addStretch()
        
        self.configure_views_btn = QPushButton("Review Data")

        self.configure_views_btn.setEnabled(False)
        self.configure_views_btn.setStyleSheet(DIALOG_DISABLED_BUTTON_STYLE) # Gunakan style baru saat inisialisasi
        layout.addWidget(self.configure_views_btn)
        
        # Start Import button
        self.start_import_btn = QPushButton("Start Import")
        self.start_import_btn.setEnabled(False)
        self.start_import_btn.setStyleSheet(DIALOG_START_BUTTON_STYLE)
        layout.addWidget(self.start_import_btn)
        
        # Tombol Cancel SUDAH DIPINDAHKAN DARI SINI
        
        return layout
        
    def _connect_signals(self):
        self.add_dicom_btn.clicked.connect(self._add_dicom_files)
        self.add_folders_btn.clicked.connect(self._add_dicom_folders)
        self.configure_views_btn.clicked.connect(self._configure_views)
        self.start_import_btn.clicked.connect(self._start_import)
        self.cancel_btn.clicked.connect(self._cancel_import)
        
    def _add_dicom_files(self):
        """Add DICOM files dengan rules:
        - System duplicate (sudah ada di app utk session_code + patient_id + study_date) → tampilkan 1 kartu 'already analyzed', tidak diproses.
        - Internal redundant (sudah ada di list UI dengan patient_id + study_date yg sama) → JANGAN dimasukkan ke list.
        - File benar-benar baru → masuk ke list + ikut dianalisis.
        """
        # Init penunjang jika belum ada
        if not hasattr(self, "_present_patient_study_keys"):
            self._present_patient_study_keys = set()
        if not hasattr(self, "_file_key_map"):
            self._file_key_map = {}

        # Tutup dialog view jika masih terbuka (biar state bersih)
        if hasattr(self, '_view_dialog') and self._view_dialog:
            try:
                self._view_dialog.close()
            except:
                pass
            self._view_dialog = None

        # Ambil file dari dialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select DICOM Files",
            "",
            "DICOM Files (*.dcm);;All Files (*)"
        )
        if not file_paths:
            return

        self.logger.info(f"[ADD_FILES] Mulai analisis {len(file_paths)} file")
        try:
            from core.config.paths import (
                check_dicom_exists, get_existing_dicom_info, extract_study_date_from_dicom
            )
            self.logger.info("[ADD_FILES] fungsi duplicate-check OK")
        except ImportError as e:
            self.logger.info(f"[ADD_FILES] Import error duplicate-check: {e}")
            # Fallback: kalau util tak ada, treat semua sebagai NEW
            new_files = [Path(p) for p in file_paths if Path(p) not in self.selected_files]
            for fp in new_files:
                self.selected_files.append(fp)
                self._add_file_to_list(fp)
            self._update_ui_state()
            if new_files:
                self._start_quick_detection(new_files)
            return

        # Jika ada perubahan list, assignment lama dibersihkan
        if self.selected_files and self.view_assignments:
            self.view_assignments.clear()
            self.logger.info("[ADD_FILES] View assignments cleared karena list berubah")

        # Keranjang hasil
        new_files: List[Path] = []
        duplicate_files = []       # System duplicate (already analyzed)
        internal_duplicates = []   # Redundant pada UI list saat ini
        error_files = []

        # Analisis satu per satu
        for idx, f in enumerate(file_paths, start=1):
            p = Path(f)

            # Skip jika persis sama path sudah ada di selection
            if p in self.selected_files:
                self.logger.info(f"[ADD_FILES] {p.name} sudah ada di selection, skip path duplikat")
                continue

            try:
                ds = pydicom.dcmread(p, stop_before_pixels=True)
                patient_id = str(getattr(ds, "PatientID", "Unknown"))
                study_date = extract_study_date_from_dicom(p)
                key = (patient_id, study_date)
                self.logger.info(f"[ADD_FILES] {idx}/{len(file_paths)} {p.name} → PID={patient_id} SD={study_date}")

                # INTERNAL redundant? (sudah ada key ini di list UI)
                if key in self._present_patient_study_keys:
                    internal_duplicates.append((p, {
                        "patient_id": patient_id,
                        "study_date": study_date,
                        "reason": "redundant in current list"
                    }))
                    self.logger.info(f"[ADD_FILES]   -> redundant in current list, tidak dimasukkan")
                    continue

                # SYSTEM duplicate? (sudah ada di app utk kode dokter/session_code)
                if self.session_code and check_dicom_exists(self.session_code, patient_id, study_date):
                    duplicate_files.append((p, {
                        "patient_id": patient_id,
                        "study_date": study_date,
                        "reason": "already analyzed"
                    }))
                    # Tampilkan 1 kartu already analyzed & tandai key-nya hadir di UI
                    self._add_already_analyzed_file_to_list(p, patient_id, study_date)
                    self._present_patient_study_keys.add(key)
                    self._file_key_map[p] = key
                    self.logger.info(f"[ADD_FILES]   -> ALREADY ANALYZED (card abu), tidak ikut proses")
                    continue

                # NEW → masukkan ke list dan catat key
                new_files.append(p)
                self._present_patient_study_keys.add(key)
                self._file_key_map[p] = key
                self.logger.info(f"[ADD_FILES]   -> NEW, dimasukkan")

            except Exception as e:
                error_files.append((p, str(e)))
                self.logger.info(f"[ADD_FILES]   -> ERROR membaca {p.name}: {e}")

        # Tambah ke UI (hanya NEW)
        added_count = 0
        for nf in new_files:
            if nf not in self.selected_files:
                self.selected_files.append(nf)
                self._add_file_to_list(nf)
                added_count += 1

        # Logging ringkas
        if duplicate_files:
            for dup_path, dup_info in duplicate_files:
                pid = dup_info.get("patient_id", "?")
                sdate = dup_info.get("study_date", "?")
                self.logger.info(f"[ADD_FILES] • Marked as already analyzed: {dup_path.name} (PID={pid}, SD={sdate})")
        if internal_duplicates:
            for dup_path, dup_info in internal_duplicates:
                pid = dup_info.get("patient_id", "?")
                sdate = dup_info.get("study_date", "?")
                self.logger.info(f"[ADD_FILES] • Skipped redundant selection: {dup_path.name} (PID={pid}, SD={sdate})")
        if error_files:
            for err_path, reason in error_files:
                self.logger.info(f"[ADD_FILES] • Error {err_path.name}: {reason}")

        self.logger.info(f"[ADD_FILES] NEW added: {added_count}, already analyzed: {len(duplicate_files)}, redundant skipped: {len(internal_duplicates)}, errors: {len(error_files)}")

        # Update UI dan mulai quick detection untuk NEW
        self._update_ui_state()
        if new_files:
            self._start_quick_detection(new_files)
    
    
    def _add_dicom_folders(self):
        """Add DICOM folders (bulk) dengan rules sama:
        - System duplicate → tampilkan 1 kartu 'already analyzed' (abu), tidak diproses.
        - Internal redundant di UI → JANGAN dimasukkan ke list.
        - NEW → masuk list + dianalisis.
        """
        # Init penunjang jika belum ada
        if not hasattr(self, "_present_patient_study_keys"):
            self._present_patient_study_keys = set()
        if not hasattr(self, "_file_key_map"):
            self._file_key_map = {}

        folder_dialog = QFileDialog(self)
        folder_dialog.setFileMode(QFileDialog.Directory)
        folder_dialog.setOption(QFileDialog.ShowDirsOnly, False)

        if not folder_dialog.exec():
            return

        folder_paths = [Path(p) for p in folder_dialog.selectedFiles()]

        from features.dicom_import.logic.input_data import scan_folders_for_dicom
        dicom_files = scan_folders_for_dicom(folder_paths)

        if not dicom_files:
            self.logger.info("[ADD_FOLDERS] Tidak ada DICOM files ditemukan")
            return

        self.logger.info(f"[ADD_FOLDERS] Found {len(dicom_files)} DICOM files from {len(folder_paths)} folders")
        try:
            from core.config.paths import (
                check_dicom_exists, get_existing_dicom_info, extract_study_date_from_dicom
            )
            self.logger.info("[ADD_FOLDERS] fungsi duplicate-check OK")
        except ImportError as e:
            self.logger.info(f"[ADD_FOLDERS] Import error duplicate-check: {e}")
            # Fallback → treat semua sebagai NEW (kecuali path yang benar2 sama)
            added = 0
            for f in dicom_files:
                if f not in self.selected_files:
                    self.selected_files.append(f)
                    self._add_file_to_list(f)
                    added += 1
            self._update_ui_state()
            if added:
                self._start_quick_detection([*dicom_files])
            return

        new_files: List[Path] = []
        duplicate_files = []      # System duplicate (already analyzed)
        internal_duplicates = []  # Redundant di daftar UI saat ini
        error_files = []

        for idx, p in enumerate(dicom_files, start=1):
            # Skip path yang sama sudah ada di selected_files
            if p in self.selected_files:
                self.logger.info(f"[ADD_FOLDERS] {p.name} sudah ada di selection, skip path duplikat")
                continue

            try:
                ds = pydicom.dcmread(p, stop_before_pixels=True)
                patient_id = str(getattr(ds, "PatientID", "Unknown"))
                study_date = extract_study_date_from_dicom(p)
                key = (patient_id, study_date)
                self.logger.info(f"[ADD_FOLDERS] {idx}/{len(dicom_files)} {p.name} → PID={patient_id} SD={study_date}")

                # INTERNAL redundant?
                if key in self._present_patient_study_keys:
                    internal_duplicates.append((p, {
                        "patient_id": patient_id,
                        "study_date": study_date,
                        "reason": "redundant in current list"
                    }))
                    self.logger.info(f"[ADD_FOLDERS]   -> redundant in current list, skip")
                    continue

                # SYSTEM duplicate?
                if self.session_code and check_dicom_exists(self.session_code, patient_id, study_date):
                    duplicate_files.append((p, {
                        "patient_id": patient_id,
                        "study_date": study_date,
                        "reason": "already analyzed"
                    }))
                    # Render kartu already analyzed, catat key
                    self._add_already_analyzed_file_to_list(p, patient_id, study_date)
                    self._present_patient_study_keys.add(key)
                    self._file_key_map[p] = key
                    self.logger.info(f"[ADD_FOLDERS]   -> ALREADY ANALYZED (card abu), tidak ikut proses")
                    continue

                # NEW
                new_files.append(p)
                self._present_patient_study_keys.add(key)
                self._file_key_map[p] = key
                self.logger.info(f"[ADD_FOLDERS]   -> NEW, dimasukkan")

            except Exception as e:
                error_files.append((p, str(e)))
                self.logger.info(f"[ADD_FOLDERS]   -> ERROR membaca {p.name}: {e}")

        # Tambahkan NEW ke UI
        added_count = 0
        for nf in new_files:
            if nf not in self.selected_files:
                self.selected_files.append(nf)
                self._add_file_to_list(nf)
                added_count += 1

        # Log ringkas
        if duplicate_files:
            for dup_path, dup_info in duplicate_files:
                pid = dup_info.get("patient_id", "?")
                sdate = dup_info.get("study_date", "?")
                self.logger.info(f"[ADD_FOLDERS] • Marked as already analyzed (folder): {dup_path.name} (PID={pid}, SD={sdate})")
        if internal_duplicates:
            for dup_path, dup_info in internal_duplicates:
                pid = dup_info.get("patient_id", "?")
                sdate = dup_info.get("study_date", "?")
                self.logger.info(f"[ADD_FOLDERS] • Skipped redundant (folder): {dup_path.name} (PID={pid}, SD={sdate})")
        if error_files:
            for err_path, reason in error_files:
                self.logger.info(f"[ADD_FOLDERS] • Error {err_path.name}: {reason}")

        self.logger.info(f"[ADD_FOLDERS] NEW added: {added_count}, already analyzed: {len(duplicate_files)}, redundant skipped: {len(internal_duplicates)}, errors: {len(error_files)}")

        # Update UI + start detection utk NEW
        self._update_ui_state()
        if new_files:
            self._start_quick_detection(new_files)
    
    def _start_quick_detection(self, file_paths: List[Path]):
        """Start quick detection analysis untuk immediate feedback"""
        #   FIXED: More thorough thread cleanup
        if hasattr(self, 'quick_detection_thread') and self.quick_detection_thread:
            if self.quick_detection_thread.isRunning():
                logging.info("  DEBUG: Terminating existing quick detection thread...")
                self.quick_detection_thread.terminate()
                self.quick_detection_thread.wait(2000)  # Wait max 2 seconds
                if self.quick_detection_thread.isRunning():
                    logging.info("⚠️ WARNING: Thread did not terminate, forcing...")
            
            # Disconnect old signals
            try:
                self.quick_detection_thread.detection_completed.disconnect()
                self.quick_detection_thread.finished.disconnect()
            except:
                pass
            
            self.quick_detection_thread = None
        
        logging.info(f"  DEBUG: Starting quick detection for {len(file_paths)} files...")
        
        try:
            self.quick_detection_thread = QuickDetectionThread(file_paths)
            self.quick_detection_thread.detection_completed.connect(self._on_quick_detection_completed)
            self.quick_detection_thread.finished.connect(self._on_quick_detection_finished)
            self.quick_detection_thread.start()
        except Exception as e:
            logging.info(f" ERROR starting quick detection: {e}")
            self.logger.info(f" Error starting file analysis: {str(e)}")
        
    def _on_quick_detection_completed(self, file_path: Path, detection_info: dict):
        """Handle completed quick detection for single file"""
        #   FIXED: Check if file still exists in selected files
        if file_path not in self.selected_files:
            logging.info(f"⚠️ WARNING: File {file_path.name} no longer in selected files, skipping detection update")
            return
        
        #   FIXED: Prevent duplicate detection processing
        if file_path in self.file_detection_status:
            existing_info = self.file_detection_status[file_path]
            if existing_info.get("total_frames") == detection_info.get("total_frames"):
                logging.info(f"  DEBUG: Detection for {file_path.name} already exists and unchanged, skipping...")
                return
        
        logging.info(f"  DEBUG: Processing detection result for {file_path.name}")
        self.file_detection_status[file_path] = detection_info
        
        # Update file status immediately
        try:
            self._update_single_file_status(file_path, detection_info)
        except Exception as e:
            logging.info(f" ERROR updating file status for {file_path.name}: {e}")
        
        # Log detection result
        patient_id = detection_info.get("patient_id", "Unknown")
        auto_count = detection_info.get("auto_configured_count", 0)
        manual_count = detection_info.get("manual_required_count", 0)
        
        if detection_info.get("has_reliable_detection", False):
            if not detection_info.get("needs_manual_config", True):
                self.logger.info(f"  {truncate_text(file_path.name, 30)}: Fully auto-tagged ({auto_count} frames)")
            else:
                self.logger.info(f"⚠️ {truncate_text(file_path.name, 30)}: Partially auto-tagged ({auto_count} auto, {manual_count} manual)")
        else:
            self.logger.info(f" {truncate_text(file_path.name, 30)}: Manual configuration required ({manual_count} frames)")
    
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
        
        self.logger.info("📊 Detection Analysis Complete:")
        if fully_auto > 0:
            self.logger.info(f"     {fully_auto} files fully auto-tagged")
        if partially_auto > 0:
            self.logger.info(f"   ⚠️ {partially_auto} files partially auto-tagged")
        if manual_only > 0:
            self.logger.info(f"    {manual_only} files need manual configuration")
        
        if fully_auto == total_files:
            self.logger.info("🎉 All files auto-tagged! You can proceed directly to import.")
        elif manual_only == 0:
            self.logger.info("⚠️ Some files need verification. Please review in Configure Views.")
        else:
            self.logger.info("⚙️ Manual configuration required for some files.")
        
        self.logger.info("Next step: Configure Views (or proceed if all auto-tagged)")
    
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
                    for i in range(self.file_list.count()):
                        item = self.file_list.item(i)
                        widget = self.file_list.itemWidget(item)
                        if item.data(Qt.UserRole) == file_path and widget:
                            lay = widget.layout()
                            # Asumsi lama: status widget ada di index 1 (setelah file_label)
                            if lay.count() > 1 and isinstance(lay.itemAt(1).widget(), QLabel):
                                sw = lay.itemAt(1).widget()
                                sw.setParent(None)  # remove dari layout
                            widget.repaint()
                            break
                    self.file_list.repaint()
                    QCoreApplication.processEvents()
                                
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
        
    def _add_duplicate_file_to_list(self, file_path: Path, duplicate_info: Dict[str, any]):
        """Add a duplicate file to the list widget with special styling and SKIP label"""
        logging.info(f"  DEBUG: _add_duplicate_file_to_list called for {file_path.name}")
        logging.info(f"  DEBUG: duplicate_info = {duplicate_info}")
        
        item = QListWidgetItem()
        item.setData(Qt.UserRole, file_path)
        # Mark this item as duplicate so it won't be processed
        
        logging.info(f"  DEBUG: Set item data - UserRole: {file_path}, UserRole+1: DUPLICATE")
        
        # Create widget untuk item
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # File name label with strikethrough
        file_name = truncate_text(file_path.name, 25)
        file_label = QLabel(file_name)
        file_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.SECONDARY};
                font-size: 12px;
                font-weight: bold;
                text-decoration: line-through;
            }}
        """)
        layout.addWidget(file_label)
        
        # Duplicate status
        patient_id = duplicate_info.get("patient_id", "Unknown")
        study_date = duplicate_info.get("study_date", "Unknown")
        reason = duplicate_info.get("reason", "Duplicate")
        
        if "within current selection" in reason:
            status_text = f"🔄 Duplicate in selection"
            tooltip_text = f"Patient: {patient_id}, Study Date: {study_date}\nAnother file with same Patient ID and Study Date already selected"
        else:
            existing_count = duplicate_info.get("existing_dicom_count", 0)
            status_text = f"Already analyzed"
            tooltip_text = f"Patient: {patient_id}, Study Date: {study_date}\nData sudah dianalisis sebelumnya"
        
        status_label = QLabel(status_text)
        status_label.setToolTip(tooltip_text)
        status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.WARNING};
                font-size: 10px;
                font-style: italic;
                font-weight: bold;
            }}
        """)
        layout.addWidget(status_label)
        
        # File path label (dimmed)
        path_text = truncate_text(str(file_path.parent), 30)
        path_label = QLabel(path_text)
        path_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.BORDER_MEDIUM};
                font-size: 9px;
                font-style: italic;
            }}
        """)
        layout.addWidget(path_label)
        
        layout.addStretch()
        
        item.setSizeHint(widget.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, widget)
    
    def _add_already_analyzed_file_to_list(self, file_path: Path, patient_id: str, study_date: str):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, file_path)
        item.setData(Qt.UserRole + 1, "ALREADY_ANALYZED")  # penanda untuk skip saat import

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4); layout.setSpacing(8)

        # Nama file (dim)
        file_label = QLabel(truncate_text(file_path.name, 25))
        file_label.setStyleSheet(f"QLabel {{ color: {Colors.SECONDARY}; font-size: 12px; font-weight: 600; }}")
        layout.addWidget(file_label)

        # Badge “already analyzed”
        badge = QLabel("already analyzed")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(20)
        badge.setStyleSheet(f"""
            QLabel {{
                background: {Colors.WARNING};
                color: white;
                font-size: 10px;
                font-weight: bold;
                border-radius: 4px;
                padding: 2px 8px;
                border: 1px solid #e0a800;
            }}
        """)

        badge.setToolTip(f"Patient: {patient_id} • Study: {study_date}")
        layout.addWidget(badge)

        # Path (lebih kecil & abu)
        path_label = QLabel(truncate_text(str(file_path.parent), 30))
        path_label.setStyleSheet(f"QLabel {{ color: {Colors.BORDER_MEDIUM}; font-size: 9px; font-style: italic; }}")
        layout.addWidget(path_label)

        layout.addStretch()

        # Tombol remove
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet(DIALOG_REMOVE_BUTTON_STYLE)
        remove_btn.clicked.connect(lambda: self._remove_file(item))
        layout.addWidget(remove_btn)

        widget.setMinimumHeight(42)
        widget.setStyleSheet(f"""
            QWidget {{
                background: rgba(255, 243, 205, 0.6);   /* soft yellow */
                border: 1px dashed {Colors.WARNING};
                border-radius: 4px;
            }}
        """)
        item.setSizeHint(widget.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, widget)

    
    def _remove_file(self, item: QListWidgetItem):
        """Remove 1 item dari UI + bersihkan seluruh state terkait:
        - selected_files, view_assignments, file_detection_status,
        - mapping _file_key_map dan set _present_patient_study_keys (supaya bisa ditambah lagi bersih).
        """
        file_path = item.data(Qt.UserRole)

        # Hapus dari selected_files (kalau ada)
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)

        # Bersihkan assignment & detection
        if file_path in self.view_assignments:
            del self.view_assignments[file_path]
        if file_path in self.file_detection_status:
            del self.file_detection_status[file_path]

        # Bersihkan key (PID, SD) yang dicatat utk redundancy tracking
        if not hasattr(self, "_present_patient_study_keys"):
            self._present_patient_study_keys = set()
        if not hasattr(self, "_file_key_map"):
            self._file_key_map = {}

        if file_path in self._file_key_map:
            key = self._file_key_map.pop(file_path, None)
            if key and key in self._present_patient_study_keys:
                self._present_patient_study_keys.remove(key)

        # Hapus dari UI list
        row = self.file_list.row(item)
        self.file_list.takeItem(row)

        # Update UI state
        self._update_ui_state()

        file_name = truncate_text(file_path.name, 40)
        self.logger.info(f"[REMOVE] Removed {file_name} dari import list")
        
    def _configure_views(self):
        """Open view configuration dialog"""
        if not self.selected_files:
            QMessageBox.warning(self, "Warning", "Please add DICOM files first!")
            return
        
        #   FIXED: Check if dialog is already open
        if hasattr(self, '_view_dialog') and self._view_dialog:
            logging.info("⚠️ WARNING: View dialog already open, bringing to front...")
            self._view_dialog.raise_()
            self._view_dialog.activateWindow()
            return
        
        #   FIXED: Validate that all files have detection status
        missing_detection = []
        for file_path in self.selected_files:
            if file_path not in self.file_detection_status:
                missing_detection.append(file_path)
        
        if missing_detection:
            logging.info(f"⚠️ WARNING: {len(missing_detection)} files missing detection status, starting analysis...")
            self.logger.info(f"⚠️ Analyzing {len(missing_detection)} files without detection status...")
            
            # Start detection for missing files
            self._start_quick_detection(missing_detection)
            
            # Show message and return
            QMessageBox.information(
                self,
                "Analysis in Progress", 
                f"Please wait for analysis to complete for {len(missing_detection)} files, then try again."
            )
            return
            
        self.logger.info("  Opening enhanced view configuration dialog...")
        logging.info(f"  DEBUG: Opening view selector with {len(self.selected_files)} files")
        
        #   FIXED: Create dialog and store reference
        try:
            self.logger.info(f"  DEBUG: Opening view configuration with {len(self.selected_files)} files:")
            for i, file_path in enumerate(self.selected_files):
                self.logger.info(f"   {i+1}. {file_path.name}")

            # Check if any of these files are marked as duplicates
            duplicate_in_selection = 0
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                item_path = item.data(Qt.UserRole)
                item_duplicate_flag = item.data(Qt.UserRole + 1)
                
                if item_path in self.selected_files and item_duplicate_flag == "DUPLICATE":
                    duplicate_in_selection += 1
                    self.logger.info(f"   ⚠️ WARNING: {item_path.name} is in selected_files but marked as DUPLICATE")

            if duplicate_in_selection > 0:
                self.logger.info(f"   🚨 PROBLEM: {duplicate_in_selection} duplicate files in selected_files!")
            else:
                self.logger.info(f"     No duplicates found in selected_files")
            self._view_dialog = DicomViewSelectorDialog(self.selected_files, self)
            
            def on_views_confirmed_debug(view_assignments):
                logging.info(f"  DEBUG: Signal received! Processing {len(view_assignments)} assignments")
                self._on_views_configured(view_assignments)
                #   FIXED: Clear dialog reference after use
                self._view_dialog = None
            
            def on_dialog_finished():
                logging.info("  DEBUG: Dialog finished, cleaning up...")
                #   FIXED: Clear dialog reference when closed
                self._view_dialog = None
                self._update_ui_state()
                QCoreApplication.processEvents()
            
            logging.info("  DEBUG: Connecting signals...")
            self._view_dialog.views_confirmed.connect(on_views_confirmed_debug)
            self._view_dialog.finished.connect(on_dialog_finished)
            
            logging.info("  DEBUG: Executing dialog...")
            result = self._view_dialog.exec()
            
            logging.info(f"  DEBUG: View dialog result: {result}")
            if result == QDialog.Rejected:
                self.logger.info(" View configuration cancelled")
            elif result == QDialog.Accepted:
                logging.info("  Dialog accepted")
            
        except Exception as e:
            logging.info(f" ERROR creating view dialog: {e}")
            import traceback
            traceback.print_exc()
            self.logger.info(f" Error opening view configuration: {str(e)}")
            
            #   FIXED: Clear dialog reference on error
            self._view_dialog = None
        
        #   FIXED: Force cleanup and UI refresh
        self._view_dialog = None
        self._update_ui_state()
        QCoreApplication.processEvents()
        
    def _on_views_configured(self, payload: Dict[str, any]):
        """Handle confirmed view assignments with background selections"""
        logging.info(f"  DEBUG: _on_views_configured called with payload keys: {list(payload.keys())}")
        
        
        # Debug: Check what files are in the payload
        if isinstance(payload, dict) and "view_assignments" in payload:
            view_assignments = payload["view_assignments"]
            logging.info(f"  DEBUG: view_assignments contains {len(view_assignments)} files")
            for file_key in view_assignments.keys():
                logging.info(f"   📄 {file_key}")
            background_assignments = payload.get("background_assignments", {})
            logging.info(f"🎨 Background assignments received: {len(background_assignments)} files")
        else:
            # Legacy format (backward compatibility)
            view_assignments = payload
            background_assignments = {}
            logging.info("⚠️ Legacy format detected - no background assignments")

        # Normalize keys to Path objects
        normalized_views = {}
        normalized_backgrounds = {}
        
        for k, v in view_assignments.items():
            p = Path(k) if not isinstance(k, Path) else k
            normalized_views[p] = v
        
        for k, v in background_assignments.items():
            p = Path(k) if not isinstance(k, Path) else k
            normalized_backgrounds[p] = v

        self.view_assignments = normalized_views
        self.background_assignments = normalized_backgrounds  # Store background data
        
        self.logger.info("  View assignments and background selections configured")
        self.logger.info(f"Files with assignments: {len(view_assignments)}")
        if background_assignments:
            self.logger.info(f"Files with background selections: {len(background_assignments)}")
    
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
                        
                        # Check if this was originally auto-tagged
                        detection_info = self.file_detection_status.get(file_path, {})
                        was_auto_configured = detection_info.get("has_reliable_detection", False) and not detection_info.get("needs_manual_config", True)
                        
                        if has_anterior and has_posterior:
                            status_widget.setText("")  # clean, tanpa badge
                            status_widget.setStyleSheet(f"QLabel {{ color: {Colors.SECONDARY}; font-size: 10px; }}")
                        else:
                            status_widget.setText("⚠️ Incomplete")
                            status_widget.setStyleSheet(f"QLabel {{ color: {Colors.WARNING}; font-size: 10px; font-weight: bold; }}")
        
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
        
        # Update Configure Views button state
        self.configure_views_btn.setEnabled(has_files)
        if has_files:
            self.configure_views_btn.setText("Review Data")
            self.configure_views_btn.setToolTip("Review data sebelum import.")
            self.configure_views_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        else:
            self.configure_views_btn.setText("Review Data")
            self.configure_views_btn.setToolTip("Add DICOM files first")
            self.configure_views_btn.setStyleSheet(DIALOG_DISABLED_BUTTON_STYLE)
        
        # Update Start Import button state
        self.start_import_btn.setEnabled(has_files and has_complete_assignments and has_session)
        if has_complete_assignments:
            auto_count = sum(1 for fp in self.view_assignments.keys() 
                             if self.file_detection_status.get(fp, {}).get("has_reliable_detection", False) 
                             and not self.file_detection_status.get(fp, {}).get("needs_manual_config", True))
            if auto_count == len(self.view_assignments):
                self.start_import_btn.setText("Start Import")
            elif auto_count > 0:
                self.start_import_btn.setText("Start Import")
            else:
                self.start_import_btn.setText("Start Import")
            self.start_import_btn.setStyleSheet(DIALOG_START_BUTTON_STYLE)
        else:
            self.start_import_btn.setText("Start Import")
            self.start_import_btn.setStyleSheet(DIALOG_DISABLED_BUTTON_STYLE) # Gunakan style abu-abu yang sama

        # Update tooltips for Start Import button
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
                self.start_import_btn.setText("Start Import")
            elif auto_count > 0:
                self.start_import_btn.setText("Start Import")
            else:
                self.start_import_btn.setText("Start Import")
        else:
            self.start_import_btn.setText("Start Import")
    
    def _start_import(self):
        """Mulai proses import:
        - Filter keluar item yang ditandai 'ALREADY_ANALYZED' (dan 'DUPLICATE' bila masih ada sisa lama).
        - Proses hanya file NEW yang sudah punya assignment.
        """
        if not self.selected_files or not self.view_assignments or not self.session_code:
            QMessageBox.warning(self, "Warning", "Please complete view configuration first!")
            return

        actual_files_to_process: Dict[Path, Dict[int, str]] = {}
        skipped_marked = 0

        self.logger.info("[START_IMPORT] Mulai filter item yang boleh diproses...")
        self.logger.info(f"[START_IMPORT] assignments: {len(self.view_assignments)} files, list items: {self.file_list.count()}")

        # Cek flag pada item UI; skip kalau ALREADY_ANALYZED atau DUPLICATE
        for file_path, assignments in self.view_assignments.items():
            is_marked_skip = False
            found_in_list = False

            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                item_path = item.data(Qt.UserRole)
                if item_path != file_path:
                    continue

                found_in_list = True
                flag = item.data(Qt.UserRole + 1)
                self.logger.info(f"[START_IMPORT]   {file_path.name} flag={flag}")
                if flag in ("ALREADY_ANALYZED", "DUPLICATE"):
                    is_marked_skip = True
                    skipped_marked += 1
                break

            if not found_in_list:
                self.logger.info(f"[START_IMPORT]   WARNING: {file_path.name} tidak ditemukan di UI list")

            if not is_marked_skip:
                actual_files_to_process[file_path] = assignments
                self.logger.info(f"[START_IMPORT]   -> queued")
            else:
                self.logger.info(f"[START_IMPORT]   -> skipped (flagged)")

        self.logger.info(f"[START_IMPORT] queued={len(actual_files_to_process)}, skipped_flagged={skipped_marked}")

        # Update view_assignments dengan hanya yang boleh diproses
        self.view_assignments = actual_files_to_process

        if not self.view_assignments:
            QMessageBox.warning(self, "Warning", "No valid files to process after filtering!")
            return

        # Hitung ringkasan auto/manual (opsional – tidak memengaruhi UI badge)
        auto_configured_count = 0
        manual_configured_count = 0
        for fp in self.view_assignments.keys():
            det = self.file_detection_status.get(fp, {})
            if det.get("has_reliable_detection", False) and not det.get("needs_manual_config", True):
                auto_configured_count += 1
            else:
                manual_configured_count += 1

        self.logger.info("[START_IMPORT] Start processing...")
        self.logger.info(f"[START_IMPORT] total to process: {len(self.view_assignments)} (auto={auto_configured_count}, manual={manual_configured_count})")
        self.logger.info(f"[START_IMPORT] Session: {self.session_code} → data/PLANAR/{self.session_code}/[patient_id]/")

        # Disable UI dan set progress
        self.add_dicom_btn.setEnabled(False)
        self.add_folders_btn.setEnabled(False)
        self.configure_views_btn.setEnabled(False)
        self.start_import_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)

        # progress bar pakai skala 0–100 (bukan jumlah file)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        # tampilkan persen global di bar
        self.progress_bar.setFormat(" 0% ")
        self.progress_bar.setAlignment(Qt.AlignCenter)

        # Jalankan thread processing
        self.processing_thread = ProcessingThread(
            self.view_assignments,
            getattr(self, 'background_assignments', {}),
            self.data_root,
            self.session_code,
        )
        self.processing_thread.progress_and_status_updated.connect(self._on_progress_and_status_updated)
        self.processing_thread.finished_processing.connect(self._on_processing_finished)
        self.processing_thread.start()
        
    def _on_progress_and_status_updated(self, current: int, total: int, filename: str, step_message: str, step_progress: float):
        # Hitung total langkah per file (pastikan ini akurat)
        TOTAL_STEPS_PER_FILE = 7

        sp = step_progress if step_progress is not None else 0.0
        if sp > 1.0:
            sp = sp / float(TOTAL_STEPS_PER_FILE)
        # clamp
        if sp < 0.0: sp = 0.0
        if sp > 1.0: sp = 1.0

        # progress global = ((file_index_selesai) + progress_file_ini) / total_files * 100
        # catatan: current = indeks file berjalan (1-based)
        if total <= 0:
            global_progress = 0
        else:
            global_progress = int( ((max(current,1) - 1) + sp) / float(total) * 100 )

        # progress per-file (untuk info teks saja)
        in_file_progress = int(sp * 100)

        # 1) progress bar menampilkan GLOBAL progress
        self.progress_bar.setValue(global_progress)
        self.progress_bar.setFormat(f" {global_progress}% ")

        # 2) label menampilkan detail per-file + pesan langkah
        file_name = truncate_text(Path(filename).name, 25)
        self.progress_label.setText(
            f"Processing: {file_name} ({current}/{total}) - {step_message}"
        )

        QCoreApplication.processEvents()
            
    def _on_processing_finished(self):
        """Handle processing completion with enhanced summary"""
        auto_configured_count = sum(1 for fp in self.view_assignments.keys() 
                                  if self.file_detection_status.get(fp, {}).get("has_reliable_detection", False) 
                                  and not self.file_detection_status.get(fp, {}).get("needs_manual_config", True))
        manual_configured_count = len(self.view_assignments) - auto_configured_count
        
        self.logger.info("🎉 Enhanced import workflow completed!")
        self.logger.info("All files processed with proper Anterior/Posterior naming")
        
        if auto_configured_count > 0 and manual_configured_count > 0:
            self.logger.info(f"  Successfully processed: {auto_configured_count} auto + {manual_configured_count} manual files")
        elif auto_configured_count == len(self.view_assignments):
            self.logger.info(f"  Successfully processed: All {auto_configured_count} auto-tagged files")
        else:
            self.logger.info(f"  Successfully processed: All {manual_configured_count} manually configured files")
        
        self.logger.info("Rescanning folder...")

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
            config_summary = f"(all {auto_configured_count} auto-tagged)"
        else:
            config_summary = f"(all {manual_configured_count} manually configured)"
        
        QMessageBox.information(
            self,
            "Import Successful",
            f"Successfully processed {processed_count} DICOM files! {config_summary}\n\n"
            "  All files have proper Anterior/Posterior view assignments\n"
            "  Complete processing pipeline executed\n"
            "  Enhanced auto-detection workflow completed\n\n"
            "Files are now ready for viewing and analysis."
        )
        self.accept()
        
    def _cancel_import(self):
        """Cancel the import process"""
        #   FIXED: Clean up view dialog if open
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
    DicomImportDialog(data_root, parent, session_code)


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
            session_path = data_root / "PLANAR" / session_code
            try:
                session_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return False, f"Cannot create session directory: {e}"
        
        
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
        "cloud_storage_available": False,  #   Changed to False
        "supported_extensions": [".dcm", ".dicom"],
        "max_files_per_import": 50,
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
        logging.info(f"Validation failed: {error_msg}")
        return
    
    # Show dialog
    use_enhanced = mode.lower() == "enhanced"
    dialog = create_dicom_import_dialog(
        data_root=test_data_root,
        session_code=session_code,
        use_enhanced_mode=use_enhanced
    )
    
    logging.info(f"Testing {mode} mode import dialog...")
    result = dialog.exec()
    
    if result == QDialog.Accepted:
        logging.info("  Import completed successfully")
    else:
        logging.info(" Import cancelled")
    
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
            logging.info(f"  Testing detection on: {file_path.name}")
            
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
            
            logging.info(f"  Reliable detection: {has_reliable}")
            logging.info(f"  Needs manual config: {needs_manual}")
            logging.info(f"  Auto configured: {auto_count}")
            logging.info(f"  Manual required: {manual_count}")
            
            if has_reliable and not needs_manual:
                logging.info(f"    Status: Fully auto-tagged")
            elif has_reliable and needs_manual:
                logging.info(f"  ⚠️ Status: Partially auto-tagged")
            else:
                logging.info(f"   Status: Manual configuration required")
            
        except Exception as e:
            logging.info(f"   Error testing {file_path.name}: {e}")
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
                logging.info(f"⚠️ File not found: {file_path}")
                continue
            
            if not file_path.suffix.lower() in ['.dcm', '.dicom']:
                logging.info(f"⚠️ Invalid file extension: {file_path}")
                continue
            
            try:
                # Quick DICOM validation
                import pydicom
                ds = pydicom.dcmread(file_path, stop_before_pixels=True)
                if not hasattr(ds, 'PatientID'):
                    logging.info(f"⚠️ Invalid DICOM (no PatientID): {file_path}")
                    continue
                
                valid_files.append(file_path)
                
            except Exception as e:
                logging.info(f"⚠️ DICOM validation failed for {file_path}: {e}")
                continue
        
        if not valid_files:
            raise ImportValidationError("No valid DICOM files found")
        
        logging.info(f"  Validated {len(valid_files)} of {len(file_paths)} files")
        
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
            "cloud_integration": False,
            "legacy_compatibility": True
        },
        "supported_formats": SUPPORTED_DICOM_EXTENSIONS
    }

def _reset_import_state(self):
    """Reset import state when file list changes"""
    logging.info("  DEBUG: Resetting import state...")
    
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
    
    logging.info("  Import state reset completed")