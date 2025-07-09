from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton
)

class PatientSelectionDialog(QDialog):
    """
    Dialog pemilihan pasien *dan* jenis modalitas (SPECT / PET).
    Setelah OK ditekan, atribut:
        • self.selected_patient_id
        • self.selected_modality        (string "SPECT" | "PET")
    akan terisi.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pilih Pasien & Modalitas")
        self.setModal(True)

        # Hilangkan tombol close (✕)
        self.setWindowFlag(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        self.selected_patient_id: str | None = None
        self.selected_modality:   str | None = None

        # ---------- UI ----------
        layout = QVBoxLayout(self)

        # Pilih kode pasien
        layout.addWidget(QLabel("Pilih kode pasien:"))
        self.patient_combo = QComboBox()
        self.patient_combo.addItems(["NSY", "ATL", "NBL"])  # ganti sesuai kebutuhan
        layout.addWidget(self.patient_combo)

        # Pilih modalitas
        layout.addWidget(QLabel("Pilih modalitas gambar:"))
        self.modality_combo = QComboBox()
        self.modality_combo.addItems(["SPECT", "PET"])
        layout.addWidget(self.modality_combo)

        # Tombol OK
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

    # --------------------------------------------------
    def accept(self):
        """Simpan pilihan & tutup dialog."""
        self.selected_patient_id = self.patient_combo.currentText()
        self.selected_modality   = self.modality_combo.currentText()
        super().accept()
