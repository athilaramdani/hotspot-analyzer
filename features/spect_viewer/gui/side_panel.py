# features/spect_viewer/gui/side_panel.py
"""
Enhanced side panel with BSI quantification results
Shows BSI chart, summary statistics, and detailed analysis comments
"""
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
    QSplitter, QPushButton, QFrame, QScrollArea
)

# Import BSI components
from .bsi_canvas import BSICanvas, BSIInfoPanel

# Import quantification integration
from features.spect_viewer.logic.quantification_integration import (
    QuantificationManager, 
    format_quantification_report,
    get_quantification_status
)

# Import UI constants
from core.gui.ui_constants import (
    Colors, 
    GROUP_BOX_STYLE, 
    INFO_LABEL_STYLE,
    DIALOG_PANEL_HEADER_STYLE,
    PRIMARY_BUTTON_STYLE,
    GRAY_BUTTON_STYLE,
    SUCCESS_BUTTON_STYLE
)


class BSISidePanel(QWidget):
    """
    Right-hand side panel with BSI quantification analysis
    Shows chart, statistics, and detailed comments
    """
    
    # Signals
    export_requested = Signal(str)  # Emit export type (chart, report, etc.)
    analysis_requested = Signal()   # Request to run analysis on current patient
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        
        # Current patient data
        self.current_patient_folder = None
        self.current_patient_id = None
        self.current_study_date = None
        
        # Quantification manager
        self.quant_manager = QuantificationManager()
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the side panel UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # Title section
        self._create_title_section(main_layout)
        
        # Create main splitter: chart (top) and details (bottom)
        self.main_splitter = QSplitter(Qt.Vertical)
        
        # Top section: BSI Chart and Info
        chart_section = self._create_chart_section()
        self.main_splitter.addWidget(chart_section)
        
        # Bottom section: Analysis Comments and Controls
        details_section = self._create_details_section()
        self.main_splitter.addWidget(details_section)
        
        # Set splitter proportions: Chart 60%, Details 40%
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([400, 200])
        
        # Style splitter
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e9ecef;
                height: 3px;
                margin: 2px;
                border-radius: 1px;
            }
            QSplitter::handle:hover {
                background-color: #4e73ff;
            }
        """)
        
        main_layout.addWidget(self.main_splitter)
    
    def _create_title_section(self, layout):
        """Create title section with patient info"""
        title_frame = QFrame()
        title_frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(8, 8, 8, 8)
        
        # Main title
        self.title_label = QLabel("<b>BSI Quantification Analysis</b>")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #2c3e50;
                font-weight: bold;
                margin-bottom: 4px;
            }
        """)
        title_layout.addWidget(self.title_label)
        
        # Patient info
        self.patient_info_label = QLabel("Select a patient to view BSI analysis")
        self.patient_info_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #6c757d;
                font-style: italic;
            }
        """)
        title_layout.addWidget(self.patient_info_label)
        
        layout.addWidget(title_frame)
    
    def _create_chart_section(self) -> QWidget:
        """Create chart section with BSI canvas and info panel"""
        section_widget = QWidget()
        section_layout = QHBoxLayout(section_widget)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(8)
        
        # Create horizontal splitter for chart and info
        chart_splitter = QSplitter(Qt.Horizontal)
        
        # Left: BSI Chart
        self.bsi_canvas = BSICanvas()
        chart_splitter.addWidget(self.bsi_canvas)
        
        # Right: BSI Info Panel
        self.bsi_info_panel = BSIInfoPanel()
        chart_splitter.addWidget(self.bsi_info_panel)
        
        # Set proportions: Chart 70%, Info 30%
        chart_splitter.setStretchFactor(0, 7)
        chart_splitter.setStretchFactor(1, 3)
        chart_splitter.setSizes([500, 200])
        
        section_layout.addWidget(chart_splitter)
        
        return section_widget
    
    def _create_details_section(self) -> QWidget:
        """Create details section with comments and controls"""
        section_widget = QWidget()
        section_layout = QVBoxLayout(section_widget)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(8)
        
        # Analysis comments section
        comments_frame = QFrame()
        comments_frame.setStyleSheet(GROUP_BOX_STYLE)
        comments_layout = QVBoxLayout(comments_frame)
        
        # Comments header
        comments_header = QLabel("<b>Analysis Comments</b>")
        comments_header.setStyleSheet(DIALOG_PANEL_HEADER_STYLE)
        comments_layout.addWidget(comments_header)
        
        # Comments text area
        self.comments_text = QTextEdit()
        self.comments_text.setReadOnly(True)
        self.comments_text.setMaximumHeight(120)
        self.comments_text.setStyleSheet("""
            QTextEdit {
                background: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
                color: #495057;
                line-height: 1.4;
            }
        """)
        self.comments_text.setPlainText("Select a patient with quantification results to view analysis comments.")
        comments_layout.addWidget(self.comments_text)
        
        section_layout.addWidget(comments_frame)
        
        # Control buttons section
        controls_frame = self._create_controls_section()
        section_layout.addWidget(controls_frame)
        
        return section_widget
    
    def _create_controls_section(self) -> QFrame:
        """Create control buttons section"""
        controls_frame = QFrame()
        controls_frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(8, 8, 8, 8)
        
        # Controls header
        controls_header = QLabel("<b>Export & Actions</b>")
        controls_header.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #495057;
                font-weight: bold;
                margin-bottom: 8px;
            }
        """)
        controls_layout.addWidget(controls_header)
        
        # Button layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        # Export chart button
        self.export_chart_btn = QPushButton("Export Chart")
        self.export_chart_btn.setStyleSheet(PRIMARY_BUTTON_STYLE + """
            QPushButton {
                font-size: 11px;
                padding: 6px 12px;
            }
        """)
        self.export_chart_btn.clicked.connect(lambda: self.export_requested.emit("chart"))
        self.export_chart_btn.setEnabled(False)
        buttons_layout.addWidget(self.export_chart_btn)
        
        # Export report button
        self.export_report_btn = QPushButton("Export Report")
        self.export_report_btn.setStyleSheet(SUCCESS_BUTTON_STYLE + """
            QPushButton {
                font-size: 11px;
                padding: 6px 12px;
            }
        """)
        self.export_report_btn.clicked.connect(lambda: self.export_requested.emit("report"))
        self.export_report_btn.setEnabled(False)
        buttons_layout.addWidget(self.export_report_btn)
        
        # Run analysis button
        self.run_analysis_btn = QPushButton("Run Analysis")
        self.run_analysis_btn.setStyleSheet(GRAY_BUTTON_STYLE + """
            QPushButton {
                font-size: 11px;
                padding: 6px 12px;
            }
        """)
        self.run_analysis_btn.clicked.connect(self.analysis_requested.emit)
        self.run_analysis_btn.setEnabled(False)
        buttons_layout.addWidget(self.run_analysis_btn)
        
        buttons_layout.addStretch()
        controls_layout.addLayout(buttons_layout)
        
        # Status indicator
        self.status_label = QLabel("No patient selected")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #6c757d;
                font-style: italic;
                margin-top: 4px;
            }
        """)
        controls_layout.addWidget(self.status_label)
        
        return controls_frame
    
    # ===== Public API =====
    def load_patient_data(self, patient_folder: Path, patient_id: str, study_date: str) -> bool:
        """
        Load BSI data for a patient
        
        Args:
            patient_folder: Patient directory path
            patient_id: Patient ID  
            study_date: Study date
            
        Returns:
            True if data loaded successfully
        """
        try:
            print(f"[BSI SIDE PANEL] Loading BSI data for patient {patient_id}")
            
            # Store current patient info
            self.current_patient_folder = patient_folder
            self.current_patient_id = patient_id
            self.current_study_date = study_date
            
            # Update patient info display
            self._update_patient_info(patient_id, study_date)
            
            # Check quantification status
            status = get_quantification_status(
                patient_folder / f"{patient_id}_{study_date}.dcm", 
                patient_id, 
                study_date
            )
            
            if not status.get("quantification_complete", False):
                self._show_no_quantification_data()
                return False
            
            # Load BSI data into canvas
            canvas_success = self.bsi_canvas.load_bsi_data(patient_folder, patient_id, study_date)
            
            if not canvas_success:
                self._show_quantification_error()
                return False
            
            # Load summary data into info panel
            summary_data = self.bsi_canvas.get_summary_data()
            self.bsi_info_panel.update_info(summary_data)
            
            # Generate analysis comments
            self._generate_analysis_comments(summary_data)
            
            # Update button states
            self._update_button_states(True)
            
            # Update status
            bsi_score = summary_data.get('bsi_score', 0) if summary_data else 0
            self.status_label.setText(f"BSI analysis loaded (Score: {bsi_score:.2f}%)")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    color: #28a745;
                    font-style: italic;
                    margin-top: 4px;
                }
            """)
            
            print(f"[BSI SIDE PANEL] Successfully loaded BSI data for {patient_id}")
            return True
            
        except Exception as e:
            print(f"[BSI SIDE PANEL] Error loading patient data: {e}")
            self._show_quantification_error()
            return False
    
    def clear_patient_data(self):
        """Clear current patient data"""
        print("[BSI SIDE PANEL] Clearing patient data")
        
        # Clear stored patient info
        self.current_patient_folder = None
        self.current_patient_id = None
        self.current_study_date = None
        
        # Clear components
        self.bsi_canvas.clear_data()
        self.bsi_info_panel.clear_info()
        
        # Reset UI
        self.patient_info_label.setText("Select a patient to view BSI analysis")
        self.comments_text.setPlainText("Select a patient with quantification results to view analysis comments.")
        
        # Update button states
        self._update_button_states(False)
        
        # Update status
        self.status_label.setText("No patient selected")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #6c757d;
                font-style: italic;
                margin-top: 4px;
            }
        """)
    
    def refresh_current_patient(self):
        """Refresh data for current patient"""
        if self.current_patient_folder and self.current_patient_id and self.current_study_date:
            self.load_patient_data(
                self.current_patient_folder,
                self.current_patient_id, 
                self.current_study_date
            )
    
    def export_chart_to_file(self, file_path: Path) -> bool:
        """Export BSI chart to file"""
        return self.bsi_canvas.export_chart(file_path)
    
    def export_report_to_file(self, file_path: Path) -> bool:
        """Export full BSI report to file"""
        if not (self.current_patient_folder and self.current_patient_id and self.current_study_date):
            return False
        
        try:
            report_text = format_quantification_report(
                self.current_patient_folder,
                self.current_patient_id,
                self.current_study_date
            )
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            
            print(f"[BSI SIDE PANEL] Report exported to: {file_path}")
            return True
            
        except Exception as e:
            print(f"[BSI SIDE PANEL] Report export failed: {e}")
            return False
    
    def get_current_bsi_score(self) -> float:
        """Get current BSI score"""
        return self.bsi_canvas.get_bsi_score()
    
    # ===== Internal Methods =====
    def _update_patient_info(self, patient_id: str, study_date: str):
        """Update patient info display"""
        try:
            formatted_date = datetime.strptime(study_date, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError:
            formatted_date = study_date
        
        self.patient_info_label.setText(f"Patient: {patient_id} | Study: {formatted_date}")
    
    def _show_no_quantification_data(self):
        """Show message when no quantification data exists"""
        self.comments_text.setPlainText(
            "No quantification data available for this patient.\n\n"
            "To generate BSI analysis:\n"
            "1. Ensure classification has been completed\n"
            "2. Run quantification analysis\n"
            "3. Classification masks will be used for BSI calculation"
        )
        
        self.status_label.setText("Quantification not completed")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #dc3545;
                font-style: italic;
                margin-top: 4px;
            }
        """)
        
        self._update_button_states(False)
        self.run_analysis_btn.setEnabled(True)  # Allow running analysis
    
    def _show_quantification_error(self):
        """Show message when quantification error occurs"""
        self.comments_text.setPlainText(
            "Error loading quantification data.\n\n"
            "Please check:\n"
            "- Classification files exist\n"
            "- Quantification JSON file is valid\n"
            "- File permissions are correct"
        )
        
        self.status_label.setText("Error loading quantification data")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #dc3545;
                font-style: italic;
                margin-top: 4px;
            }
        """)
        
        self._update_button_states(False)
    
    def _generate_analysis_comments(self, summary_data: Dict[str, Any]):
        """Generate analysis comments based on BSI data"""
        if not summary_data:
            self.comments_text.setPlainText("No summary data available.")
            return
        
        bsi_score = summary_data.get('bsi_score', 0)
        total_abnormal = summary_data.get('total_abnormal_hotspots', 0)
        segments_affected = summary_data.get('segments_with_abnormal', 0)
        segments_total = summary_data.get('segments_analyzed', 0)
        
        # Generate interpretation based on BSI score
        if bsi_score < 1.0:
            interpretation = "Low BSI suggests minimal bone abnormalities."
            severity = "Low"
        elif bsi_score < 3.0:
            interpretation = "Moderate BSI indicates some bone lesions present."
            severity = "Moderate"
        elif bsi_score < 8.0:
            interpretation = "High BSI suggests significant bone involvement."
            severity = "High"
        else:
            interpretation = "Very high BSI indicates extensive bone disease."
            severity = "Very High"
        
        # Create detailed comment
        comments = []
        comments.append(f"BSI ANALYSIS REPORT")
        comments.append(f"=" * 40)
        comments.append(f"")
        comments.append(f"BSI Score: {bsi_score:.2f}% ({severity})")
        comments.append(f"{interpretation}")
        comments.append(f"")
        comments.append(f"FINDINGS:")
        comments.append(f"• Total abnormal hotspots detected: {total_abnormal}")
        comments.append(f"• Anatomical segments affected: {segments_affected}/{segments_total}")
        comments.append(f"• Analysis method: Classification-based quantification")
        comments.append(f"")
        
        if total_abnormal > 0:
            comments.append(f"RECOMMENDATIONS:")
            if bsi_score > 5.0:
                comments.append(f"• Consider additional imaging for extent evaluation")
                comments.append(f"• Multidisciplinary team consultation recommended")
            elif bsi_score > 2.0:
                comments.append(f"• Monitor disease progression with follow-up imaging")
                comments.append(f"• Clinical correlation advised")
            else:
                comments.append(f"• Routine follow-up as clinically indicated")
            
            comments.append(f"• Correlation with clinical symptoms and other imaging")
        else:
            comments.append(f"RECOMMENDATIONS:")
            comments.append(f"• No significant bone abnormalities detected")
            comments.append(f"• Routine clinical follow-up as appropriate")
        
        comments.append(f"")
        comments.append(f"Note: BSI quantification is based on classification of hotspot")
        comments.append(f"regions as normal or abnormal using machine learning analysis.")
        
        self.comments_text.setPlainText("\n".join(comments))
    
    def _update_button_states(self, has_data: bool):
        """Update button enabled states"""
        self.export_chart_btn.setEnabled(has_data)
        self.export_report_btn.setEnabled(has_data)
        
        # Run analysis button: enabled if we have a patient but no quantification
        has_patient = bool(self.current_patient_id)
        self.run_analysis_btn.setEnabled(has_patient and not has_data)
    
    # ===== Backward Compatibility =====
    def set_image_mode(self, mode: str):
        """Backward compatibility - BSI panel doesn't use image modes"""
        pass
    
    def set_patient_meta(self, meta: dict):
        """Backward compatibility for old patient meta format"""
        if not meta:
            self.clear_patient_data()
            return
        
        patient_id = meta.get("patient_id", "Unknown")
        study_date = meta.get("study_date", "Unknown")
        
        # Try to find patient folder (this would need to be set from parent)
        if hasattr(self, '_current_session_code'):
            from core.config.paths import get_patient_spect_path
            patient_folder = get_patient_spect_path(patient_id, self._current_session_code)
            if patient_folder.exists():
                self.load_patient_data(patient_folder, patient_id, study_date)
    
    def set_session_code(self, session_code: str):
        """Set session code for path resolution"""
        self._current_session_code = session_code