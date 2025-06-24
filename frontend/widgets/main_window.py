from pathlib import Path
from typing import Dict

import numpy as np
from PyQt5.QtCore  import Qt
from PyQt5.QtGui   import QPixmap, QImage
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QFileDialog,
    QMessageBox, QToolBar, QAction, QSplitter
)

from backend.dicom_loader import load_frames_and_metadata

from .patient_info  import PatientInfoBar
from .view_selector import ViewSelector
from .side_panel    import SidePanel


class MainWindow(QMainWindow):
    """Patient bar → selector card → gambar; side-panel kanan."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BSI Analyzer")
        self.resize(1480, 880)
        self._patients: Dict[str, dict] = {}
        self._build_ui()

    # --------------------------------------------------------- UI build
    def _build_ui(self):
        # patient bar
        self.patient_bar = PatientInfoBar()
        self.patient_bar.id_combo.currentTextChanged.connect(self._on_patient_changed)
        tb_patient = QToolBar(movable=False)
        tb_patient.addWidget(self.patient_bar)
        self.addToolBar(Qt.TopToolBarArea, tb_patient)

        # actions toolbar
        tb_act = QToolBar("Actions", movable=False)
        tb_act.addAction(QAction("Open DICOM", self, triggered=self._open_dicom))
        tb_act.addAction(QAction("Export Report", self, triggered=self._export_report))
        self.addToolBar(Qt.TopToolBarArea, tb_act)

        # left side: selector + image
        left = QWidget()
        vbox = QVBoxLayout(left)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        self.view_selector = ViewSelector()
        self.view_selector.view_changed.connect(self._update_image)
        vbox.addWidget(self.view_selector, 0, Qt.AlignHCenter)

        self.img_lbl = QLabel(alignment=Qt.AlignCenter)
        self.img_lbl.setStyleSheet("background:#000;")
        vbox.addWidget(self.img_lbl, 1)

        # right side
        self.side_panel = SidePanel()

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.side_panel)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        self.setCentralWidget(split)

    # --------------------------------------------------------- slots
    def _open_dicom(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select DICOM", "", "DICOM (*.dcm)"
        )
        if not path:
            return
        try:
            frames, meta = load_frames_and_metadata(path)
        except Exception as exc:
            QMessageBox.critical(self, "DICOM Error", str(exc))
            return
        if not frames:
            QMessageBox.warning(self, "Empty", "Tidak ada frame di file.")
            return

        pid = meta.get("patient_id") or f"patient_{len(self._patients)+1}"
        self._patients[pid] = {"frames": frames, "meta": meta}

        if pid not in [self.patient_bar.id_combo.itemText(i)
                       for i in range(self.patient_bar.id_combo.count())]:
            self.patient_bar.id_combo.addItem(pid)
        self.patient_bar.id_combo.setCurrentText(pid)  # trigger update

    def _export_report(self):
        print("[Export] – sambungkan backend nanti")

    def _on_patient_changed(self, pid: str):
        if pid not in self._patients:
            return
        data = self._patients[pid]
        self.patient_bar.set_patient_meta(data["meta"])
        self.view_selector.set_views(list(data["frames"].keys()))
        self._update_image()

    def _update_image(self):
        pid = self.patient_bar.id_combo.currentText()
        if pid not in self._patients:
            return
        view = self.view_selector.current_view()
        frame = self._patients[pid]["frames"].get(view)
        if frame is None:
            self.img_lbl.clear()
            return
        pix = self._array_to_pixmap(frame)
        self.img_lbl.setPixmap(
            pix.scaled(self.img_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_image()

    # ------------------------------ helper
    @staticmethod
    def _array_to_pixmap(arr: np.ndarray) -> QPixmap:
        img = arr.astype(np.float32)
        img -= img.min()
        if img.max() > 0:
            img = img / img.max() * 255
        img = img.astype(np.uint8)
        h, w = img.shape
        qimg = QImage(img.data, w, h, w, QImage.Format_Grayscale8)
        return QPixmap.fromImage(qimg)
