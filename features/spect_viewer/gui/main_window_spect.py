# features/spect_viewer/gui/main_window_spect.py - FIXED with BSI integration
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Dict, List
import numpy as np
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout, QDialog, QApplication, QLabel, QFileDialog, QMessageBox,QCheckBox, QInputDialog 
)
from PySide6.QtGui import QCloseEvent, QShortcut, QKeySequence
import multiprocessing

# Import NEW config paths and session management
from core.config.paths import (
    get_session_spect_path,
    get_patient_spect_path,
    SPECT_DATA_PATH,
    generate_filename_stem,
    extract_study_date_from_dicom
)
from core.config.sessions import get_current_session

# Import NEW directory scanner for new structure
from features.dicom_import.logic.directory_scanner import (
    scan_spect_directory_new_structure,
    get_session_patients,
    get_patient_dicom_files
)
from features.spect_viewer.gui.segmentation_editor_dialog import SegmentationEditorDialog
from features.spect_viewer.gui.hotspot_editor_dialog import HotspotEditorDialog
# ===== TAMBAHKAN IMPORT LOADING DIALOG =====
from core.gui.loading_dialog import SPECTLoadingDialog
# ===========================================
from features.spect_viewer.logic.processing_wrapper import run_yolo_detection_for_patient, run_hotspot_processing_in_process
from features.dicom_import.logic.dicom_loader import load_frames_and_metadata, extract_study_date_from_dicom
from features.spect_viewer.logic.hotspot_processor import HotspotProcessor
from core.utils.image_converter import load_frames_and_metadata_matrix

# Import the new dialog
from features.dicom_import.gui.dicom_import_dialog_v2 import DicomImportDialog
from core.gui.ui_constants import (
    PRIMARY_BUTTON_STYLE,     # blue "Import DICOM…" button
    SUCCESS_BUTTON_STYLE,     # green "Rescan Folder" button
    GRAY_BUTTON_STYLE,        # grey "Logout" button
    ZOOM_BUTTON_STYLE,        # orange "Zoom In/Out" buttons
    SCAN_BUTTON_STYLE,        # purple "Scan N" buttons
)

from core.gui.searchable_combobox import SearchableComboBox
from core.gui.patient_info_bar import PatientInfoBar
from .scan_timeline import ScanTimelineWidget  # UPDATED: Use modular timeline widget

# ✅ FIXED: Import BSISidePanel instead of SidePanel
from .side_panel import BSISidePanel
from ..logic.adjust_contrast import ContrastDialog
from .mode_selector import ModeSelector
from features.spect_viewer.logic.processing_wrapper import run_yolo_detection_for_patient, run_hotspot_processing_in_process,run_segmentation_in_process

# ✅ NEW: Import BSI integration
from features.spect_viewer.logic.bsi_timeline_integration import (
    get_bsi_integration,
    load_bsi_for_selected_patient,
    update_timeline_scans_with_bsi
)

