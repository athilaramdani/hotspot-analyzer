# features/dicom_import/gui/doctor_selection_dialog.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton
)

# Import session config
from core.config.sessions import (
    get_available_session_codes, 
    get_available_modalities,
    get_session_manager
)

class DoctorSelectionDialog(QDialog):
    """
    Dialog pemilihan pasien *dan* jenis modalitas (SPECT / PET).
    Setelah OK ditekan, atribut:
        • self.selected_doctor_id
        • self.selected_modality        (string "SPECT" | "PET")
    akan terisi.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pilih Pasien & Modalitas")
        self.setModal(True)

        # Hilangkan tombol close (✕)
        self.setWindowFlag(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        self.selected_doctor_id: str | None = None
        self.selected_modality: str | None = None
        self.session_manager = get_session_manager()

        # ---------- UI ----------
        layout = QVBoxLayout(self)

        # Pilih kode pasien
        layout.addWidget(QLabel("Pilih kode pasien:"))
        self.doctor_combo = QComboBox()
        
        # Load dari config sessions.py
        available_codes = get_available_session_codes()
        self.doctor_combo.addItems(available_codes)
        layout.addWidget(self.doctor_combo)

        # Pilih modalitas
        layout.addWidget(QLabel("Pilih modalitas gambar:"))
        self.modality_combo = QComboBox()
        
        # Load dari config sessions.py
        available_modalities = get_available_modalities()
        self.modality_combo.addItems(available_modalities)
        layout.addWidget(self.modality_combo)

        # Tombol OK
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

        # Load last session jika ada
        self._load_last_session()

    def _load_last_session(self):
        """Load last used session if enabled"""
        if self.session_manager.get_session_config("remember_last_session", True):
            last_session = self.session_manager.get_last_session()
            if last_session:
                # Set doctor combo
                session_code = last_session.get("session_code")
                if session_code:
                    index = self.doctor_combo.findText(session_code)
                    if index >= 0:
                        self.doctor_combo.setCurrentIndex(index)
                
                # Set modality combo
                modality = last_session.get("modality", "SPECT")
                modality_index = self.modality_combo.findText(modality)
                if modality_index >= 0:
                    self.modality_combo.setCurrentIndex(modality_index)

    # --------------------------------------------------
    def accept(self):
        """Simpan pilihan & tutup dialog."""
        self.selected_doctor_id = self.doctor_combo.currentText()
        self.selected_modality = self.modality_combo.currentText()
        
        # Create session menggunakan session manager
        try:
            session = self.session_manager.create_session(
                self.selected_doctor_id,
                self.selected_modality
            )
            print(f"[SESSION] Created: {session['session_id']}")
        except Exception as e:
            print(f"[ERROR] Failed to create session: {e}")
        
        super().accept()