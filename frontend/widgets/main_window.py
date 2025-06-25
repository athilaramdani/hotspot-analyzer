# frontend/widgets/main_window.py
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Dict, List

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QAction
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QSplitter, QPushButton,
    QMessageBox
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader      import load_frames_and_metadata
from .dicom_import_dialog      import DicomImportDialog
from .searchable_combobox      import SearchableComboBox
from .patient_info             import PatientInfoBar
from .scan_timeline            import ScanTimelineWidget
from .side_panel               import SidePanel


# --------------------------------------------------------------------------- window
class MainWindow(QMainWindow):
    """
    Tampilan utama:
        ┌── toolbar patient ‐ info
        ├── toolbar actions  (Import DICOM, Rescan Folder)
        ├── toolbar scan nav (dinamis)
        └── splitter  (timeline | chart+comment)
    """
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)

        # cache
        self._patient_id_map: Dict[str, List[Path]] = {}
        self._loaded_patients_cache: Dict[str, List[Dict]] = {}

        self._build_ui()
        self._initial_patient_scan()

    # --------------------------------------------------------------------- UI build
    def _build_ui(self) -> None:
        # ---- 1. Patient bar ------------------------------------------------
        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)

        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)

        tb_patient = QToolBar(movable=False)
        tb_patient.addWidget(self.patient_bar)
        self.addToolBar(Qt.TopToolBarArea, tb_patient)

        # ---- 2. Global actions --------------------------------------------
        tb_act = QToolBar("Global Actions", movable=False)
        tb_act.addAction(QAction("Import DICOM…", self, triggered=self._show_import))
        tb_act.addAction(QAction("Rescan Folder", self, triggered=self._initial_patient_scan))
        self.addToolBar(Qt.TopToolBarArea, tb_act)

        # ---- 3. Scan‑navigation toolbar (isi dinamis) ----------------------
        self.scan_nav_toolbar = QToolBar("Scan Navigation", movable=False)
        self.addToolBar(Qt.TopToolBarArea, self.scan_nav_toolbar)

        # ---- 4. Main splitter (timeline | side‑panel) ----------------------
        self.timeline_widget = ScanTimelineWidget()   # kiri
        self.side_panel      = SidePanel()            # kanan

        splitter = QSplitter()
        splitter.addWidget(self.timeline_widget)
        splitter.addWidget(self.side_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

    # --------------------------------------------------------------------- Import DICOM
    def _show_import(self) -> None:
        """
        Buka dialog drag‑and‑drop + progress.  Setelah selesai → refresh list.
        """
        dlg = DicomImportDialog(Path("data"), self)
        dlg.files_imported.connect(lambda _: self._initial_patient_scan())  # perbarui UI
        dlg.exec()

    # --------------------------------------------------------------------- Scan folder
    def _initial_patient_scan(self) -> None:
        """
        Scan folder ./data → perbarui combobox & kosongkan tampilan.
        """
        id_combo = self.patient_bar.id_combo
        id_combo.clear()

        self._patient_id_map = scan_dicom_directory(Path("data"))
        items = [f"ID : {pid}" for pid in sorted(self._patient_id_map.keys())]
        id_combo.addItems(items)
        id_combo.clearSelection()

        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([])
        self.scan_nav_toolbar.clear()

    # --------------------------------------------------------------------- Pilih pasien
    def _on_patient_selected(self, text: str) -> None:
        try:
            pid = text.split(" : ")[1].strip()
        except IndexError:
            return
        self._load_and_display_patient(pid)

    def _load_and_display_patient(self, pid: str) -> None:
        # cache agar load sekali saja
        scans = self._loaded_patients_cache.get(pid)
        if scans is None:
            paths = self._patient_id_map.get(pid, [])
            scans = []
            for p in paths:
                try:
                    frames, meta = load_frames_and_metadata(p)
                    scans.append({"meta": meta, "frames": frames})
                except Exception as e:
                    print(f"[WARN] gagal baca {p}: {e}")
            scans.sort(key=lambda s: s["meta"].get("study_date", ""))
            self._loaded_patients_cache[pid] = scans

        if scans:
            self.patient_bar.set_patient_meta(scans[-1]["meta"])
            self._populate_scan_nav(len(scans))
            self.timeline_widget.display_timeline(scans)
        else:
            self.timeline_widget.display_timeline([])
            self.scan_nav_toolbar.clear()

    # --------------------------------------------------------------------- Toolbar scan‑nav
    def _populate_scan_nav(self, n_scans: int) -> None:
        self.scan_nav_toolbar.clear()
        if not n_scans:
            return

        # toggle anterior/posterior
        self._view_btn: Dict[str, QPushButton] = {}
        for v in ("Anterior", "Posterior"):
            b = QPushButton(v, checkable=True)
            b.clicked.connect(partial(self._set_timeline_view, v))
            self.scan_nav_toolbar.addWidget(b)
            self._view_btn[v] = b
        self._view_btn["Anterior"].setChecked(True)
        self.scan_nav_toolbar.addSeparator()

        # tombol setiap scan
        for i in range(n_scans):
            act = QAction(f"Scan {i+1}", self,
                          triggered=partial(self.timeline_widget.scroll_to_scan, i))
            self.scan_nav_toolbar.addAction(act)

    def _set_timeline_view(self, view: str) -> None:
        for v, btn in self._view_btn.items():
            btn.setChecked(v == view)
        self.timeline_widget.set_active_view(view)
