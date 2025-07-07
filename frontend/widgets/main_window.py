# frontend/widgets/main_window.py
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout, QDialog
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader import load_frames_and_metadata

# Import the new dialog
from .dicom_import_dialog_v2 import DicomImportDialog

from .searchable_combobox import SearchableComboBox
from .patient_info import PatientInfoBar
from .scan_timeline import ScanTimelineWidget
from .side_panel import SidePanel
from .mode_selector import ModeSelector
from .view_selector import ViewSelector


class MainWindow(QMainWindow):

    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)
        self.session_code = session_code
        self.data_root = data_root
        print("[DEBUG] session_code in MainWindow =", self.session_code)

        # Caches
        self._patient_id_map: Dict[str, List[Path]] = {}
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

        # Updated Import button dengan styling yang lebih baik
        import_btn = QPushButton("Import DICOM…")
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #4e73ff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3e63e6;
            }
            QPushButton:pressed {
                background-color: #324fc7;
            }
        """)
        import_btn.clicked.connect(self._show_import_dialog)
        
        rescan_btn = QPushButton("Rescan Folder")
        rescan_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        rescan_btn.clicked.connect(self._scan_folder)
        
        self.mode_selector = ModeSelector()
        self.view_selector = ViewSelector()
        self.mode_selector.mode_changed.connect(self._set_mode)
        self.view_selector.view_changed.connect(self._set_view)

        top_layout.addWidget(import_btn)
        top_layout.addWidget(rescan_btn)
        top_layout.addWidget(self.mode_selector)
        top_layout.addWidget(self.view_selector)

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
        zoom_style = """
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """
        zoom_in_btn.setStyleSheet(zoom_style)
        zoom_out_btn.setStyleSheet(zoom_style)
        
        view_button_layout.addWidget(zoom_in_btn)
        view_button_layout.addWidget(zoom_out_btn)

        # --- Splitter (UI Utama) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel Kiri: Timeline untuk menampilkan gambar
        self.timeline_widget = ScanTimelineWidget()
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
        """Scan folder untuk mencari DICOM files"""
        print("[DEBUG] Starting folder scan...")
        
        id_combo = self.patient_bar.id_combo
        id_combo.clear()
        
        # 1. Pindai semua direktori seperti biasa
        all_patients_map = scan_dicom_directory(self.data_root)
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
        """Load patient data"""
        print(f"[DEBUG] Loading patient: {pid}")
        
        full_pid = f"{pid}_{self.session_code}"
        scans = self._loaded.get(full_pid)
        
        if scans is None:
            print(f"[DEBUG] Loading scans for {full_pid} from disk...")
            scans = []
            for p in self._patient_id_map.get(full_pid, []):
                try:
                    frames, meta = load_frames_and_metadata(p)
                    print(f"[DEBUG] > Loaded DICOM: {p.name}")
                    print(f"[DEBUG]   - Frames: {list(frames.keys())}")
                    print(f"[DEBUG]   - Meta: {meta}")
                    scans.append({"meta": meta, "frames": frames, "path": p})
                except Exception as e:
                    print(f"[WARN] failed to read {p}: {e}")
                    
            scans.sort(key=lambda s: s["meta"].get("study_date", ""))
            self._loaded[full_pid] = scans  # Simpan di cache

        print(f"[DEBUG] Total scan ditemukan untuk {full_pid}: {len(scans)}")
        self.patient_bar.set_patient_meta(scans[-1]["meta"] if scans else {})
        self._populate_scan_buttons(scans)

        # Set initial scan selection
        if scans:
            self._on_scan_button_clicked(0)

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
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #9C27B0;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #7B1FA2;
                }
                QPushButton:checked {
                    background-color: #4A148C;
                }
                QPushButton:pressed {
                    background-color: #4A148C;
                }
            """)
            btn.clicked.connect(partial(self._on_scan_button_clicked, i))
            self.scan_button_container.addWidget(btn)
            self.scan_buttons.append(btn)

    def _on_scan_button_clicked(self, index: int) -> None:
        """Handle scan button click"""
        print(f"[DEBUG] Scan button clicked: index = {index}")
        
        # Set image mode
        self.timeline_widget.set_image_mode("Both") 
        
        # Update button states
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
        self.timeline_widget.set_image_mode(m)