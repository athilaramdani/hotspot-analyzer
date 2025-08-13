# features/spect_viewer/gui/bsi_canvas.py - UPDATED for V1.2 with 3-line chart

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
    ✅ UPDATED: V1.2 BSI Canvas with 3-line chart (Anterior, Posterior, Combined)
    """
    
    chart_clicked = Signal(str)
    
    def __init__(self, parent: QWidget = None):
        self.figure = Figure(figsize=(8, 6), facecolor='white')
        super().__init__(self.figure)
        self.setParent(parent)
        
        self.patient_folder = None
        self.patient_id = None
        
        # ✅ NEW: Line visibility controls (default all visible)
        self.anterior_visible = True
        self.posterior_visible = True
        self.combined_visible = True
        
        self.setMinimumSize(400, 300)
        self._plot_empty_chart()
        
    def load_bsi_data(self, patient_folder: Path, patient_id: str, study_date: str) -> bool:
        """Load V1.2 BSI data and display 3-line trend chart"""
        self.patient_folder = patient_folder
        self.patient_id = patient_id
        
        try:
            self._plot_bsi_trend_chart_v2()
            return True
            
        except Exception as e:
            print(f"[BSI CANVAS V1.2] Error loading BSI data: {e}")
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
        self.figure.suptitle('BSI Quantification Trend (V1.2)', fontsize=14, fontweight='bold', color=Colors.DARK_GRAY)
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
        self.figure.suptitle('BSI Quantification Trend (V1.2)', fontsize=14, fontweight='bold', color='#d32f2f')
        self.figure.tight_layout()
        self.draw()
    
    def _plot_bsi_trend_chart_v2(self):
        """✅ NEW: Plot 3-line chart for V1.2 BSI (Anterior, Posterior, Combined)"""
        if not self.patient_folder or not self.patient_id:
            self._plot_empty_chart()
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        try:
            manager = QuantificationManager()
            all_scores = manager.load_all_quantification_scores(self.patient_folder, self.patient_id)

            if not all_scores:
                ax.text(0.5, 0.5, 'No V1.2 BSI scores found for this patient', ha='center', va='center',
                        transform=ax.transAxes, fontsize=12, color='gray')
                self.figure.suptitle(f'BSI Trend for {self.patient_id} (V1.2)', fontsize=14, fontweight='bold')
                self.figure.tight_layout()
                self.draw()
                return

            all_scores = sorted(all_scores, key=lambda x: x["study_date"])
            
            # ✅ Prepare data for 3 lines
            dates = []
            anterior_scores = []
            posterior_scores = []
            combined_scores = []
            date_labels = []
            
            for entry in all_scores:
                try:
                    date_str = entry["study_date"]
                    print(f"[DEBUG BSI V1.2] Processing date: {date_str}")
                    
                    date_obj = datetime.strptime(date_str, "%Y%m%d")
                    formatted_date = date_obj.strftime("%d %b %Y")
                    
                    dates.append(date_obj)
                    anterior_scores.append(entry.get("anterior_bsi", 0))
                    posterior_scores.append(entry.get("posterior_bsi", 0))
                    combined_scores.append(entry.get("combined_bsi", 0))
                    date_labels.append(formatted_date)
                    
                    print(f"[DEBUG BSI V1.2] Added: Ant={entry.get('anterior_bsi', 0):.1f}% Post={entry.get('posterior_bsi', 0):.1f}% Combined={entry.get('combined_bsi', 0):.1f}%")
                    
                except ValueError as e:
                    print(f"[WARN] Invalid date format in V1.2 BSI data: {entry['study_date']}, skipping...")
                    continue

            if not dates:
                ax.text(0.5, 0.5, 'No valid dates found in V1.2 BSI data', ha='center', va='center',
                        transform=ax.transAxes, fontsize=12, color='red')
                self.figure.suptitle(f'BSI Trend for {self.patient_id} (V1.2)', fontsize=14, fontweight='bold')
                self.figure.tight_layout()
                self.draw()
                return

            # ✅ Plot 3 lines as requested by team
            if self.anterior_visible:
                ax.plot(dates, anterior_scores, marker='o', linestyle='-', color='#ff6b6b', linewidth=2, markersize=6, label='Anterior BSI')
            if self.posterior_visible:
                ax.plot(dates, posterior_scores, marker='^', linestyle='-', color='#4ecdc4', linewidth=2, markersize=6, label='Posterior BSI')
            if self.combined_visible:
                ax.plot(dates, combined_scores, marker='s', linestyle='-', color='#007bff', linewidth=2, markersize=6, label='Combined BSI')

            # ✅ Only show legend if at least one line is visible
            if self.anterior_visible or self.posterior_visible or self.combined_visible:
                ax.legend(loc='upper left', fontsize=9)

            # ✅ Set axis and formatting
            ax.set_xticks(dates)
            ax.set_xticklabels(date_labels, rotation=45, ha='right')

            ax.set_title(f"BSI Score Trend (V1.2 - Separate Views)", fontsize=12, fontweight='bold')
            ax.set_xlabel("Study Date", fontsize=10)
            ax.set_ylabel("BSI Score", fontsize=10)
            ax.grid(True, linestyle='--', alpha=0.6)
            
            # ✅ Add legend for 3 lines
            ax.legend(loc='upper left', fontsize=9)
            
            self.figure.suptitle(f'BSI Analysis for Patient: {self.patient_id} (V1.2)', fontsize=14, fontweight='bold')

        except Exception as e:
            print(f"[BSI CANVAS V1.2] Failed to plot BSI trend: {e}")
            self._plot_error_chart(str(e))
            return

        self.figure.tight_layout()
        self.draw()
    
    
    
    def set_line_visibility(self, anterior_visible: bool, posterior_visible: bool, combined_visible: bool):
        """✅ NEW: Control visibility of BSI lines"""
        self.anterior_visible = anterior_visible
        self.posterior_visible = posterior_visible
        self.combined_visible = combined_visible
        # Redraw chart with new visibility settings
        self._plot_bsi_trend_chart_v2()
    
    def export_chart(self, file_path: Path, dpi: int = 300) -> bool:
        """Export chart to image file"""
        try:
            self.figure.savefig(str(file_path), dpi=dpi, bbox_inches='tight', facecolor='white')
            print(f"[BSI CANVAS V1.2] Chart exported to: {file_path}")
            return True
        except Exception as e:
            print(f"[BSI CANVAS V1.2] Export failed: {e}")
            return False

class BSIInfoPanel(QWidget):
    """
    ✅ UPDATED: Info panel for V1.2 BSI summary (shows anterior/posterior/combined)
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
        title_label = QLabel("<b>BSI Summary (V1.2)</b>")
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
        
        # ✅ V1.2 Info labels (3 BSI scores)
        self.anterior_bsi_label = QLabel("Anterior BSI: N/A")
        self.posterior_bsi_label = QLabel("Posterior BSI: N/A")
        self.combined_bsi_label = QLabel("Combined BSI: N/A")
        self.abnormal_hotspots_label = QLabel("Total Abnormal: N/A")
        self.normal_hotspots_label = QLabel("Total Normal: N/A")
        self.analysis_method_label = QLabel("Method: V1.2 Color-based")
        
        # Style labels
        labels = [
            self.anterior_bsi_label,
            self.posterior_bsi_label,
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
        
        # Insert Combined BSI at the top
        self.info_layout.removeWidget(self.combined_bsi_label)
        self.info_layout.insertWidget(0, self.combined_bsi_label)
        
        layout.addWidget(self.info_frame)
        
        # Initially show no data message
        self._show_no_data()
    
    def update_info(self, summary_data: Dict[str, Any]):
        """✅ UPDATED: Update info panel with V1.2 BSI summary data"""
        self.summary_data = summary_data
        
        if not summary_data:
            self._show_no_data()
            return
        
        # ✅ Extract V1.2 data
        anterior_bsi = summary_data.get('anterior_bsi', 0)
        posterior_bsi = summary_data.get('posterior_bsi', 0)
        combined_bsi = summary_data.get('combined_bsi', 0)
        total_abnormal = summary_data.get('total_abnormal_hotspots', 0)
        total_normal = summary_data.get('total_normal_hotspots', 0)
        
        # ✅ Update labels with V1.2 data
        self.anterior_bsi_label.setText(f"Anterior BSI: {anterior_bsi:.2f}%")
        self.posterior_bsi_label.setText(f"Posterior BSI: {posterior_bsi:.2f}%")
        self.combined_bsi_label.setText(f"Combined BSI: {combined_bsi:.2f}%")
        
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
        
        self.abnormal_hotspots_label.setText(f"Total Abnormal: {total_abnormal}")
        self.normal_hotspots_label.setText(f"Total Normal: {total_normal}")
        self.analysis_method_label.setText("Method: V1.2 Color-based (Ant+Post)")
        
        # Show info frame
        self.info_frame.setVisible(True)
    
    def _show_no_data(self):
        """Show no data message for V1.2"""
        self.anterior_bsi_label.setText("Anterior BSI: N/A")
        self.posterior_bsi_label.setText("Posterior BSI: N/A")
        self.combined_bsi_label.setText("Combined BSI: N/A")
        
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
        
        self.abnormal_hotspots_label.setText("Total Abnormal: N/A")
        self.normal_hotspots_label.setText("Total Normal: N/A")
        self.analysis_method_label.setText("Method: Select patient with V1.2 quantification")
        
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