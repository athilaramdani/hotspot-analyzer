# frontend/widgets/pet_import_dialog.py
"""
Dialog untuk import data PET
"""
from pathlib import Path
from typing import Optional
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QGroupBox, QRadioButton, QButtonGroup, QMessageBox,
    QTextEdit, QDialogButtonBox
)

from backend.pet_directory_scanner import get_pet_files, validate_pet_file


class PETImportDialog(QDialog):
    """Dialog untuk import PET data dari file atau folder"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import PET Data")
        self.setModal(True)
        self.resize(600, 400)
        
        # Variables
        self.selected_path: Optional[Path] = None
        self.patient_id: str = ""
        
        self._create_ui()
        self._connect_signals()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        
        # Source selection group
        source_group = QGroupBox("Select Source")
        source_layout = QVBoxLayout(source_group)
        
        # Radio buttons for source type
        self.source_button_group = QButtonGroup()
        
        self.file_radio = QRadioButton("Import from file")
        self.folder_radio = QRadioButton("Import from folder")
        self.folder_radio.setChecked(True)  # Default
        
        self.source_button_group.addButton(self.file_radio)
        self.source_button_group.addButton(self.folder_radio)
        
        source_layout.addWidget(self.file_radio)
        source_layout.addWidget(self.folder_radio)
        
        # Path selection
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select file or folder...")
        self.browse_btn = QPushButton("Browse...")
        
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        source_layout.addLayout(path_layout)
        
        layout.addWidget(source_group)
        
        # Patient ID group
        patient_group = QGroupBox("Patient Information")
        patient_layout = QVBoxLayout(patient_group)
        
        patient_id_layout = QHBoxLayout()
        patient_id_layout.addWidget(QLabel("Patient ID:"))
        self.patient_id_edit = QLineEdit()
        self.patient_id_edit.setPlaceholderText("Enter patient ID...")
        patient_id_layout.addWidget(self.patient_id_edit)
        
        patient_layout.addLayout(patient_id_layout)
        
        # Auto-detect button
        self.auto_detect_btn = QPushButton("Auto-detect from folder name")
        patient_layout.addWidget(self.auto_detect_btn)
        
        layout.addWidget(patient_group)
        
        # Preview/info area
        info_group = QGroupBox("Import Information")
        info_layout = QVBoxLayout(info_group)
        
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(100)
        self.info_text.setReadOnly(True)
        self.info_text.setPlaceholderText("Select source to see information...")
        info_layout.addWidget(self.info_text)
        
        layout.addWidget(info_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)
        
        # Store references
        self.ok_button = button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
    
    def _connect_signals(self):
        """Connect signals to slots"""
        self.browse_btn.clicked.connect(self._browse_source)
        self.path_edit.textChanged.connect(self._on_path_changed)
        self.patient_id_edit.textChanged.connect(self._update_ok_button)
        self.auto_detect_btn.clicked.connect(self._auto_detect_patient_id)
        self.source_button_group.buttonClicked.connect(self._on_source_type_changed)
    
    def _browse_source(self):
        """Browse for file or folder"""
        if self.file_radio.isChecked():
            # Browse for file
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select PET file",
                "",
                "NIfTI files (*.nii *.nii.gz);;All files (*)"
            )
            if file_path:
                self.path_edit.setText(file_path)
        else:
            # Browse for folder
            folder_path = QFileDialog.getExistingDirectory(
                self, 
                "Select PET folder"
            )
            if folder_path:
                self.path_edit.setText(folder_path)
    
    def _on_path_changed(self, path_text: str):
        """Handle path change"""
        if not path_text:
            self.selected_path = None
            self.info_text.clear()
            self._update_ok_button()
            return
        
        path = Path(path_text)
        if not path.exists():
            self.selected_path = None
            self.info_text.setText("Path does not exist")
            self._update_ok_button()
            return
        
        self.selected_path = path
        self._update_info_display()
        self._update_ok_button()
    
    def _update_info_display(self):
        """Update the information display"""
        if not self.selected_path:
            return
        
        info_lines = []
        
        if self.selected_path.is_file():
            # Single file
            info_lines.append(f"File: {self.selected_path.name}")
            info_lines.append(f"Size: {self.selected_path.stat().st_size / 1024 / 1024:.2f} MB")
            
            # Validate if it's a valid PET file
            if validate_pet_file(self.selected_path):
                info_lines.append("✓ Valid PET file")
            else:
                info_lines.append("✗ Invalid PET file")
        else:
            # Folder
            info_lines.append(f"Folder: {self.selected_path.name}")
            
            # Get PET files in folder
            pet_files = get_pet_files(self.selected_path)
            if pet_files:
                info_lines.append(f"Found {len(pet_files)} PET files:")
                for file_type, file_path in pet_files.items():
                    info_lines.append(f"  • {file_type}: {file_path.name}")
            else:
                info_lines.append("No PET files found in folder")
        
        self.info_text.setText("\n".join(info_lines))
    
    def _auto_detect_patient_id(self):
        """Auto-detect patient ID from folder name"""
        if not self.selected_path:
            QMessageBox.warning(self, "Warning", "Please select a source first")
            return
        
        # Try to extract patient ID from path
        detected_id = self._extract_patient_id_from_path(self.selected_path)
        
        if detected_id:
            self.patient_id_edit.setText(detected_id)
            QMessageBox.information(self, "Success", f"Detected patient ID: {detected_id}")
        else:
            QMessageBox.warning(self, "Warning", "Could not auto-detect patient ID from path")
    
    def _extract_patient_id_from_path(self, path: Path) -> Optional[str]:
        """Extract patient ID from path"""
        # Try different patterns
        patterns = [
            r'(\d+)',  # numeric ID
            r'([A-Z]{2,4})',  # uppercase letters (like NSY, ATL, NBL)
            r'(patient[_-]?\d+)',  # patient_XX format
            r'(p\d+)',  # pXX format
        ]
        
        # Check folder name first
        folder_name = path.name if path.is_dir() else path.parent.name
        
        for pattern in patterns:
            match = re.search(pattern, folder_name, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # If no pattern matches, return the folder name itself if it's reasonable
        if len(folder_name) <= 10 and folder_name.isalnum():
            return folder_name
        
        return None
    
    def _on_source_type_changed(self):
        """Handle source type change"""
        self.path_edit.clear()
        self.info_text.clear()
        self._update_ok_button()
    
    def _update_ok_button(self):
        """Update OK button enabled state"""
        path_valid = self.selected_path is not None and self.selected_path.exists()
        patient_id_valid = bool(self.patient_id_edit.text().strip())
        
        self.ok_button.setEnabled(path_valid and patient_id_valid)
    
    def accept(self):
        """Accept the dialog and validate inputs"""
        if not self.selected_path or not self.selected_path.exists():
            QMessageBox.warning(self, "Warning", "Please select a valid source path")
            return
        
        patient_id = self.patient_id_edit.text().strip()
        if not patient_id:
            QMessageBox.warning(self, "Warning", "Please enter a patient ID")
            return
        
        # Validate patient ID format (basic validation)
        if not re.match(r'^[A-Za-z0-9_-]+$', patient_id):
            QMessageBox.warning(self, "Warning", "Patient ID can only contain letters, numbers, underscores, and hyphens")
            return
        
        # Store values
        self.patient_id = patient_id
        
        # Additional validation for PET files
        if self.selected_path.is_file():
            if not validate_pet_file(self.selected_path):
                reply = QMessageBox.question(
                    self, 
                    "Warning", 
                    "The selected file may not be a valid PET file. Continue anyway?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
        else:
            # Folder - check if it contains any PET files
            pet_files = get_pet_files(self.selected_path)
            if not pet_files:
                reply = QMessageBox.question(
                    self, 
                    "Warning", 
                    "No PET files found in the selected folder. Continue anyway?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
        
        super().accept()