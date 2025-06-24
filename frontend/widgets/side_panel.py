from PyQt5.QtCore    import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

from .bsi_canvas import BSICanvas


class SidePanel(QWidget):
    """Right-hand side with chart + comment box."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.chart = BSICanvas(self)

        self.comment_box = QLabel(
            "Quantitative analysis shows n regions with increased uptake "
            "and a Bone Scan Index of x%.",
            self
        )
        self.comment_box.setWordWrap(True)
        self.comment_box.setAlignment(Qt.AlignTop)
        self.comment_box.setStyleSheet(
            "background:#fff;border:1px solid #ccc;padding:6px;"
        )
        self.comment_box.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        layout.addWidget(self.chart, 3)
        layout.addWidget(self.comment_box, 2)
