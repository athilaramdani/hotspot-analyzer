# features/spect_viewer/gui/main_window_spect.py
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Dict, List
import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout, QDialog, QApplication
)
from PySide6.QtGui import QCloseEvent
import multiprocessing

# Import config paths
from core.config.paths import SPECT_DATA_PATH, get_patient_spect_path

# ===== TAMBAHKAN IMPORT LOADING DIALOG =====
from core.gui.loading_dialog import SPECTLoadingDialog
# ===========================================

from features.dicom_import.logic.directory_scanner import scan_dicom_directory
from features.dicom_import.logic.dicom_loader import load_frames_and_metadata
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
from features.spect_viewer.logic.processing_wrapper import run_hotspot_processing_in_process

class MainWindowSpect(QMainWindow):
    logout_requested = Signal()
    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)
        self.session_code = session_code
        self.pool = multiprocessing.Pool(processes=1)
        self.data_root = data_root
        print("[DEBUG] session_code in MainWindow =", self.session_code)

        # Caches
        self._patient_id_map: Dict[str, List[Path]] = {}
        self._loaded: Dict[str, List[Dict]] = {}
        self.scan_buttons: List[QPushButton] = []
        
        # Hotspot processor
        #self.hotspot_processor = HotspotProcessor()

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

        # Updated Import button dengan styling yang lebih baik
        import_btn = QPushButton("Import DICOM…")
        import_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        import_btn.clicked.connect(self._show_import_dialog)
        
        rescan_btn = QPushButton("Rescan Folder")
        rescan_btn.setStyleSheet(SUCCESS_BUTTON_STYLE)
        rescan_btn.clicked.connect(self._scan_folder)
        
        self.mode_selector = ModeSelector()
        self.view_selector = ViewSelector()
        self.mode_selector.mode_changed.connect(self._set_mode)
        self.view_selector.view_changed.connect(self._set_view)

        top_layout.addWidget(import_btn)
        top_layout.addWidget(rescan_btn)
        top_layout.addWidget(self.mode_selector)
        top_layout.addWidget(self.view_selector)

        # add logout button
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

        # --- Splitter (UI Utama) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel Kiri: Timeline untuk menampilkan gambar
        self.timeline_widget = ScanTimelineWidget()
        self.timeline_widget.set_session_code(self.session_code)
        main_splitter.addWidget(self.timeline_widget)

        # Panel Kanan: Grafik dan ringkasan
        self.side_panel = SidePanel()
        main_splitter.addWidget(self.side_panel)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        # --- Perakitan Final ---
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(top_actions)
        main_layout.addWidget(view_button_widget)
        main_layout.addWidget(main_splitter, stretch=1)
        self.setCentralWidget(main_widget)
   
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
        """Scan folder untuk mencari DICOM files using config paths"""
        print("[DEBUG] Starting folder scan...")
        
        id_combo = self.patient_bar.id_combo
        id_combo.clear()
        
        # Use config path instead of hardcoded path
        spect_data_dir = SPECT_DATA_PATH
        
        # 1. Pindai semua direktori seperti biasa
        all_patients_map = scan_dicom_directory(spect_data_dir)
        print(f"[DEBUG] Semua patient ID dari scanner:")
        for pid in all_patients_map.keys():
            print(f"  - {pid}")
            
        # 2. Saring (filter) hasilnya untuk hanya menyertakan yang berakhiran '_kode'
        filter_suffix = f"_{self.session_code}"
        self._patient_id_map = {
            pid: path
            for pid, path in all_patients_map.items()
            if pid.endswith(filter_suffix)
        }
        print(f"[DEBUG] ID pasien dengan suffix {filter_suffix}: {list(self._patient_id_map.keys())}")

        # Tampilkan hasil saringan (tanpa akhiran _kode)
        id_combo.addItems([
            f"ID : {pid.removesuffix(filter_suffix)} ({self.session_code})"
            for pid in sorted(self._patient_id_map)
        ])
        print(f"[DEBUG] Added {id_combo.count()} patient IDs to combo box")

        # Clear selections dan reset UI
        id_combo.clearSelection()
        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([])
        
        print("[DEBUG] Folder scan completed")
    
    def _on_patient_selected(self, txt: str) -> None:
        """Handle patient selection"""
        print(f"[DEBUG] _on_patient_selected: {txt}")
        try:
            # Ambil hanya bagian ID tanpa (session_code)
            pid = txt.split(" : ")[1].split(" ")[0]
        except IndexError:
            print("[DEBUG] Failed to parse patient ID from selection")
            return
        self._load_patient(pid)
    
    def _load_patient(self, pid: str) -> None:
        """Loads patient data using a multiprocessing pool for backend processing with loading dialog."""
        print(f"[DEBUG] Loading patient: {pid}")
        print(f"[CACHE DEBUG] Isi cache sebelum load: {list(self._loaded.keys())}")

        full_pid = f"{pid}_{self.session_code}"
        
        # ===== TAMBAHKAN LOADING DIALOG =====
        loading_dialog = None
        # ====================================
        
        if full_pid in self._loaded:
            print(f"[DEBUG] Data untuk {full_pid} ditemukan di cache.")
            scans = self._loaded[full_pid]
        else:
            print(f"[DEBUG] Loading scans for {full_pid} from disk...")
            
            # ===== SHOW LOADING DIALOG =====
            loading_dialog = SPECTLoadingDialog(pid, parent=self)
            loading_dialog.show()
            QApplication.processEvents()  # Update UI immediately
            # ===============================
            
            initial_scans = []
            async_results = []

            # Update loading step
            loading_dialog.update_loading_step("Scanning DICOM directories...", 10)
            QApplication.processEvents()

            # Use config path functions
            all_patients_map = scan_dicom_directory(SPECT_DATA_PATH)
            self._patient_id_map.update(all_patients_map)

            # Update loading step
            loading_dialog.update_loading_step("Loading DICOM files...", 25)
            QApplication.processEvents()

            for p in self._patient_id_map.get(full_pid, []):
                try:
                    frames, meta = load_frames_and_metadata(p)
                    scan_data = {"meta": meta, "frames": frames, "path": p}
                    initial_scans.append(scan_data)
                    print(f"--> [TES] MEMANGGIL BACKEND DENGAN patient_id: {pid}")
                    
                    # Update loading step
                    loading_dialog.update_loading_step(f"Processing scan {len(initial_scans)}...", 40)
                    QApplication.processEvents()
                    
                    # --- FIX DI SINI: Pastikan 'pid' ditambahkan sebagai argumen kedua ---
                    result = self.pool.apply_async(run_hotspot_processing_in_process, args=(p, pid))
                    async_results.append(result)

                except Exception as e:
                    print(f"[WARN] Gagal membaca data awal {p}: {e}")
            
            # Update loading step
            loading_dialog.update_loading_step("Processing hotspot detection...", 60)
            QApplication.processEvents()
            
            print(f"[DEBUG] Menunggu {len(async_results)} pekerjaan backend selesai...")
            processed_scans = []
            for i, scan_data in enumerate(initial_scans):
                try:
                    # Update progress per scan
                    progress = 60 + (i + 1) / len(initial_scans) * 30  # 60-90%
                    loading_dialog.update_loading_step(f"Processing hotspot for scan {i + 1}/{len(initial_scans)}...", int(progress))
                    QApplication.processEvents()
                    
                    hotspot_data = async_results[i].get(timeout=120) # Timeout 2 menit
                    if hotspot_data:
                        scan_data["hotspot_frames"] = hotspot_data.get("frames")
                        scan_data["hotspot_frames_ant"] = hotspot_data.get("ant_frames")
                        scan_data["hotspot_frames_post"] = hotspot_data.get("post_frames")
                    else:
                        scan_data["hotspot_frames"] = scan_data["frames"]
                        scan_data["hotspot_frames_ant"] = scan_data["frames"]
                        scan_data["hotspot_frames_post"] = scan_data["frames"]
                    processed_scans.append(scan_data)
                except Exception as e:
                    print(f"[ERROR] Gagal mendapatkan hasil dari backend untuk {scan_data['path']}: {e}")
            
            # Update loading step
            loading_dialog.update_loading_step("Finalizing data...", 95)
            QApplication.processEvents()
            
            scans = sorted(processed_scans, key=lambda s: s["meta"].get("study_date", ""))
            
            if scans:
                print(f"[DEBUG] Menyimpan {len(scans)} scan ke cache untuk {full_pid}")
                self._loaded[full_pid] = scans
            else:
                print(f"[WARN] Tidak ada scan yang diproses untuk {full_pid}. Cache tidak disimpan.")

            # Update loading step
            loading_dialog.update_loading_step("Loading completed!", 100)
            QApplication.processEvents()

        # ===== CLOSE LOADING DIALOG =====
        if loading_dialog:
            loading_dialog.close()
        # ================================

        print(f"[DEBUG] Semua data dimuat. Total scan: {len(scans)}")
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

    def _on_scan_button_clicked(self, index: int) -> None:
        """Fungsi ini sekarang menjadi pusat logika yang benar."""
        current_mode = self.mode_selector.current_mode()
        self.timeline_widget.set_image_mode(current_mode) 
        
        # 1. Update tampilan tombol
        for i, btn in enumerate(self.scan_buttons):
            btn.setChecked(i == index)

        # Get current patient data
        try:
            id_text = self.patient_bar.id_combo.currentText()
            pid = id_text.split(" : ")[1].split(" ")[0]
        except (IndexError, AttributeError):
            print("[DEBUG] Failed to get current patient ID")
            return

        # Load scan data
        full_pid = f"{pid}_{self.session_code}"
        scans = self._loaded.get(full_pid, []) 

        if not scans or index >= len(scans):
            print(f"[DEBUG] Invalid scan index {index} for patient {full_pid}")
            return
        
        selected_scan = scans[index]

        # Update timeline display
        self.timeline_widget.display_timeline(scans, active_index=index)

        # Update side panel
        self.side_panel.set_chart_data(scans)
        self.side_panel.set_summary(selected_scan["meta"])
        
        print(f"[DEBUG] Menampilkan {len(scans)} scan di timeline")

    # --- Zoom and view callbacks ---
    def zoom_in(self):
        """Zoom in timeline"""
        self.timeline_widget.zoom_in()

    def zoom_out(self):
        """Zoom out timeline"""
        self.timeline_widget.zoom_out()

    def _set_view(self, v: str) -> None:
        """Set active view"""
        self.timeline_widget.set_active_view(v)

    def _set_mode(self, m: str) -> None:
        """Handle mode changes including hotspot mode."""
        self.timeline_widget.set_image_mode(m)
        
        # If switching to hotspot mode, refresh the current scan
        if m == "Hotspot":
            # Get currently selected scan and refresh it
            for i, btn in enumerate(self.scan_buttons):
                if btn.isChecked():
                    self._on_scan_button_clicked(i)
                    break