# features/spect_viewer/gui/bsi_canvas.py
"""
BSI Canvas widget for displaying quantification results
Uses matplotlib to show BSI charts and segment breakdown
"""
from pathlib import Path
from typing import Dict, Optional, Any
import json
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, Signal

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# Import quantification integration
from features.spect_viewer.logic.quantification_integration import QuantificationManager

# Import UI constants
from core.gui.ui_constants import (
    Colors, 
    INFO_LABEL_STYLE, 
    GROUP_BOX_STYLE,
    DIALOG_PANEL_HEADER_STYLE
)


class BSICanvas(FigureCanvas):
    """
    Matplotlib canvas for displaying BSI quantification results
    Shows segment breakdown chart and summary statistics
    """
    
    chart_clicked = Signal(str)  # Emit segment name when clicked
    
    def __init__(self, parent: QWidget = None):
        # Create figure with subplots
        self.figure = Figure(figsize=(8, 6), facecolor='white')
        super().__init__(self.figure)
        self.setParent(parent)
        
        # BSI data
        self.bsi_data = None
        self.summary_data = None
        
        # Setup canvas
        self.setMinimumSize(400, 300)
        
        # Initialize with empty chart
        self._plot_empty_chart()
        
    def load_bsi_data(self, patient_folder: Path, patient_id: str, study_date: str) -> bool:
        """
        Load BSI quantification data for patient
        
        Args:
            patient_folder: Patient directory path
            patient_id: Patient ID
            study_date: Study date
            
        Returns:
            True if data loaded successfully
        """
        try:
            manager = QuantificationManager()
            results = manager.load_quantification_results(patient_folder, patient_id, study_date)
            
            if not results:
                self._plot_no_data_chart()
                return False
            
            self.bsi_data = results.get('bsi_results', {})
            self.summary_data = manager.get_bsi_summary()
            
            # Plot the data
            self._plot_bsi_chart()
            return True
            
        except Exception as e:
            print(f"[BSI CANVAS] Error loading BSI data: {e}")
            self._plot_error_chart(str(e))
            return False
    
    def clear_data(self):
        """Clear BSI data and show empty chart"""
        self.bsi_data = None
        self.summary_data = None
        self._plot_empty_chart()
    
    def _plot_empty_chart(self):
        """Plot empty chart placeholder"""
        self.figure.clear()
        
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, 'No BSI Data Available\n\nSelect a patient with quantification results', 
                ha='center', va='center', fontsize=12, color=Colors.DARK_GRAY,
                transform=ax.transAxes, 
                bbox=dict(boxstyle="round,pad=0.3", facecolor=Colors.LIGHT_GRAY, alpha=0.8))
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        self.figure.suptitle('BSI Quantification Chart', fontsize=14, fontweight='bold', color=Colors.DARK_GRAY)
        self.figure.tight_layout()
        self.draw()
    
    def _plot_no_data_chart(self):
        """Plot chart when no quantification data exists"""
        self.figure.clear()
        
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, 'No Quantification Data\n\nRun classification and quantification\nfirst to see BSI results', 
                ha='center', va='center', fontsize=12, color=Colors.WARNING,
                transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.3", facecolor='#fff3cd', alpha=0.8))
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        self.figure.suptitle('BSI Quantification Chart', fontsize=14, fontweight='bold', color=Colors.DARK_GRAY)
        self.figure.tight_layout()
        self.draw()
    
    def _plot_error_chart(self, error_message: str):
        """Plot chart when error occurs"""
        self.figure.clear()
        
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, f'Error Loading BSI Data\n\n{error_message}', 
                ha='center', va='center', fontsize=11, color='#d32f2f',
                transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.3", facecolor='#ffebee', alpha=0.8))
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        self.figure.suptitle('BSI Quantification Chart', fontsize=14, fontweight='bold', color='#d32f2f')
        self.figure.tight_layout()
        self.draw()
    
    def _plot_bsi_chart(self):
        """Plot BSI chart with segment breakdown"""
        if not self.bsi_data or not self.summary_data:
            self._plot_empty_chart()
            return
        
        self.figure.clear()
        
        # Create subplots: main chart (top) and summary stats (bottom)
        gs = self.figure.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.3)
        
        # Main chart: Segment breakdown
        ax_main = self.figure.add_subplot(gs[0])
        self._plot_segment_breakdown(ax_main)
        
        # Summary stats
        ax_summary = self.figure.add_subplot(gs[1])
        self._plot_summary_stats(ax_summary)
        
        # Overall title
        bsi_score = self.summary_data.get('bsi_score', 0)
        patient_id = self.summary_data.get('patient_id', 'Unknown')
        
        self.figure.suptitle(f'BSI Analysis: {patient_id} (BSI Score: {bsi_score:.2f}%)', 
                           fontsize=14, fontweight='bold', color=Colors.DARK_GRAY)
        
        self.figure.tight_layout()
        self.draw()
    
    def _plot_segment_breakdown(self, ax):
        """Plot segment breakdown bar chart"""
        # Prepare data - filter out background and segments with no pixels
        segments = []
        normal_percentages = []
        abnormal_percentages = []
        colors = []
        
        for segment_name, data in self.bsi_data.items():
            if segment_name == "background" or data['total_segment_pixels'] == 0:
                continue
                
            segments.append(segment_name.replace(' ', '\n'))  # Line break for long names
            normal_percentages.append(data['percentage_normal'] * 100)
            abnormal_percentages.append(data['percentage_abnormal'] * 100)
            
            # Color based on abnormal percentage
            abnormal_pct = data['percentage_abnormal'] * 100
            if abnormal_pct > 10:
                colors.append('#d32f2f')  # High abnormal - red
            elif abnormal_pct > 5:
                colors.append('#ff9800')  # Medium abnormal - orange
            elif abnormal_pct > 0:
                colors.append('#ffc107')  # Low abnormal - yellow
            else:
                colors.append('#4caf50')  # Normal - green
        
        if not segments:
            ax.text(0.5, 0.5, 'No segment data available', ha='center', va='center', 
                   transform=ax.transAxes, fontsize=12, color=Colors.DARK_GRAY)
            return
        
        # Create horizontal bar chart
        y_pos = np.arange(len(segments))
        
        # Plot bars
        bars_abnormal = ax.barh(y_pos, abnormal_percentages, color=colors, alpha=0.8, label='Abnormal')
        bars_normal = ax.barh(y_pos, normal_percentages, left=abnormal_percentages, 
                             color=Colors.SUCCESS, alpha=0.4, label='Normal')
        
        # Customize chart
        ax.set_yticks(y_pos)
        ax.set_yticklabels(segments, fontsize=9)
        ax.set_xlabel('Percentage (%)', fontsize=10, fontweight='bold')
        ax.set_title('Hotspot Distribution by Anatomical Segment', fontsize=12, fontweight='bold', pad=15)
        
        # Add value labels on bars
        for i, (abnormal_pct, normal_pct) in enumerate(zip(abnormal_percentages, normal_percentages)):
            if abnormal_pct > 1:  # Only show label if percentage is significant
                ax.text(abnormal_pct/2, i, f'{abnormal_pct:.1f}%', 
                       ha='center', va='center', fontweight='bold', fontsize=8, color='white')
            if normal_pct > 1:
                ax.text(abnormal_pct + normal_pct/2, i, f'{normal_pct:.1f}%', 
                       ha='center', va='center', fontweight='bold', fontsize=8, color='black')
        
        # Customize grid and spines
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # Legend
        ax.legend(loc='lower right', fontsize=9)
        
        # Set x-axis limit based on data
        max_total = max([a + n for a, n in zip(abnormal_percentages, normal_percentages)]) if abnormal_percentages else 10
        ax.set_xlim(0, max(max_total * 1.1, 5))
    
    def _plot_summary_stats(self, ax):
        """Plot summary statistics"""
        ax.axis('off')  # Hide axes for text display
        
        # Prepare summary text
        total_abnormal = self.summary_data.get('total_abnormal_hotspots', 0)
        total_normal = self.summary_data.get('total_normal_hotspots', 0)
        segments_abnormal = self.summary_data.get('segments_with_abnormal', 0)
        segments_analyzed = self.summary_data.get('segments_analyzed', 0)
        bsi_score = self.summary_data.get('bsi_score', 0)
        
        # Create summary text with formatting
        summary_text = f"""Summary Statistics:
        
BSI Score: {bsi_score:.2f}%    •    Total Abnormal Hotspots: {total_abnormal}    •    Total Normal Hotspots: {total_normal}
        
Segments with Abnormal Hotspots: {segments_abnormal}/{segments_analyzed}    •    Overall Abnormal Rate: {self.summary_data.get('overall_abnormal_percentage', 0)*100:.2f}%"""
        
        # Display summary text
        ax.text(0.5, 0.5, summary_text, ha='center', va='center', 
               transform=ax.transAxes, fontsize=10, 
               bbox=dict(boxstyle="round,pad=0.5", facecolor=Colors.LIGHT_GRAY, alpha=0.8))
    
    def get_summary_data(self) -> Optional[Dict[str, Any]]:
        """Get current summary data"""
        return self.summary_data
    
    def get_bsi_score(self) -> float:
        """Get current BSI score"""
        if self.summary_data:
            return self.summary_data.get('bsi_score', 0.0)
        return 0.0
    
    def export_chart(self, file_path: Path, dpi: int = 300):
        """Export chart to file"""
        try:
            self.figure.savefig(str(file_path), dpi=dpi, bbox_inches='tight', 
                              facecolor='white', edgecolor='none')
            print(f"[BSI CANVAS] Chart exported to: {file_path}")
            return True
        except Exception as e:
            print(f"[BSI CANVAS] Export failed: {e}")
            return False


