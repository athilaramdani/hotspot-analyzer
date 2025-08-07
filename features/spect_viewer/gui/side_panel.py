# features/spect_viewer/gui/side_panel.py
"""
Enhanced side panel with BSI quantification results
Shows BSI chart, summary statistics, and detailed analysis comments
"""
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
from PySide6.QtGui import QColor
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
        """Membangun UI utama panel dengan QScrollArea agar bisa di-scroll."""
        
        # Layout utama panel ini hanya akan berisi satu widget: QScrollArea.
        main_panel_layout = QVBoxLayout(self)
        main_panel_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Buat QScrollArea untuk membungkus semua konten.
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        # 2. Buat widget "kontainer" yang akan diletakkan di dalam scroll area.
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        # 3. Buat layout untuk widget "kontainer". SEMUA elemen UI akan masuk ke layout ini.
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(12)

        # --- Mulai Tambahkan Semua Elemen Secara Berurutan ke 'content_layout' ---

        # A. Judul
        self._create_title_section(content_layout)

        # B. BSI Chart
        self.bsi_canvas = BSICanvas()
        content_layout.addWidget(self.bsi_canvas)

        # C. Area Tombol Pilihan Scan
        scan_selector = self._create_scan_selection_section()
        content_layout.addWidget(scan_selector)

        # D. Tabel Hasil BSI
        results_table = self._create_results_table()
        content_layout.addWidget(results_table)
        
        # E. Tombol Kontrol (Export, dll.)
        controls_section = self._create_controls_section()
        content_layout.addWidget(controls_section)
        
        # F. Beri ruang kosong di bagian bawah agar konten tidak menempel
        content_layout.addStretch()

        # 4. Terakhir, tambahkan QScrollArea yang sudah berisi semua konten ke layout utama panel.
        main_panel_layout.addWidget(scroll_area)
    
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
    def _create_results_table(self) -> QWidget:
        """Membuat tabel untuk menampilkan rincian hasil BSI per segmen."""
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Anatomical Region", "% Abnormal", "Abnormal Pixels", "Normal Pixels"])
        self.results_table.setMinimumHeight(300) # Beri tinggi minimal
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers) # Agar tidak bisa diedit
        self.results_table.horizontalHeader().setStretchLastSection(True)
        
        # Atur lebar kolom
        self.results_table.setColumnWidth(0, 150) # Region
        self.results_table.setColumnWidth(1, 100) # % Abnormal
        
        return self.results_table
    def _create_scan_selection_section(self) -> QWidget:
        """Membuat widget container untuk tombol pilihan scan."""
        section_widget = QFrame()
        section_widget.setStyleSheet("padding: 8px 0px;")
        
        self.scan_buttons_layout = QHBoxLayout(section_widget)
        self.scan_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.scan_buttons_layout.setSpacing(8)
        
        # Label
        label = QLabel("<b>Select Scan:</b>")
        self.scan_buttons_layout.addWidget(label)
        
        self.scan_buttons_layout.addStretch()
        return section_widget
    def _populate_results_table(self, bsi_results: dict):
        """Mengisi tabel dengan data hasil BSI dari scan yang dipilih."""
        if not bsi_results:
            self.results_table.setRowCount(0)
            return

        # UBAH BARIS INI:
        # Sebelumnya: segments_to_display = {k: v for k, v in bsi_results.items() if k != "background" ...}
        # Menjadi:
        segments_to_display = bsi_results
        
        self.results_table.setRowCount(len(segments_to_display))
        
        # Urutkan berdasarkan nama segmen agar konsisten (opsional tapi disarankan)
        sorted_segments = sorted(segments_to_display.items())
        
        for row, (segment_name, data) in enumerate(sorted_segments):
            # Kolom 0: Nama Region
            # Gunakan .title() untuk membuat huruf kapital di awal kata (e.g., "cervical vertebrae" -> "Cervical Vertebrae")
            self.results_table.setItem(row, 0, QTableWidgetItem(segment_name.title()))
            
            # Kolom 1: Persentase Abnormal
            abnormal_pct = data.get('percentage_abnormal', 0) * 100
            item_pct = QTableWidgetItem(f"{abnormal_pct:.2f}%")
            self.results_table.setItem(row, 1, item_pct)
            
            # Kolom 2: Piksel Abnormal
            self.results_table.setItem(row, 2, QTableWidgetItem(str(data.get('hotspot_abnormal', 0))))
            
            # Kolom 3: Piksel Normal
            self.results_table.setItem(row, 3, QTableWidgetItem(str(data.get('hotspot_normal', 0))))
            
            # (Opsional) Beri warna pada baris berdasarkan tingkat abnormalitas
            if abnormal_pct > 10:
                item_pct.setBackground(QColor("#d32f2f")) # Merah
                item_pct.setForeground(QColor("white"))
            elif abnormal_pct > 2:
                item_pct.setBackground(QColor("#ffc107")) # Kuning
    
    def _on_scan_selected(self, scan_data: dict, emit_signal: bool = True):
        """Menangani saat tombol scan ditekan dan mengisi tabel."""
        study_date = scan_data.get("study_date")
        if not study_date:
            return

        print(f"[BSI SIDE PANEL] Scan dipilih: {study_date}, memuat detail...")
        self.current_study_date = study_date
        self._update_patient_info(self.current_patient_id, self.current_study_date)

        # Muat hasil kuantifikasi LENGKAP untuk studi ini
        quant_results = self.quant_manager.load_quantification_results(
            self.current_patient_folder, self.current_patient_id, study_date
        )
        
        if quant_results:
            # Ambil bagian 'bsi_results' dan isi tabel
            bsi_results_data = quant_results.get('bsi_results', {})
            self._populate_results_table(bsi_results_data)

        if emit_signal:
            self.scan_selected.emit(study_date)

    def _create_chart_section(self) -> QWidget:
        self.bsi_canvas = BSICanvas()
        return self.bsi_canvas
    
    def _create_details_section(self) -> QWidget:
        """Create details section with comments and controls"""
        controls_frame = self._create_controls_section()
        return controls_frame
    
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
    # GANTI FUNGSI INI DI DALAM KELAS BSISidePanel
    def load_patient_data(self, patient_folder: Path, patient_id: str, study_date: str) -> bool:
        """
        Memuat data BSI untuk pasien.
        - Chart akan menampilkan tren BSI dari semua studi.
        - Info Panel dan Komentar akan menampilkan detail dari study_date yang dipilih.
        """
        try:
            print(f"[BSI SIDE PANEL] Loading data for patient {patient_id}, focus on study {study_date}")
            
            # Simpan info pasien saat ini
            self.current_patient_folder = patient_folder
            self.current_patient_id = patient_id
            self.current_study_date = study_date
            
            # Update label info pasien di bagian atas
            self._update_patient_info(patient_id, study_date)
            
            # LANGKAH 1: Muat dan tampilkan chart tren BSI (diagram garis)
            # Fungsi ini sekarang akan memuat SEMUA skor untuk pasien tersebut
            # dan mengabaikan 'study_date' yang dilewatkan.
            canvas_success = self.bsi_canvas.load_bsi_data(patient_folder, patient_id, study_date)
            
            if not canvas_success:
                # Jika chart gagal dimuat (misal: tidak ada data sama sekali)
                self._show_no_quantification_data()
                self._update_button_states(False)
                # Tetap aktifkan tombol 'Run Analysis' jika belum ada kuantifikasi
                status = get_quantification_status(patient_folder / f"{patient_id}_{study_date}.dcm", patient_id, study_date)
                self.run_analysis_btn.setEnabled(status.get("can_run_quantification", False))
                return False

            # LANGKAH 2: Muat data ringkasan untuk STUDI SPESIFIK yang dipilih
            # Kita gunakan QuantificationManager secara langsung di sini.
            summary_data_specific_study = None
            quant_results = self.quant_manager.load_quantification_results(patient_folder, patient_id, study_date)
            if quant_results:
                summary_data_specific_study = self.quant_manager.get_bsi_summary()

            if not summary_data_specific_study:
                self._show_quantification_error() # Tampilkan error jika data studi spesifik tidak bisa dimuat
                return False

            # LANGKAH 3: Update Info Panel dan Komentar dengan data studi spesifik
            # self.bsi_info_panel.update_info(summary_data_specific_study)
            # self._generate_analysis_comments(summary_data_specific_study)
            
            # Update status tombol dan label
            self._update_button_states(True)
            bsi_score = summary_data_specific_study.get('bsi_score', 0)
            self.status_label.setText(f"Trend loaded. Showing details for study BSI: {bsi_score:.2f}%")
            self.status_label.setStyleSheet("QLabel { font-size: 10px; color: #28a745; font-style: italic; margin-top: 4px; }")
            
            print(f"[BSI SIDE PANEL] Successfully displayed BSI trend and study details for {patient_id}")
            return True
            
        except Exception as e:
            print(f"[BSI SIDE PANEL] Error loading patient data: {e}")
            import traceback
            traceback.print_exc()
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
        # self.bsi_info_panel.clear_info()
        
        # Reset UI
        self.patient_info_label.setText("Select a patient to view BSI analysis")
        # self.comments_text.setPlainText("Select a patient with quantification results to view analysis comments.")
        
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