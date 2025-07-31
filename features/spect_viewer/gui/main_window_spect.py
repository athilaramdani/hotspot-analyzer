# features/spect_viewer/gui/main_window_spect.py - FIXED: XML detection with study date
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Dict, List
import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout, QDialog, QApplication, QLabel
)
from PySide6.QtGui import QCloseEvent
import multiprocessing

# Import NEW config paths and session management
from core.config.paths import (
    get_session_spect_path,
    get_patient_spect_path,
    SPECT_DATA_PATH,
    generate_filename_stem
)
from core.config.sessions import get_current_session

# Import NEW directory scanner for new structure
# Langkah 1: Hapus baris yang salah
from features.dicom_import.logic.directory_scanner import (
    scan_spect_directory_new_structure,
    get_session_patients,
    get_patient_dicom_files
)

# ===== TAMBAHKAN IMPORT LOADING DIALOG =====
from core.gui.loading_dialog import SPECTLoadingDialog
# ===========================================
from features.spect_viewer.logic.processing_wrapper import run_yolo_detection_for_patient, run_hotspot_processing_in_process
from features.dicom_import.logic.dicom_loader import load_frames_and_metadata, extract_study_date_from_dicom
from features.spect_viewer.logic.hotspot_processor import HotspotProcessor
from core.utils.image_converter import load_frames_and_metadata_matrix

# Import the new dialog
from features.dicom_import.gui.dicom_import_dialog_v2 import DicomImportDialog
from core.gui.ui_constants import (
    PRIMARY_BUTTON_STYLE,     # blue "Import DICOM…" button
    SUCCESS_BUTTON_STYLE,     # green "Rescan Folder" button
    GRAY_BUTTON_STYLE,        # grey "Logout" button
    ZOOM_BUTTON_STYLE,        # orange "Zoom In/Out" buttons
    SCAN_BUTTON_STYLE,        # purple "Scan N" buttons
)

from core.gui.searchable_combobox import SearchableComboBox
from core.gui.patient_info_bar import PatientInfoBar
from .scan_timeline import ScanTimelineWidget
from .side_panel import SidePanel
from .mode_selector import ModeSelector
from .view_selector import ViewSelector
from features.spect_viewer.logic.processing_wrapper import run_yolo_detection_for_patient, run_hotspot_processing_in_process,run_segmentation_in_process

