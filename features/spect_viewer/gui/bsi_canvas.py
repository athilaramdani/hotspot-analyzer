# features/spect_viewer/gui/bsi_canvas.py - FIXED for Single View Support

from pathlib import Path
from typing import Dict, Optional, Any
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from core.gui.ui_constants import (
    DIALOG_PANEL_HEADER_STYLE
)
import json
from matplotlib.dates import DateFormatter
import numpy as np

from datetime import datetime
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# Import quantification integration
from features.spect_viewer.logic.quantification_integration import QuantificationManager

# Import UI constants
from core.gui.ui_constants import Colors

class BSICanvas(FigureCanvas):
    """
    ✅ FIXED: V1.2 BSI Canvas with 3-line chart - SUPPORTS SINGLE VIEW
    """
    
    chart_clicked = Signal(str)
    
    def __init__(self, parent: QWidget = None):
        self.figure = Figure(figsize=(8, 6), facecolor='white')
        super().__init__(self.figure)
        self.setParent(parent)
        
        self.patient_folder = None
        self.patient_id = None
        
        # Line visibility controls (default all visible)
        self.anterior_visible = True
        self.posterior_visible = True
        # ✅ REMOVED: combined_visible - simplify to per-frame only
        
        self.setMinimumSize(400, 300)
        self._plot_empty_chart()
        
    def load_bsi_data(self, patient_folder: Path, patient_id: str, study_date: str) -> bool:
        """✅ FIXED: Load V1.2 BSI data and display 3-line trend chart with single view support"""
        # ✅ FIXED: Ensure we use patient base folder for trend analysis
        if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
            # Current folder is study_date folder, go up to patient folder for trend
            self.patient_folder = patient_folder.parent
            print(f"[BSI CANVAS] Using patient base folder for trend: {self.patient_folder}")
        else:
            # Current folder is already patient folder
            self.patient_folder = patient_folder
            print(f"[BSI CANVAS] Using patient folder for trend: {self.patient_folder}")
        
        self.patient_id = patient_id
        
        try:
            self._plot_bsi_trend_chart_v2()
            return True
            
        except Exception as e:
            print(f"[BSI CANVAS V1.0 SINGLE] Error loading BSI data: {e}")
            self._plot_error_chart(str(e))
            return False
    
    def clear_data(self):
        """Clear BSI data and show empty chart"""
        self.patient_folder = None
        self.patient_id = None
        self._plot_empty_chart()
    
    def _plot_empty_chart(self):
        """Show placeholder when no data available"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, 'No BSI Data Available\n\nSelect a patient to view BSI trend\n(Anterior, Posterior, Combined)', 
                ha='center', va='center', fontsize=12, color=Colors.DARK_GRAY,
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.figure.suptitle('BSI Quantification Trend', fontsize=14, fontweight='bold', color=Colors.DARK_GRAY)
        self.figure.tight_layout()
        self.draw()

    def _plot_error_chart(self, error_message: str):
        """Show error chart"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, f'Error Loading BSI Data\n\n{error_message}', 
                ha='center', va='center', fontsize=11, color='#d32f2f',
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.figure.suptitle('BSI Quantification Trend', fontsize=14, fontweight='bold', color='#d32f2f')
        self.figure.tight_layout()
        self.draw()
    
    def _plot_bsi_trend_chart_v2(self):
        """✅ FIXED: Plot 3-line chart for BSI with single view support and better date handling"""
        if not self.patient_folder or not self.patient_id:
            self._plot_empty_chart()
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        try:
            manager = QuantificationManager()
            all_scores = manager.load_all_quantification_scores(self.patient_folder, self.patient_id)

            if not all_scores:
                ax.text(0.5, 0.5, 'No BSI scores found for this patient', ha='center', va='center',
                        transform=ax.transAxes, fontsize=12, color='gray')
                self.figure.suptitle(f'BSI Trend for {self.patient_id}', fontsize=14, fontweight='bold')
                self.figure.tight_layout()
                self.draw()
                return

            all_scores = sorted(all_scores, key=lambda x: x["study_date"])
            
            # Prepare data for 3 lines with single view support
            dates = []
            anterior_scores = []
            posterior_scores = []
            combined_scores = []
            date_labels = []
            
            for entry in all_scores:
                try:
                    date_str = entry["study_date"]
                    processing_mode = entry.get('processing_mode', 'unknown')
                    
                    print(f"[DEBUG BSI CANVAS] Processing date: {date_str}, mode: {processing_mode}")
                    
                    # ✅ FIX: Better date validation and parsing
                    try:
                        # Try to parse as YYYYMMDD format
                        if len(date_str) == 8 and date_str.isdigit():
                            date_obj = datetime.strptime(date_str, "%Y%m%d")
                            formatted_date = date_obj.strftime("%d %b %Y")
                        else:
                            print(f"[WARN] Invalid date format in BSI data: {date_str}, using current date")
                            # ✅ FIX: Use current date as fallback instead of skipping
                            date_obj = datetime.now()
                            formatted_date = f"{date_str} (Invalid)"
                            
                    except ValueError as ve:
                        print(f"[WARN] Date parsing failed for {date_str}: {ve}, using current date")
                        date_obj = datetime.now()
                        formatted_date = f"{date_str} (Invalid)"
                    
                    dates.append(date_obj)
                    
                    # Handle single view data properly
                    ant_bsi = entry.get("anterior_bsi", 0) if processing_mode != 'single_view_posterior' else None
                    post_bsi = entry.get("posterior_bsi", 0) if processing_mode != 'single_view_anterior' else None
                    combined_bsi = entry.get("combined_bsi", 0)
                    
                    anterior_scores.append(ant_bsi)
                    posterior_scores.append(post_bsi)
                    combined_scores.append(combined_bsi)
                    date_labels.append(formatted_date)
                    
                    print(f"[DEBUG BSI CANVAS] Added: Ant={ant_bsi} Post={post_bsi}")
                    
                except Exception as e:
                    print(f"[WARN] Error processing BSI entry: {e}")
                    continue

            if not dates:
                ax.text(0.5, 0.5, 'No valid dates found in BSI data', ha='center', va='center',
                        transform=ax.transAxes, fontsize=12, color='red')
                self.figure.suptitle(f'BSI Trend for {self.patient_id}', fontsize=14, fontweight='bold')
                self.figure.tight_layout()
                self.draw()
                return

            # Plot lines with single view support (existing code continues...)
            
            # Plot anterior line (only where data is available)
            if self.anterior_visible:
                ant_dates = [d for i, d in enumerate(dates) if anterior_scores[i] is not None]
                ant_values = [v for v in anterior_scores if v is not None]
                if ant_dates and ant_values:
                    ax.plot(ant_dates, ant_values, marker='o', linestyle='-', color='#ff6b6b', 
                        linewidth=2, markersize=6, label='Anterior BSI')
            
            # Plot posterior line (only where data is available)
            if self.posterior_visible:
                post_dates = [d for i, d in enumerate(dates) if posterior_scores[i] is not None]
                post_values = [v for v in posterior_scores if v is not None]
                if post_dates and post_values:
                    ax.plot(post_dates, post_values, marker='^', linestyle='-', color='#4ecdc4', 
                        linewidth=2, markersize=6, label='Posterior BSI')

            # Only show legend if at least one line is visible
            if self.anterior_visible or self.posterior_visible:
                legend = ax.legend(loc='upper left', fontsize=9)

            # Set axis and formatting
            ax.set_xticks(dates)
            ax.set_xticklabels(date_labels, rotation=45, ha='right')

            ax.set_title("BSI Score Trend", fontsize=12, fontweight='bold')
            ax.set_xlabel("Study Date", fontsize=10)
            ax.set_ylabel("BSI Score", fontsize=10)
            ax.grid(True, linestyle='--', alpha=0.6)
            
            self.figure.suptitle(f'BSI Analysis for Patient: {self.patient_id}', fontsize=14, fontweight='bold')

        except Exception as e:
            print(f"[BSI CANVAS] Failed to plot BSI trend: {e}")
            import traceback
            traceback.print_exc()
            self._plot_error_chart(str(e))
            return

        self.figure.tight_layout()
        self.draw()
    
    def set_line_visibility(self, anterior_visible: bool, posterior_visible: bool):
        """Control visibility of BSI lines"""
        self.anterior_visible = anterior_visible
        self.posterior_visible = posterior_visible
        # ✅ REMOVED: combined_visible parameter - simplify interface
        # Redraw chart with new visibility settings
        self._plot_bsi_trend_chart_v2()
    
    def export_chart(self, file_path: Path, dpi: int = 300) -> bool:
        """Export chart to image file"""
        try:
            self.figure.savefig(str(file_path), dpi=dpi, bbox_inches='tight', facecolor='white')
            print(f"[BSI CANVAS V1.2 SINGLE] Chart exported to: {file_path}")
            return True
        except Exception as e:
            print(f"[BSI CANVAS V1.2 SINGLE] Export failed: {e}")
            return False

