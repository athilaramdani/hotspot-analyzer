# core\gui\patient_info_bar.py
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QLineEdit
from datetime import datetime
from .searchable_combobox import SearchableComboBox
from core.gui.ui_constants import PATIENT_INFO_FIELD_STYLE, PATIENT_INFO_LABEL_STYLE

class PatientInfoBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(16, 8, 16, 8)
        self.grid_layout.setHorizontalSpacing(24)
        self.grid_layout.setVerticalSpacing(6)

        #   Detect available font family for CSS
        self.font_family = "Poppins" if "Poppins" in QFont().families() else "Arial"

        #   Define CSS styles with font included
        self.label_style = f"""
            QLabel {{
                color: #000;
                font-family: '{self.font_family}';
                font-weight: bold;
                font-size: 17px;
                padding: 4px 8px;
                background: transparent;
            }}
        """

        #   Alternative: Combine with existing style constant
        base_field_style = PATIENT_INFO_FIELD_STYLE if PATIENT_INFO_FIELD_STYLE else ""
        
        self.field_style = f"""
            QLineEdit {{
                font-family: '{self.font_family}';
                font-size: 12px;
                font-weight:bold;
            }}
        """ + base_field_style

        self.combo_style = f"""
            QComboBox {{
                font-family: '{self.font_family}';
                font-size: 12px;
                font-weight: normal;
                min-height: 20px;
                padding: 2px 4px;
                border: 1px solid #ccc;
                background: white;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
        """

        # Inisialisasi QLineEdit dengan CSS styling
        self.name_edit = QLineEdit(readOnly=True)
        self.birth_edit = QLineEdit(readOnly=True)
        self.age_edit = QLineEdit(readOnly=True)
        self.sex_edit = QLineEdit(readOnly=True)
        self.weight_edit = QLineEdit(readOnly=True)
        self.height_edit = QLineEdit(readOnly=True)
        self.study_edit = QLineEdit(readOnly=True)

        # Apply CSS styling to all fields
        widgets = [self.name_edit, self.birth_edit, self.age_edit, self.sex_edit, 
                  self.weight_edit, self.height_edit, self.study_edit]
        for w in widgets:
            w.setStyleSheet(self.field_style)

        # Set minimum width for consistent alignment
        self.name_edit.setMinimumWidth(200)
        self.birth_edit.setMinimumWidth(100)
        self.age_edit.setMinimumWidth(60)
        self.sex_edit.setMinimumWidth(60)
        self.weight_edit.setMinimumWidth(70)
        self.height_edit.setMinimumWidth(70)
        self.study_edit.setMinimumWidth(100)

        # Membuat label dengan CSS styling
        # Row 0: Patient ID | Name | Age | Sex
        self._create_label("Patient ID:", 0, 0)
        self._create_label("Name:", 0, 2)
        self._create_label("Age:", 0, 4)
        self._create_label("Sex:", 0, 6)
        
        # Row 1: Birth Date | Weight | Height | Study Date
        self._create_label("Birth Date:", 1, 0)
        self._create_label("Weight:", 1, 2)
        self._create_label("Height:", 1, 4)
        self._create_label("Study Date:", 1, 6)

        # Menambahkan QLineEdit ke layout
        # Row 0: Patient ID(0,1) | Name(0,3) | Age(0,5) | Sex(0,7)
        self.grid_layout.addWidget(self.name_edit, 0, 3)
        self.grid_layout.addWidget(self.age_edit, 0, 5)
        self.grid_layout.addWidget(self.sex_edit, 0, 7)
        
        # Row 1: Birth Date(1,1) | Weight(1,3) | Height(1,5) | Study Date(1,7)
        self.grid_layout.addWidget(self.birth_edit, 1, 1)
        self.grid_layout.addWidget(self.weight_edit, 1, 3)
        self.grid_layout.addWidget(self.height_edit, 1, 5)
        self.grid_layout.addWidget(self.study_edit, 1, 7)

        # Memberikan 'stretch' ke kolom terakhir
        self.grid_layout.setColumnStretch(8, 1)

    def _create_label(self, text, row, col):
        l = QLabel(text, self)
        l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        l.setStyleSheet(self.label_style)  #   Use CSS styling
        self.grid_layout.addWidget(l, row, col)

    def set_id_combobox(self, combobox: SearchableComboBox):
        self.id_combo = combobox
        #   Apply CSS styling to combobox
        self.id_combo.setStyleSheet(self.combo_style)
        self.id_combo.setMinimumWidth(150)
        self.grid_layout.addWidget(self.id_combo, 0, 1)

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

        # Birth date with age calculation
        birth_date_str = meta.get("patient_birth_date", "")
        try:
            birth_date = datetime.strptime(birth_date_str, "%Y%m%d")
            self.birth_edit.setText(birth_date.strftime("%d-%m-%Y"))
            
            # Calculate age
            today = datetime.now()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            self.age_edit.setText(f"{age}Y")
        except (ValueError, TypeError):
            self.birth_edit.setText(birth_date_str or "N/A")
            self.age_edit.setText("N/A")

        # Weight and Height
        weight = meta.get("patient_weight", "")
        if weight:
            try:
                weight_val = float(weight)
                self.weight_edit.setText(f"{weight_val:.0f} kg")
            except (ValueError, TypeError):
                self.weight_edit.setText("N/A")
        else:
            self.weight_edit.setText("N/A")

        height = meta.get("patient_size", "")
        if height:
            try:
                height_val = float(height)
                self.height_edit.setText(f"{height_val:.2f} m")
            except (ValueError, TypeError):
                self.height_edit.setText("N/A")
        else:
            self.height_edit.setText("N/A")

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

        # For PET mode, create a simple field for patient ID
        if not hasattr(self, 'id_combo') and not hasattr(self, 'id_edit'):
            self.id_edit = QLineEdit(readOnly=True)
            self.id_edit.setStyleSheet(self.field_style)  #   Use CSS styling
            self.id_edit.setMinimumWidth(150)
            self.grid_layout.addWidget(self.id_edit, 0, 1)

        # Set patient ID
        if hasattr(self, 'id_edit'):
            self.id_edit.setText(pet_data.patient_id)

        # Extract info from PET metadata
        pet_info = self._extract_pet_info(pet_data)
        
        # Update fields with available info
        self.name_edit.setText(pet_info.get("name", "N/A"))
        self.birth_edit.setText(pet_info.get("birth_date", "N/A"))
        self.age_edit.setText("N/A")  # Usually not available in PET NIfTI
        self.sex_edit.setText(pet_info.get("sex", "N/A"))
        self.weight_edit.setText("N/A")  # Usually not available in PET NIfTI
        self.height_edit.setText("N/A")  # Usually not available in PET NIfTI
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
            metadata = pet_data.pet_metadata
            
            if 'patient_name' in metadata:
                info["name"] = metadata['patient_name']
            if 'patient_birth_date' in metadata:
                info["birth_date"] = metadata['patient_birth_date']
            if 'patient_sex' in metadata:
                info["sex"] = metadata['patient_sex']
            if 'study_date' in metadata:
                info["study_date"] = metadata['study_date']
        
        # Default name for PET files
        if info["name"] == "N/A":
            info["name"] = f"Patient {pet_data.patient_id}"
        
        return info

    def clear_info(self, keep_id_list=False):
        if not keep_id_list and hasattr(self, 'id_combo'):
            self.id_combo.setCurrentIndex(0)
        if hasattr(self, 'id_edit'):
            self.id_edit.setText("N/A")
        self.name_edit.setText("N/A")
        self.birth_edit.setText("N/A")
        self.age_edit.setText("N/A")
        self.sex_edit.setText("N/A")
        self.weight_edit.setText("N/A")
        self.height_edit.setText("N/A")
        self.study_edit.setText("N/A")

    def clear(self):
        """Clear all info - alias for clear_info"""
        self.clear_info(keep_id_list=False)