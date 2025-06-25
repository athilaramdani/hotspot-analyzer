from typing import List

from PySide6.QtCore    import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton

class ViewSelector(QWidget):
    """
    Dinamis: set_views([...]) → membuat tombol card.
    Signal: view_changed(str) – label view terpilih.
    """
    view_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._btns = {}
        self.set_views(["Anterior", "Posterior"])   # default

    # ------------------------------------------------ public
    def set_views(self, labels: List[str]):
        # bersihkan
        for i in reversed(range(self._layout.count())):
            self._layout.itemAt(i).widget().deleteLater()
        self._btns.clear()

        for idx, lbl in enumerate(labels):
            btn = QPushButton(lbl, checkable=True)
            btn.setStyleSheet("""
                QPushButton {
                    border:1px solid #ccc; border-top-left-radius:6px;
                    border-top-right-radius:6px; padding:6px 16px;
                    background:#fafafa;
                }
                QPushButton:checked {
                    background:#4e73ff; color:white; border:1px solid #4e73ff;
                }
            """)
            btn.clicked.connect(lambda _, k=lbl: self._on_clicked(k))
            self._layout.addWidget(btn)
            self._btns[lbl] = btn

        if labels:
            self._btns[labels[0]].setChecked(True)

    def current_view(self) -> str:
        for lbl, btn in self._btns.items():
            if btn.isChecked():
                return lbl
        return ""

    # ------------------------------------------------ private
    def _on_clicked(self, label: str):
        for lbl, b in self._btns.items():
            b.setChecked(lbl == label)
        self.view_changed.emit(label)
