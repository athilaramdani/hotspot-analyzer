# frontend/widgets/main_window_pet.py
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Dict, List

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout, QDialog, QLabel,
    QFileDialog, QMessageBox, QComboBox, QSlider, QGridLayout,
    QFrame, QApplication
)

from features.pet_viewer.logic.pet_directory_scanner import scan_pet_directory
from features.pet_viewer.logic.pet_loader import load_pet_data, PETData

from .pet_import_dialog import PETImportDialog
from core.gui.patient_info_bar import PatientInfoBar
from .pet_viewer_widget import PETViewerWidget


class MainWindowPet(QMainWindow):
    logout_requested = Signal()
    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        super().__init__()
        self.setWindowTitle("PET Viewer - Hotspot Analyzer")
        self.resize(1600, 900)
        self.session_code = session_code
        self.data_root = data_root
        self.pet_data_root = data_root / "PET"
        
        # Ensure PET data directory exists
        self.pet_data_root.mkdir(parents=True, exist_ok=True)
        
        print("[DEBUG] session_code in MainWindowPet =", self.session_code)
        
        # Caches
        self._patient_id_map: Dict[str, List[Path]] = {}
        self._loaded: Dict[str, PETData] = {}
        self.current_patient_id: str | None = None
        self.current_pet_data: PETData | None = None
        
        # Create UI
        self._create_ui()
        
        QTimer.singleShot(0, self.initial_load)
        # # Load initial data
        # self._refresh_patient_list()
        
        # # Auto-select session patient if available
        # if self.session_code:
        #     self._auto_select_patient()
        
    def initial_load(self):
            """Performs the initial data scan and patient selection."""
            print("[DEBUG] Starting initial data load for PET window...")
            self._refresh_patient_list()
            if self.session_code:
                self._auto_select_patient()    

    
    def _create_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top toolbar
        toolbar_layout = QHBoxLayout()
        
        # Import button
        self.import_btn = QPushButton("Import PET Data")
        self.import_btn.clicked.connect(self._import_pet_data)
        toolbar_layout.addWidget(self.import_btn)
        
        # Patient selection
        toolbar_layout.addWidget(QLabel("Patient:"))
        self.patient_combo = QComboBox()
        self.patient_combo.currentTextChanged.connect(self._on_patient_changed)
        toolbar_layout.addWidget(self.patient_combo)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_patient_list)
        toolbar_layout.addWidget(self.refresh_btn)
        
        toolbar_layout.addStretch()
        #logout button
        self.logout_btn = QPushButton("Logout")
        self.logout_btn.clicked.connect(self._handle_logout)

        toolbar_layout.addWidget(self.logout_btn)

        main_layout.addLayout(toolbar_layout)
        
        # Patient info bar
        self.patient_info = PatientInfoBar()
        main_layout.addWidget(self.patient_info)
        
        # Main content area
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Left panel for controls (if needed later)
        left_panel = QWidget()
        left_panel.setMaximumWidth(200)
        left_panel.setMinimumWidth(200)
        left_layout = QVBoxLayout(left_panel)
        
        # Status label
        self.status_label = QLabel("No PET data loaded")
        left_layout.addWidget(self.status_label)
        
        left_layout.addStretch()
        self.splitter.addWidget(left_panel)
        
        # Right panel - PET viewer
        self.pet_viewer = PETViewerWidget()
        self.splitter.addWidget(self.pet_viewer)
        
        # Set splitter proportions
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    def _handle_logout(self):
        """Handle logout request"""
        self.logout_requested.emit()
        self.close()

    
    def _refresh_patient_list(self):
        """Refresh the patient list from PET data directory"""
        try:
            self._patient_id_map = scan_pet_directory(self.pet_data_root)
            
            # Update combo box
            self.patient_combo.clear()
            if self._patient_id_map:
                patient_ids = sorted(self._patient_id_map.keys())
                self.patient_combo.addItems(patient_ids)
                self.statusBar().showMessage(f"Found {len(patient_ids)} patients")
            else:
                self.statusBar().showMessage("No PET data found")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to scan PET directory: {str(e)}")
            self.statusBar().showMessage("Error scanning directory")
    
    def _auto_select_patient(self):
        """Auto-select the session patient if available"""
        if self.session_code:
            index = self.patient_combo.findText(self.session_code)
            if index >= 0:
                self.patient_combo.setCurrentIndex(index)
    
    def _on_patient_changed(self, patient_id: str):
        """Handle patient selection change"""
        if not patient_id:
            self.current_patient_id = None
            self.current_pet_data = None
            self.pet_viewer.clear()
            self.status_label.setText("No PET data loaded")
            self.patient_info.clear()
            return
        
        self.current_patient_id = patient_id
        self._load_patient_data(patient_id)
    
    def _load_patient_data(self, patient_id: str):
        """Load PET data for the selected patient"""
        try:
            # Check if already loaded
            if patient_id in self._loaded:
                self.current_pet_data = self._loaded[patient_id]
                self._update_ui_with_data()
                return
            
            # Get patient folder
            patient_folders = self._patient_id_map.get(patient_id, [])
            if not patient_folders:
                self.status_label.setText(f"No data found for patient {patient_id}")
                return
            
            # Load from first folder (assuming one folder per patient)
            patient_folder = patient_folders[0]
            
            self.statusBar().showMessage(f"Loading PET data for patient {patient_id}...")
            QApplication.processEvents()  # Update UI
            
            # Load PET data
            pet_data = load_pet_data(patient_folder)
            
            if pet_data:
                self._loaded[patient_id] = pet_data
                self.current_pet_data = pet_data
                self._update_ui_with_data()
                self.statusBar().showMessage(f"Loaded PET data for patient {patient_id}")
            else:
                self.status_label.setText(f"Failed to load PET data for patient {patient_id}")
                self.statusBar().showMessage("Failed to load PET data")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load PET data: {str(e)}")
            self.statusBar().showMessage("Error loading PET data")
    
    def _update_ui_with_data(self):
        """Update UI with loaded PET data"""
        if not self.current_pet_data:
            return
        
        # Update patient info
        self.patient_info.update_from_pet_data(self.current_pet_data)
        
        # Update viewer
        self.pet_viewer.set_pet_data(self.current_pet_data)
        
        # Update status
        self.status_label.setText(f"Patient: {self.current_patient_id}\nPET data loaded")
    
    def _import_pet_data(self):
        """Import PET data from file or folder"""
        dialog = PETImportDialog(self)
        if dialog.exec() == QDialog.Accepted:
            source_path = dialog.selected_path
            patient_id = dialog.patient_id
            
            if source_path and patient_id:
                try:
                    self._copy_pet_data_to_storage(source_path, patient_id)
                    self._refresh_patient_list()
                    
                    # Auto-select the imported patient
                    index = self.patient_combo.findText(patient_id)
                    if index >= 0:
                        self.patient_combo.setCurrentIndex(index)
                        
                    QMessageBox.information(self, "Success", 
                                          f"PET data imported successfully for patient {patient_id}")
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to import PET data: {str(e)}")
    
    def _copy_pet_data_to_storage(self, source_path: Path, patient_id: str):
        """Copy PET data from source to data storage"""
        import shutil
        
        # Create patient folder in PET data directory
        patient_folder = self.pet_data_root / patient_id
        patient_folder.mkdir(parents=True, exist_ok=True)
        
        if source_path.is_file():
            # Single file - copy to patient folder
            shutil.copy2(source_path, patient_folder)
        else:
            # Directory - copy all contents
            for item in source_path.iterdir():
                if item.is_file():
                    shutil.copy2(item, patient_folder)
                elif item.is_dir():
                    shutil.copytree(item, patient_folder / item.name, dirs_exist_ok=True)
        
        print(f"Copied PET data from {source_path} to {patient_folder}")
    
    def closeEvent(self, event):
        """Handle application close"""
        print("[DEBUG] Cleaning up PET window resources...")
        if hasattr(self, 'pet_viewer') and hasattr(self.pet_viewer, 'cleanup'):
            self.pet_viewer.cleanup()
        event.accept()
