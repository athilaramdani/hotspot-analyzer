"""
PyQt5 desktop UI prototype for Bone Scan Index (BSI) workflow
----------------------------------------------------------------
* Single–file, but modular via small helper classes so it is easy
  to break out into separate modules later.
* Focuses *only* on the frontend layer – no model/backend logic.
* Compatible with Python 3.8+ & PyQt5 5.15+
* Uses matplotlib for the line‑chart placeholder on the right panel.

Run with:
    python frontend_ui.py

The code intentionally avoids business logic; slot methods print to
stdout so you can hook in your actual processing later.
"""

import sys
from pathlib import Path
from typing import List

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QToolBar,
    QAction,
    QPushButton,
    QTabWidget,
    QScrollArea,
    QGridLayout,
    QSplitter,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QFileDialog,
    QMessageBox,
)

# --- Optional matplotlib import for the chart in the side panel
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# -----------------------------------------------------------------------------
# Helper Widgets
# -----------------------------------------------------------------------------
class PatientInfoBar(QWidget):
    """Top bar with basic patient metadata."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self.name_edit = QLineEdit("John Dory")
        self.name_edit.setFixedWidth(160)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["M", "F"])
        self.birth_edit = QLineEdit("No birth date")
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setValue(50)
        self.opacity_spin.setSuffix("%")

        font_bold = QFont()
        font_bold.setBold(True)
        name_label = QLabel("Name:")
        name_label.setFont(font_bold)
        gender_label = QLabel("Gender:")
        gender_label.setFont(font_bold)
        birth_label = QLabel("Date of birth:")
        birth_label.setFont(font_bold)
        opacity_label = QLabel("Opacity:")
        opacity_label.setFont(font_bold)

        for w in (
            name_label,
            self.name_edit,
            gender_label,
            self.gender_combo,
            birth_label,
            self.birth_edit,
            opacity_label,
            self.opacity_spin,
        ):
            layout.addWidget(w)
            if isinstance(w, QLabel):
                w.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        layout.addStretch()


class ScanTabs(QTabWidget):
    """Dynamic tabs for multiple scan sessions (Scan1, Scan2, …)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setTabPosition(QTabWidget.North)
        self.setMovable(True)

    def add_scan(self, title: str, image_paths: List[Path]):
        widget = ScanGridWidget(image_paths)
        idx = self.addTab(widget, title)
        self.setCurrentIndex(idx)


class ScanGridWidget(QWidget):
    """Scrollable grid of anterior/posterior images for a single scan session."""

    def __init__(self, image_paths: List[Path], parent: QWidget | None = None):
        super().__init__(parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(16)
        grid.setContentsMargins(12, 12, 12, 12)

        for col, path in enumerate(image_paths):
            pix = QPixmap(str(path)).scaledToWidth(260, Qt.SmoothTransformation)
            lbl = QLabel()
            lbl.setPixmap(pix)
            lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(lbl, 0, col)
            caption = QLabel(path.stem)
            caption.setAlignment(Qt.AlignCenter)
            grid.addWidget(caption, 1, col)

        scroll.setWidget(container)
        vbox = QVBoxLayout(self)
        vbox.addWidget(scroll)


class BSICanvas(FigureCanvas):
    """Matplotlib line chart placeholder for BSI over time."""

    def __init__(self, parent: QWidget | None = None):
        fig = Figure(figsize=(4, 3))
        super().__init__(fig)
        self.axes = fig.add_subplot(111)
        self.plot_dummy()

    def plot_dummy(self):
        years = [0, 0.5, 1]
        bsi_values = [5.3, 4.1, 9.6]
        self.axes.clear()
        self.axes.plot(years, bsi_values, marker="o")
        self.axes.set_xlabel("Time (Years)")
        self.axes.set_ylabel("Bone Scan Index (%)")
        self.draw()


class SidePanel(QWidget):
    """Right‑hand side with chart + comment box."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.chart = BSICanvas()
        self.comment_box = QLabel(
            "Quantitative analysis shows n regions with increased uptake and a Bone Scan Index of x%."
        )
        self.comment_box.setWordWrap(True)
        self.comment_box.setAlignment(Qt.AlignTop)
        self.comment_box.setStyleSheet("background:#fff;border:1px solid #ccc;padding:6px;")
        self.comment_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.chart, 3)
        layout.addWidget(self.comment_box, 2)


# -----------------------------------------------------------------------------
# Main Window
# -----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BSI Analyzer Prototype")
        self.resize(1280, 720)
        self._build_ui()

    # ------------------------- UI construction helpers --------------------- #
    def _build_ui(self):
        # Patient info bar at the top
        self.patient_bar = PatientInfoBar()
        self.addToolBarBreak()
        patient_toolbar = QToolBar()
        patient_toolbar.setMovable(False)
        patient_toolbar.addWidget(self.patient_bar)
        self.addToolBar(Qt.TopToolBarArea, patient_toolbar)

        # Main splitter (images left, side panel right)
        self.scan_tabs = ScanTabs()
        self.side_panel = SidePanel()

        splitter = QSplitter()
        splitter.addWidget(self.scan_tabs)
        splitter.addWidget(self.side_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        # Toolbar with actions similar to EXINI UI
        self._build_main_toolbar()

    def _build_main_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)

        # Add sample actions
        open_act = QAction("Open Scan", self)
        open_act.triggered.connect(self.open_scan_dialog)
        export_act = QAction("Export Report", self)
        export_act.triggered.connect(lambda: print("Export clicked"))
        tb.addAction(open_act)
        tb.addSeparator()
        tb.addAction(export_act)

    # ------------------------- Slots & helpers ----------------------------- #
    def open_scan_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select scan images (anterior + posterior)",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not paths:
            return
        if len(paths) % 2 != 0:
            QMessageBox.warning(self, "Scan Import", "Harus genap (anterior+posterior).")
            return
        # Group every 2 images as one scan (simple heuristic)
        for i in range(0, len(paths), 2):
            scan_idx = (i // 2) + 1
            self.scan_tabs.add_scan(f"Scan {scan_idx}", [Path(p) for p in paths[i : i + 2]])


# -----------------------------------------------------------------------------
# Application entry point
# -----------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
