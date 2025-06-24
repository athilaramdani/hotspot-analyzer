from pathlib import Path
from typing import Dict, List
from functools import partial
from PyQt5.QtCore import Qt 
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QMessageBox, 
    QToolBar, QAction, QSplitter
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader import load_frames_and_metadata
from .searchable_combobox import SearchableComboBox
from .patient_info import PatientInfoBar
from .scan_timeline import ScanTimelineWidget
from .side_panel import SidePanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer (Timeline View)")
        self.resize(1600, 900)
        self._patient_id_map: Dict[str, List[Path]] = {}
        self._loaded_patients_cache: Dict[str, List[Dict]] = {}
        self._build_ui()
        self._initial_patient_scan()

    def _build_ui(self):
        # 1. Widget info pasien dengan dropdown kustom
        searchable_id_combo = SearchableComboBox()
        searchable_id_combo.item_selected.connect(self._on_patient_selected)
        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(searchable_id_combo)
        tb_patient = QToolBar("Patient Info", movable=False)
        tb_patient.addWidget(self.patient_bar)
        self.addToolBar(Qt.TopToolBarArea, tb_patient)
        
        # 2. Toolbar untuk aksi global
        tb_act = QToolBar("Global Actions", movable=False)
        tb_act.addAction(QAction("Rescan Folder", self, triggered=self._initial_patient_scan))
        self.addToolBar(Qt.TopToolBarArea, tb_act)
        
        # 3. Toolbar untuk navigasi scan (Awalnya kosong)
        self.scan_nav_toolbar = QToolBar("Scan Navigation", movable=False)
        self.addToolBar(Qt.TopToolBarArea, self.scan_nav_toolbar)

        # 4. KONTEN UTAMA: Splitter Horizontal
        #    Ini adalah bagian yang membuat layout kiri (timeline) dan kanan (grafik)
        self.timeline_widget = ScanTimelineWidget() # Panel Kiri
        self.side_panel = SidePanel() # Panel Kanan
        
        main_splitter = QSplitter() # Widget pemisah
        main_splitter.addWidget(self.timeline_widget)
        main_splitter.addWidget(self.side_panel)
        main_splitter.setStretchFactor(0, 4) # Panel kiri 4x lebih besar
        main_splitter.setStretchFactor(1, 1) # Panel kanan
        self.setCentralWidget(main_splitter)

    def _update_scan_navigation_toolbar(self, num_scans: int):
        self.scan_nav_toolbar.clear()
        if num_scans == 0: return

        self.view_toggle_buttons = {}
        for view_name in ["Anterior", "Posterior"]:
            btn = QPushButton(view_name)
            btn.setCheckable(True)
            btn.clicked.connect(partial(self._set_timeline_view, view_name))
            self.scan_nav_toolbar.addWidget(btn)
            self.view_toggle_buttons[view_name] = btn
        
        self.view_toggle_buttons["Anterior"].setChecked(True)
        self.scan_nav_toolbar.addSeparator()

        for i in range(num_scans):
            action = QAction(f"Scan {i+1}", self)
            action.triggered.connect(partial(self._on_scan_nav_button_clicked, i))
            self.scan_nav_toolbar.addAction(action)

    def _initial_patient_scan(self):
        self.patient_bar.id_combo.clear()
        self.patient_bar.id_combo.addItem("Select Patient ID")
        self._patient_id_map = scan_dicom_directory(Path("data"))
        for pid in sorted(self._patient_id_map.keys()):
            self.patient_bar.id_combo.addItem(f"ID: {pid}")

    def _on_patient_selected(self, selected_text: str):
        if "Select Patient ID" in selected_text:
            self.patient_bar.clear_info(keep_id_list=True)
            self.timeline_widget.display_timeline([])
            self._update_scan_navigation_toolbar(0)
            return
        pid = selected_text.replace("ID: ", "").strip()
        self._load_and_display_patient(pid)

    def _load_and_display_patient(self, pid: str):
        if pid in self._loaded_patients_cache:
            patient_timeline_data = self._loaded_patients_cache[pid]
        else:
            file_paths = self._patient_id_map.get(pid, [])
            if not file_paths: return
            all_scans = []
            for path in file_paths:
                try:
                    frames, meta = load_frames_and_metadata(path)
                    all_scans.append({"meta": meta, "frames": frames})
                except Exception as e: print(f"Warning: Could not load file {path}: {e}")
            if not all_scans: return
            all_scans.sort(key=lambda scan: scan["meta"].get("study_date", "0"))
            patient_timeline_data = all_scans
            self._loaded_patients_cache[pid] = patient_timeline_data
        
        if patient_timeline_data:
            self.patient_bar.set_patient_meta(patient_timeline_data[-1]["meta"])
            self._update_scan_navigation_toolbar(len(patient_timeline_data))
            self.timeline_widget.display_timeline(patient_timeline_data)
        else:
            self.timeline_widget.display_timeline([])
            self._update_scan_navigation_toolbar(0)

    def _set_timeline_view(self, view_name: str):
        for name, button in self.view_toggle_buttons.items():
            button.setChecked(name == view_name)
        self.timeline_widget.set_active_view(view_name)
        
    def _on_scan_nav_button_clicked(self, index: int):
        print(f"Navigating to Scan {index + 1}")
        self.timeline_widget.scroll_to_scan(index)