# frontend/widgets/main_window.py
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing  import Dict, List

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QAction
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QSplitter, QPushButton
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader      import load_frames_and_metadata

from .dicom_import_dialog      import DicomImportDialog
from .searchable_combobox      import SearchableComboBox
from .patient_info             import PatientInfoBar
from .scan_timeline            import ScanTimelineWidget
from .side_panel               import SidePanel

# **NEW**
from .mode_selector            import ModeSelector
from .view_selector           import ViewSelector

class MainWindow(QMainWindow):
    """
    Layout:
        ┌ patient info
        ├ global actions
        ├ nav bar (view + mode + scan-buttons)
        └ splitter  (timeline | side-panel)
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)

        # caches
        self._patient_id_map: Dict[str, List[Path]] = {}
        self._loaded: Dict[str, List[Dict]]         = {}

        self._build_ui()
        self._scan_folder()

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        # ---------------- patient bar -------------------------------------
        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)

        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)

        tb_patient = QToolBar(movable=False)
        tb_patient.addWidget(self.patient_bar)
        self.addToolBar(Qt.TopToolBarArea, tb_patient)

        # ---------------- global actions ----------------------------------
        tb_actions = QToolBar("Global", movable=False)
        tb_actions.addAction(
            QAction("Import DICOM…", self, triggered=self._show_import_dialog)
        )
        tb_actions.addAction(
            QAction("Rescan Folder", self, triggered=self._scan_folder)
        )
        self.addToolBar(Qt.TopToolBarArea, tb_actions)
        # Permanent Mode Selector Toolbar
        tb_modes = QToolBar("Mode", movable=False)  # <-- Create a new toolbar

        # Paste your old code here
        self.mode_selector = ModeSelector()
        self.mode_selector.mode_changed.connect(self._set_mode)
        
        # Add it to the NEW toolbar, not nav_toolbar
        tb_modes.addWidget(self.mode_selector) # <-- This is the only line you change
        
        # Add the new, permanent toolbar to the window
        self.addToolBar(Qt.TopToolBarArea, tb_modes)

        # ---------------- navigation bar  ---------------------------------
        self.nav_toolbar = QToolBar("Navigation", movable=False)
        self.addToolBar(Qt.TopToolBarArea, self.nav_toolbar)

        # ---------------- main splitter -----------------------------------
        self.timeline_widget = ScanTimelineWidget()
        self.side_panel      = SidePanel()

        sp = QSplitter()
        sp.addWidget(self.timeline_widget)
        sp.addWidget(self.side_panel)
        sp.setStretchFactor(0, 4)
        sp.setStretchFactor(1, 1)
        self.setCentralWidget(sp)

    # ------------------------------------------------------------------- import
    def _show_import_dialog(self) -> None:
        dlg = DicomImportDialog(Path("data"), self)
        dlg.files_imported.connect(lambda _: self._scan_folder())
        dlg.exec()

    # ------------------------------------------------------------------- folder scan
    def _scan_folder(self) -> None:
        """
        Scan ./data → refresh combobox & bersihkan tampilan.
        """
        id_combo = self.patient_bar.id_combo
        id_combo.clear()

        self._patient_id_map = scan_dicom_directory(Path("data"))
        id_combo.addItems([f"ID : {pid}" for pid in sorted(self._patient_id_map)])
        id_combo.clearSelection()

        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([])
        self.nav_toolbar.clear()

    # ------------------------------------------------------------------- patient
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

        # update ui
        self.patient_bar.set_patient_meta(scans[-1]["meta"] if scans else {})
        self._build_nav(len(scans))
        self.timeline_widget.display_timeline(scans)

   # In main_window.py

    def _build_nav(self, n_scans: int) -> None:
        self.nav_toolbar.clear()
        if not n_scans:
            return

        # --- This is your existing view selector code ---
        self.view_selector = ViewSelector()
        self.view_selector.view_changed.connect(self._set_view)
        self.nav_toolbar.addWidget(self.view_selector)

        # --- ADD THIS SECTION FOR ZOOM BUTTONS ---
        self.nav_toolbar.addSeparator()

        zoom_in_btn = QPushButton("Zoom In")
        zoom_out_btn = QPushButton("Zoom Out")

        # These lines connect the buttons to the functions in ScanTimelineWidget
        zoom_in_btn.clicked.connect(self.timeline_widget.zoom_in)
        zoom_out_btn.clicked.connect(self.timeline_widget.zoom_out)

        self.nav_toolbar.addWidget(zoom_in_btn)
        self.nav_toolbar.addWidget(zoom_out_btn)

        self.nav_toolbar.addSeparator()
        # --- END OF ZOOM BUTTONS SECTION ---

        # --- This is your existing scan buttons code ---
        for i in range(n_scans):
            act = QAction(f"Scan {i+1}", self,
                          triggered=partial(self.timeline_widget.scroll_to_scan, i))
            self.nav_toolbar.addAction(act)

    # ---------------- callbacks ------------------------------------------
    def _set_view(self, v: str) -> None:
        print(f"Calling set_active_view with: {v}")
        self.timeline_widget.set_active_view(v)

    def _set_mode(self, m: str) -> None:
        self.timeline_widget.set_image_mode(m)
