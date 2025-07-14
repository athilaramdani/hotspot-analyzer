# frontend/widgets/patient_info.py
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QLineEdit
from datetime import datetime
from .searchable_combobox import SearchableComboBox

class PatientInfoBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)  # Beri batas maksimal
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(16, 8, 16, 8)
        self.grid_layout.setHorizontalSpacing(24)
        self.grid_layout.setVerticalSpacing(6)

        font_family = "Poppins" if "Poppins" in QFont().families() else "Arial"
        self.bold_font = QFont(font_family, 10, QFont.Bold)
        normal_font = QFont(font_family, 10)

        # Inisialisasi QLineEdit
        self.name_edit = QLineEdit(readOnly=True)
        self.birth_edit = QLineEdit(readOnly=True)
        self.sex_edit = QLineEdit(readOnly=True)
        self.study_edit = QLineEdit(readOnly=True)

        widgets = [self.name_edit, self.birth_edit, self.sex_edit, self.study_edit]
        for w in widgets:
            w.setFont(normal_font)

        # Set minimum width for Name to ensure consistent alignment and space
        self.name_edit.setMinimumWidth(250)
        # Menambahkan minimum width untuk QLineEdit lainnya jika diperlukan untuk konsistensi
        self.birth_edit.setMinimumWidth(150) # Contoh: memberi ruang untuk tanggal
        self.sex_edit.setMinimumWidth(80)    # Contoh: memberi ruang untuk 'Male'/'Female'
        self.study_edit.setMinimumWidth(150) # Contoh: memberi ruang untuk tanggal

        # Membuat label
        self._create_label("Patient ID:", 0, 0)
        self._create_label("Name:", 0, 2)
        self._create_label("Birth Date:", 1, 0)
        self._create_label("Sex:", 1, 2)
        self._create_label("Study Date:", 1, 4)

        # Menambahkan QLineEdit ke layout
        # Perhatikan penempatan kolom:
        # Patient ID di (0,1), Name di (0,3)
        # Birth Date di (1,1), Sex di (1,3), Study Date di (1,5)
        self.grid_layout.addWidget(self.name_edit, 0, 3)
        self.grid_layout.addWidget(self.birth_edit, 1, 1)
        self.grid_layout.addWidget(self.sex_edit, 1, 3)
        self.grid_layout.addWidget(self.study_edit, 1, 5)

        # Memberikan 'stretch' ke kolom terakhir untuk mengisi ruang kosong
        # Ini akan mendorong elemen ke kiri dan memberi ruang ekstra di kanan
        self.grid_layout.setColumnStretch(6, 1)

    def _create_label(self, text, row, col):
        l = QLabel(text, self)
        l.setFont(self.bold_font)
        l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.grid_layout.addWidget(l, row, col)

    def set_id_combobox(self, combobox: SearchableComboBox):
        self.id_combo = combobox
        font = QFont("Poppins", 10) if "Poppins" in QFont().families() else QFont("Arial", 10)
        self.id_combo.setFont(font)
        
        # Atur lebar minimum untuk combobox agar tidak terlalu sempit
        self.id_combo.setMinimumWidth(150) # Sesuaikan nilai ini sesuai kebutuhan
        
        self.grid_layout.addWidget(self.id_combo, 0, 1) # Penempatan combobox
        
        # Tambahkan stretch pada kolom tempat combobox berada jika perlu,
        # tapi biasanya setMinimumWidth dan setHorizontalSpacing sudah cukup.
        # Jika Anda ingin combobox mengambil lebih banyak ruang di kolomnya,
        # bisa menggunakan self.grid_layout.setColumnStretch(1, 1)
        # Namun, ini akan membuat kolom 1 melebar lebih banyak, yang mungkin menggeser kolom lain.
        # Coba dulu tanpa ini.

    def set_patient_meta(self, meta: dict):
        if not meta:
            self.clear_info(keep_id_list=True)
            return

        raw_name = meta.get("patient_name", "N/A")
        if isinstance(raw_name, str) and '^' in raw_name:
            parts = raw_name.split('^')
            formatted_name = f"{parts[1]} {parts[0]}".strip()
        else:
            formatted_name = str(raw_name)

        self.name_edit.setText(formatted_name)
        self.sex_edit.setText(meta.get("patient_sex", "N/A"))

        birth_date_str = meta.get("patient_birth_date", "")
        try:
            self.birth_edit.setText(datetime.strptime(birth_date_str, "%Y%m%d").strftime("%d-%m-%Y"))
        except (ValueError, TypeError):
            self.birth_edit.setText(birth_date_str or "N/A")

        study_date_str = meta.get("study_date", "")
        try:
            self.study_edit.setText(datetime.strptime(study_date_str, "%Y%m%d").strftime("%d-%m-%Y"))
        except (ValueError, TypeError):
            self.study_edit.setText(study_date_str or "N/A")

    def update_from_pet_data(self, pet_data):
        """Update patient info from PET data"""
        if not pet_data:
            self.clear_info(keep_id_list=True)
            return

        # Set patient ID directly since we don't have a combobox in PET mode
        if hasattr(self, 'id_combo'):
            # For SPECT mode with combo box
            pass
        else:
            # For PET mode, create a simple label or linedit for patient ID
            if not hasattr(self, 'id_label_created'):
                self.id_edit = QLineEdit(readOnly=True)
                font = QFont("Poppins", 10) if "Poppins" in QFont().families() else QFont("Arial", 10)
                self.id_edit.setFont(font)
                self.id_edit.setMinimumWidth(150)
                self.grid_layout.addWidget(self.id_edit, 0, 1)
                self.id_label_created = True

        # Set patient ID
        if hasattr(self, 'id_edit'):
            self.id_edit.setText(pet_data.patient_id)

        # Extract info from PET metadata
        pet_info = self._extract_pet_info(pet_data)
        
        # Update fields with available info
        self.name_edit.setText(pet_info.get("name", "N/A"))
        self.birth_edit.setText(pet_info.get("birth_date", "N/A"))
        self.sex_edit.setText(pet_info.get("sex", "N/A"))
        self.study_edit.setText(pet_info.get("study_date", "N/A"))

    def _extract_pet_info(self, pet_data):
        """Extract patient info from PET data"""
        info = {
            "name": "N/A",
            "birth_date": "N/A", 
            "sex": "N/A",
            "study_date": "N/A"
        }
        
        # Try to extract from metadata if available
        if pet_data.pet_metadata:
            # Check if metadata contains patient info
            metadata = pet_data.pet_metadata
            
            # Some NIfTI files might have patient info in header
            if 'patient_name' in metadata:
                info["name"] = metadata['patient_name']
            if 'patient_birth_date' in metadata:
                info["birth_date"] = metadata['patient_birth_date']
            if 'patient_sex' in metadata:
                info["sex"] = metadata['patient_sex']
            if 'study_date' in metadata:
                info["study_date"] = metadata['study_date']
        
        # For NIfTI files, patient info is usually not embedded
        # So we'll show basic info based on what we know
        info["name"] = f"Patient {pet_data.patient_id}"
        
        return info

    def clear_info(self, keep_id_list=False):
        if not keep_id_list and hasattr(self, 'id_combo'):
            self.id_combo.setCurrentIndex(0)
        if hasattr(self, 'id_edit'):
            self.id_edit.setText("N/A")
        self.name_edit.setText("N/A")
        self.birth_edit.setText("N/A")
        self.sex_edit.setText("N/A")
        self.study_edit.setText("N/A")

    def clear(self):
        """Clear all info - alias for clear_info"""
        self.clear_info(keep_id_list=False)