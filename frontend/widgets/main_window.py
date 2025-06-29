# frontend/widgets/main_window.py
from __future__ import annotations
from pathlib import Path
from functools import partial
from typing  import Dict, List

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QSplitter, QToolButton,
    QApplication, QStyle
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader      import load_frames_and_metadata

from .dicom_import_dialog import DicomImportDialog
from .searchable_combobox import SearchableComboBox
from .patient_info        import PatientInfoBar
from .scan_timeline       import ScanTimelineWidget
from .side_panel          import SidePanel
from .mode_selector       import ModeSelector
from .view_selector       import ViewSelector

# palet helper dari app.py
from frontend.app import make_light_palette, make_dark_palette


class MainWindow(QMainWindow):
    """
    Hotspot Analyzer main window.
    • Baris-1 : PatientInfo | Import | Rescan | Mode selector | Theme toggle
    • Baris-2 : View selector | Zoom (+/−) | Scan 1..N
    • Bawah   : Timeline (kiri) + SidePanel (kanan)
    """

    # ──────────────────────────── INIT ────────────────────────────────────
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)

        # theme state
        self._dark_mode = False

        # caches
        self._patient_id_map: Dict[str, List[Path]] = {}
        self._loaded: Dict[str, List[Dict]]         = {}

        self._build_ui()
        self._scan_folder()

    # ─────────────────────────── UI BUILD ─────────────────────────────────
    def _build_ui(self) -> None:
        # ▸ Patient bar
        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)

        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)

        tb_patient = QToolBar(movable=False)
        tb_patient.addWidget(self.patient_bar)
        self.addToolBar(Qt.TopToolBarArea, tb_patient)

        # ▸ Global actions
        tb_actions = QToolBar("Global", movable=False)
        tb_actions.addAction(
            QAction("Import DICOM…", self, triggered=self._show_import_dialog)
        )
        tb_actions.addAction(
            QAction("Rescan Folder", self, triggered=self._scan_folder)
        )
        self.addToolBar(Qt.TopToolBarArea, tb_actions)

        # ▸ Mode selector
        tb_modes = QToolBar("Mode", movable=False)
        self.mode_selector = ModeSelector()
        self.mode_selector.mode_changed.connect(self._set_mode)
        tb_modes.addWidget(self.mode_selector)
        self.addToolBar(Qt.TopToolBarArea, tb_modes)

        # ▸ Theme toggle (🌞 / 🌙)
        theme_btn = QToolButton()
        theme_btn.setCheckable(True)
        theme_btn.setToolTip("Toggle Dark / Light mode")
        theme_btn.setIcon(QIcon.fromTheme("weather-clear"))
        theme_btn.toggled.connect(self._toggle_theme)

        tb_theme = QToolBar(movable=False)
        tb_theme.addWidget(theme_btn)
        tb_theme.setContentsMargins(0, 0, 8, 0)
        self.addToolBar(Qt.TopToolBarArea, tb_theme)

        # ── break → navigation bar di baris kedua
        self.addToolBarBreak(Qt.TopToolBarArea)

        # ▸ Navigation toolbar
        self.nav_toolbar = QToolBar("Navigation", movable=False)
        self.addToolBar(Qt.TopToolBarArea, self.nav_toolbar)

        # ▸ Main splitter (timeline | side panel)
        self.timeline_widget = ScanTimelineWidget()
        self.side_panel      = SidePanel()

        sp = QSplitter()
        sp.addWidget(self.timeline_widget)
        sp.addWidget(self.side_panel)
        sp.setStretchFactor(0, 4)
        sp.setStretchFactor(1, 1)
        self.setCentralWidget(sp)

    # ─────────────────────────── Theme toggle ────────────────────────────
    def _toggle_theme(self, checked: bool) -> None:
        self._dark_mode = checked
        QApplication.instance().setPalette(
            make_dark_palette() if checked else make_light_palette()
        )
        sender: QToolButton = self.sender()  # type: ignore
        if sender:
            sender.setIcon(
                QIcon.fromTheme("weather-clear-night" if checked else "weather-clear")
            )

    # ─────────────────────────── Import dialog ───────────────────────────
    def _show_import_dialog(self) -> None:
        dlg = DicomImportDialog(Path("data"), self)
        dlg.files_imported.connect(lambda _: self._scan_folder())
        dlg.exec()

    # ─────────────────────────── Folder scan ─────────────────────────────
    def _scan_folder(self) -> None:
        combo = self.patient_bar.id_combo
        combo.clear()

        self._patient_id_map = scan_dicom_directory(Path("data"))
        combo.addItems([f"ID : {pid}" for pid in sorted(self._patient_id_map)])
        combo.clearSelection()

        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([])
        self.nav_toolbar.clear()

    # ─────────────────────────── Patient ops ─────────────────────────────
    def _on_patient_selected(self, txt: str) -> None:
        if " : " not in txt:
            return
        pid = txt.split(" : ")[1]
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
        self._build_nav(len(scans))
        self.timeline_widget.display_timeline(scans)

    # ─────────────────────────── Navigation bar ──────────────────────────
    def _build_nav(self, n_scans: int) -> None:
        self.nav_toolbar.clear()
        if not n_scans:
            return

        # view selector
        self.view_selector = ViewSelector()
        self.view_selector.view_changed.connect(self._set_view)
        self.nav_toolbar.addWidget(self.view_selector)

        # zoom buttons (icon + / -)
        zoom_cfg = [
            ("Zoom In",  self.timeline_widget.zoom_in ,
             self.style().standardIcon(QStyle.SP_ArrowUp)),
            ("Zoom Out", self.timeline_widget.zoom_out,
             self.style().standardIcon(QStyle.SP_ArrowDown)),
        ]
        for tip, slot, icon in zoom_cfg:
            btn = QToolButton()
            btn.setToolTip(tip)
            btn.setIcon(icon)
            btn.clicked.connect(slot)
            self.nav_toolbar.addWidget(btn)

        self.nav_toolbar.addSeparator()

        # scan jump buttons
        for i in range(n_scans):
            act = QAction(f"Scan {i+1}", self,
                          triggered=partial(self.timeline_widget.scroll_to_scan, i))
            self.nav_toolbar.addAction(act)

    # ─────────────────────────── Callbacks ───────────────────────────────
    def _set_view(self, v: str) -> None:
        self.timeline_widget.set_active_view(v)

    def _set_mode(self, m: str) -> None:
        self.timeline_widget.set_image_mode(m)
