# features/pet_viewer/gui/main_window_pet.py
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
from core.gui.searchable_combobox import SearchableComboBox
# ===== TAMBAHKAN IMPORT INI =====
from core.gui.loading_dialog import PETLoadingDialog
# =================================
from .pet_viewer_widget import PETViewerWidget

# Import UI constants for consistent styling
from core.gui.ui_constants import (
    PRIMARY_BUTTON_STYLE,
    SUCCESS_BUTTON_STYLE,
    GRAY_BUTTON_STYLE,
)


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
        
        # Load initial data after UI is ready
        QTimer.singleShot(0, self.initial_load)
        
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
        main_layout.setContentsMargins(5, 5, 5, 5)  # Set reasonable margins
        main_layout.setSpacing(3)  # Set consistent spacing
        
        # --- Top Bar (matching SPECT layout) ---
        top_actions = QWidget()
        top_layout = QHBoxLayout(top_actions)
        top_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        top_layout.setSpacing(5)  # Set consistent spacing
        
        # Create SearchableComboBox for patient selection
        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)
        
        # Patient info bar with integrated search combo
        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)
        top_layout.addWidget(self.patient_bar)
        
        # Add stretch to push buttons to the right
        top_layout.addStretch()
        
        # Import button with primary style
        self.import_btn = QPushButton("Import PET Data…")
        self.import_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.import_btn.clicked.connect(self._import_pet_data)
        top_layout.addWidget(self.import_btn)
        
        # Refresh button with success style
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(SUCCESS_BUTTON_STYLE)
        self.refresh_btn.clicked.connect(self._refresh_patient_list)
        top_layout.addWidget(self.refresh_btn)
        
        # Logout button with gray style
        self.logout_btn = QPushButton("Logout")
        self.logout_btn.setStyleSheet(GRAY_BUTTON_STYLE)
        self.logout_btn.clicked.connect(self._handle_logout)
        top_layout.addWidget(self.logout_btn)

        main_layout.addWidget(top_actions)
        
        # --- Main content area ---
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter, 1)  # Tambah stretch factor 1
        
        # Left panel for controls
        left_panel = QWidget()
        left_panel.setMaximumWidth(200)
        left_panel.setMinimumWidth(200)
        left_layout = QVBoxLayout(left_panel)
        
        # Status label
        self.status_label = QLabel("No PET data loaded")
        left_layout.addWidget(self.status_label)
        
        # Add image type selector
        left_layout.addWidget(QLabel("Image Type:"))
        self.image_type_combo = QComboBox()
        self.image_type_combo.addItems(["PET", "CT", "SEG", "SUV"])
        self.image_type_combo.currentTextChanged.connect(self._on_image_type_changed)
        left_layout.addWidget(self.image_type_combo)
        
        left_layout.addStretch()
        self.splitter.addWidget(left_panel)
        
        # Right panel - PET viewer
        self.pet_viewer = PETViewerWidget()
        self.splitter.addWidget(self.pet_viewer)
        
        # Set splitter proportions
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([200, 1400])  # Fix ukuran splitter
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
            
            # Update searchable combo box
            search_combo = self.patient_bar.id_combo
            search_combo.clear()
            
            if self._patient_id_map:
                patient_ids = sorted(self._patient_id_map.keys())
                # Add patients to searchable combo with consistent format
                for patient_id in patient_ids:
                    search_combo.addItem(f"ID : {patient_id}")
                
                self.statusBar().showMessage(f"Found {len(patient_ids)} patients")
            else:
                self.statusBar().showMessage("No PET data found")
            
            # Clear selection and reset UI
            search_combo.clearSelection()
            self.patient_bar.clear_info(keep_id_list=True)
            self.pet_viewer.clear()
            self.status_label.setText("No PET data loaded")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to scan PET directory: {str(e)}")
            self.statusBar().showMessage("Error scanning directory")
    
    def _auto_select_patient(self):
        """Auto-select the session patient if available"""
        if self.session_code:
            search_combo = self.patient_bar.id_combo
            # Find patient by searching for the session code
            for i in range(search_combo.count()):
                item_text = search_combo.itemText(i)
                if self.session_code in item_text:
                    search_combo.setCurrentIndex(i)
                    break
    
    def _on_patient_selected(self, txt: str):
        """Handle patient selection from searchable combo box"""
        print(f"[DEBUG] _on_patient_selected: {txt}")
        try:
            # Extract patient ID from format "ID : patient_id"
            patient_id = txt.split(" : ")[1].strip()
        except IndexError:
            print("[DEBUG] Failed to parse patient ID from selection")
            return
        
        self.current_patient_id = patient_id
        self._load_patient_data(patient_id)
    
    def _on_image_type_changed(self, image_type: str):
        """Handle image type selection change"""
        if self.pet_viewer and self.current_pet_data:
            self.pet_viewer.set_image_type(image_type)
    
    def _load_patient_data(self, patient_id: str):
        """Load PET data for the selected patient"""
        loading_dialog = None
        
        def progress_callback(message: str, progress: int):
            if loading_dialog:
                loading_dialog.update_loading_step(message, progress)
                QApplication.processEvents()
        
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
            
            # Load from first folder
            patient_folder = patient_folders[0]
            
            # Show loading dialog
            loading_dialog = PETLoadingDialog(patient_id, parent=self)
            loading_dialog.show()
            QApplication.processEvents()
            
            # Load PET data dengan progress callback
            pet_data = load_pet_data(patient_folder, progress_callback)
            
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
        
        finally:
            if loading_dialog:
                loading_dialog.close()
    
    def _update_ui_with_data(self):
        """Update UI with loaded PET data"""
        if not self.current_pet_data:
            return
        
        # Update patient info - extract from PET metadata if available
        patient_meta = {
            "patient_id": self.current_patient_id,
            "patient_name": f"Patient {self.current_patient_id}",
            "patient_sex": "N/A",
            "patient_birth_date": "",
            "study_date": ""
        }
        
        # Try to get better info from PET metadata
        if self.current_pet_data.pet_metadata:
            meta = self.current_pet_data.pet_metadata
            if "patient_name" in meta:
                patient_meta["patient_name"] = meta["patient_name"]
            if "patient_sex" in meta:
                patient_meta["patient_sex"] = meta["patient_sex"]
            if "patient_birth_date" in meta:
                patient_meta["patient_birth_date"] = meta["patient_birth_date"]
            if "study_date" in meta:
                patient_meta["study_date"] = meta["study_date"]
        
        self.patient_bar.set_patient_meta(patient_meta)
        
        # Update viewer
        self.pet_viewer.set_pet_data(self.current_pet_data)
        
        # Update image type combo based on available data
        available_types = self.pet_viewer.get_available_image_types()
        self.image_type_combo.clear()
        for img_type, is_available in available_types.items():
            if is_available:
                self.image_type_combo.addItem(img_type)
        
        # Select first available type
        if self.image_type_combo.count() > 0:
            self.image_type_combo.setCurrentIndex(0)
        
        # Update status
        self.status_label.setText(f"Patient: {self.current_patient_id}\nPET data loaded")
    
    def _import_pet_data(self):
        """Import PET data from file or folder"""
        dialog = PETImportDialog(self)
        if dialog.exec() == QDialog.Accepted:
            source_path = dialog.selected_path
            patient_id = dialog.patient_id
            
            if source_path and patient_id:
                # ===== SHOW LOADING DIALOG FOR IMPORT =====
                loading_dialog = PETLoadingDialog(patient_id, parent=self)
                loading_dialog.set_message(f"Importing PET data for patient {patient_id}...")
                loading_dialog.show()
                QApplication.processEvents()
                # ==========================================
                
                try:
                    loading_dialog.update_loading_step("Copying files...", 30)
                    QApplication.processEvents()
                    
                    self._copy_pet_data_to_storage(source_path, patient_id)
                    
                    loading_dialog.update_loading_step("Refreshing patient list...", 70)
                    QApplication.processEvents()
                    
                    self._refresh_patient_list()
                    
                    loading_dialog.update_loading_step("Selecting patient...", 90)
                    QApplication.processEvents()
                    
                    # Auto-select the imported patient
                    search_combo = self.patient_bar.id_combo
                    for i in range(search_combo.count()):
                        if patient_id in search_combo.itemText(i):
                            search_combo.setCurrentIndex(i)
                            break
                    
                    loading_dialog.update_loading_step("Import completed!", 100)
                    QApplication.processEvents()
                    
                    QMessageBox.information(self, "Success", 
                                          f"PET data imported successfully for patient {patient_id}")
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to import PET data: {str(e)}")
                
                finally:
                    loading_dialog.close()
    
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