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
      FIXED: BSI Side Panel that supports single view quantification
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
        
        #   SIMPLIFIED: Update chart visibility without combined
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
        
        
    def _wire_two_tables_once(self):
        """
        Wire tabel kiri (Region) & kanan (data) supaya:
        - scroll vertikal dua arah (kiri ikut kanan dan sebaliknya)
        - tinggi baris tersinkron
        - perubahan jumlah baris / sorting di kanan ikut nyusun ulang kiri
        """
        if getattr(self, "_two_tables_wired", False):
            return

        # --- Scroll vertikal sinkron dua arah ---
        right_v = self.results_table_right.verticalScrollBar()
        left_v  = self.results_table_left.verticalScrollBar()

        right_v.valueChanged.connect(left_v.setValue)
        left_v.valueChanged.connect(right_v.setValue)

        # Scroll per-pixel biar halus & konsisten
        self.results_table_left.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.results_table_right.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        # --- Sinkron tinggi baris via vertical header ---
        right_vh = self.results_table_right.verticalHeader()
        left_vh  = self.results_table_left.verticalHeader()

        def _on_row_height_changed(logical_index: int, old_size: int, new_size: int):
            if logical_index < self.results_table_left.rowCount():
                left_vh.resizeSection(logical_index, new_size)

        right_vh.sectionResized.connect(_on_row_height_changed)

        # Jika jumlah baris berubah, lakukan resync penuh
        def _full_resync_heights():
            rows = min(self.results_table_left.rowCount(), self.results_table_right.rowCount())
            for r in range(rows):
                left_vh.resizeSection(r, self.results_table_right.rowHeight(r))

        model = self.results_table_right.model()
        model.rowsInserted.connect(lambda *args: _full_resync_heights())
        model.rowsRemoved.connect(lambda *args: _full_resync_heights())

        # (dihapus) Tidak perlu sync sorting lagi karena sorting dimatikan
        # model.layoutChanged.connect(self._sync_left_order_with_right)

        self._two_tables_wired = True
        
        
    def _sync_left_order_with_right(self):
        # Kumpulkan urutan region dari tabel kanan (pakai UserRole+1 yang diisi saat populate)
        order = []
        total_row_idx = None
        rows = self.results_table_right.rowCount()
        for r in range(rows):
            it0 = self.results_table_right.item(r, 0)
            if not it0:
                continue
            if it0.data(Qt.UserRole) == "zzz_total":
                total_row_idx = r
                continue
            region_key = it0.data(Qt.UserRole + 1)  # diset di _populate_results_table_v2
            order.append((r, region_key))

        # rewrite isi tabel kiri mengikuti urutan kanan
        # NOTE: baris TOTAL tetap paling bawah
        for dst_row, (_, region_key) in enumerate(order):
            self.results_table_left.setItem(dst_row, 0, QTableWidgetItem((region_key or "").title()))

        # TOTAL di baris terakhir (jaga bold & sort key)
        last = len(order)
        if last < self.results_table_left.rowCount():
            from PySide6.QtGui import QFont
            total_item = QTableWidgetItem("TOTAL")
            f = QFont(); f.setBold(True)
            total_item.setFont(f)
            total_item.setData(Qt.UserRole, "zzz_total")
            self.results_table_left.setItem(last, 0, total_item)
    
    
    def _create_results_table_v2(self) -> QWidget:
        """Container 2-table (left: Region freeze, right: data columns)"""
        from PySide6.QtWidgets import QSizePolicy, QHeaderView

        table_container = QFrame()
        table_container.setObjectName("bsiTableFrame")
        table_container.setStyleSheet("""
            QFrame#bsiTableFrame {
                border: 1px solid #e9ecef; border-radius: 6px;
                background: #ffffff;
            }
            QTableWidget { border: none; }
            QHeaderView::section {
                background: #f8f9fa; border: none;
                border-bottom: 1px solid #e9ecef;
                padding: 6px;
            }
        """)
        table_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        outer = QVBoxLayout(table_container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Title
        title = QLabel("<b>Quantification Results</b>")
        title.setStyleSheet("font-size: 12px; color: #495057; font-weight: bold; margin: 8px;")
        outer.addWidget(title)

        # Row: two tables stuck together
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        outer.addLayout(row)

        # LEFT (Region, frozen)
        self.results_table_left = QTableWidget()
        self.results_table_left.setColumnCount(1)
        self.results_table_left.setHorizontalHeaderLabels(["Region"])
        self.results_table_left.verticalHeader().setVisible(False)
        self.results_table_left.setAlternatingRowColors(True)
        self.results_table_left.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_table_left.setSelectionMode(QAbstractItemView.NoSelection)
        self.results_table_left.setSortingEnabled(False)
        self.results_table_left.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.results_table_left.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # kolom region stretch biar “penuh” area kiri, keliatan menyatu
        self.results_table_left.horizontalHeader().setStretchLastSection(True)
        # row-height default lebih besar & bisa di-drag
        self.results_table_left.verticalHeader().setDefaultSectionSize(30)
        self.results_table_left.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # Separator tipis biar kayak garis grid di tengah
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #e9ecef;")

        # RIGHT (data)
        self.results_table_right = QTableWidget()
        self.results_table_right.setColumnCount(4)
        self.results_table_right.setHorizontalHeaderLabels([
            "Malignant Ant", "Malignant Post", "Benign Ant", "Benign Post"
        ])
        self.results_table_right.verticalHeader().setVisible(False)
        self.results_table_right.setAlternatingRowColors(True)
        self.results_table_right.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_table_right.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.results_table_right.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # ⬇️ matiin sorting di tabel kanan
        self.results_table_right.setSortingEnabled(False)
        header = self.results_table_right.horizontalHeader()
        # ⬇️ hilangin indikator & klik header biar ga “kesannya bisa sort”
        header.setSortIndicatorShown(False)
        header.setSectionsClickable(False)
        header.setSectionResizeMode(header.ResizeMode.Interactive)
        # row-height default lebih besar & bisa di-drag
        self.results_table_right.verticalHeader().setDefaultSectionSize(30)
        self.results_table_right.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # Default widths
        self.results_table_left.setMinimumWidth(200)
        self.results_table_right.setColumnWidth(0, 130)
        self.results_table_right.setColumnWidth(1, 130)
        self.results_table_right.setColumnWidth(2, 120)
        self.results_table_right.setColumnWidth(3, 120)

        # Bikin area tabel lebih tinggi supaya lega
        self.results_table_right.setMinimumHeight(650)

        # tempelkan
        row.addWidget(self.results_table_left)
        row.addWidget(sep)
        row.addWidget(self.results_table_right, 1)  # kanan ambil sisa lebar

        # Note
        note = QLabel("<i>Format: pixel_count (decimal_ratio) • Drag header untuk resize</i>")
        note.setStyleSheet("font-size: 10px; color: #6c757d; font-style: italic; margin: 6px 8px;")
        outer.addWidget(note)

        # Sinkron scroll + sort (sekali saja)
        self._wire_two_tables_once()

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
        """  FIXED: Load patient data tanpa scan selector"""
        try:
            #   FIXED: For table data, use exact study_date folder
            self.current_patient_folder = patient_folder
            self.current_patient_id = patient_id
            self.current_study_date = study_date
            
            #   FIXED: For BSI canvas trend, pass patient base folder
            if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
                # Current folder is study_date folder, canvas needs parent for trend
                canvas_patient_folder = patient_folder.parent
            else:
                # Current folder is already patient folder
                canvas_patient_folder = patient_folder
            
            # Test BSI canvas loading with correct folder
            canvas_success = self.bsi_canvas.load_bsi_data(canvas_patient_folder, patient_id, study_date)
            
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
                if hasattr(self, 'results_table_left'):
                    self.results_table_left.setRowCount(0)
                if hasattr(self, 'results_table_right'):
                    self.results_table_right.setRowCount(0)
                self._update_patient_info(patient_id, "No Data Found")
                self._update_button_states(False)
                    
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.clear_patient_data()
            return False
            
    def _populate_results_table_v2(self, anterior_data: dict, posterior_data: dict, processing_mode: str = "unknown"):
        if not anterior_data and not posterior_data:
            self.results_table_left.setRowCount(0)
            self.results_table_right.setRowCount(0)
            return

        all_regions = set(anterior_data.keys()) | set(posterior_data.keys())
        all_regions.discard('background')
        sorted_regions = sorted(all_regions)
        rows = len(sorted_regions) + 1

        self.results_table_left.setRowCount(rows)
        self.results_table_right.setRowCount(rows)

        total_ant_benign = total_post_benign = 0
        total_ant_malignant = total_post_malignant = 0

        for row, region_name in enumerate(sorted_regions):
            ant = anterior_data.get(region_name, {}) or {}
            pos = posterior_data.get(region_name, {}) or {}

            ant_benign = ant.get('benign_pixels', 0); ant_benign_ratio = ant.get('benign_ratio', 0.0)
            pos_benign = pos.get('benign_pixels', 0); pos_benign_ratio = pos.get('benign_ratio', 0.0)
            ant_malig  = ant.get('malignant_pixels', 0); ant_malig_ratio  = ant.get('malignant_ratio', 0.0)
            pos_malig  = pos.get('malignant_pixels', 0); pos_malig_ratio  = pos.get('malignant_ratio', 0.0)

            total_ant_benign += ant_benign; total_post_benign += pos_benign
            total_ant_malignant += ant_malig; total_post_malignant += pos_malig

            if processing_mode == 'single_view_anterior':
                pos_benign_text = "N/A"; pos_malig_text = "N/A"
            else:
                pos_benign_text = f"{pos_benign} ({pos_benign_ratio:.3f})"
                pos_malig_text  = f"{pos_malig} ({pos_malig_ratio:.3f})"

            if processing_mode == 'single_view_posterior':
                ant_benign_text = "N/A"; ant_malig_text = "N/A"
            else:
                ant_benign_text = f"{ant_benign} ({ant_benign_ratio:.3f})"
                ant_malig_text  = f"{ant_malig} ({ant_malig_ratio:.3f})"

            # LEFT (Region)
            self.results_table_left.setItem(row, 0, QTableWidgetItem(region_name.title()))

            # RIGHT (4 kolom)
            right_items = [
                QTableWidgetItem(ant_malig_text),
                QTableWidgetItem(pos_malig_text),
                QTableWidgetItem(ant_benign_text),
                QTableWidgetItem(pos_benign_text),
            ]
            for c, it in enumerate(right_items):
                # simpan region untuk sync sort
                it.setData(Qt.UserRole + 1, region_name)
                # warna malignant
                if c in (0, 1):
                    if c == 0 and ant_malig > 0 and processing_mode != 'single_view_posterior':
                        it.setBackground(QColor(255, 200, 200))
                    elif c == 1 and pos_malig > 0 and processing_mode != 'single_view_anterior':
                        it.setBackground(QColor(255, 200, 200))
                    elif it.text() == "N/A":
                        it.setBackground(QColor(240, 240, 240))
                self.results_table_right.setItem(row, c, it)

        # TOTAL ROW
        last = len(sorted_regions)
        from PySide6.QtGui import QFont
        total_lbl = QTableWidgetItem("TOTAL")
        f = QFont(); f.setBold(True)
        total_lbl.setFont(f)
        total_lbl.setData(Qt.UserRole, "zzz_total")
        self.results_table_left.setItem(last, 0, total_lbl)

        if processing_mode == 'single_view_anterior':
            totals = [QTableWidgetItem(str(total_ant_malignant)),
                    QTableWidgetItem("N/A"),
                    QTableWidgetItem(str(total_ant_benign)),
                    QTableWidgetItem("N/A")]
        elif processing_mode == 'single_view_posterior':
            totals = [QTableWidgetItem("N/A"),
                    QTableWidgetItem(str(total_post_malignant)),
                    QTableWidgetItem("N/A"),
                    QTableWidgetItem(str(total_post_benign))]
        else:
            totals = [QTableWidgetItem(str(total_ant_malignant)),
                    QTableWidgetItem(str(total_post_malignant)),
                    QTableWidgetItem(str(total_ant_benign)),
                    QTableWidgetItem(str(total_post_benign))]

        for it in totals:
            it.setBackground(QColor(230, 230, 230))
            it.setData(Qt.UserRole, "zzz_total")
        for c, it in enumerate(totals):
            # simpan region dummy supaya fungsi sync gak error
            it.setData(Qt.UserRole + 1, "__total__")
            self.results_table_right.setItem(last, c, it)

        # Pas-pasin lebar tabel kiri ke konten (biar terlihat nyatu, tanpa H-scroll)
        left = self.results_table_left
        left.resizeColumnsToContents()
        width = left.verticalHeader().width() + left.sizeHintForColumn(0) + 12
        left.setFixedWidth(max(200, width))

        # Samakan tinggi semua baris awal (cadangan selain sinyal sectionResized)
        rows_sync = min(self.results_table_left.rowCount(), self.results_table_right.rowCount())
        for r in range(rows_sync):
            self.results_table_left.verticalHeader().resizeSection(r, self.results_table_right.rowHeight(r))

    
    def _update_patient_info(self, patient_id: str, study_date: str):
        """  SIMPLIFIED: Update patient info display"""
        try:
            formatted_date = datetime.strptime(study_date, "%Y%m%d").strftime("%b %d, %Y")
        except (ValueError, TypeError):
            formatted_date = study_date or "N/A"
        
        #   SIMPLE: Clean patient info
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
        if hasattr(self, 'results_table_left'):
            self.results_table_left.setRowCount(0)
        if hasattr(self, 'results_table_right'):
            self.results_table_right.setRowCount(0)
        
        #   SIMPLIFIED: No processing mode parameter
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
                print("[BSI PANEL]   Refresh successful")
            else:
                print("[BSI PANEL]  Refresh failed")
        else:
            print("[BSI PANEL] No patient data to refresh")
    
    def _export_csv_data_v2(self):
        """  UPDATED: Export CSV data with single view support"""
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
                headers = ["Region", "Malignant Ant", "Malignant Post", "Benign Ant", "Benign Post"]
                writer.writerow(headers)

                rows = self.results_table_left.rowCount()
                for row in range(rows):
                    region_item = self.results_table_left.item(row, 0)
                    region = region_item.text() if region_item else ""

                    r0 = self.results_table_right.item(row, 0)
                    r1 = self.results_table_right.item(row, 1)
                    r2 = self.results_table_right.item(row, 2)
                    r3 = self.results_table_right.item(row, 3)

                    row_data = [
                        region,
                        r0.text() if r0 else "",
                        r1.text() if r1 else "",
                        r2.text() if r2 else "",
                        r3.text() if r3 else "",
                    ]
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
        """  UPDATED: Export V1.2 report to text file with single view support"""
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
                
                #   Add processing mode info
                if hasattr(self, 'quant_manager') and self.quant_manager.current_results:
                    summary_stats = self.quant_manager.current_results.get('summary_statistics', {})
                    processing_mode = summary_stats.get('processing_mode', 'unknown')
                    f.write(f"Processing Mode: {processing_mode}\n")
                    
                    if processing_mode == 'single_view_anterior':
                        f.write("Note: Only anterior view files were available for processing\n")
                    elif processing_mode == 'single_view_posterior':
                        f.write("Note: Only posterior view files were available for processing\n")
                
                f.write("\n")
                
                #   Add V1.2 BSI scores with single view support
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
                right_headers = ["Malignant Ant", "Malignant Post", "Benign Ant", "Benign Post"]
                rows = self.results_table_left.rowCount()
                for row in range(rows):
                    region_item = self.results_table_left.item(row, 0)
                    if not region_item:
                        continue
                    region_name = region_item.text()
                    f.write(f"{region_name}:\n")

                    for c, head in enumerate(right_headers):
                        it = self.results_table_right.item(row, c)
                        value = it.text() if it else "N/A"
                        f.write(f"  {head}: {value}\n")
                    f.write("\n")
                
                f.write("=" * 60 + "\n")
                
            return True
            
        except Exception as e:
            print(f"[BSI REPORT V1.2 SINGLE] Error exporting report: {e}")
            return False