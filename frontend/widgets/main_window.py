from __future__ import annotations

"""Main window for the Hotspot‑Analyzer desktop application.
This version resolves previous Git merge‑conflicts and merges the latest
changes from *HEAD* and *main* branches.

UI LAYOUT
─────────
• Top‑row toolbars  ─ PatientInfo │ Import │ Rescan │ Mode │ Theme toggle
• Second‑row       ─ View selector │ Zoom {+/‑} │ Scan jump buttons
• Central area     ─ Splitter: (Timeline / Image) ︱ SidePanel
"""

from pathlib import Path
from functools import partial
from typing import Dict, List, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QStyle,
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader import load_frames_and_metadata

from .dicom_import_dialog import DicomImportDialog
from .searchable_combobox import SearchableComboBox
from .patient_info import PatientInfoBar
from .scan_timeline import ScanTimelineWidget
from .side_panel import SidePanel
from .mode_selector import ModeSelector
from .view_selector import ViewSelector

# palette helpers (provided by frontend/app.py)
from frontend.app import make_light_palette, make_dark_palette


class MainWindow(QMainWindow):
    """Hotspot Analyzer main window class."""

    # ────────────────────────── INIT ──────────────────────────
    def __init__(self) -> None:  # noqa: D401
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)

        # current theme‑state
        self._dark_mode: bool = False

        # caches
        self._patient_id_map: Dict[str, List[Path]] = {}
        self._loaded: Dict[str, List[Dict[str, Union[dict, list, Path]]]] = {}

        self._build_ui()
        self._scan_folder()

    # ────────────────────────── UI BUILD ──────────────────────
    def _build_ui(self) -> None:
        """Compose all widgets and toolbars."""

        # ▸ Patient info bar (contains the searchable combo)
        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)

        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)

        tb_patient = QToolBar("Patient", self)
        tb_patient.setMovable(False)
        tb_patient.addWidget(self.patient_bar)
        self.addToolBar(Qt.TopToolBarArea, tb_patient)

        # ▸ Global actions (Import / Rescan)
        tb_actions = QToolBar("Actions", self)
        tb_actions.setMovable(False)
        tb_actions.addAction(
            QAction("Import DICOM…", self, triggered=self._show_import_dialog)
        )
        tb_actions.addAction(
            QAction("Rescan Folder", self, triggered=self._scan_folder)
        )
        self.addToolBar(Qt.TopToolBarArea, tb_actions)

        # ▸ Mode selector (BSI / Counts / …)
        self.mode_selector = ModeSelector()
        self.mode_selector.mode_changed.connect(self._set_mode)

        tb_modes = QToolBar("Mode", self)
        tb_modes.setMovable(False)
        tb_modes.addWidget(self.mode_selector)
        self.addToolBar(Qt.TopToolBarArea, tb_modes)

        # ▸ Theme toggle button (🌞 / 🌙)
        theme_btn = QToolButton()
        theme_btn.setCheckable(True)
        theme_btn.setToolTip("Toggle Dark / Light mode")
        theme_btn.setIcon(QIcon.fromTheme("weather-clear"))
        theme_btn.toggled.connect(self._toggle_theme)

        tb_theme = QToolBar("Theme", self)
        tb_theme.setMovable(False)
        tb_theme.addWidget(theme_btn)
        self.addToolBar(Qt.TopToolBarArea, tb_theme)

        # ─── Break — navigation tool‑bar occupies 2nd row ───
        self.addToolBarBreak(Qt.TopToolBarArea)

        self.nav_toolbar = QToolBar("Navigation", self)
        self.nav_toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.nav_toolbar)

        # ▸ Central splitter (timeline/image | side panel)
        self.timeline_widget = ScanTimelineWidget()
        self.view_selector = ViewSelector()
        self.view_selector.view_changed.connect(self._set_view)

        # left panel (image view + timeline)
        self.left_image_label = QLabel("No scans to display", alignment=Qt.AlignCenter)
        left_panel = QWidget()
        lyt_left = QVBoxLayout(left_panel)
        lyt_left.setContentsMargins(0, 0, 0, 0)
        lyt_left.setSpacing(4)
        lyt_left.addWidget(self.left_image_label)
        lyt_left.addWidget(self.timeline_widget)

        # right panel (quantitative charts / metadata)
        self.side_panel = SidePanel()

        main_splitter = QSplitter()
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(self.side_panel)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        # ▸ Assemble central widget
        central = QWidget()
        central_lyt = QVBoxLayout(central)
        central_lyt.setContentsMargins(8, 8, 8, 8)
        central_lyt.setSpacing(6)
        central_lyt.addWidget(main_splitter)
        self.setCentralWidget(central)

    # ──────────────────────── THEME TOGGLE ────────────────────
    def _toggle_theme(self, checked: bool) -> None:
        self._dark_mode = checked
        QApplication.instance().setPalette(make_dark_palette() if checked else make_light_palette())
        sender: QToolButton | None = self.sender()  # type: ignore[attr-defined]
        if sender is not None:
            sender.setIcon(
                QIcon.fromTheme("weather-clear-night" if checked else "weather-clear")
            )

    # ───────────────────── IMPORT DIALOG ──────────────────────
    def _show_import_dialog(self) -> None:
        dlg = DicomImportDialog(Path("data"), self)
        dlg.files_imported.connect(lambda _: self._scan_folder())
        dlg.exec()

    # ───────────────────────── FOLDER SCAN ─────────────────────
    def _scan_folder(self) -> None:
        combo = self.patient_bar.id_combo
        combo.clear()

        self._patient_id_map = scan_dicom_directory(Path("data"))
        combo.addItems([f"ID : {pid}" for pid in sorted(self._patient_id_map)])
        combo.clearSelection()

        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([])
        self._build_nav(0)

    # ───────────────────── PATIENT OPERATIONS ──────────────────
    def _on_patient_selected(self, txt: str) -> None:
        if " : " not in txt:
            return
        pid = txt.split(" : ", maxsplit=1)[1]
        self._load_patient(pid)

    def _load_patient(self, pid: str) -> None:
        scans = self._loaded.get(pid)

        if scans is None:
            scans = []
            for p in self._patient_id_map.get(pid, []):
                try:
                    frames, meta = load_frames_and_metadata(p)
                    scans.append({"meta": meta, "frames": frames, "path": p})
                except Exception as exc:
                    print(f"[WARN] failed to read {p}: {exc}")
            scans.sort(key=lambda s: s["meta"].get("study_date", ""))
            self._loaded[pid] = scans

        # update patient meta‑info & timeline display
        self.patient_bar.set_patient_meta(scans[-1]["meta"] if scans else {})
        self.timeline_widget.display_timeline(scans)
        self._build_nav(len(scans))

    # ─────────────────────── NAVIGATION BAR ───────────────────
    def _build_nav(self, n_scans: int) -> None:
        """Refresh navigation toolbar based on number of scans."""
        self.nav_toolbar.clear()

        if n_scans == 0:
            return

        # ▸ View selector
        self.nav_toolbar.addWidget(self.view_selector)

        # ▸ Zoom buttons (+ / –)
        zoom_cfg = [
            ("Zoom In", self.zoom_in, self.style().standardIcon(QStyle.SP_ArrowUp)),
            ("Zoom Out", self.zoom_out, self.style().standardIcon(QStyle.SP_ArrowDown)),
        ]
        for tip, slot, icon in zoom_cfg:
            btn = QToolButton()
            btn.setToolTip(tip)
            btn.setIcon(icon)
            btn.clicked.connect(slot)  # type: ignore[arg-type]
            self.nav_toolbar.addWidget(btn)

        self.nav_toolbar.addSeparator()

        # ▸ Scan‑jump actions
        for idx in range(n_scans):
            act = QAction(
                f"Scan {idx + 1}",
                self,
                triggered=partial(self.timeline_widget.scroll_to_scan, idx),
            )
            self.nav_toolbar.addAction(act)

    # ────────────────────────── CALLBACKS ─────────────────────
    def _set_view(self, view: str) -> None:
        self.timeline_widget.set_active_view(view)

    def _set_mode(self, mode: str) -> None:
        self.timeline_widget.set_image_mode(mode)

    # ────────────────────────── ZOOM CTRL ──────────────────────
    def zoom_in(self) -> None:
        self.timeline_widget.zoom_in()

    def zoom_out(self) -> None:
        self.timeline_widget.zoom_out()
