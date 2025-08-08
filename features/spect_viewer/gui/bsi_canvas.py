# HAPUS SELURUH KELAS BSICanvas LAMA ANDA DI bsi_canvas.py
# LALU GANTI DENGAN KODE LENGKAP DI BAWAH INI

from pathlib import Path
from typing import Dict, Optional, Any
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from core.gui.ui_constants import (
    DIALOG_PANEL_HEADER_STYLE
)
import json
from matplotlib.dates import DateFormatter
import numpy as np

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
    Matplotlib canvas untuk menampilkan hasil kuantifikasi BSI.
    Menampilkan grafik tren BSI (diagram garis) dari waktu ke waktu.
    """
    
    chart_clicked = Signal(str)  # Emit segment name when clicked (jika diperlukan nanti)
    
    def __init__(self, parent: QWidget = None):
        # Membuat figure dengan warna latar putih
        self.figure = Figure(figsize=(8, 6), facecolor='white')
        super().__init__(self.figure)
        self.setParent(parent)
        
        # Inisialisasi data
        self.patient_folder = None
        self.patient_id = None
        
        # Setup canvas
        self.setMinimumSize(400, 300)
        
        # Tampilkan chart kosong saat pertama kali dibuka
        self._plot_empty_chart()
        
    def load_bsi_data(self, patient_folder: Path, patient_id: str, study_date: str) -> bool:
        """
        Memuat data tren BSI untuk pasien dan menampilkannya sebagai diagram garis.
        Argumen 'study_date' diabaikan karena chart ini menampilkan semua studi.
        
        Returns:
            True jika data untuk tren berhasil dimuat dan ditampilkan.
        """
        self.patient_folder = patient_folder
        self.patient_id = patient_id
        
        try:
            # Panggil fungsi untuk menggambar chart tren BSI
            self._plot_bsi_trend_chart()
            return True
            
        except Exception as e:
            print(f"[BSI CANVAS] Error saat memuat data BSI: {e}")
            self._plot_error_chart(str(e))
            return False
    
    def clear_data(self):
        """Membersihkan data BSI dan menampilkan chart kosong."""
        self.patient_folder = None
        self.patient_id = None
        self._plot_empty_chart()
    
    def _plot_empty_chart(self):
        """Menampilkan placeholder saat tidak ada data."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, 'No BSI Data Available\n\nSelect a patient to view BSI trend', 
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
        """Menampilkan chart jika terjadi error."""
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
    
    # INI ADALAH SATU-SATUNYA FUNGSI UNTUK MENGGAMBAR CHART
    def _plot_bsi_trend_chart(self):
        """Menggambar diagram garis (line chart) untuk tren BSI dari waktu ke waktu."""
        if not self.patient_folder or not self.patient_id:
            self._plot_empty_chart()
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        try:
            manager = QuantificationManager()
            all_scores = manager.load_all_quantification_scores(self.patient_folder, self.patient_id)

            if not all_scores:
                ax.text(0.5, 0.5, 'No historical BSI scores found for this patient', ha='center', va='center',
                        transform=ax.transAxes, fontsize=12, color='gray')
                self.figure.suptitle(f'BSI Trend for {self.patient_id}', fontsize=14, fontweight='bold')
                self.figure.tight_layout()
                self.draw()
                return

            all_scores = sorted(all_scores, key=lambda x: x["study_date"])
            dates = [entry["study_date"] for entry in all_scores]
            scores = [entry["bsi_score"] for entry in all_scores]

            ax.plot(dates, scores, marker='o', linestyle='-', color='#007bff', linewidth=2, markersize=6)

            ax.set_title(f"BSI Score Trend", fontsize=12, fontweight='bold')
            ax.set_xlabel("Study Date", fontsize=10)
            ax.set_ylabel("BSI Score (%)", fontsize=10)
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.tick_params(axis='x', rotation=45)
            ax.xaxis.set_major_formatter(DateFormatter('%d-%b-%Y'))
            self.figure.suptitle(f'BSI Analysis for Patient: {self.patient_id}', fontsize=14, fontweight='bold')

        except Exception as e:
            print(f"[BSI CANVAS] Failed to plot BSI trend: {e}")
            self._plot_error_chart(str(e))
            return

        self.figure.tight_layout()
        self.draw()

    def export_chart(self, file_path: Path, dpi: int = 300) -> bool:
        """Mengekspor chart ke file gambar."""
        try:
            self.figure.savefig(str(file_path), dpi=dpi, bbox_inches='tight', facecolor='white')
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
    
    def _create_scan_selection_section(self) -> QWidget:
        """Membuat widget container untuk tombol pilihan scan."""
        section_widget = QFrame()
        section_widget.setObjectName("scanSelectorFrame")
        section_widget.setStyleSheet("""
            #scanSelectorFrame {
                padding: 8px;
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        
        # Layout ini akan kita isi dengan tombol secara dinamis nanti
        self.scan_buttons_layout = QHBoxLayout(section_widget)
        self.scan_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.scan_buttons_layout.setSpacing(8)
        self.scan_buttons_layout.addStretch() # Agar tombol rata kiri
        
        return section_widget
    
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