class MainWindowSpect(QMainWindow):
    logout_requested = Signal()
    
    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        super().__init__()
        self.setWindowTitle(f"Hotspot Analyzer - Session: {session_code or 'Unknown'}")
        self.resize(1600, 900)
        self.session_code = session_code
        self.pool = multiprocessing.Pool(processes=1)
        self.data_root = data_root
        self.invert_original = False
        self._last_invert_state = False
        print(f"[DEBUG] session_code in MainWindow = {self.session_code}")

        # NEW: Store session-patient mapping from new structure
        self._session_patients_map: Dict[str, List[str]] = {}
        self._loaded: Dict[str, List[Dict]] = {}
        self.scan_buttons: List[QPushButton] = []
        
        # ✅ NEW: BSI integration
        self.bsi_integration = get_bsi_integration()

        self._build_ui()
        self._scan_folder()
    

    def _setup_timeline_connections(self):
        """✅ Setup timeline connections with proper view synchronization"""
        
        # Timeline scan selection already connected in __init__
        # Just ensure session code is set
        if hasattr(self.timeline_widget, 'set_session_code') and self.session_code:
            self.timeline_widget.set_session_code(self.session_code)
        
        print("[MainWindow] Timeline connections established")

    def _setup_keyboard_shortcuts(self):
        """✅ Setup global keyboard shortcuts with error handling"""
        
        try:
            # Timeline zoom shortcuts (global) - with safety checks
            if hasattr(self, 'timeline_widget'):
                # Zoom shortcuts
                zoom_in_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
                zoom_in_shortcut.activated.connect(self._safe_zoom_in)
                
                zoom_in_alt_shortcut = QShortcut(QKeySequence("Ctrl+="), self)
                zoom_in_alt_shortcut.activated.connect(self._safe_zoom_in)
                
                zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
                zoom_out_shortcut.activated.connect(self._safe_zoom_out)
                
                # ✅ FIXED: Safe zoom reset with fallback
                zoom_reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
                zoom_reset_shortcut.activated.connect(self._safe_zoom_reset)
            
            # View switching shortcuts
            anterior_shortcut = QShortcut(QKeySequence("Ctrl+1"), self)
            anterior_shortcut.activated.connect(lambda: self._sync_view_across_components("Anterior"))
            
            posterior_shortcut = QShortcut(QKeySequence("Ctrl+2"), self)
            posterior_shortcut.activated.connect(lambda: self._sync_view_across_components("Posterior"))
            
            print("[MainWindow] ✅ Global keyboard shortcuts setup complete")
            
        except Exception as e:
            print(f"[MainWindow] ⚠️ Error setting up keyboard shortcuts: {e}")

    def _safe_zoom_in(self):
        """Safe zoom in with error handling"""
        try:
            if hasattr(self, 'timeline_widget') and hasattr(self.timeline_widget, 'zoom_in'):
                self.timeline_widget.zoom_in()
            else:
                print("[MainWindow] Timeline widget or zoom_in method not available")
        except Exception as e:
            print(f"[MainWindow] Error in zoom in: {e}")

    def _safe_zoom_out(self):
        """Safe zoom out with error handling"""
        try:
            if hasattr(self, 'timeline_widget') and hasattr(self.timeline_widget, 'zoom_out'):
                self.timeline_widget.zoom_out()
            else:
                print("[MainWindow] Timeline widget or zoom_out method not available")
        except Exception as e:
            print(f"[MainWindow] Error in zoom out: {e}")

    def _safe_zoom_reset(self):
        """Safe zoom reset with fallback implementation"""
        try:
            if hasattr(self, 'timeline_widget'):
                # Try the zoom_reset method first
                if hasattr(self.timeline_widget, 'zoom_reset'):
                    self.timeline_widget.zoom_reset()
                else:
                    # ✅ FALLBACK: Manual zoom reset if method doesn't exist
                    print("[MainWindow] zoom_reset method not found, using fallback")
                    if hasattr(self.timeline_widget, '_zoom_factor'):
                        self.timeline_widget._zoom_factor = 1.0
                        if hasattr(self.timeline_widget, '_rebuild'):
                            self.timeline_widget._rebuild()
                        print("[MainWindow] ✅ Zoom reset via fallback method")
                    else:
                        print("[MainWindow] Cannot reset zoom - no zoom_factor attribute")
            else:
                print("[MainWindow] Timeline widget not available")
        except Exception as e:
            print(f"[MainWindow] Error in zoom reset: {e}")

    def _sync_view_across_components(self, view_name: str):
        """"✅ Synchronize view across all components"""
        print(f"[MainWindow] Syncing view '{view_name}' across all components")

        try:
            # Hanya update timeline widget
            if hasattr(self, 'timeline_widget'):
                self.timeline_widget.set_active_view(view_name)

            print(f"[MainWindow] ✅ View sync completed")

        except Exception as e:
            print(f"[MainWindow] Error syncing view: {e}")

    def update_timeline_with_scans_enhanced(self, scans_data: list, active_index: int = -1):
        """✅ Enhanced timeline update with BSI integration"""
        try:
            print(f"[MainWindow] Updating timeline with {len(scans_data)} scans")
            
            # ✅ Update scans with BSI information
            updated_scans = update_timeline_scans_with_bsi(scans_data, self.session_code)
            
            # Set session code for timeline
            if hasattr(self, 'timeline_widget') and self.session_code:
                self.timeline_widget.set_session_code(self.session_code)
            
            # Update timeline display
            self.timeline_widget.display_timeline(updated_scans, active_index)
            
            print(f"[MainWindow] ✅ Timeline updated with BSI integration")
            
        except Exception as e:
            print(f"[MainWindow] Error updating timeline: {e}")
            # Fallback to original method
            self.timeline_widget.display_timeline(scans_data, active_index)

    def complete_initialization_setup(self):
        """✅ Complete initialization sequence - CALL THIS AT END OF __init__"""
        
        # 3. Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()
        
        # 4. Initialize with default view
        default_view = "Anterior"
        self._sync_view_across_components(default_view)
        
        print("[MainWindow] ✅ Complete integration initialization finished")
    def _update_active_layers_display(self):
        """Update the active layers display in control panel"""
        if not self.timeline_widget._active_layers:
            self.active_layers_label.setText("Active Layers: <i>None selected</i>")
            self.active_layers_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #dc3545;
                    padding: 8px;
                    background: #f8d7da;
                    border: 1px solid #f5c6cb;
                    border-radius: 4px;
                    margin: 5px 0px;
                }
            """)
        else:
            layers_text = ", ".join(self.timeline_widget._active_layers)
            self.active_layers_label.setText(f"Active Layers: <b>{layers_text}</b>")
            self.active_layers_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #155724;
                    padding: 8px;
                    background: #d4edda;
                    border: 1px solid #c3e6cb;
                    border-radius: 4px;
                    margin: 5px 0px;
                }
            """)

    def _update_edit_button_states(self):
        """Update edit button states based on scan availability and potential for editing"""
        
        # Check if we have any scan loaded
        has_scan = bool(self.timeline_widget._scans_cache and self.timeline_widget.active_scan_index >= 0)
        
        # ✅ FIXED: For segmentation - check if segmentation files exist (required for editing)
        has_segmentation_data = self.timeline_widget.has_layer_data("Segmentation") if has_scan else False
        
        # ✅ FIXED: For hotspot - always allow editing if scan exists (can create hotspot files)
        # User should be able to edit hotspot even if classification files don't exist yet
        can_edit_hotspot = has_scan
        
        # Enable buttons based on editability
        self.seg_edit_btn.setEnabled(has_segmentation_data and has_scan)
        self.hotspot_edit_btn.setEnabled(can_edit_hotspot)  # ✅ Always enabled if scan exists
        
        # Debug output
        print(f"[EDIT BUTTONS] Has scan: {has_scan}, Has seg data: {has_segmentation_data}, Can edit hotspot: {can_edit_hotspot}")
        print(f"[EDIT BUTTONS] Seg button enabled: {self.seg_edit_btn.isEnabled()}, Hotspot button enabled: {self.hotspot_edit_btn.isEnabled()}")
        
    def _update_scan_info_display(self):
        """✅ FIXED: Update scan information with BSI data"""
        if not self.timeline_widget._scans_cache or self.timeline_widget.active_scan_index < 0:
            self.scan_info_label.setText("No scan selected")
            return
            
        if self.timeline_widget.active_scan_index < len(self.timeline_widget._scans_cache):
            scan = self.timeline_widget._scans_cache[self.timeline_widget.active_scan_index]
            meta = scan["meta"]
            
            # Format scan info
            scan_num = self.timeline_widget.active_scan_index + 1
            total_scans = len(self.timeline_widget._scans_cache)
            date = meta.get("study_date", "Unknown")
            
            try:
                formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%b %d, %Y")
            except ValueError:
                formatted_date = date
            
            # Get BSI information
            bsi_info = ""
            if meta.get("has_bsi", False):
                # ✅ FIX: Use combined_bsi instead of bsi_score
                bsi_combined = meta.get("bsi_combined", 0.0)
                bsi_anterior = meta.get("bsi_anterior", 0.0)
                bsi_posterior = meta.get("bsi_posterior", 0.0)
                
                # ✅ Show combined BSI in main window
                bsi_info = f"<br>BSI Combined: {bsi_combined:.1f}<br>Ant: {bsi_anterior:.1f} | Post: {bsi_posterior:.1f}"

            # ✅ FIX: Replace self.current_view with static text
            info_text = f"""
            <b>Scan {scan_num}/{total_scans}</b><br>
            Date: {formatted_date}<br>
            <b>View: Anterior & Posterior</b>{bsi_info}
            """
            
            self.scan_info_label.setText(info_text)
    def _open_segmentation_editor(self):
        """Buka editor segmentasi untuk scan saat ini."""
        if not self.timeline_widget._scans_cache or self.timeline_widget.active_scan_index < 0:
            return
        
        # ✅ FIX: Ask the user which view to edit
        views = ["Anterior", "Posterior"]
        selected_view, ok = QInputDialog.getItem(self, "Select View", 
                                                "Which view would you like to edit?", views, 0, False)

        if ok and selected_view:
            scan = self.timeline_widget._scans_cache[self.timeline_widget.active_scan_index]
            
            dlg = SegmentationEditorDialog(scan, selected_view, parent=self)
            if dlg.exec():
                # self.editor_completed is not a standard signal, assuming you meant to connect to a refresh
                self._on_editor_completed()

    def _open_hotspot_editor(self):
        """Buka editor hotspot untuk scan saat ini."""
        if not self.timeline_widget._scans_cache or self.timeline_widget.active_scan_index < 0:
            return

        # ✅ FIX: Ask the user which view to edit
        views = ["Anterior", "Posterior"]
        selected_view, ok = QInputDialog.getItem(self, "Select View", 
                                                "Which view would you like to edit?", views, 0, False)

        if ok and selected_view:
            scan = self.timeline_widget._scans_cache[self.timeline_widget.active_scan_index]

            try:
                patient_id, _ = self.timeline_widget._get_patient_session_from_scan(scan)
                
                dicom_path = Path(scan["path"])
                study_date = extract_study_date_from_dicom(dicom_path)
                filename_with_date = generate_filename_stem(patient_id, study_date)
                
                view_normalized = selected_view.lower()
                view_short = "ant" if "ant" in view_normalized else "post"
                
                classification_files = {
                    'mask_path': dicom_path.parent / f"{filename_with_date}_{view_normalized}_classification_mask.png",
                    'xml_path': dicom_path.parent / f"{filename_with_date}_{view_short}_classification.xml",
                    'json_path': dicom_path.parent / f"{filename_with_date}_{view_normalized}_classification.json"
                }
                
                enhanced_scan = scan.copy()
                enhanced_scan['classification_files'] = classification_files
                enhanced_scan['is_classification_mode'] = True
                
                dlg = HotspotEditorDialog(enhanced_scan, selected_view, parent=self)
                if dlg.exec():
                    self._on_editor_completed()

            except Exception as e:
                print(f"[ERROR] Failed to open hotspot editor: {e}")



    def _on_invert_changed(self, state: int):
        """Enhanced debugging for checkbox state changes"""
        print(f"[DEBUG] === INVERT CHECKBOX CHANGED ===")
        
        # Use the checkbox's own isChecked() method - most reliable
        actual_checked = self.invert_checkbox.isChecked()
        
        print(f"[DEBUG] Checkbox state: {state}, isChecked(): {actual_checked}")
        
        # Update the flag
        old_invert = self.invert_original
        self.invert_original = actual_checked
        
        print(f"[DEBUG] Invert flag changed: {old_invert} -> {self.invert_original}")
        
        # Call timeline method
        if hasattr(self, 'timeline_widget') and self.timeline_widget is not None:
            print(f"[DEBUG] Calling timeline_widget.set_invert_original({self.invert_original})")
            self.timeline_widget.set_invert_original(self.invert_original)
            print(f"[DEBUG] ✅ Timeline invert method called successfully")
        else:
            print(f"[DEBUG] ❌ Timeline widget not ready!")

    # Add this to the end of your _build_ui method or call it after window is shown
    def test_checkbox_connection(self):
        """Test method to verify invert connection works"""
        print(f"[TEST] Testing invert connection...")
        print(f"[TEST] Timeline widget exists: {hasattr(self, 'timeline_widget')}")
        print(f"[TEST] Checkbox exists: {hasattr(self, 'invert_checkbox')}")
        
        if hasattr(self, 'invert_checkbox'):
            print(f"[TEST] Current checkbox state: {self.invert_checkbox.isChecked()}")
            # Manually trigger the signal
            current_state = self.invert_checkbox.isChecked()
            self.invert_checkbox.setChecked(not current_state)
            print(f"[TEST] Toggled checkbox to: {not current_state}")
                
    def _build_ui(self) -> None:
        # --- Top Bar ---
        top_actions = QWidget()
        top_layout = QHBoxLayout(top_actions)

        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)
        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)
        top_layout.addWidget(self.patient_bar)
        top_layout.addStretch()

        # Import and action buttons
        import_btn = QPushButton("Import DICOM…")
        import_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        import_btn.clicked.connect(self._show_import_dialog)
        
        rescan_btn = QPushButton("Rescan Folder")
        rescan_btn.setStyleSheet(SUCCESS_BUTTON_STYLE)
        rescan_btn.clicked.connect(self._scan_folder)
        # Menambahkan tombol-tombol penting ke layout
        top_layout.addWidget(import_btn)
        top_layout.addWidget(rescan_btn)

        # Logout button
        logout_btn = QPushButton("Logout")
        logout_btn.setStyleSheet(GRAY_BUTTON_STYLE)
        logout_btn.clicked.connect(self._handle_logout)
        top_layout.addWidget(logout_btn)
        
        # --- Scan & Zoom Buttons ---
        view_button_widget = QWidget()
        view_button_layout = QHBoxLayout(view_button_widget)
        self.scan_button_container = QHBoxLayout()
        view_button_layout.addLayout(self.scan_button_container)
        view_button_layout.addStretch()

        # --- Main Splitter (RESIZABLE LAYOUT: Mode Selector | Timeline | BSI Panel) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT PANEL: Mode selector (RESIZABLE - no fixed width)
        left_panel = QWidget()
        left_panel.setMinimumWidth(200)   # Minimum width only
        left_panel.setMaximumWidth(500)   # Maximum width for usability
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        
        # Panel title untuk clarity
        title_label = QLabel("<b>Layer Controls</b>")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #495057;
                padding: 8px;
                background: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #e9ecef;
                margin-bottom: 8px;
            }
        """)
        left_layout.addWidget(title_label)
        
        # NEW: Enhanced mode selector with checkboxes
        self.mode_selector = ModeSelector()
        # Connect NEW signals for checkbox-based mode selector
        self.mode_selector.layers_changed.connect(self._on_layers_changed)
        self.mode_selector.opacity_changed.connect(self._set_layer_opacity)
        left_layout.addWidget(self.mode_selector)

        # CREATE TIMELINE WIDGET FIRST (before invert checkbox)
        self.timeline_widget = ScanTimelineWidget()
        self.timeline_widget.set_session_code(self.session_code)

        # FIXED: Connect timeline scan selection signal to sync with scan buttons
        self.timeline_widget.scan_selected.connect(self._on_timeline_scan_selected)

        # ✅ NEW: Connect editor completion signals to refresh BSI panel
        self.timeline_widget.editor_completed.connect(self._on_editor_completed)

        # NOW CREATE AND CONNECT INVERT CHECKBOX (after timeline exists)
        self.invert_checkbox = QCheckBox("Invert Image Colors")
        self.invert_checkbox.setStyleSheet("margin-top: 8px; font-weight: bold;")
        
        # ✅ Connect the checkbox AFTER timeline widget exists
        print(f"[DEBUG] Connecting invert checkbox...")
        self.invert_checkbox.stateChanged.connect(self._on_invert_changed)
        
        # ✅ Test the connection immediately
        print(f"[DEBUG] Testing checkbox connection...")
        print(f"[DEBUG] Timeline widget exists: {hasattr(self, 'timeline_widget')}")
        if hasattr(self, 'timeline_widget'):
            print(f"[DEBUG] Timeline widget type: {type(self.timeline_widget)}")
        
        left_layout.addWidget(self.invert_checkbox)
        print(f"[DEBUG] Invert checkbox created and connected")

        # 3. Label Info Layer Aktif (PINDAHAN)
        self.active_layers_label = QLabel("Active Layers: None")
        self.active_layers_label.setWordWrap(True)
        left_layout.addWidget(self.active_layers_label)

        # 4. Tombol Edit (PINDAHAN)
        self.seg_edit_btn = QPushButton("Edit Segmentation")
        self.seg_edit_btn.clicked.connect(self._open_segmentation_editor)
        self.seg_edit_btn.setStyleSheet(SUCCESS_BUTTON_STYLE + """
            QPushButton:disabled {
                background-color: #d3d3d3;
                color: #888;
                border-color: #aaa;
            }
        """)

        self.hotspot_edit_btn = QPushButton("Edit Hotspot")
        self.hotspot_edit_btn.clicked.connect(self._open_hotspot_editor)
        self.hotspot_edit_btn.setStyleSheet(ZOOM_BUTTON_STYLE + """
            QPushButton:disabled {
                background-color: #d3d3d3;
                color: #888;
                border-color: #aaa;
            }
        """)

        edit_layout = QHBoxLayout()
        edit_layout.addWidget(self.seg_edit_btn)
        edit_layout.addWidget(self.hotspot_edit_btn)
        left_layout.addLayout(edit_layout)

        # 5. Label Info Scan (PINDAHAN)
        self.scan_info_label = QLabel("No scan selected")
        self.scan_info_label.setWordWrap(True)
        left_layout.addWidget(self.scan_info_label)
    
        # Layout horizontal untuk tombol zoom
        zoom_buttons_layout = QHBoxLayout()
        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_in_btn.setStyleSheet(ZOOM_BUTTON_STYLE)

        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_out_btn.setStyleSheet(ZOOM_BUTTON_STYLE)

        zoom_buttons_layout.addWidget(zoom_in_btn)
        zoom_buttons_layout.addWidget(zoom_out_btn)
        left_layout.addLayout(zoom_buttons_layout)

        contrast_button = QPushButton("Adjust Contrast")
        contrast_button.setStyleSheet(ZOOM_BUTTON_STYLE) # Use a style you like
        contrast_button.clicked.connect(self._open_contrast_dialog)
        left_layout.addWidget(contrast_button)

        left_layout.addStretch()
        
        main_splitter.addWidget(left_panel)

        # Add timeline widget to splitter (it's already created above)
        main_splitter.addWidget(self.timeline_widget)

        # ✅ FIXED: RIGHT PANEL: BSI Side Panel instead of old SidePanel
        self.bsi_panel = BSISidePanel()
        self.bsi_panel.set_session_code(self.session_code)
        
        # ✅ NEW: Connect BSI panel signals
        self.bsi_panel.export_requested.connect(self._on_bsi_export_requested)
        self.bsi_panel.analysis_requested.connect(self._on_bsi_analysis_requested)
        
        main_splitter.addWidget(self.bsi_panel)
        
        # Set splitter proportions: Mode Selector | Timeline | BSI Panel
        # Make all panels resizable with proper ratios
        main_splitter.setStretchFactor(0, 1)  # Mode selector: resizable
        main_splitter.setStretchFactor(1, 3)  # Timeline: gets most space
        main_splitter.setStretchFactor(2, 1)  # BSI panel: resizable
        main_splitter.setSizes([280, 900, 350])  # Initial sizes (total: 1530)
        
        # Style the splitter handles for better visibility
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e9ecef;
                width: 4px;
                margin: 2px 0px;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #4e73ff;
            }
            QSplitter::handle:pressed {
                background-color: #324fc7;
            }
        """)

        # --- Perakitan Final ---
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(top_actions)
        main_layout.addWidget(view_button_widget)
        main_layout.addWidget(main_splitter, stretch=1)
        self.setCentralWidget(main_widget)
        self.complete_initialization_setup()

        QTimer.singleShot(1000, self.test_checkbox_connection)
        
    def debug_timeline_status(self):
        """Debug method untuk cek status timeline"""
        if hasattr(self, 'timeline_widget'):
            print(f"[DEBUG] Timeline current view: {getattr(self.timeline_widget, 'current_view', 'Unknown')}")
            print(f"[DEBUG] Timeline active layers: {self.timeline_widget.get_active_layers()}")
            print(f"[DEBUG] Timeline has layer data - Original: {self.timeline_widget.has_layer_data('Original')}")
            print(f"[DEBUG] Timeline has layer data - Segmentation: {self.timeline_widget.has_layer_data('Segmentation')}")
            print(f"[DEBUG] Timeline has layer data - Hotspot: {self.timeline_widget.has_layer_data('Hotspot')}")

    def _open_contrast_dialog(self):
        """Opens the B/C dialog after asking the user to select a view."""
        
        if not self.timeline_widget._scans_cache:
            QMessageBox.warning(self, "No Scan", "Please select a patient and scan first.")
            return

        # 1. Ask the user which view to edit
        views = ["Anterior", "Posterior"]
        selected_view, ok = QInputDialog.getItem(self, "Select View",
                                                "Which view would you like to adjust?", views, 0, False)

        if ok and selected_view:
            # ✅ FIX: Use the new getter method to get the initial state for the SELECTED view
            initial_state = self.timeline_widget.get_brightness_contrast(selected_view)
            initial_b = initial_state["brightness"]
            initial_c = initial_state["contrast"]

            dialog = ContrastDialog(self)
            dialog.set_initial_values(initial_b, initial_c)

            # Connect the live preview signal using a lambda to pass the selected view
            preview_connection = lambda b, c: self.timeline_widget.preview_brightness_contrast(selected_view, b, c)
            dialog.adjustment_changed.connect(preview_connection)
            
            result = dialog.exec()

            if result == QDialog.Accepted:
                # Apply the final values to the correct view
                values = dialog.get_values()
                if values:
                    brightness, contrast = values
                    self.timeline_widget.set_brightness_contrast(selected_view, brightness, contrast)
            else:
                # Revert the changes for the correct view if cancelled
                print(f"[DEBUG] Contrast dialog for {selected_view} cancelled, reverting.")
                self.timeline_widget.set_brightness_contrast(selected_view, initial_b, initial_c)

            # Disconnect the signal to be safe
            dialog.adjustment_changed.disconnect(preview_connection)

    # ✅ NEW: BSI panel event handlers
    def _on_bsi_export_requested(self, export_type: str):
        """Handle BSI export requests"""
        print(f"[BSI] Export requested: {export_type}")
        
        try:
            if export_type == "chart":
                # Export BSI chart
                file_path, _ = QFileDialog.getSaveFileName(
                    self, 
                    "Export BSI Chart",
                    f"bsi_chart_{self._get_current_patient_id()}.png",
                    "PNG Files (*.png);;All Files (*)"
                )
                
                if file_path:
                    success = self.bsi_panel.export_chart_to_file(Path(file_path))
                    if success:
                        QMessageBox.information(self, "Export Successful", f"BSI chart exported to:\n{file_path}")
                    else:
                        QMessageBox.warning(self, "Export Failed", "Failed to export BSI chart.")
            
            elif export_type == "report":
                # Export BSI report
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Export BSI Report", 
                    f"bsi_report_{self._get_current_patient_id()}.txt",
                    "Text Files (*.txt);;All Files (*)"
                )
                
                if file_path:
                    success = self.bsi_panel.export_report_to_file(Path(file_path))
                    if success:
                        QMessageBox.information(self, "Export Successful", f"BSI report exported to:\n{file_path}")
                    else:
                        QMessageBox.warning(self, "Export Failed", "Failed to export BSI report.")
        
        except Exception as e:
            print(f"[BSI ERROR] Export failed: {e}")
            QMessageBox.critical(self, "Export Error", f"Export failed:\n{str(e)}")

    def _on_bsi_analysis_requested(self):
        """Handle BSI analysis requests"""
        print("[BSI] Analysis requested")
        
        try:
            # Get current patient info
            patient_id, session_code = self._get_current_patient_info()
            
            if not patient_id:
                QMessageBox.warning(self, "No Patient Selected", "Please select a patient first.")
                return
            
            # Run quantification analysis
            from features.spect_viewer.logic.processing_wrapper import run_quantification_for_patient
            
            # Get patient DICOM file
            dicom_files = get_patient_dicom_files(session_code, patient_id, primary_only=True)
            
            if not dicom_files:
                QMessageBox.warning(self, "No DICOM Files", "No DICOM files found for this patient.")
                return
            
            dicom_path = dicom_files[0]  # Use first DICOM file
            study_date = extract_study_date_from_dicom(dicom_path)
            
            # Show loading dialog
            loading_dialog = SPECTLoadingDialog(f"Running BSI analysis for {patient_id}...", parent=self)
            loading_dialog.show()
            QApplication.processEvents()
            
            # Run quantification
            success = run_quantification_for_patient(dicom_path, patient_id, study_date)
            
            loading_dialog.close()
            
            if success:
                QMessageBox.information(self, "Analysis Complete", "BSI quantification completed successfully!")
                # Refresh BSI panel
                self.bsi_panel.refresh_current_patient()
            else:
                QMessageBox.warning(self, "Analysis Failed", "BSI quantification failed. Please check that classification has been completed.")
        
        except Exception as e:
            print(f"[BSI ERROR] Analysis failed: {e}")
            if 'loading_dialog' in locals():
                loading_dialog.close()
            QMessageBox.critical(self, "Analysis Error", f"BSI analysis failed:\n{str(e)}")

    def _get_current_patient_id(self) -> str:
        """Get current patient ID for file naming"""
        try:
            patient_id, _ = self._get_current_patient_info()
            return patient_id or "unknown"
        except:
            return "unknown"

    def _get_current_patient_info(self) -> tuple[str, str]:
        """Get current patient ID and session code"""
        try:
            id_text = self.patient_bar.id_combo.currentText()
            if not id_text.startswith("ID: "):
                return None, None
                
            remainder = id_text[4:]  # Remove "ID: "
            patient_id = remainder.split(" (")[0]  # "12"
            session_part = remainder.split(" (")[1]  # "NSY)"
            session = session_part.rstrip(")")  # "NSY"
            
            return patient_id, session
        except:
            return None, None

    # FIXED: NEW method to handle timeline scan selection
    def _on_timeline_scan_selected(self, scan_index: int):
        """Handle scan selection from timeline widget"""
        print(f"[DEBUG] Timeline scan selected signal received: {scan_index}")
        
        # Update scan buttons to reflect selection
        print(f"[DEBUG] Timeline scan selected signal received: {scan_index}")
        
        # ✅ FIXED: Block signals to prevent recursive updates
        for i, btn in enumerate(self.scan_buttons):
            btn.blockSignals(True)
            btn.setChecked(i == scan_index)
            btn.blockSignals(False)
            
        # ✅ NEW: Update BSI panel with selected scan data
        try:
            patient_id, session_code = self._get_current_patient_info()
            
            if not patient_id or not session_code:
                print(f"[DEBUG] Invalid patient info")
                return
                
            cache_key = f"{patient_id}_{session_code}"
            scans = self._loaded.get(cache_key, [])
            
            if scans and scan_index < len(scans):
                selected_scan = scans[scan_index]
                
                # ✅ NEW: Load BSI data for selected scan
                self._load_bsi_for_scan(selected_scan, session_code)
                
                print(f"[DEBUG] Updated BSI panel for scan {scan_index + 1}")
                
        except (IndexError, AttributeError) as e:
            print(f"[DEBUG] Failed to update BSI panel: {e}")
        
        self._update_scan_info_display()
        self._update_edit_button_states()

    def _on_editor_completed(self):
        """Handle editor completion - refresh BSI panel and timeline"""
        print("[MainWindow] Editor completed, refreshing BSI panel...")
        
        try:
            # Get current patient info
            patient_id, session_code = self._get_current_patient_info()
            
            if not patient_id or not session_code:
                print("[MainWindow] No patient selected, skipping refresh")
                return
            
            # Refresh timeline to pick up new files
            self.timeline_widget.refresh_current_view()
            
            # Refresh BSI panel with latest data
            self._refresh_bsi_panel_for_current_patient()
            
            print("[MainWindow] ✅ Auto-refresh completed")
            
        except Exception as e:
            print(f"[MainWindow] Error in auto-refresh: {e}")

    def _refresh_bsi_panel_for_current_patient(self):
        """Refresh BSI panel for currently selected patient"""
        try:
            # ✅ IMPROVED: Use BSI panel's own refresh method
            if hasattr(self, 'bsi_panel'):
                self.bsi_panel.refresh_current_patient()
            
            print(f"[MainWindow] ✅ BSI panel auto-refreshed")
            
        except Exception as e:
            print(f"[MainWindow] Error refreshing BSI panel: {e}")
            
    def _load_bsi_for_scan(self, scan_data: Dict, session_code: str):
        """Load BSI data for selected scan"""
        try:
            print(f"[BSI] Loading BSI data for selected scan")
            
            # Extract patient info from scan
            dicom_path = Path(scan_data["path"])
            patient_folder = dicom_path.parent
            
            # Get patient ID from path or scan data
            patient_id = patient_folder.name
            study_date = extract_study_date_from_dicom(dicom_path)
            
            # Load BSI data
            self.bsi_panel.load_patient_data(patient_folder, patient_id, study_date)
            
        except Exception as e:
            print(f"[BSI ERROR] Failed to load BSI data: {e}")
            self.bsi_panel.clear_patient_data()

    # NEW: Handle checkbox-based layer changes
    def _on_layers_changed(self, active_layers: list) -> None:
        """Handle layer selection changes from checkbox mode selector"""
        print(f"[DEBUG] Layers changed to: {active_layers}")
        
        # Check if "Hotspot" was just activated and needs processing
        if "Hotspot" in active_layers and not self.timeline_widget.is_layer_active("Hotspot"):
            # Check if hotspot data is available
            if not self.timeline_widget.has_layer_data("Hotspot"):
                print("[DEBUG] Hotspot layer activated but no data found, triggering processing...")
                self._run_hotspot_processing_on_demand()
            else:
                print("[DEBUG] Hotspot layer activated and data is available")
        
        # Update timeline with new layer selection
        self.timeline_widget.set_active_layers(active_layers)
        self._update_active_layers_display()
        self._update_edit_button_states()

    def _set_layer_opacity(self, layer: str, opacity: float) -> None:
        """Handle layer opacity changes from mode selector"""
        print(f"[DEBUG] Setting {layer} opacity to {opacity:.2f}")
        self.timeline_widget.set_layer_opacity(layer, opacity)


    # UPDATED: Enhanced scan button click handler for checkbox system
    def _on_scan_button_clicked(self, index: int) -> None:
        """✅ FIXED: Handle scan button click with proper synchronization"""
        print(f"[DEBUG] Scan button {index + 1} clicked")
        
        # ✅ FIXED: Block signals to prevent lag and sync issues
        for i, btn in enumerate(self.scan_buttons):
            btn.blockSignals(True)
            btn.setChecked(i == index)
            btn.blockSignals(False)
        
        # Get current active layers and sync timeline settings
        active_layers = self.mode_selector.get_active_layers()
        self.timeline_widget.set_active_layers(active_layers)
        
        # Sync all opacity settings from mode selector to timeline
        all_opacities = self.mode_selector.get_all_opacities()
        for layer, opacity in all_opacities.items():
            self.timeline_widget.set_layer_opacity(layer, opacity)
        
        # Update button display
        for i, btn in enumerate(self.scan_buttons):
            btn.setChecked(i == index)

        # Get current patient data
        try:
            patient_id, session_code = self._get_current_patient_info()
            cache_key = f"{patient_id}_{session_code}"
        except:
            print("[DEBUG] Failed to get current patient ID")
            return

        # Load scan data
        scans = self._loaded.get(cache_key, []) 

        if not scans or index >= len(scans):
            print(f"[DEBUG] Invalid scan index {index} for patient {cache_key}")
            return
        
        selected_scan = scans[index]

        # ✅ ENHANCED: Update timeline display with BSI integration
        self.update_timeline_with_scans_enhanced(scans, active_index=index)

        # Update BSI panel with selected scan
        self._load_bsi_for_scan(selected_scan, session_code)
    
        # ✅ NEW: Sync BSI panel scan selection without signal loop
        if hasattr(self, 'bsi_panel') and hasattr(self.bsi_panel, 'select_scan_by_index'):
            self.bsi_panel.select_scan_by_index(index)
        
        print(f"[DEBUG] Displaying {len(scans)} scans in timeline with layers: {active_layers}")
        self._update_scan_info_display()
        self._update_edit_button_states()

    # UPDATED: Remove old _set_mode method, add layer management methods
    def reset_mode_selector(self):
        """Reset mode selector to default values"""
        self.mode_selector.reset_to_defaults()
        self.timeline_widget.set_active_layers([])
        
        # Reset all opacity values in timeline - UPDATED with new layer
        default_opacities = {
            "Image": 1.0,
            "Segmentation": 0.35,
            "Hotspot": 0.5,
            "HotspotBBox": 1.0
        }
        for layer, opacity in default_opacities.items():
            self.timeline_widget.set_layer_opacity(layer, opacity)

    def set_default_layers(self):
        """Set default layer configuration (Image only)"""
        print("[DEBUG] Setting default layers: 'Image' checkbox should now be ON.")
        self.mode_selector.set_layer_active("Image", True)
            
    def get_current_layer_status(self) -> dict:
        """Get current layer status for debugging/logging"""
        return {
            "active_layers": self.mode_selector.get_active_layers(),
            "opacities": self.mode_selector.get_all_opacities(),
            "both_mode": self.mode_selector.is_both_mode(),
            "has_active_layers": self.mode_selector.has_any_active_layers()
        }

    # BACKWARD COMPATIBILITY: Keep old method names but adapt to new system
    def _set_mode(self, mode: str) -> None:
        """Backward compatibility method for old mode system"""
        print(f"[DEBUG] Legacy mode set to: {mode} - converting to layer system")
        
        # Reset all layers first
        self.mode_selector.reset_to_defaults()
        
        # Convert old mode to layer selections
        if mode == "Original":
            self.mode_selector.set_layer_active("Image", True)
        elif mode == "Segmentation":
            self.mode_selector.set_layer_active("Image", True)
            self.mode_selector.set_layer_active("Segmentation", True)
        elif mode == "Hotspot":
            self.mode_selector.set_layer_active("Image", True)
            self.mode_selector.set_layer_active("Hotspot", True)
        elif mode == "Both":
            self.mode_selector.set_layer_active("All", True)
        
        # Refresh current scan if any is selected
        if hasattr(self, 'scan_buttons'):
            for i, btn in enumerate(self.scan_buttons):
                if btn.isChecked():
                    self._on_scan_button_clicked(i)
                    break

    def _handle_logout(self):
        """Emits the logout signal and closes the window."""
        self.logout_requested.emit()
        self.close()
    
    def closeEvent(self, event: QCloseEvent):
        print("[DEBUG] Membersihkan sumber daya di MainWindow (SPECT)...")
        print("[DEBUG] Menutup process pool...")
        self.pool.close()
        self.pool.join()
        print("[DEBUG] Process pool ditutup.")
        if hasattr(self, 'timeline_widget') and hasattr(self.timeline_widget, 'cleanup'):
            self.timeline_widget.cleanup()
        if hasattr(self, 'bsi_panel') and hasattr(self.bsi_panel, 'cleanup'):
            print("[DEBUG] Cleaning up BSI panel...")
        super().closeEvent(event)

    # Rest of the methods remain the same...
    def _run_hotspot_processing_on_demand(self):
        """
        Check if hotspot files exist, if not, create them (fallback only)
        Most of the time this shouldn't be needed since hotspot processing 
        is done during import.
        """
        try:
            id_text = self.patient_bar.id_combo.currentText()
            if not id_text.startswith("ID: "): return
            
            remainder = id_text[4:]
            patient_id = remainder.split(" (")[0]
            session = remainder.split(" (")[1].rstrip(")")
            
            cache_key = f"{patient_id}_{session}"
            scans = self._loaded.get(cache_key, [])
            if not scans: return

            print("[DEBUG] Checking hotspot files availability...")
            
            # Check if hotspot files already exist
            missing_hotspot_files = []
            for scan_data in scans:
                try:
                    dicom_path = scan_data["path"]
                    study_date = extract_study_date_from_dicom(dicom_path)
                    filename_stem = generate_filename_stem(patient_id, study_date)
                    
                    hotspot_ant = dicom_path.parent / f"{filename_stem}_ant_hotspot_colored.png"
                    hotspot_post = dicom_path.parent / f"{filename_stem}_post_hotspot_colored.png"
                    
                    if not hotspot_ant.exists() or not hotspot_post.exists():
                        missing_hotspot_files.append(dicom_path)
                        print(f"[DEBUG] Missing hotspot files for: {filename_stem}")
                    
                except Exception as e:
                    print(f"[WARN] Could not check hotspot files: {e}")
            
            if not missing_hotspot_files:
                print("[DEBUG] All hotspot files already exist! Refreshing timeline...")
                self.timeline_widget.refresh_current_view()
                return
            
            print(f"[DEBUG] Creating {len(missing_hotspot_files)} missing hotspot files...")
            
            # Show loading dialog only if we need to process
            loading_dialog = SPECTLoadingDialog("Creating missing hotspot files...", parent=self)
            loading_dialog.show()
            QApplication.processEvents()

            hotspot_jobs = []
            for dicom_file in missing_hotspot_files:
                job = self.pool.apply_async(
                    run_hotspot_processing_in_process, 
                    args=(dicom_file, patient_id)
                )
                hotspot_jobs.append(job)
            
            # Wait for processing to complete
            for job in hotspot_jobs:
                job.get(timeout=180)

            loading_dialog.close()
            print("[DEBUG] Missing hotspot files created. Refreshing timeline...")
            
            # Refresh timeline to load the newly created files
            self.timeline_widget.refresh_current_view()

        except Exception as e:
            print(f"[ERROR] Failed to run on-demand hotspot processing: {e}")
            if 'loading_dialog' in locals() and loading_dialog:
                loading_dialog.close()

    def _show_import_dialog(self) -> None:
        """Show the updated import dialog"""
        print("[DEBUG] Opening DICOM import dialog...")
        
        dlg = DicomImportDialog(
            data_root=self.data_root, 
            parent=self, 
            session_code=self.session_code
        )
        
        # Connect signal untuk auto-rescan setelah import
        dlg.files_imported.connect(self._on_files_imported)
        
        # Show dialog
        result = dlg.exec()
        
        if result == QDialog.Accepted:
            print("[DEBUG] Import dialog accepted")
        else:
            print("[DEBUG] Import dialog cancelled")

    def _on_files_imported(self):
        """Handle files imported signal"""
        print("[DEBUG] Files imported signal received, rescanning folder...")
        self._scan_folder()

    def _scan_folder(self) -> None:
        """Scan folder using NEW directory structure - FIXED to filter by current session only"""
        print(f"[DEBUG] Starting folder scan for session: {self.session_code}")
        
        id_combo = self.patient_bar.id_combo
        id_combo.clear()
        
        # Use NEW directory scanner for new structure
        all_sessions_map = scan_spect_directory_new_structure(SPECT_DATA_PATH)
        print(f"[DEBUG] Found {len(all_sessions_map)} total sessions: {list(all_sessions_map.keys())}")
        
        # FIXED: Only use current session if specified
        if self.session_code:
            if self.session_code in all_sessions_map:
                # Only show patients from current session
                session_patients = {self.session_code: all_sessions_map[self.session_code]}
                print(f"[DEBUG] Filtered to session {self.session_code}: {len(session_patients[self.session_code])} patients")
            else:
                # Session not found, show empty
                session_patients = {}
                print(f"[DEBUG] Session {self.session_code} not found in data")
        else:
            # No session specified, show all (fallback)
            session_patients = all_sessions_map
            print(f"[DEBUG] No session filter, showing all sessions")
        
        self._session_patients_map = session_patients
        
        # Populate combo box with patients from filtered sessions only
        all_patients = []
        for session, patients in session_patients.items():
            for patient_id in patients.keys():
                display_text = f"ID: {patient_id} ({session})"
                all_patients.append((display_text, patient_id, session))
        
        # Sort by patient ID
        all_patients.sort(key=lambda x: x[1])
        
        # Add to combo box
        for display_text, patient_id, session in all_patients:
            id_combo.addItem(display_text)
        
        print(f"[DEBUG] Added {len(all_patients)} patients to combo box for session {self.session_code}")

        # Clear selections dan reset UI
        id_combo.clearSelection()
        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([])
        
        # ✅ NEW: Clear BSI panel
        self.bsi_panel.clear_patient_data()
        
        print("[DEBUG] Folder scan completed")
    
    def _on_patient_selected(self, txt: str) -> None:
        """Handle patient selection with new structure - FIXED parsing logic"""
        print(f"[DEBUG] _on_patient_selected: {txt}")
        try:
            # FIXED: Parse "ID: 12 (NSY)" format correctly
            # Split by "ID: " first, then parse the rest
            if not txt.startswith("ID: "):
                print(f"[DEBUG] Invalid format: {txt}")
                return
                
            # Remove "ID: " prefix and get "12 (NSY)"
            remainder = txt[4:]  # Remove "ID: "
            
            # Split by " (" to separate patient_id and session
            if " (" not in remainder:
                print(f"[DEBUG] No session found in: {remainder}")
                return
                
            patient_id = remainder.split(" (")[0]  # "12"
            session_part = remainder.split(" (")[1]  # "NSY)"
            session = session_part.rstrip(")")  # "NSY"
            
            print(f"[DEBUG] Parsed - Patient: {patient_id}, Session: {session}")
            self._load_patient(patient_id, session)
            
        except (IndexError, ValueError) as e:
            print(f"[DEBUG] Failed to parse patient selection: {e}")
            print(f"[DEBUG] Original text: '{txt}'")
            return
    
    def _load_patient(self, patient_id: str, session_code: str) -> None:
        """Load patient data using new directory structure - SIMPLIFIED without AI processing"""
        print(f"[DEBUG] Loading patient: {patient_id} from session: {session_code}")
        
        # Create cache key
        cache_key = f"{patient_id}_{session_code}"
        print(f"[CACHE DEBUG] Cache key: {cache_key}")
        print(f"[CACHE DEBUG] Existing cache keys: {list(self._loaded.keys())}")

        loading_dialog = None
        
        if cache_key in self._loaded:
            print(f"[DEBUG] Data untuk {cache_key} ditemukan di cache.")
            scans = self._loaded[cache_key]
        else:
            print(f"[DEBUG] Loading scans for {cache_key} from disk...")
            
            # Show loading dialog
            loading_dialog = SPECTLoadingDialog(patient_id, parent=self)
            loading_dialog.show()
            QApplication.processEvents()
            
            initial_scans = []

            loading_dialog.update_loading_step("Scanning patient directory...", 20)
            QApplication.processEvents()

            # Get patient DICOM files using new structure
            dicom_files = get_patient_dicom_files(session_code, patient_id, primary_only=True)
            print(f"[DEBUG] Found {len(dicom_files)} DICOM files for patient {patient_id}")
            
            # ❌ NO MORE YOLO DETECTION - IT'S ALREADY DONE DURING IMPORT
            
            loading_dialog.update_loading_step("Loading DICOM files...", 40)
            QApplication.processEvents()

            for dicom_file in dicom_files:
                try:
                    frames, meta = load_frames_and_metadata(dicom_file)
                    scan_data = {"meta": meta, "frames": frames, "path": dicom_file}
                    
                    # ✅ ALL PROCESSING ALREADY DONE DURING IMPORT
                    # Just add placeholders for hotspot data - will be loaded when needed
                    scan_data["hotspot_frames"] = scan_data["frames"]  # Placeholder
                    scan_data["hotspot_frames_ant"] = scan_data["frames"]  # Placeholder  
                    scan_data["hotspot_frames_post"] = scan_data["frames"]  # Placeholder
                    
                    initial_scans.append(scan_data)
                    print(f"[DEBUG] Processed DICOM: {dicom_file.name}")
                    
                    loading_dialog.update_loading_step(f"Loading scan {len(initial_scans)}...", 50 + (len(initial_scans) * 30 // len(dicom_files)))
                    QApplication.processEvents()

                except Exception as e:
                    print(f"[WARN] Failed to read DICOM {dicom_file}: {e}")
            
            loading_dialog.update_loading_step("Finalizing data...", 90)
            QApplication.processEvents()
            
            # ❌ NO MORE ASYNC PROCESSING - EVERYTHING IS ALREADY DONE
            processed_scans = initial_scans
            
            # Get study date for file checking (for debug info)
            for scan_data in processed_scans:
                try:
                    study_date = extract_study_date_from_dicom(scan_data["path"])
                    filename_stem = generate_filename_stem(patient_id, study_date)
                    print(f"[DEBUG] Scan files for {filename_stem}:")
                    
                    # Check what files exist (all should be created during import)
                    xml_ant = scan_data["path"].parent / f"{filename_stem}_ant.xml"
                    xml_post = scan_data["path"].parent / f"{filename_stem}_post.xml"
                    hotspot_ant = scan_data["path"].parent / f"{filename_stem}_ant_hotspot_colored.png"
                    hotspot_post = scan_data["path"].parent / f"{filename_stem}_post_hotspot_colored.png"
                    
                    files_status = []
                    if xml_ant.exists(): files_status.append("XML-ant")
                    if xml_post.exists(): files_status.append("XML-post")  
                    if hotspot_ant.exists(): files_status.append("Hotspot-ant")
                    if hotspot_post.exists(): files_status.append("Hotspot-post")
                    
                    print(f"[DEBUG] Available files: {', '.join(files_status) if files_status else 'None'}")
                    
                    # ✅ TAMBAHKAN KODE DEBUG PNG DI SINI
                    # Debug: Check if original PNG files exist
                    patient_folder = scan_data["path"].parent
                    anterior_png = patient_folder / f"{filename_stem}_anterior_original.png"
                    posterior_png = patient_folder / f"{filename_stem}_posterior_original.png"
                    
                    png_status = []
                    if anterior_png.exists():
                        png_status.append("Anterior-PNG")
                    if posterior_png.exists():
                        png_status.append("Posterior-PNG")
                        
                    print(f"[DEBUG] Available PNG files for {filename_stem}: {', '.join(png_status) if png_status else 'None'}")
                    
                except Exception as e:
                    print(f"[WARN] Could not check files for scan: {e}")
            
            scans = sorted(processed_scans, key=lambda s: s["meta"].get("study_date", ""))
            
            if scans:
                print(f"[DEBUG] Saving {len(scans)} scans to cache for {cache_key}")
                self._loaded[cache_key] = scans
            else:
                print(f"[WARN] No scans processed for {cache_key}. Cache not saved.")

            loading_dialog.update_loading_step("Loading completed!", 100)
            QApplication.processEvents()

        # Close loading dialog
        if loading_dialog:
            loading_dialog.close()
        
        # Reset the layer controls to their default state for the new patient
        self.reset_mode_selector()
        self.set_default_layers()

        print(f"[DEBUG] All data loaded. Total scans: {len(scans)}")
        if scans:
            # 1. Set the visual state of the layer controls first.
            self.reset_mode_selector()
            self.set_default_layers()  # This makes the "Original" checkbox appear checked.

            # 2. Populate the patient info bar and create the scan buttons.
            self.patient_bar.set_patient_meta(scans[-1]["meta"])
            self._populate_scan_buttons(scans)

            # 3. CRITICAL FIX: Force the timeline widget to use the default state.
            # This directly tells the viewer what layer to display for the initial load,
            # bypassing any potential state conflicts.
            # Note: If you renamed "Original" to "Image", change the string below.
            default_layers_for_display = ['Image']
            self.timeline_widget.set_active_layers(default_layers_for_display)

            # Also sync opacity settings to ensure consistency.
            all_opacities = self.mode_selector.get_all_opacities()
            for layer, opacity in all_opacities.items():
                self.timeline_widget.set_layer_opacity(layer, opacity)

            # 4. Now, update the UI with the scan data.
            self.update_timeline_with_scans_enhanced(scans, active_index=0)
            self._load_bsi_for_scan(scans[0], session_code)

            # 5. Visually check the first scan button (do NOT use .click()).
            if self.scan_buttons:
                self.scan_buttons[0].setChecked(True)

            # 6. Update all info labels to reflect the new state.
            self._update_scan_info_display()
            self._update_edit_button_states()
            self._update_active_layers_display()

        else:
            # This part for when no scans are found remains the same.
            self.patient_bar.clear_info()
            self._populate_scan_buttons([])
            self.timeline_widget.display_timeline([])
            self.bsi_panel.clear_patient_data()


    def _populate_scan_buttons(self, scans: List[Dict]) -> None:
        """Populate scan buttons"""
        # Clear existing buttons
        for btn in self.scan_buttons:
            btn.deleteLater()
        self.scan_buttons.clear()

        # Create new buttons
        for i, scan in enumerate(scans):
            btn = QPushButton(f"Scan {i + 1}")
            btn.setCheckable(True)
            btn.setStyleSheet(SCAN_BUTTON_STYLE)
            btn.clicked.connect(partial(self._on_scan_button_clicked, i))
            self.scan_button_container.addWidget(btn)
            self.scan_buttons.append(btn)

    # --- Zoom and view callbacks ---
    def zoom_in(self):
        """Zoom in timeline"""
        self.timeline_widget.zoom_in()

    def zoom_out(self):
        """Zoom out timeline"""
        self.timeline_widget.zoom_out()