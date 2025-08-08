from pathlib import Path
from typing import Dict, Any,List
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea,
    QTableWidget, QTableWidgetItem, QAbstractItemView
)
from PySide6.QtGui import QColor

from .bsi_canvas import BSICanvas
from features.spect_viewer.logic.quantification_integration import QuantificationManager
from core.gui.ui_constants import PRIMARY_BUTTON_STYLE

# Definisikan style tombol di sini agar mudah diakses
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
    export_requested = Signal(str)
    analysis_requested = Signal()
    scan_selected = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.current_patient_folder = None
        self.current_patient_id = None
        self.current_study_date = None
        self.scan_buttons = []
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
        content_layout.addWidget(self._create_scan_selection_section())
        content_layout.addWidget(self._create_results_table())
        content_layout.addWidget(self._create_controls_section())
        content_layout.addStretch()
        main_panel_layout.addWidget(scroll_area)

    def _create_title_section(self, layout):
        title_frame = QFrame()
        title_frame.setStyleSheet("background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 8px;")
        title_layout = QVBoxLayout(title_frame)
        self.title_label = QLabel("<b>BSI Quantification Analysis</b>")
        self.title_label.setStyleSheet("font-size: 14px; color: #2c3e50; font-weight: bold; margin-bottom: 4px;")
        title_layout.addWidget(self.title_label)
        self.patient_info_label = QLabel("Select a patient to view BSI analysis")
        self.patient_info_label.setStyleSheet("font-size: 11px; color: #6c757d; font-style: italic;")
        title_layout.addWidget(self.patient_info_label)
        layout.addWidget(title_frame)

    def _create_scan_selection_section(self) -> QWidget:
        section_widget = QFrame()
        section_widget.setStyleSheet("padding: 8px 0px;")
        self.scan_buttons_layout = QHBoxLayout(section_widget)
        self.scan_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.scan_buttons_layout.setSpacing(8)
        label = QLabel("<b>Select Scan:</b>")
        self.scan_buttons_layout.addWidget(label)
        self.scan_buttons_layout.addStretch()
        return section_widget

    def _create_results_table(self) -> QWidget:
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Region", "Total Pixels", "Normal Pixels", "Normal (%)", "Abnormal Pixels", "Abnormal (%)"
        ])
        self.results_table.setMinimumHeight(450)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_table.horizontalHeader().setStretchLastSection(False)
        self.results_table.setColumnWidth(0, 140)
        self.results_table.setColumnWidth(1, 80)
        self.results_table.setColumnWidth(2, 90)
        self.results_table.setColumnWidth(3, 80)
        self.results_table.setColumnWidth(4, 100)
        self.results_table.setColumnWidth(5, 90)
        return self.results_table

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
        buttons_layout.addStretch()
        controls_layout.addLayout(buttons_layout)
        return controls_frame

    def load_patient_data(self, patient_folder: Path, patient_id: str, study_date: str) -> bool:
        try:
            self.current_patient_folder = patient_folder
            self.current_patient_id = patient_id
            self.bsi_canvas.load_bsi_data(patient_folder, patient_id, study_date)
            all_scans = self.quant_manager.load_all_quantification_scores(patient_folder, patient_id)
            if all_scans:
                all_scans = sorted(all_scans, key=lambda x: x["study_date"])
                self._populate_scan_buttons(all_scans)
                if self.scan_buttons:
                    self._on_scan_selected(self.scan_buttons[0], all_scans[0], emit_signal=False)
                self._update_button_states(True)
            else:
                self._populate_scan_buttons([])
                self.results_table.setRowCount(0)
                self._update_patient_info(patient_id, "No Scans Found")
                self._update_button_states(False)
            return True
        except Exception as e:
            print(f"[BSI SIDE PANEL] Error loading patient data: {e}")
            self.clear_patient_data()
            return False

    def _populate_scan_buttons(self, all_scans: list):
        for btn in self.scan_buttons:
            self.scan_buttons_layout.removeWidget(btn)
            btn.deleteLater()
        self.scan_buttons.clear()
        for i, scan_data in enumerate(all_scans):
            btn = QPushButton(f"Scan {i + 1}")
            btn.clicked.connect(lambda checked, b=btn, data=scan_data: self._on_scan_selected(b, data))
            self.scan_buttons_layout.insertWidget(self.scan_buttons_layout.count() - 1, btn)
            self.scan_buttons.append(btn)

    def _on_scan_selected(self, clicked_button: QPushButton, scan_data: dict, emit_signal: bool = True):
        for btn in self.scan_buttons:
            btn.setStyleSheet(INACTIVE_BUTTON_STYLE if btn is not clicked_button else ACTIVE_BUTTON_STYLE)
        
        study_date = scan_data.get("study_date")
        if not study_date: return
        
        self.current_study_date = study_date
        self._update_patient_info(self.current_patient_id, self.current_study_date)
        quant_results = self.quant_manager.load_quantification_results(
            self.current_patient_folder, self.current_patient_id, study_date
        )
        if quant_results:
            bsi_results_data = quant_results.get('bsi_results', {})
            self._populate_results_table(bsi_results_data)
        if emit_signal:
            self.scan_selected.emit(study_date)

    def _populate_results_table(self, bsi_results: dict):
        if not bsi_results:
            self.results_table.setRowCount(0)
            return
        sorted_segments = sorted(bsi_results.items())
        self.results_table.setRowCount(len(sorted_segments))
        for row, (segment_name, data) in enumerate(sorted_segments):
            items = [
                QTableWidgetItem(segment_name.title()),
                QTableWidgetItem(str(data.get('total_segment_pixels', 0))),
                QTableWidgetItem(str(data.get('hotspot_normal', 0))),
                QTableWidgetItem(f"{data.get('percentage_normal', 0) * 100:.2f}%"),
                QTableWidgetItem(str(data.get('hotspot_abnormal', 0))),
                QTableWidgetItem(f"{data.get('percentage_abnormal', 0) * 100:.2f}%")
            ]
            for col, item in enumerate(items):
                self.results_table.setItem(row, col, item)

    def _update_patient_info(self, patient_id: str, study_date: str):
        try:
            formatted_date = datetime.strptime(study_date, "%Y%m%d").strftime("%b %d, %Y")
        except (ValueError, TypeError):
            formatted_date = study_date or "N/A"
        self.patient_info_label.setText(f"Patient: {patient_id} | Study: {formatted_date}")
    
    # FUNGSI YANG HILANG DITAMBAHKAN KEMBALI DI SINI
    def _update_button_states(self, has_data: bool):
        """Mengaktifkan atau menonaktifkan tombol-tombol kontrol."""
        self.export_chart_btn.setEnabled(has_data)
        # Tambahkan tombol lain di sini jika ada, contoh:
        # self.export_report_btn.setEnabled(has_data)
        # self.run_analysis_btn.setEnabled(not has_data)
        
    def clear_patient_data(self):
        """Membersihkan semua data pasien dari panel dan me-reset UI."""
        print("[BSI SIDE PANEL] Clearing all patient data...")
        self.current_patient_folder = None
        self.current_patient_id = None
        self.current_study_date = None
        self.bsi_canvas.clear_data()
        self.results_table.setRowCount(0)
        self._update_patient_info("N/A", "N/A")
        for btn in self.scan_buttons:
            self.scan_buttons_layout.removeWidget(btn)
            btn.deleteLater()
        self.scan_buttons.clear()
        self._update_button_states(False)

    def set_session_code(self, session_code: str):
        """Menyimpan session code untuk keperluan internal."""
        self._current_session_code = session_code