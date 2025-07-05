from PySide6.QtCore import Qt 
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton
)

class PatientSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pilih Kode Pasien")
        self.setModal(True)
        # Menghilangkan tombol close (X) di pojok jendela
        self.setWindowFlag(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        self.selected_patient_id = None

        # --- UI Layout ---
        layout = QVBoxLayout(self)
        
        label = QLabel("Aplikasi ini memerlukan kode pasien untuk melanjutkan:")
        self.patient_combo = QComboBox()
        
        # ✅ Ganti dengan 3 kode spesifik Anda
        self.patient_combo.addItems([
            "NSY", 
            "ATL", 
            "NBL"
        ])
        
        # Hanya ada tombol OK
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        layout.addWidget(label)
        layout.addWidget(self.patient_combo)
        layout.addWidget(self.ok_button)

    def accept(self):
        """Saat OK ditekan, simpan ID yang dipilih."""
        self.selected_patient_id = self.patient_combo.currentText()
        super().accept()