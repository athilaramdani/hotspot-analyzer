# frontend/widgets/dicom_import_dialog.py
from __future__ import annotations
from pathlib import Path
from typing  import List

from PySide6.QtCore    import Qt, QThread, Signal, Slot, QObject
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QFileDialog, QProgressBar, QMessageBox
)

from backend.input_data import process_files


# ---------------------------------------------------------------- worker (thread)
class _ImportWorker(QObject):
    progress = Signal(int, int, str)   # done, total, path
    finished = Signal(list)            # list[Path]
    failed   = Signal(str)

    def __init__(self, paths: List[Path], data_root: Path):
        super().__init__()
        self._paths     = paths
        self._data_root = data_root

    @Slot()
    def run(self):
        try:
            out = process_files(
                self._paths,
                data_root=self._data_root,
                progress_cb=lambda d, t, p: self.progress.emit(d, t, p),
            )
            self.finished.emit(out)
        except Exception as e:
            self.failed.emit(str(e))


# ---------------------------------------------------------------- dialog UI
class DicomImportDialog(QDialog):
    """
    Dialog drag‑and‑drop / pilih file  → jalan pipeline segmentasi + copy
    Emit `files_imported(list[Path])` ketika selesai.
    """
    files_imported = Signal(list)

    def __init__(self, data_root: Path, parent=None):
        # ----------- perbaikan: JANGAN pakai keyword 'flags' ---------------
        super().__init__(parent, Qt.Window)
        # -------------------------------------------------------------------
        self.setWindowTitle("Import DICOM")
        self.resize(480, 360)

        self._data_root = data_root
        self._paths: List[Path] = []

        # ------------------- layout & widgets ------------------------------
        vbox = QVBoxLayout(self)

        self._list = QListWidget(self)
        vbox.addWidget(QLabel("Files to import:"))
        vbox.addWidget(self._list, 1)

        btn_add   = QPushButton("Add Files…")
        btn_clear = QPushButton("Clear")
        self._btn_import = QPushButton("Import")
        self._btn_import.setEnabled(False)

        bar = QHBoxLayout()
        bar.addWidget(btn_add)
        bar.addWidget(btn_clear)
        bar.addStretch(1)
        bar.addWidget(self._btn_import)
        vbox.addLayout(bar)

        self._progress = QProgressBar()
        self._progress.hide()
        vbox.addWidget(self._progress)

        # ------------------- signals --------------------------------------
        btn_add.clicked.connect(self._on_add)
        btn_clear.clicked.connect(self._on_clear)
        self._btn_import.clicked.connect(self._on_import)

    # ------------------------------------------------ internal helpers
    def _update_buttons(self):
        self._btn_import.setEnabled(bool(self._paths))

    # ------------------------------------------------ slots
    def _on_add(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select DICOM files", str(Path.home()), "DICOM (*.dcm)"
        )
        for f in files:
            p = Path(f)
            if p not in self._paths:
                self._paths.append(p)
                QListWidgetItem(p.name, self._list)
        self._update_buttons()

    def _on_clear(self):
        self._paths.clear()
        self._list.clear()
        self._update_buttons()

    def _on_import(self):
        if not self._paths:
            return

        # lock UI
        self._btn_import.setEnabled(False)
        self._progress.setMaximum(len(self._paths))
        self._progress.setValue(0)
        self._progress.show()

        # worker thread
        self._thr    = QThread(self)
        self._worker = _ImportWorker(self._paths, self._data_root)
        self._worker.moveToThread(self._thr)

        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._thr.started.connect(self._worker.run)

        self._worker.finished.connect(self._thr.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thr.finished.connect(self._thr.deleteLater)
        self._thr.start()

    # ------------------- worker callbacks ---------------------------------
    @Slot(int, int, str)
    def _on_progress(self, done: int, total: int, p: str):
        self._progress.setValue(done)
        self._progress.setFormat(f"%v/%m  – {Path(p).name}")

    @Slot(list)
    def _on_done(self, out: list):
        self.files_imported.emit(out)
        self.accept()

    @Slot(str)
    def _on_failed(self, msg: str):
        QMessageBox.critical(self, "Import failed", msg)
        self.reject()
