from PySide6.QtCore    import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox


class FrameSelector(QWidget):
    """
    Dropdown kecil: Anterior | Posterior.
    Meng-emit signal frame_changed(index) tiap kali diganti.
    """
    frame_changed = Signal(int)      # 0 = Anterior, 1 = Posterior

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        layout.addWidget(QLabel("View:", alignment=Qt.AlignRight | Qt.AlignVCenter))
        self.combo = QComboBox()
        self.combo.addItems(["Anterior", "Posterior"])
        self.combo.currentIndexChanged.connect(self.frame_changed.emit)

        layout.addWidget(self.combo)
        layout.addStretch()

    def current_index(self) -> int:
        return self.combo.currentIndex()
