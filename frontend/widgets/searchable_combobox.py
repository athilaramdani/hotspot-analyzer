from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QLineEdit, QListView, QVBoxLayout, QWidget, QFrame

class SearchableComboBox(QComboBox):
    item_selected = pyqtSignal(str)
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setEditable(True); self.lineEdit().setReadOnly(True); self.lineEdit().setAlignment(Qt.AlignCenter)
        self._setup_popup_view()
        self.activated.connect(self._emit_custom_signal)

    def _setup_popup_view(self):
        self.list_view = QListView(self); container = QWidget(); layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5); layout.setSpacing(5)
        self.search_bar = QLineEdit(); self.search_bar.setPlaceholderText("Search Patient ID...")
        self.search_bar.textChanged.connect(self._filter_items)
        separator = QFrame(); separator.setFrameShape(QFrame.HLine); separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(self.search_bar); layout.addWidget(separator); layout.addWidget(self.list_view)
        self.setModel(self.list_view.model()); self.setView(self.list_view); self.view().setLayout(layout)

    def _filter_items(self, text: str):
        text = text.lower()
        for i in range(self.count()):
            if text in self.itemText(i).lower(): self.view().setRowHidden(i, False)
            else: self.view().setRowHidden(i, True)

    def showPopup(self):
        super().showPopup()
        self.view().setMinimumWidth(self.width()); self._filter_items(''); self.search_bar.clear(); self.search_bar.setFocus()
    
    def _emit_custom_signal(self, index: int):
        self.item_selected.emit(self.itemText(index))