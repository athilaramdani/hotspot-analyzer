# features/spect_viewer/gui/side_panel.py - FIXED for Single View Support

from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QCheckBox
)
from PySide6.QtGui import QColor

from .bsi_canvas import BSICanvas
from features.spect_viewer.logic.quantification_integration import QuantificationManager
from core.gui.ui_constants import PRIMARY_BUTTON_STYLE

# Button styles
INACTIVE_BUTTON_STYLE = """
    QPushButton {
        background-color: #a9a9a9; border: none; color: white;
        padding: 8px; font-weight: bold; border-radius: 4px;
    }
    QPushButton:hover { background-color: #8c8c8c; }
"""
ACTIVE_BUTTON_STYLE = """
    QPushButton {
        background-color: #4e73df; border: none; color: white;
        padding: 8px; font-weight: bold; border-radius: 4px;
    }
"""

class BSISidePanel(QWidget):
    """
    ✅ FIXED: BSI Side Panel that supports single view quantification
    """
    export_requested = Signal(str)
    analysis_requested = Signal()
    scan_selected = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.current_patient_folder = None
        self.current_patient_id = None
        self.current_study_date = None
        # self.scan_buttons = []
        self.quant_manager = QuantificationManager()
        self._build_ui()

    def _build_ui(self):
        main_panel_layout = QVBoxLayout(self)
        main_panel_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(12)

        self._create_title_section(content_layout)
        self.bsi_canvas = BSICanvas()
        content_layout.addWidget(self.bsi_canvas)
        self._create_chart_controls_section(content_layout)
        # content_layout.addWidget(self._create_scan_selection_section())
        content_layout.addWidget(self._create_results_table_v2())
        content_layout.addWidget(self._create_controls_section())
        content_layout.addStretch()
        main_panel_layout.addWidget(scroll_area)

    def _on_chart_visibility_changed(self):
        """Handle chart visibility checkbox changes"""
        anterior_visible = self.anterior_checkbox.isChecked()
        posterior_visible = self.posterior_checkbox.isChecked()
        
        # ✅ SIMPLIFIED: Update chart visibility without combined
        self.bsi_canvas.set_line_visibility(anterior_visible, posterior_visible)

    def _create_title_section(self, layout):
        title_frame = QFrame()
        title_frame.setStyleSheet("background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 8px;")
        title_layout = QVBoxLayout(title_frame)
        self.title_label = QLabel("<b>BSI Quantification Analysis </b>")
        self.title_label.setStyleSheet("font-size: 14px; color: #2c3e50; font-weight: bold; margin-bottom: 4px;")
        title_layout.addWidget(self.title_label)
        self.patient_info_label = QLabel("Select a patient to view BSI analysis")
        self.patient_info_label.setStyleSheet("font-size: 11px; color: #6c757d; font-style: italic;")
        title_layout.addWidget(self.patient_info_label)
        layout.addWidget(title_frame)
        
    def _create_chart_controls_section(self, layout):
        """Create checkbox controls for BSI chart lines"""
        controls_frame = QFrame()
        controls_frame.setStyleSheet("background: #f0f8ff; border: 1px solid #cce7ff; border-radius: 4px; padding: 8px; margin: 4px 0px;")
        controls_layout = QVBoxLayout(controls_frame)
        
        # Title
        controls_title = QLabel("<b>Chart Display Options</b>")
        controls_title.setStyleSheet("font-size: 11px; color: #495057; font-weight: bold; margin-bottom: 4px;")
        controls_layout.addWidget(controls_title)
        
        # Checkboxes layout
        checkboxes_layout = QHBoxLayout()
        
        # Anterior checkbox
        self.anterior_checkbox = QCheckBox("Anterior")
        self.anterior_checkbox.setChecked(True)
        self.anterior_checkbox.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        self.anterior_checkbox.stateChanged.connect(self._on_chart_visibility_changed)
        checkboxes_layout.addWidget(self.anterior_checkbox)
        
        # Posterior checkbox
        self.posterior_checkbox = QCheckBox("Posterior")
        self.posterior_checkbox.setChecked(True)
        self.posterior_checkbox.setStyleSheet("color: #4ecdc4; font-weight: bold;")
        self.posterior_checkbox.stateChanged.connect(self._on_chart_visibility_changed)
        checkboxes_layout.addWidget(self.posterior_checkbox)
        
        checkboxes_layout.addStretch()
        controls_layout.addLayout(checkboxes_layout)
        layout.addWidget(controls_frame)
        
    # def _create_scan_selection_section(self) -> QWidget:
    #     section_widget = QFrame()
    #     section_widget.setStyleSheet("padding: 8px 0px;")
    #     self.scan_buttons_layout = QHBoxLayout(section_widget)
    #     self.scan_buttons_layout.setContentsMargins(0, 0, 0, 0)
    #     self.scan_buttons_layout.setSpacing(8)
    #     label = QLabel("<b>Select Scan:</b>")
    #     self.scan_buttons_layout.addWidget(label)
    #     self.scan_buttons_layout.addStretch()
    #     return section_widget

    def _create_results_table_v2(self) -> QWidget:
        """✅ FIXED: V1.2 table format with support for single view data"""
        table_container = QFrame()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        # Table title
        table_title = QLabel("<b>Quantification Results</b>")
        table_title.setStyleSheet("font-size: 12px; color: #495057; font-weight: bold; margin-bottom: 8px;")
        table_layout.addWidget(table_title)
        
        # ✅ V1.2 table structure
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "Region", 
            "Benign Ant", "Benign Post",
            "Malignant Ant", "Malignant Post"
        ])
        
        self.results_table.setMinimumHeight(450)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # Enable user column resizing
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(header.ResizeMode.Interactive)
        
        # Set initial column widths (user can adjust)
        self.results_table.setColumnWidth(0, 200)  # Region name
        self.results_table.setColumnWidth(1, 120)  # Benign Ant
        self.results_table.setColumnWidth(2, 120)  # Benign Post  
        self.results_table.setColumnWidth(3, 130)  # Malignant Ant
        self.results_table.setColumnWidth(4, 130)  # Malignant Post
        
        # Set minimum column widths to prevent too narrow
        for col in range(5):
            header.setMinimumSectionSize(80)  # Minimum 80px per column
        
        # Enable horizontal scrollbar when needed
        from PySide6.QtWidgets import QSizePolicy
        self.results_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.results_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Enable sorting by clicking headers
        self.results_table.setSortingEnabled(True)
        
        table_layout.addWidget(self.results_table)
        
        # Add note about format
        note_label = QLabel("<i>Format: pixel_count (decimal_ratio) - Data per pixel • Drag column borders to resize</i>")
        note_label.setStyleSheet("font-size: 10px; color: #6c757d; font-style: italic; margin-top: 4px;")
        table_layout.addWidget(note_label)
        
        return table_container

    def _create_controls_section(self) -> QWidget:
        controls_frame = QFrame()
        controls_frame.setStyleSheet("background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 4px; padding: 8px;")
        controls_layout = QVBoxLayout(controls_frame)
        controls_header = QLabel("<b>Export & Actions</b>")
        controls_header.setStyleSheet("font-size: 12px; color: #495057; font-weight: bold; margin-bottom: 8px;")
        controls_layout.addWidget(controls_header)
        buttons_layout = QHBoxLayout()
        
        self.export_chart_btn = QPushButton("Export Chart")
        self.export_chart_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.export_chart_btn.clicked.connect(lambda: self.export_requested.emit("chart"))
        buttons_layout.addWidget(self.export_chart_btn)
        
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.export_csv_btn.clicked.connect(self._export_csv_data_v2)
        buttons_layout.addWidget(self.export_csv_btn)
        
        buttons_layout.addStretch()
        controls_layout.addLayout(buttons_layout)
        return controls_frame

    def load_patient_data(self, patient_folder: Path, patient_id: str, study_date: str) -> bool:
        """✅ FIXED: Load patient data tanpa scan selector"""
        try:
            self.current_patient_folder = patient_folder
            self.current_patient_id = patient_id
            self.current_study_date = study_date  # Set study_date langsung
            
            # Test BSI canvas loading
            canvas_success = self.bsi_canvas.load_bsi_data(patient_folder, patient_id, study_date)
            
            # Test quantification manager - langsung load untuk study_date yang diberikan
            quant_results = self.quant_manager.load_quantification_results(
                patient_folder, patient_id, study_date
            )
            
            if quant_results:
                # Extract table data structure (handles single view)
                anterior_data = quant_results.get('anterior_results', {}).get('bsi_results', {}) if quant_results.get('anterior_results') else {}
                posterior_data = quant_results.get('posterior_results', {}).get('bsi_results', {}) if quant_results.get('posterior_results') else {}
                processing_mode = quant_results.get('summary_statistics', {}).get('processing_mode', 'unknown')
                
                self._populate_results_table_v2(anterior_data, posterior_data, processing_mode)
                self._update_patient_info(patient_id, study_date)
                self._update_button_states(True)
            else:
                if hasattr(self, 'results_table'):
                    self.results_table.setRowCount(0)
                self._update_patient_info(patient_id, "No Data Found")
                self._update_button_states(False)
                    
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.clear_patient_data()
            return False
    
    # def _populate_scan_buttons(self, all_scans: list):
    #     """✅ UPDATED: Populate scan selection buttons without mode indicators"""
    #     for btn in self.scan_buttons:
    #         self.scan_buttons_layout.removeWidget(btn)
    #         btn.deleteLater()
    #     self.scan_buttons.clear()
        
    #     for i, scan_data in enumerate(all_scans):
    #         # ✅ FIXED: Simple scan button without mode indicator
    #         btn = QPushButton(f"Scan {i + 1}")
    #         btn.clicked.connect(lambda checked, b=btn, data=scan_data: self._on_scan_selected(b, data))
            
    #         # ✅ FIXED: Use standard button style without color coding
    #         btn.setStyleSheet(INACTIVE_BUTTON_STYLE)
            
    #         self.scan_buttons_layout.insertWidget(self.scan_buttons_layout.count() - 1, btn)
    #         self.scan_buttons.append(btn)

    # def _on_scan_selected(self, clicked_button: QPushButton, scan_data: dict, emit_signal: bool = True):
    #     """✅ UPDATED: Handle scan selection - NO COMBINED BSI"""
    #     # Update button styles
    #     for btn in self.scan_buttons:
    #         if btn is clicked_button:
    #             btn.setStyleSheet(ACTIVE_BUTTON_STYLE)
    #         else:
    #             btn.setStyleSheet(INACTIVE_BUTTON_STYLE)
        
    #     study_date = scan_data.get("study_date")
    #     if not study_date: 
    #         return
        
    #     self.current_study_date = study_date
    #     processing_mode = scan_data.get('processing_mode', 'unknown')
    #     self._update_patient_info(self.current_patient_id, self.current_study_date)
        
    #     # Load combined results (supports single view)
    #     quant_results = self.quant_manager.load_quantification_results(
    #         self.current_patient_folder, self.current_patient_id, study_date
    #     )
        
    #     if quant_results:
    #         # Extract table data structure (handles single view)
    #         anterior_data = quant_results.get('anterior_results', {}).get('bsi_results', {}) if quant_results.get('anterior_results') else {}
    #         posterior_data = quant_results.get('posterior_results', {}).get('bsi_results', {}) if quant_results.get('posterior_results') else {}
    #         self._populate_results_table_v2(anterior_data, posterior_data, processing_mode)
        
    #     if emit_signal:
    #         self.scan_selected.emit(study_date)

    # def select_scan_by_index(self, scan_index: int):
    #     """Select scan by index without emitting signals (called from main window)"""
    #     if 0 <= scan_index < len(self.scan_buttons):
    #         print(f"[BSI PANEL SINGLE] Selecting scan {scan_index + 1} from main window")
    #         # Get scan data
    #         all_scans = self.quant_manager.load_all_quantification_scores(
    #             self.current_patient_folder, self.current_patient_id
    #         )
    #         if all_scans and scan_index < len(all_scans):
    #             sorted_scans = sorted(all_scans, key=lambda x: x["study_date"])
    #             scan_data = sorted_scans[scan_index]
    #             # Call without emitting signal to prevent loop
    #             self._on_scan_selected(self.scan_buttons[scan_index], scan_data, emit_signal=False)
            
    def _populate_results_table_v2(self, anterior_data: dict, posterior_data: dict, processing_mode: str = "unknown"):
        """✅ FIXED: Populate table with single view support and proper sorting"""
        if not anterior_data and not posterior_data:
            self.results_table.setRowCount(0)
            return
        
        # Get all unique regions from both views
        all_regions = set(anterior_data.keys()) | set(posterior_data.keys())
        all_regions.discard('background')
        
        sorted_regions = sorted(all_regions)
        # +1 for total row
        self.results_table.setRowCount(len(sorted_regions) + 1)
        
        # Initialize totals for summary row
        total_ant_benign = 0
        total_post_benign = 0
        total_ant_malignant = 0
        total_post_malignant = 0
        
        for row, region_name in enumerate(sorted_regions):
            # Get data for both views
            ant_data = anterior_data.get(region_name, {})
            post_data = posterior_data.get(region_name, {})
            
            # Extract values with format: pixel_count (decimal_ratio)
            ant_benign = ant_data.get('benign_pixels', 0)
            ant_benign_ratio = ant_data.get('benign_ratio', 0.0)
            post_benign = post_data.get('benign_pixels', 0)
            post_benign_ratio = post_data.get('benign_ratio', 0.0)
            
            ant_malignant = ant_data.get('malignant_pixels', 0)
            ant_malignant_ratio = ant_data.get('malignant_ratio', 0.0)
            post_malignant = post_data.get('malignant_pixels', 0)
            post_malignant_ratio = post_data.get('malignant_ratio', 0.0)
            
            # Add to totals
            total_ant_benign += ant_benign
            total_post_benign += post_benign
            total_ant_malignant += ant_malignant
            total_post_malignant += post_malignant
            
            # Handle N/A for single view mode
            if processing_mode == 'single_view_anterior':
                post_benign_text = "N/A"
                post_malignant_text = "N/A"
            elif processing_mode == 'single_view_posterior':
                ant_benign_text = "N/A"
                ant_malignant_text = "N/A"
            else:
                # Dual view - show all data
                post_benign_text = f"{post_benign} ({post_benign_ratio:.3f})"
                post_malignant_text = f"{post_malignant} ({post_malignant_ratio:.3f})"
                ant_benign_text = f"{ant_benign} ({ant_benign_ratio:.3f})"
                ant_malignant_text = f"{ant_malignant} ({ant_malignant_ratio:.3f})"
            
            # Use appropriate text format
            if processing_mode != 'single_view_posterior':
                ant_benign_text = f"{ant_benign} ({ant_benign_ratio:.3f})"
                ant_malignant_text = f"{ant_malignant} ({ant_malignant_ratio:.3f})"
            if processing_mode != 'single_view_anterior':
                post_benign_text = f"{post_benign} ({post_benign_ratio:.3f})"
                post_malignant_text = f"{post_malignant} ({post_malignant_ratio:.3f})"
            
            # Create table items
            items = [
                QTableWidgetItem(region_name.title()),
                QTableWidgetItem(ant_benign_text),
                QTableWidgetItem(post_benign_text),
                QTableWidgetItem(ant_malignant_text),
                QTableWidgetItem(post_malignant_text)
            ]
            
            # Color coding for malignant values
            for col, item in enumerate(items):
                if col in [3, 4]:  # Malignant columns
                    if col == 3 and ant_malignant > 0 and processing_mode != 'single_view_posterior':
                        item.setBackground(QColor(255, 200, 200))
                    elif col == 4 and post_malignant > 0 and processing_mode != 'single_view_anterior':
                        item.setBackground(QColor(255, 200, 200))
                    elif item.text() == "N/A":
                        item.setBackground(QColor(240, 240, 240))  # Gray for N/A
                
                self.results_table.setItem(row, col, item)
        
        # ✅ FIXED: ADD TOTAL ROW at the bottom (handles table sorting properly)
        total_row = len(sorted_regions)
        
        # Handle totals for single view mode
        if processing_mode == 'single_view_anterior':
            total_items = [
                QTableWidgetItem("TOTAL"),
                QTableWidgetItem(str(total_ant_benign)),
                QTableWidgetItem("N/A"),
                QTableWidgetItem(str(total_ant_malignant)),
                QTableWidgetItem("N/A")
            ]
        elif processing_mode == 'single_view_posterior':
            total_items = [
                QTableWidgetItem("TOTAL"),
                QTableWidgetItem("N/A"),
                QTableWidgetItem(str(total_post_benign)),
                QTableWidgetItem("N/A"),
                QTableWidgetItem(str(total_post_malignant))
            ]
        else:
            total_items = [
                QTableWidgetItem("TOTAL"),
                QTableWidgetItem(str(total_ant_benign)),
                QTableWidgetItem(str(total_post_benign)),
                QTableWidgetItem(str(total_ant_malignant)),
                QTableWidgetItem(str(total_post_malignant))
            ]
        
        # ✅ FIXED: Set custom sort role to ensure TOTAL always stays at bottom
        for col, item in enumerate(total_items):
            if item.text() == "N/A":
                item.setBackground(QColor(220, 220, 220))  # Darker gray for N/A in totals
            else:
                item.setBackground(QColor(230, 230, 230))  # Gray background
            if col == 0:
                # Use QFont for bold instead of setStyleSheet
                from PySide6.QtGui import QFont
                font = QFont()
                font.setBold(True)
                item.setFont(font)
                # ✅ CRITICAL: Set custom sort role to keep TOTAL at bottom
                item.setData(Qt.UserRole, "zzz_total")  # This ensures it sorts to the bottom
            else:
                # For numeric columns, set a very high sort value to keep at bottom
                item.setData(Qt.UserRole, 999999)
            self.results_table.setItem(total_row, col, item)

    def _update_patient_info(self, patient_id: str, study_date: str):
        """✅ SIMPLIFIED: Update patient info display"""
        try:
            formatted_date = datetime.strptime(study_date, "%Y%m%d").strftime("%b %d, %Y")
        except (ValueError, TypeError):
            formatted_date = study_date or "N/A"
        
        # ✅ SIMPLE: Clean patient info
        self.patient_info_label.setText(f"Patient: {patient_id} | Study: {formatted_date} | BSI Analysis")
    
    def _update_button_states(self, has_data: bool):
        """Enable/disable control buttons"""
        # SAFETY CHECK: Only update buttons if they exist
        if hasattr(self, 'export_chart_btn'):
            self.export_chart_btn.setEnabled(has_data)
        if hasattr(self, 'export_csv_btn'):
            self.export_csv_btn.setEnabled(has_data)
        
    def clear_patient_data(self):
        """Clear all patient data from panel"""
        print("[BSI SIDE PANEL] Clearing all patient data...")
        self.current_patient_folder = None
        self.current_patient_id = None
        self.current_study_date = None
        self.bsi_canvas.clear_data()
        
        # SAFETY CHECK: Only clear table if it exists
        if hasattr(self, 'results_table'):
            self.results_table.setRowCount(0)
        
        # ✅ SIMPLIFIED: No processing mode parameter
        self._update_patient_info("N/A", "N/A")
        # for btn in self.scan_buttons:
        #     self.scan_buttons_layout.removeWidget(btn)
        #     btn.deleteLater()
        # self.scan_buttons.clear()
        self._update_button_states(False)

    def set_session_code(self, session_code: str):
        """Set session code for internal use"""
        self._current_session_code = session_code
    
    def refresh_current_patient(self):
        """Refresh BSI panel for current patient"""
        if self.current_patient_folder and self.current_patient_id:
            print(f"[BSI PANEL] Refreshing data for patient {self.current_patient_id}")
            success = self.load_patient_data(
                self.current_patient_folder, 
                self.current_patient_id, 
                self.current_study_date or "latest"
            )
            if success:
                print("[BSI PANEL] ✅ Refresh successful")
            else:
                print("[BSI PANEL] ❌ Refresh failed")
        else:
            print("[BSI PANEL] No patient data to refresh")
    
    def _export_csv_data_v2(self):
        """✅ UPDATED: Export CSV data with single view support"""
        if not self.current_patient_id or not self.current_study_date:
            print("[BSI EXPORT] No patient data to export")
            return
            
        try:
            from PySide6.QtWidgets import QFileDialog
            import csv
            
            # Get save location
            filename = f"BSI_Results_{self.current_patient_id}_{self.current_study_date}.csv"
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Export BSI Results to CSV", 
                filename,
                "CSV Files (*.csv)"
            )
            
            if not file_path:
                return
                
            # Export table data
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(["BSI Quantification Results"])
                writer.writerow([])
                
                # Add processing mode info if available
                if hasattr(self, 'quant_manager') and self.quant_manager.current_results:
                    summary_stats = self.quant_manager.current_results.get('summary_statistics', {})
                    processing_mode = summary_stats.get('processing_mode', 'unknown')
                    writer.writerow(["Processing Mode", processing_mode])
                    writer.writerow([])
                
                # Write table headers
                headers = ["Region", "Benign Ant", "Benign Post", "Malignant Ant", "Malignant Post"]
                writer.writerow(headers)
                
                # Write data rows
                for row in range(self.results_table.rowCount()):
                    row_data = []
                    for col in range(self.results_table.columnCount()):
                        item = self.results_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
                
                # Write summary info
                writer.writerow([])
                writer.writerow(["Summary Information"])
                writer.writerow(["Patient ID", self.current_patient_id])
                writer.writerow(["Study Date", datetime.strptime(self.current_study_date, "%Y%m%d").strftime("%Y-%m-%d")])
                writer.writerow(["Export Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(["Analysis Method", "BSI Color-based Separate Views"])
                writer.writerow(["Data Format", "pixel_count (decimal_ratio) - per pixel"])
                writer.writerow(["Note", "Benign = Normal hotspots, Malignant = Abnormal hotspots"])
                writer.writerow(["Total Row", "Sum of all regions for each column (N/A for unavailable views)"])
                                
                # Add BSI scores summary with single view support
                if hasattr(self, 'quant_manager') and self.quant_manager.current_results:
                    summary_stats = self.quant_manager.current_results.get('summary_statistics', {})
                    anterior_bsi = summary_stats.get('anterior_bsi', 0.0)
                    posterior_bsi = summary_stats.get('posterior_bsi', 0.0)
                    processing_mode = summary_stats.get('processing_mode', 'unknown')
                    
                    writer.writerow([])
                    writer.writerow(["BSI Summary"])
                    
                    # AFTER:
                    if processing_mode == 'dual_view':
                        writer.writerow(["Anterior BSI", f"{anterior_bsi:.10f}".rstrip('0').rstrip('.')])
                        writer.writerow(["Posterior BSI", f"{posterior_bsi:.10f}".rstrip('0').rstrip('.')])
                    elif processing_mode == 'single_view_anterior':
                        writer.writerow(["Anterior BSI (%)", f"{anterior_bsi:.2f}%"])
                        writer.writerow(["Posterior BSI (%)", "N/A (files not available)"])
                        writer.writerow(["Note", "Only anterior view processed"])
                    elif processing_mode == 'single_view_posterior':
                        writer.writerow(["Anterior BSI (%)", "N/A (files not available)"])
                        writer.writerow(["Posterior BSI (%)", f"{posterior_bsi:.2f}%"])
                        writer.writerow(["Note", "Only posterior view processed"])
                    else:
                        writer.writerow(["Processing Mode", processing_mode])
                                    
            print(f"[BSI EXPORT] CSV exported successfully: {file_path}")
            
        except Exception as e:
            print(f"[BSI EXPORT] Error exporting CSV: {e}")

    def export_chart_to_file(self, file_path: Path) -> bool:
        """Export chart to file"""
        return self.bsi_canvas.export_chart(file_path)

    def export_report_to_file(self, file_path: Path) -> bool:
        """✅ UPDATED: Export V1.2 report to text file with single view support"""
        try:
            if not self.current_patient_id or not self.current_study_date:
                return False
                
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("BSI QUANTIFICATION REPORT\n")
                f.write("=" * 60 + "\n")
                f.write(f"Patient ID: {self.current_patient_id}\n")
                f.write(f"Study Date: {datetime.strptime(self.current_study_date, '%Y%m%d').strftime('%Y-%m-%d')}\n")
                f.write(f"Analysis Method: BSI Color-based Separate Views\n")
                f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                # ✅ Add processing mode info
                if hasattr(self, 'quant_manager') and self.quant_manager.current_results:
                    summary_stats = self.quant_manager.current_results.get('summary_statistics', {})
                    processing_mode = summary_stats.get('processing_mode', 'unknown')
                    f.write(f"Processing Mode: {processing_mode}\n")
                    
                    if processing_mode == 'single_view_anterior':
                        f.write("Note: Only anterior view files were available for processing\n")
                    elif processing_mode == 'single_view_posterior':
                        f.write("Note: Only posterior view files were available for processing\n")
                
                f.write("\n")
                
                # ✅ Add V1.2 BSI scores with single view support
                if hasattr(self, 'quant_manager') and self.quant_manager.current_results:
                    summary_stats = self.quant_manager.current_results.get('summary_statistics', {})
                    anterior_bsi = summary_stats.get('anterior_bsi', 0.0)
                    posterior_bsi = summary_stats.get('posterior_bsi', 0.0)
                    processing_mode = summary_stats.get('processing_mode', 'unknown')
                    
                    f.write("BSI SCORES:\n")
                    f.write("-" * 30 + "\n")
                    
                    if processing_mode == 'dual_view':
                        ant_str = f"{anterior_bsi:.10f}".rstrip('0').rstrip('.')
                        post_str = f"{posterior_bsi:.10f}".rstrip('0').rstrip('.')
                        f.write(f"Anterior BSI: {ant_str}\n")
                        f.write(f"Posterior BSI: {post_str}\n")
                    elif processing_mode == 'single_view_anterior':
                        f.write(f"Anterior BSI: {anterior_bsi:.2f}%\n")
                        f.write(f"Posterior BSI: N/A (files not available)\n")
                    elif processing_mode == 'single_view_posterior':
                        f.write(f"Anterior BSI: N/A (files not available)\n")
                    
                    f.write("\n")
                
                f.write("DETAILED QUANTIFICATION DATA:\n")
                f.write("-" * 30 + "\n")
                f.write("Format: pixel_count (decimal_ratio) - per pixel\n")
                f.write("Note: N/A indicates data not available for that view\n\n")
                
                # Export table data
                for row in range(self.results_table.rowCount()):
                    region_item = self.results_table.item(row, 0)
                    if region_item:
                        region_name = region_item.text()
                        f.write(f"{region_name}:\n")
                        
                        # Get data for each column
                        for col in range(1, self.results_table.columnCount()):
                            header = self.results_table.horizontalHeaderItem(col).text()
                            item = self.results_table.item(row, col)
                            value = item.text() if item else "N/A"
                            f.write(f"  {header}: {value}\n")
                        f.write("\n")
                
                f.write("=" * 60 + "\n")
                
            return True
            
        except Exception as e:
            print(f"[BSI REPORT V1.2 SINGLE] Error exporting report: {e}")
            return False