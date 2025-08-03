# core\gui\searchable_combobox.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QComboBox, QLineEdit, QListView, QVBoxLayout, QWidget, QFrame
class SearchableComboBox(QComboBox):
    """
    Versi final dengan perbaikan stabilitas popup.
    - [FIX UTAMA] Menggunakan metode 'insertWidget' yang lebih aman untuk menjamin search box muncul.
    - [OK] Placeholder text ditampilkan dengan benar saat kosong.
    - [OK] Popup selalu muncul, bahkan jika hanya ada satu item.
    - [OK] Tinggi dropdown dibatasi untuk menampilkan maks 5 item.
    """
    item_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # Kita gunakan mode non-editable, ini lebih sederhana dan stabil untuk placeholder.
        self.setEditable(False) 
        self.setPlaceholderText("Search Patient ID")
        
        self.setMaxVisibleItems(5)
        self._list_view = QListView(self)
        self.setView(self._list_view)
        
        self._search_bar = None
        self._popup_customized = False
        
        self.currentIndexChanged.connect(self._on_item_activated)

    def mousePressEvent(self, event: QMouseEvent):
        """
        Memaksa popup untuk selalu muncul saat combobox diklik.
        """
        # Cek jika ada item atau tidak, tetap tampilkan popup agar search box muncul
        self.showPopup()
        event.accept()

    def clearSelection(self):
        """
        Membersihkan pilihan dan menampilkan placeholder text dengan mengatur index ke -1.
        """
        self.setCurrentIndex(-1)

    def showPopup(self):
        """
        Menimpa method dasar untuk menyuntikkan search bar saat popup muncul.
        """
        super().showPopup()

        # Kustomisasi hanya dilakukan sekali saat popup pertama kali dibuat.
        if not self._popup_customized:
            self._customize_popup()

        # Setiap kali popup muncul, reset filter dan fokus ke search bar.
        self.view().setMinimumWidth(self.width())
        self._filter_items('')
        if self._search_bar:
            self._search_bar.clear()
            self._search_bar.setFocus()

    def _customize_popup(self):
        """
        [PERBAIKAN KUNCI] Menyisipkan search bar ke dalam layout popup yang sudah ada.
        Ini adalah metode yang paling stabil dan tidak mengganggu.
        """
        popup_frame = self.view().parentWidget()
        if not popup_frame:
            print("Peringatan: Tidak dapat menemukan frame popup.")
            return

        # Dapatkan layout yang sudah ada dari frame popup.
        layout = popup_frame.layout()
        if not layout:
            print("Peringatan: Frame popup tidak memiliki layout.")
            return

        # Buat widget search bar dan separator
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("Search Patient ID...")
        self._search_bar.textChanged.connect(self._filter_items)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        
        # Sisipkan widget kita di bagian paling atas dari layout yang sudah ada.
        # Ini akan mendorong daftar item (yang sudah ada di layout) ke bawah.
        layout.insertWidget(0, self._search_bar)
        layout.insertWidget(1, separator)
        
        self._popup_customized = True

    def _filter_items(self, text: str):
        """
        Menyembunyikan/menampilkan item di list view berdasarkan teks pencarian.
        """
        text = text.lower()
        for i in range(self.count()):
            item_text = self.itemText(i)
            if item_text and text in item_text.lower():
                self.view().setRowHidden(i, False)
            else:
                self.view().setRowHidden(i, True)
    
    def _on_item_activated(self, index: int):
        """
        Mengirim sinyal 'item_selected' dengan teks dari item yang dipilih.
        """
        text = self.itemText(index)
        print(f"[DEBUG] item activated → {text} @ index {index}")
        if index >= 0:
            text = self.itemText(index)
            print(f"[DEBUG] item activated → {text}")
            self.item_selected.emit(text)