class MainWindowSpect(QMainWindow):
    logout_requested = Signal()
    
    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        super().__init__()
        self.setWindowTitle(f"Hotspot Analyzer - Session: {session_code or 'Unknown'}")
        self.resize(1600, 900)
        self.session_code = session_code
        self.pool = multiprocessing.Pool(processes=1)
        self.data_root = data_root
        print(f"[DEBUG] session_code in MainWindow = {self.session_code}")

        # NEW: Store session-patient mapping from new structure
        self._session_patients_map: Dict[str, List[str]] = {}
        self._loaded: Dict[str, List[Dict]] = {}
        self.scan_buttons: List[QPushButton] = []

        self._build_ui()
        self._scan_folder()

    def _build_ui(self) -> None:
        # --- Top Bar ---
        top_actions = QWidget()
        top_layout = QHBoxLayout(top_actions)

        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)
        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)
        top_layout.addWidget(self.patient_bar)
        top_layout.addStretch()

        # Import and action buttons
        import_btn = QPushButton("Import DICOM…")
        import_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        import_btn.clicked.connect(self._show_import_dialog)
        
        rescan_btn = QPushButton("Rescan Folder")
        rescan_btn.setStyleSheet(SUCCESS_BUTTON_STYLE)
        rescan_btn.clicked.connect(self._scan_folder)
        
        # View selector (keep on top bar)
        self.view_selector = ViewSelector()
        self.view_selector.view_changed.connect(self._set_view)

        top_layout.addWidget(import_btn)
        top_layout.addWidget(rescan_btn)
        top_layout.addWidget(self.view_selector)

        # Logout button
        logout_btn = QPushButton("Logout")
        logout_btn.setStyleSheet(GRAY_BUTTON_STYLE)
        logout_btn.clicked.connect(self._handle_logout)
        top_layout.addWidget(logout_btn)
        
        # --- Scan & Zoom Buttons ---
        view_button_widget = QWidget()
        view_button_layout = QHBoxLayout(view_button_widget)
        self.scan_button_container = QHBoxLayout()
        view_button_layout.addLayout(self.scan_button_container)
        view_button_layout.addStretch()
        
        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.clicked.connect(self.zoom_out)
        
        # Styling untuk zoom buttons
        zoom_in_btn.setStyleSheet(ZOOM_BUTTON_STYLE)
        zoom_out_btn.setStyleSheet(ZOOM_BUTTON_STYLE)
        
        view_button_layout.addWidget(zoom_in_btn)
        view_button_layout.addWidget(zoom_out_btn)

        # --- Main Splitter (RESIZABLE LAYOUT: Mode Selector | Timeline | Side Panel) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT PANEL: Mode selector (RESIZABLE - no fixed width)
        left_panel = QWidget()
        left_panel.setMinimumWidth(200)   # Minimum width only
        left_panel.setMaximumWidth(500)   # Maximum width for usability
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        
        # Panel title untuk clarity
        title_label = QLabel("<b>Layer Controls</b>")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #495057;
                padding: 8px;
                background: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #e9ecef;
                margin-bottom: 8px;
            }
        """)
        left_layout.addWidget(title_label)
        
        # NEW: Enhanced mode selector with checkboxes
        self.mode_selector = ModeSelector()
        
        # Connect NEW signals for checkbox-based mode selector
        self.mode_selector.layers_changed.connect(self._on_layers_changed)
        self.mode_selector.opacity_changed.connect(self._set_layer_opacity)
        
        left_layout.addWidget(self.mode_selector)
        left_layout.addStretch()
        
        main_splitter.addWidget(left_panel)

        # MIDDLE PANEL: Timeline untuk menampilkan gambar
        self.timeline_widget = ScanTimelineWidget()
        self.timeline_widget.set_session_code(self.session_code)
        
        # FIXED: Connect timeline scan selection signal to sync with scan buttons
        self.timeline_widget.scan_selected.connect(self._on_timeline_scan_selected)
        
        main_splitter.addWidget(self.timeline_widget)

        # RIGHT PANEL: Grafik dan ringkasan
        self.side_panel = SidePanel()
        main_splitter.addWidget(self.side_panel)
        
        # Set splitter proportions: Mode Selector | Timeline | Side Panel
        # Make all panels resizable with proper ratios
        main_splitter.setStretchFactor(0, 1)  # Mode selector: resizable
        main_splitter.setStretchFactor(1, 3)  # Timeline: gets most space
        main_splitter.setStretchFactor(2, 1)  # Side panel: resizable
        main_splitter.setSizes([280, 900, 320])  # Initial sizes (total: 1500)
        
        # Style the splitter handles for better visibility
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e9ecef;
                width: 4px;
                margin: 2px 0px;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #4e73ff;
            }
            QSplitter::handle:pressed {
                background-color: #324fc7;
            }
        """)

        # --- Perakitan Final ---
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(top_actions)
        main_layout.addWidget(view_button_widget)
        main_layout.addWidget(main_splitter, stretch=1)
        self.setCentralWidget(main_widget)

    # FIXED: NEW method to handle timeline scan selection
    def _on_timeline_scan_selected(self, scan_index: int):
        """Handle scan selection from timeline widget"""
        print(f"[DEBUG] Timeline scan selected signal received: {scan_index}")
        
        # Update scan buttons to reflect selection
        for i, btn in enumerate(self.scan_buttons):
            btn.setChecked(i == scan_index)
        
        # Update side panel with selected scan data
        try:
            id_text = self.patient_bar.id_combo.currentText()
            if not id_text.startswith("ID: "):
                print(f"[DEBUG] Invalid format: {id_text}")
                return
                
            remainder = id_text[4:]  # Remove "ID: "
            patient_id = remainder.split(" (")[0]  # "12"
            session_part = remainder.split(" (")[1]  # "NSY)"
            session = session_part.rstrip(")")  # "NSY"
            
            cache_key = f"{patient_id}_{session}"
            scans = self._loaded.get(cache_key, [])
            
            if scans and scan_index < len(scans):
                selected_scan = scans[scan_index]
                self.side_panel.set_chart_data(scans)
                self.side_panel.set_summary(selected_scan["meta"])
                print(f"[DEBUG] Updated side panel for scan {scan_index + 1}")
                
        except (IndexError, AttributeError) as e:
            print(f"[DEBUG] Failed to update side panel: {e}")

    # NEW: Handle checkbox-based layer changes
    def _on_layers_changed(self, active_layers: list) -> None:
        """Handle layer selection changes from checkbox mode selector"""
        # Cek apakah "Hotspot" baru saja diaktifkan
        if "Hotspot" in active_layers and not self.timeline_widget.is_layer_active("Hotspot"):
            # Jalankan proses pembuatan gambar hotspot di background
            self._run_hotspot_processing_on_demand()
        
        self.timeline_widget.set_active_layers(active_layers)

    def _set_layer_opacity(self, layer: str, opacity: float) -> None:
        """Handle layer opacity changes from mode selector"""
        print(f"[DEBUG] Setting {layer} opacity to {opacity:.2f}")
        self.timeline_widget.set_layer_opacity(layer, opacity)

    def _set_view(self, v: str) -> None:
        """Set active view"""
        print(f"[DEBUG] Setting view to: {v}")
        self.timeline_widget.set_active_view(v)

    # UPDATED: Enhanced scan button click handler for checkbox system
    def _on_scan_button_clicked(self, index: int) -> None:
        """Handle scan button click with checkbox mode support"""
        print(f"[DEBUG] Scan button {index + 1} clicked")
        
        # Get current active layers and sync timeline settings
        active_layers = self.mode_selector.get_active_layers()
        self.timeline_widget.set_active_layers(active_layers)
        
        # Sync all opacity settings from mode selector to timeline
        all_opacities = self.mode_selector.get_all_opacities()
        for layer, opacity in all_opacities.items():
            self.timeline_widget.set_layer_opacity(layer, opacity)
        
        # Update button display
        for i, btn in enumerate(self.scan_buttons):
            btn.setChecked(i == index)

        # Get current patient data
        try:
            id_text = self.patient_bar.id_combo.currentText()
            # Parse "ID: 12 (NSY)" format correctly
            if not id_text.startswith("ID: "):
                print(f"[DEBUG] Invalid format: {id_text}")
                return
                
            remainder = id_text[4:]  # Remove "ID: "
            patient_id = remainder.split(" (")[0]  # "12"
            session_part = remainder.split(" (")[1]  # "NSY)"
            session = session_part.rstrip(")")  # "NSY"
            
            cache_key = f"{patient_id}_{session}"
        except (IndexError, AttributeError):
            print("[DEBUG] Failed to get current patient ID")
            return

        # Load scan data
        scans = self._loaded.get(cache_key, []) 

        if not scans or index >= len(scans):
            print(f"[DEBUG] Invalid scan index {index} for patient {cache_key}")
            return
        
        selected_scan = scans[index]

        # Update timeline display with current settings
        self.timeline_widget.display_timeline(scans, active_index=index)

        # Update side panel
        self.side_panel.set_chart_data(scans)
        self.side_panel.set_summary(selected_scan["meta"])
        
        print(f"[DEBUG] Displaying {len(scans)} scans in timeline with layers: {active_layers}")

    # UPDATED: Remove old _set_mode method, add layer management methods
    def reset_mode_selector(self):
        """Reset mode selector to default values"""
        self.mode_selector.reset_to_defaults()
        self.timeline_widget.set_active_layers([])
        
        # Reset all opacity values in timeline
        default_opacities = {
            "Original": 1.0,
            "Segmentation": 0.7,
            "Hotspot": 0.8
        }
        for layer, opacity in default_opacities.items():
            self.timeline_widget.set_layer_opacity(layer, opacity)

    def set_default_layers(self):
        """Set default layer configuration (Original only)"""
        self.mode_selector.set_layer_active("Original", True)
        
    def get_current_layer_status(self) -> dict:
        """Get current layer status for debugging/logging"""
        return {
            "active_layers": self.mode_selector.get_active_layers(),
            "opacities": self.mode_selector.get_all_opacities(),
            "both_mode": self.mode_selector.is_both_mode(),
            "has_active_layers": self.mode_selector.has_any_active_layers()
        }

    # BACKWARD COMPATIBILITY: Keep old method names but adapt to new system
    def _set_mode(self, mode: str) -> None:
        """Backward compatibility method for old mode system"""
        print(f"[DEBUG] Legacy mode set to: {mode} - converting to layer system")
        
        # Reset all layers first
        self.mode_selector.reset_to_defaults()
        
        # Convert old mode to layer selections
        if mode == "Original":
            self.mode_selector.set_layer_active("Original", True)
        elif mode == "Segmentation":
            self.mode_selector.set_layer_active("Original", True)
            self.mode_selector.set_layer_active("Segmentation", True)
        elif mode == "Hotspot":
            self.mode_selector.set_layer_active("Original", True)
            self.mode_selector.set_layer_active("Hotspot", True)
        elif mode == "Both":
            self.mode_selector.set_layer_active("Both", True)
        
        # Refresh current scan if any is selected
        if hasattr(self, 'scan_buttons'):
            for i, btn in enumerate(self.scan_buttons):
                if btn.isChecked():
                    self._on_scan_button_clicked(i)
                    break

    def _handle_logout(self):
        """Emits the logout signal and closes the window."""
        self.logout_requested.emit()
        self.close()
    
    def closeEvent(self, event: QCloseEvent):
        print("[DEBUG] Membersihkan sumber daya di MainWindow (SPECT)...")
        print("[DEBUG] Menutup process pool...")
        self.pool.close()
        self.pool.join()
        print("[DEBUG] Process pool ditutup.")
        if hasattr(self, 'timeline_widget') and hasattr(self.timeline_widget, 'cleanup'):
            self.timeline_widget.cleanup()
        if hasattr(self, 'side_panel') and hasattr(self.side_panel, 'cleanup'):
            self.side_panel.cleanup()
        super().closeEvent(event)
    def _run_hotspot_processing_on_demand(self):
        """
        Memicu proses hotspot (Otsu) untuk pasien yang sedang aktif.
        """
        try:
            id_text = self.patient_bar.id_combo.currentText()
            if not id_text.startswith("ID: "): return
            
            remainder = id_text[4:]
            patient_id = remainder.split(" (")[0]
            session = remainder.split(" (")[1].rstrip(")")
            
            cache_key = f"{patient_id}_{session}"
            scans = self._loaded.get(cache_key, [])
            if not scans: return

            print("[DEBUG] Memicu proses hotspot on-demand...")
            
            # Tampilkan dialog loading
            loading_dialog = SPECTLoadingDialog("Processing Hotspots...", parent=self)
            loading_dialog.show()
            QApplication.processEvents()

            hotspot_jobs = []
            for scan_data in scans:
                dicom_file = scan_data["path"]
                job = self.pool.apply_async(
                    run_hotspot_processing_in_process, 
                    args=(dicom_file, patient_id)
                )
                hotspot_jobs.append(job)
            
            # Tunggu semua proses selesai
            for job in hotspot_jobs:
                job.get(timeout=180)

            loading_dialog.close()
            print("[DEBUG] Proses hotspot on-demand selesai. Merefresh timeline...")
            
            # [PENTING] Refresh timeline untuk memuat file yang baru dibuat
            self.timeline_widget.refresh_current_view()

        except Exception as e:
            print(f"[ERROR] Gagal menjalankan proses hotspot on-demand: {e}")
            if 'loading_dialog' in locals() and loading_dialog:
                loading_dialog.close()

    def _show_import_dialog(self) -> None:
        """Show the updated import dialog"""
        print("[DEBUG] Opening DICOM import dialog...")
        
        dlg = DicomImportDialog(
            data_root=self.data_root, 
            parent=self, 
            session_code=self.session_code
        )
        
        # Connect signal untuk auto-rescan setelah import
        dlg.files_imported.connect(self._on_files_imported)
        
        # Show dialog
        result = dlg.exec()
        
        if result == QDialog.Accepted:
            print("[DEBUG] Import dialog accepted")
        else:
            print("[DEBUG] Import dialog cancelled")

    def _on_files_imported(self):
        """Handle files imported signal"""
        print("[DEBUG] Files imported signal received, rescanning folder...")
        self._scan_folder()

    def _scan_folder(self) -> None:
        """Scan folder using NEW directory structure - FIXED to filter by current session only"""
        print(f"[DEBUG] Starting folder scan for session: {self.session_code}")
        
        id_combo = self.patient_bar.id_combo
        id_combo.clear()
        
        # Use NEW directory scanner for new structure
        all_sessions_map = scan_spect_directory_new_structure(SPECT_DATA_PATH)
        print(f"[DEBUG] Found {len(all_sessions_map)} total sessions: {list(all_sessions_map.keys())}")
        
        # FIXED: Only use current session if specified
        if self.session_code:
            if self.session_code in all_sessions_map:
                # Only show patients from current session
                session_patients = {self.session_code: all_sessions_map[self.session_code]}
                print(f"[DEBUG] Filtered to session {self.session_code}: {len(session_patients[self.session_code])} patients")
            else:
                # Session not found, show empty
                session_patients = {}
                print(f"[DEBUG] Session {self.session_code} not found in data")
        else:
            # No session specified, show all (fallback)
            session_patients = all_sessions_map
            print(f"[DEBUG] No session filter, showing all sessions")
        
        self._session_patients_map = session_patients
        
        # Populate combo box with patients from filtered sessions only
        all_patients = []
        for session, patients in session_patients.items():
            for patient_id in patients.keys():
                display_text = f"ID: {patient_id} ({session})"
                all_patients.append((display_text, patient_id, session))
        
        # Sort by patient ID
        all_patients.sort(key=lambda x: x[1])
        
        # Add to combo box
        for display_text, patient_id, session in all_patients:
            id_combo.addItem(display_text)
        
        print(f"[DEBUG] Added {len(all_patients)} patients to combo box for session {self.session_code}")

        # Clear selections dan reset UI
        id_combo.clearSelection()
        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([])
        
        print("[DEBUG] Folder scan completed")
    
    def _on_patient_selected(self, txt: str) -> None:
        """Handle patient selection with new structure - FIXED parsing logic"""
        print(f"[DEBUG] _on_patient_selected: {txt}")
        try:
            # FIXED: Parse "ID: 12 (NSY)" format correctly
            # Split by "ID: " first, then parse the rest
            if not txt.startswith("ID: "):
                print(f"[DEBUG] Invalid format: {txt}")
                return
                
            # Remove "ID: " prefix and get "12 (NSY)"
            remainder = txt[4:]  # Remove "ID: "
            
            # Split by " (" to separate patient_id and session
            if " (" not in remainder:
                print(f"[DEBUG] No session found in: {remainder}")
                return
                
            patient_id = remainder.split(" (")[0]  # "12"
            session_part = remainder.split(" (")[1]  # "NSY)"
            session = session_part.rstrip(")")  # "NSY"
            
            print(f"[DEBUG] Parsed - Patient: {patient_id}, Session: {session}")
            self._load_patient(patient_id, session)
            
        except (IndexError, ValueError) as e:
            print(f"[DEBUG] Failed to parse patient selection: {e}")
            print(f"[DEBUG] Original text: '{txt}'")
            return
    
    def _load_patient(self, patient_id: str, session_code: str) -> None:
        """Load patient data using new directory structure with enhanced XML detection"""
        print(f"[DEBUG] Loading patient: {patient_id} from session: {session_code}")
        
        # Create cache key
        cache_key = f"{patient_id}_{session_code}"
        print(f"[CACHE DEBUG] Cache key: {cache_key}")
        print(f"[CACHE DEBUG] Existing cache keys: {list(self._loaded.keys())}")

        loading_dialog = None
        
        if cache_key in self._loaded:
            print(f"[DEBUG] Data untuk {cache_key} ditemukan di cache.")
            scans = self._loaded[cache_key]
        else:
            print(f"[DEBUG] Loading scans for {cache_key} from disk...")
            
            # Show loading dialog
            loading_dialog = SPECTLoadingDialog(patient_id, parent=self)
            loading_dialog.show()
            QApplication.processEvents()
            
            initial_scans = []
            async_results = []

            loading_dialog.update_loading_step("Scanning patient directory...", 10)
            QApplication.processEvents()

            # Get patient DICOM files using new structure
            dicom_files = get_patient_dicom_files(session_code, patient_id, primary_only=True)
            print(f"[DEBUG] Found {len(dicom_files)} DICOM files for patient {patient_id}")
            
            loading_dialog.update_loading_step("Running YOLO detection (creating XML)...", 20)
            QApplication.processEvents()
            
            yolo_jobs = []
            for dicom_file in dicom_files:
                # Panggil proses deteksi YOLO di latar belakang
                job = self.pool.apply_async(run_yolo_detection_for_patient, args=(dicom_file, patient_id))
                yolo_jobs.append(job)
            
            # Tunggu semua proses YOLO selesai
            print(f"[DEBUG] Waiting for {len(yolo_jobs)} YOLO jobs to complete...")
            for job in yolo_jobs:
                job.get(timeout=180) # Tunggu maksimal 3 menit
            
            print("[DEBUG] All YOLO detection jobs completed. XML files are now ready.")
            
            loading_dialog.update_loading_step("Loading DICOM files...", 25)
            QApplication.processEvents()

            for dicom_file in dicom_files:
                try:
                    frames, meta = load_frames_and_metadata(dicom_file)
                    scan_data = {"meta": meta, "frames": frames, "path": dicom_file}
                    initial_scans.append(scan_data)
                    print(f"[DEBUG] Processed DICOM: {dicom_file.name}")
                    
                    loading_dialog.update_loading_step(f"Processing scan {len(initial_scans)}...", 40)
                    QApplication.processEvents()
                    
                    # Process hotspot detection with enhanced XML detection
                    result = self.pool.apply_async(
                        run_hotspot_processing_in_process, 
                        args=(dicom_file, patient_id)
                    )
                    async_results.append(result)

                except Exception as e:
                    print(f"[WARN] Failed to read DICOM {dicom_file}: {e}")
            
            loading_dialog.update_loading_step("Processing hotspot detection...", 60)
            QApplication.processEvents()
            
            print(f"[DEBUG] Waiting for {len(async_results)} backend jobs to complete...")
            processed_scans = []
            for i, scan_data in enumerate(initial_scans):
                try:
                    progress = 60 + (i + 1) / len(initial_scans) * 30  # 60-90%
                    loading_dialog.update_loading_step(
                        f"Processing hotspot for scan {i + 1}/{len(initial_scans)}...", 
                        int(progress)
                    )
                    QApplication.processEvents()
                    
                    # Get study date for XML file detection logging
                    try:
                        study_date = extract_study_date_from_dicom(scan_data["path"])
                        filename_stem = generate_filename_stem(patient_id, study_date)
                        print(f"[DEBUG] Processing scan with filename stem: {filename_stem}")
                        
                        # Check for XML files with study date naming
                        xml_ant_new = scan_data["path"].parent / f"{filename_stem}_ant.xml"
                        xml_post_new = scan_data["path"].parent / f"{filename_stem}_post.xml"
                        xml_ant_old = scan_data["path"].parent / f"{patient_id}_ant.xml"
                        xml_post_old = scan_data["path"].parent / f"{patient_id}_post.xml"
                        
                        xml_files_found = []
                        for xml_file in [xml_ant_new, xml_post_new, xml_ant_old, xml_post_old]:
                            if xml_file.exists():
                                xml_files_found.append(xml_file.name)
                        
                        if xml_files_found:
                            print(f"[DEBUG] XML files found for {filename_stem}: {xml_files_found}")
                        else:
                            print(f"[DEBUG] No XML files found for {filename_stem}")
                            
                    except Exception as e:
                        print(f"[WARN] Could not check XML files: {e}")
                    
                    hotspot_data = async_results[i].get(timeout=120)
                    if hotspot_data:
                        scan_data["hotspot_frames"] = hotspot_data.get("frames")
                        scan_data["hotspot_frames_ant"] = hotspot_data.get("ant_frames")
                        scan_data["hotspot_frames_post"] = hotspot_data.get("post_frames")
                        print(f"[DEBUG] Hotspot processing completed for scan {i + 1}")
                    else:
                        scan_data["hotspot_frames"] = scan_data["frames"]
                        scan_data["hotspot_frames_ant"] = scan_data["frames"]
                        scan_data["hotspot_frames_post"] = scan_data["frames"]
                        print(f"[DEBUG] No hotspot data, using original frames for scan {i + 1}")
                    processed_scans.append(scan_data)
                except Exception as e:
                    print(f"[ERROR] Failed to get backend result for {scan_data['path']}: {e}")
            
            loading_dialog.update_loading_step("Finalizing data...", 95)
            QApplication.processEvents()
            
            scans = sorted(processed_scans, key=lambda s: s["meta"].get("study_date", ""))
            
            if scans:
                print(f"[DEBUG] Saving {len(scans)} scans to cache for {cache_key}")
                self._loaded[cache_key] = scans
            else:
                print(f"[WARN] No scans processed for {cache_key}. Cache not saved.")

            loading_dialog.update_loading_step("Loading completed!", 100)
            QApplication.processEvents()

        # Close loading dialog
        if loading_dialog:
            loading_dialog.close()

        print(f"[DEBUG] All data loaded. Total scans: {len(scans)}")
        if scans:
            self.patient_bar.set_patient_meta(scans[-1]["meta"])
            self._populate_scan_buttons(scans)
            self._on_scan_button_clicked(0)
        else:
            self.patient_bar.clear_info()
            self._populate_scan_buttons([])
            self.timeline_widget.display_timeline([])

    def _populate_scan_buttons(self, scans: List[Dict]) -> None:
        """Populate scan buttons"""
        # Clear existing buttons
        for btn in self.scan_buttons:
            btn.deleteLater()
        self.scan_buttons.clear()

        # Create new buttons
        for i, scan in enumerate(scans):
            btn = QPushButton(f"Scan {i + 1}")
            btn.setCheckable(True)
            btn.setStyleSheet(SCAN_BUTTON_STYLE)
            btn.clicked.connect(partial(self._on_scan_button_clicked, i))
            self.scan_button_container.addWidget(btn)
            self.scan_buttons.append(btn)

    # --- Zoom and view callbacks ---
    def zoom_in(self):
        """Zoom in timeline"""
        self.timeline_widget.zoom_in()

    def zoom_out(self):
        """Zoom out timeline"""
        self.timeline_widget.zoom_out()