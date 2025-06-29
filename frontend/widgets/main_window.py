# frontend/widgets/main_window.py
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing  import Dict, List

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QAction
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout,QLabel
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
        # ---------------- Patient Info Bar & Toolbar ----------------
        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)

        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)

        # Create top actions layout
        top_actions = QWidget()
        top_layout = QHBoxLayout(top_actions)
        top_layout.setContentsMargins(10, 5, 10, 5)
        top_layout.setSpacing(10)

        top_layout.addWidget(self.patient_bar)
        
        # Import and Rescan buttons
        import_btn = QPushButton("Import DICOM…")
        import_btn.clicked.connect(self._show_import_dialog)
        rescan_btn = QPushButton("Rescan Folder")
        rescan_btn.clicked.connect(self._scan_folder)

        top_layout.addWidget(import_btn)
        top_layout.addWidget(rescan_btn)

        # Add mode/view selectors
        self.mode_selector = ModeSelector()
        self.view_selector = ViewSelector()
        self.mode_selector.mode_changed.connect(self._set_mode)
        self.view_selector.view_changed.connect(self._set_view)

        top_layout.addWidget(self.mode_selector)
        top_layout.addWidget(self.view_selector)

        # ---------------- Zoom Buttons Only -----------------------------------
        view_button_layout = QHBoxLayout()

        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.clicked.connect(self.zoom_out)

        view_button_layout.addWidget(zoom_in_btn)
        view_button_layout.addWidget(zoom_out_btn)
        view_button_layout.addStretch()  # Optional: push buttons to left

        view_button_widget = QWidget()
        view_button_widget.setLayout(view_button_layout)


        # ---------------- Split View: Left Image View | Right Panel --------------
        main_splitter = QSplitter()

        # Left view: image area with timeline
        self.left_image_panel = QWidget()
        self.left_image_panel.setMinimumWidth(600)
        self.left_image_layout = QVBoxLayout(self.left_image_panel)

        # Timeline Widget
        self.timeline_widget = ScanTimelineWidget()

        # Image display
        self.left_image_layout.addWidget(self.timeline_widget)

        main_splitter.addWidget(self.left_image_panel)

        # Right: side panel with timeline + chart + quantitative summary
        self.side_panel = SidePanel()
        main_splitter.addWidget(self.side_panel)

        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        # ---------------- Final Assembly -----------------------------------------
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        main_layout.addWidget(top_actions)
        main_layout.addWidget(view_button_widget)
        main_layout.addWidget(main_splitter, stretch=1)

        self.setCentralWidget(main_widget)


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
        if hasattr(self, 'timeline_widget'):
            self.timeline_widget.display_timeline([])
        

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
        
        self.timeline_widget.display_timeline(scans)

   # In main_window.py

    # Add these methods inside the MainWindow class
    def zoom_in(self):
        if hasattr(self, 'timeline_widget'):
            self.timeline_widget.zoom_in()

    def zoom_out(self):
        if hasattr(self, 'timeline_widget'):
            self.timeline_widget.zoom_out()

    # ---------------- callbacks ------------------------------------------
    def _set_view(self, v: str) -> None:
        print(f"Calling set_active_view with: {v}")
        self.timeline_widget.set_active_view(v)

    def _set_mode(self, m: str) -> None:
        self.timeline_widget.set_image_mode(m)