class BSIInfoPanel(QWidget):
    """
    ✅ FIXED: Info panel for V1.2 BSI summary with single view support
    """
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        
        self.summary_data = None
        self._build_ui()
    
    def _build_ui(self):
        """Build the V1.2 info panel UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Title
        title_label = QLabel("<b>BSI Summary</b>")
        title_label.setStyleSheet(DIALOG_PANEL_HEADER_STYLE)
        layout.addWidget(title_label)
        
        # Create info display frame
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        self.info_layout = QVBoxLayout(self.info_frame)
        self.info_layout.setContentsMargins(8, 8, 8, 8)
        
        # ✅ V1.2 Info labels (3 BSI scores + processing mode)
        self.combined_bsi_label = QLabel("Combined BSI: N/A")
        self.anterior_bsi_label = QLabel("Anterior BSI: N/A")
        self.posterior_bsi_label = QLabel("Posterior BSI: N/A")
        self.processing_mode_label = QLabel("Mode: Unknown")
        self.abnormal_hotspots_label = QLabel("Total Abnormal: N/A")
        self.normal_hotspots_label = QLabel("Total Normal: N/A")
        self.analysis_method_label = QLabel("Method: Color-based")
        
        # ✅ Make Combined BSI most prominent
        self.combined_bsi_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                padding: 6px;
                margin: 4px 0px;
                background: #f0f4ff;
                border-radius: 3px;
                border: 1px solid #4e73ff;
            }
        """)
        
        # Add Combined BSI at the top
        self.info_layout.addWidget(self.combined_bsi_label)
        
        # Style other labels
        labels = [
            self.anterior_bsi_label,
            self.posterior_bsi_label,
            self.processing_mode_label,
            self.abnormal_hotspots_label, 
            self.normal_hotspots_label,
            self.analysis_method_label
        ]
        
        for label in labels:
            label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #495057;
                    padding: 4px;
                    margin: 2px 0px;
                }
            """)
            label.setWordWrap(True)
            self.info_layout.addWidget(label)
        
        layout.addWidget(self.info_frame)
        
        # Initially show no data message
        self._show_no_data()
    
    def update_info(self, summary_data: Dict[str, Any]):
        """✅ FIXED: Update info panel with V1.2 BSI summary data including single view support"""
        self.summary_data = summary_data
        
        if not summary_data:
            self._show_no_data()
            return
        
        # ✅ Extract V1.2 data with single view support
        anterior_bsi = summary_data.get('anterior_bsi', 0)
        posterior_bsi = summary_data.get('posterior_bsi', 0)
        combined_bsi = summary_data.get('combined_bsi', 0)
        processing_mode = summary_data.get('processing_mode', 'unknown')
        total_abnormal = summary_data.get('total_abnormal_hotspots', 0)
        total_normal = summary_data.get('total_normal_hotspots', 0)
        
        # ✅ Update labels with V1.2 data and processing mode awareness
        self.combined_bsi_label.setText(f"Combined BSI: {combined_bsi:.2f}%")
        
        if processing_mode == 'dual_view':
            self.anterior_bsi_label.setText(f"Anterior BSI: {anterior_bsi:.2f}%")
            self.posterior_bsi_label.setText(f"Posterior BSI: {posterior_bsi:.2f}%")
            self.processing_mode_label.setText("Mode: Dual View")
        elif processing_mode == 'single_view_anterior':
            self.anterior_bsi_label.setText(f"Anterior BSI: {anterior_bsi:.2f}%")
            self.posterior_bsi_label.setText("Posterior BSI: N/A")
            self.processing_mode_label.setText("Mode: Anterior Only")
        elif processing_mode == 'single_view_posterior':
            self.anterior_bsi_label.setText("Anterior BSI: N/A")
            self.posterior_bsi_label.setText(f"Posterior BSI: {posterior_bsi:.2f}%")
            self.processing_mode_label.setText("Mode: Posterior Only")
        else:
            self.anterior_bsi_label.setText(f"Anterior BSI: {anterior_bsi:.2f}%")
            self.posterior_bsi_label.setText(f"Posterior BSI: {posterior_bsi:.2f}%")
            self.processing_mode_label.setText(f"Mode: {processing_mode}")
        
        # ✅ Color-code combined BSI
        if combined_bsi > 5:
            score_color = "#d32f2f"  # High BSI - red
        elif combined_bsi > 2:
            score_color = "#ff9800"  # Medium BSI - orange
        else:
            score_color = "#4caf50"  # Low BSI - green
        
        self.combined_bsi_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                color: {score_color};
                padding: 6px;
                margin: 4px 0px;
                background: #f0f4ff;
                border-radius: 3px;
                border: 1px solid {score_color};
            }}
        """)
        
        # ✅ Color-code processing mode label
        if processing_mode == 'dual_view':
            mode_color = "#4caf50"  # Green for dual view
        elif processing_mode in ['single_view_anterior', 'single_view_posterior']:
            mode_color = "#ff9800"  # Orange for single view
        else:
            mode_color = "#6c757d"  # Gray for unknown
        
        self.processing_mode_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                font-weight: bold;
                color: {mode_color};
                padding: 4px;
                margin: 2px 0px;
            }}
        """)
        
        self.abnormal_hotspots_label.setText(f"Total Abnormal: {total_abnormal}")
        self.normal_hotspots_label.setText(f"Total Normal: {total_normal}")
        
        # Update method label with processing mode info
        if processing_mode == 'dual_view':
            self.analysis_method_label.setText("Method: Color-based (Ant+Post)")
        elif processing_mode == 'single_view_anterior':
            self.analysis_method_label.setText("Method: Color-based (Ant only)")
        elif processing_mode == 'single_view_posterior':
            self.analysis_method_label.setText("Method: Color-based (Post only)")
        else:
            self.analysis_method_label.setText("Method: Color-based")
        
        # Show info frame
        self.info_frame.setVisible(True)
    
    def _show_no_data(self):
        """Show no data message for V1.2"""
        self.anterior_bsi_label.setText("Anterior BSI: N/A")
        self.posterior_bsi_label.setText("Posterior BSI: N/A")
        self.combined_bsi_label.setText("Combined BSI: N/A")
        self.processing_mode_label.setText("Mode: N/A")
        
        self.combined_bsi_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #6c757d;
                padding: 6px;
                margin: 4px 0px;
                background: #f8f9fa;
                border-radius: 3px;
                border: 1px solid #e9ecef;
            }
        """)
        
        self.processing_mode_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #6c757d;
                padding: 4px;
                margin: 2px 0px;
            }
        """)
        
        self.abnormal_hotspots_label.setText("Total Abnormal: N/A")
        self.normal_hotspots_label.setText("Total Normal: N/A")
        self.analysis_method_label.setText("Method: Select patient with quantification")
        
        self.info_frame.setVisible(True)
    
    def clear_info(self):
        """Clear info panel"""
        self.summary_data = None
        self._show_no_data()
    
    def get_combined_bsi_score(self) -> float:
        """Get current combined BSI score"""
        if self.summary_data:
            return self.summary_data.get('combined_bsi', 0.0)
        return 0.0