class BSIInfoPanel(QWidget):
    """
    Information panel for BSI summary statistics
    Displays key metrics in a formatted layout
    """
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        
        self.summary_data = None
        self._build_ui()
    
    def _build_ui(self):
        """Build the info panel UI"""
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
        
        # Info labels
        self.bsi_score_label = QLabel("BSI Score: N/A")
        self.abnormal_hotspots_label = QLabel("Abnormal Hotspots: N/A")
        self.normal_hotspots_label = QLabel("Normal Hotspots: N/A")
        self.segments_affected_label = QLabel("Affected Segments: N/A")
        self.analysis_method_label = QLabel("Method: N/A")
        
        # Style labels
        labels = [
            self.bsi_score_label,
            self.abnormal_hotspots_label, 
            self.normal_hotspots_label,
            self.segments_affected_label,
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
        
        # Make BSI score more prominent
        self.bsi_score_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                padding: 6px;
                margin: 4px 0px;
                background: #f8f9fa;
                border-radius: 3px;
                border: 1px solid #e9ecef;
            }
        """)
        
        layout.addWidget(self.info_frame)
        
        # Initially show no data message
        self._show_no_data()
    
    def update_info(self, summary_data: Dict[str, Any]):
        """Update info panel with BSI summary data"""
        self.summary_data = summary_data
        
        if not summary_data:
            self._show_no_data()
            return
        
        # Update labels with data
        bsi_score = summary_data.get('bsi_score', 0)
        total_abnormal = summary_data.get('total_abnormal_hotspots', 0)
        total_normal = summary_data.get('total_normal_hotspots', 0)
        segments_abnormal = summary_data.get('segments_with_abnormal', 0)
        segments_total = summary_data.get('segments_analyzed', 0)
        
        # Format BSI score with color coding
        if bsi_score > 5:
            score_color = "#d32f2f"  # High BSI - red
        elif bsi_score > 2:
            score_color = "#ff9800"  # Medium BSI - orange
        else:
            score_color = "#4caf50"  # Low BSI - green
        
        self.bsi_score_label.setText(f"BSI Score: {bsi_score:.2f}%")
        self.bsi_score_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                color: {score_color};
                padding: 6px;
                margin: 4px 0px;
                background: #f8f9fa;
                border-radius: 3px;
                border: 1px solid #e9ecef;
            }}
        """)
        
        self.abnormal_hotspots_label.setText(f"Abnormal Hotspots: {total_abnormal}")
        self.normal_hotspots_label.setText(f"Normal Hotspots: {total_normal}")
        self.segments_affected_label.setText(f"Affected Segments: {segments_abnormal}/{segments_total}")
        self.analysis_method_label.setText("Method: Classification-based BSI")
        
        # Show info frame
        self.info_frame.setVisible(True)
    
    def _show_no_data(self):
        """Show no data message"""
        self.bsi_score_label.setText("BSI Score: N/A")
        self.bsi_score_label.setStyleSheet("""
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
        
        self.abnormal_hotspots_label.setText("Abnormal Hotspots: N/A")
        self.normal_hotspots_label.setText("Normal Hotspots: N/A")
        self.segments_affected_label.setText("Affected Segments: N/A")
        self.analysis_method_label.setText("Method: Select patient with quantification results")
        
        self.info_frame.setVisible(True)
    
    def clear_info(self):
        """Clear info panel"""
        self.summary_data = None
        self._show_no_data()
    
    def get_bsi_score(self) -> float:
        """Get current BSI score"""
        if self.summary_data:
            return self.summary_data.get('bsi_score', 0.0)
        return 0.0