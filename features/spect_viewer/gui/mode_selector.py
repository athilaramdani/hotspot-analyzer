# frontend/widgets/mode_selector.py
from PySide6.QtCore    import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton


class ModeSelector(QWidget):
    """
    Tombol toggle untuk memilih tampilan gambar:
        • Original     – raw grayscale
        • Segment      – hasil AI (RGB)
        • Hotspot      – hotspot detection with bounding boxes
        • Both         – combined view
    """
    mode_changed = Signal(str)            # "Original" | "Segmentation" | "Hotspot" | "Both"

    _LABELS = ["Original", "Segmentation", "Hotspot", "Both"]


    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._btns = {}
        for i, lbl in enumerate(self._LABELS):
            btn = QPushButton(lbl, checkable=True)
            btn.setStyleSheet("""
                QPushButton {
                    border:1px solid #ccc; border-top-left-radius:6px;
                    border-top-right-radius:6px;
                    padding:6px 8px; /* <-- The smaller padding */
                    background:#fafafa;
                }
                QPushButton:checked {
                    background:#4e73ff; color:white; border:1px solid #4e73ff;
                }
            """)
            btn.clicked.connect(lambda _, k=lbl: self._on_clicked(k))
            lay.addWidget(btn)
            self._btns[lbl] = btn

        # default
        self._btns["Original"].setChecked(True)

    # ------------------------------------------------------------------ private
    def _on_clicked(self, label: str) -> None:
        for lbl, b in self._btns.items():
            b.setChecked(lbl == label)
        self.mode_changed.emit(label)

    # ------------------------------------------------------------------ public
    def current_mode(self) -> str:
        for lbl, b in self._btns.items():
            if b.isChecked():
                return lbl
        return "Original"