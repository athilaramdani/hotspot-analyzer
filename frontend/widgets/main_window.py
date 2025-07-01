# frontend/widgets/main_window.py
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader import load_frames_and_metadata

from .dicom_import_dialog import DicomImportDialog
from .searchable_combobox import SearchableComboBox
from .patient_info import PatientInfoBar
from .scan_timeline import ScanTimelineWidget  # Menggunakan timeline widget lagi
from .side_panel import SidePanel
from .mode_selector import ModeSelector
from .view_selector import ViewSelector

class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)

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

        import_btn = QPushButton("Import DICOM…")
        import_btn.clicked.connect(self._show_import_dialog)
        rescan_btn = QPushButton("Rescan Folder")
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
        dlg = DicomImportDialog(Path("data"), self)
        dlg.files_imported.connect(lambda _: self._scan_folder())
        dlg.exec()

    def _scan_folder(self) -> None:
        id_combo = self.patient_bar.id_combo
        id_combo.clear()
        self._patient_id_map = scan_dicom_directory(Path("data"))
        id_combo.addItems([f"ID : {pid}" for pid in sorted(self._patient_id_map)])
        id_combo.clearSelection()
        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([]) # Kosongkan timeline

    def _on_patient_selected(self, txt: str) -> None:
        try:
            pid = txt.split(" : ")[1]
        except IndexError:
            return
        self._load_patient(pid)

    def _load_patient(self, pid: str) -> None:
        scans = self._loaded.get(pid)
        if scans is None:
            scans = []
            for p in self._patient_id_map.get(pid, []):
                try:
                    frames, meta = load_frames_and_metadata(p)
                    scans.append({"meta": meta, "frames": frames, "path": p})
                except Exception as e:
                    print(f"[WARN] failed to read {p}: {e}")
            scans.sort(key=lambda s: s["meta"].get("study_date", ""))
            self._loaded[pid] = scans

        self.patient_bar.set_patient_meta(scans[-1]["meta"] if scans else {})
        self._populate_scan_buttons(scans)

        if scans:
            self._on_scan_button_clicked(0)

    def _populate_scan_buttons(self, scans: List[Dict]) -> None:
        for btn in self.scan_buttons:
            btn.deleteLater()
        self.scan_buttons.clear()

        for i, scan in enumerate(scans):
            btn = QPushButton(f"Scan {i + 1}")
            btn.setCheckable(True)
            btn.clicked.connect(partial(self._on_scan_button_clicked, i))
            self.scan_button_container.addWidget(btn)
            self.scan_buttons.append(btn)

    def _on_scan_button_clicked(self, index: int) -> None:
        """Fungsi ini sekarang menjadi pusat logika yang benar."""
        
        # 1. Update tampilan tombol
        for i, btn in enumerate(self.scan_buttons):
            btn.setChecked(i == index)

        # 2. Ambil data scan untuk pasien saat ini (CARA YANG BENAR)
        try:
            # Ambil teks dari ComboBox, contoh: "ID : 0001443575"
            id_text = self.patient_bar.id_combo.currentText()
            # Pisahkan teks untuk mendapatkan ID saja
            pid = id_text.split(" : ")[1]
        except (IndexError, AttributeError):
            # Jika gagal (tidak ada pasien terpilih), hentikan fungsi
            return

        scans = self._loaded.get(pid, [])
        if not scans or index >= len(scans):
            return
        
        selected_scan = scans[index]

        # 3. Perintahkan timeline di KIRI untuk menampilkan HANYA scan yang dipilih
        self.timeline_widget.display_timeline(scans, active_index=index)

        # 4. Perintahkan panel di KANAN untuk update grafik dan ringkasan
        self.side_panel.set_chart_data(scans)
        self.side_panel.set_summary(selected_scan["meta"])

    # --- Callbacks untuk zoom, view, dan mode ---
    def zoom_in(self):
        self.timeline_widget.zoom_in()

    def zoom_out(self):
        self.timeline_widget.zoom_out()

    def _set_view(self, v: str) -> None:
        self.timeline_widget.set_active_view(v)

    def _set_mode(self, m: str) -> None:
        self.timeline_widget.set_image_mode(m)