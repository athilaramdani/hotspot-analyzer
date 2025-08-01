# features/spect_viewer/gui/scan_timeline_widget.py
"""
Main SPECT timeline widget - modular version
Handles UI layout and coordinates between data manager and card renderer
"""
from __future__ import annotations
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton, QSplitter
)

# Import logic components
from features.spect_viewer.logic.timeline_data_manager import TimelineDataManager

# Import UI components
from .timeline_cards import CardFactory, TimelineCard
from .segmentation_editor_dialog import SegmentationEditorDialog
from .hotspot_editor_dialog import HotspotEditorDialog

# Import UI constants
from core.gui.ui_constants import (
    SUCCESS_BUTTON_STYLE,  # Green for segmentation edit
    ZOOM_BUTTON_STYLE,     # Orange for hotspot edit  
    GRAY_BUTTON_STYLE      # Gray for disabled
)


class ScanTimelineWidget(QWidget):
    """
    Modular SPECT timeline widget with separated logic and UI
    Handles display of scan timeline with layered image compositing
    """
    # Signals
    scan_selected = Signal(int)  # Emit scan index when selected
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        
        # Initialize data manager
        self.data_manager = TimelineDataManager()
        
        # UI state
        self.current_view = "Anterior"
        self._zoom_factor = 1.0
        self.card_width = 350
        
        # Card storage
        self._cards: List[TimelineCard] = []
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the main UI layout"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create main splitter for resizable layout
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # LEFT SIDE: Scrollable timeline area
        self._setup_timeline_area()
        
        # RIGHT SIDE: Layer control panel (resizable)
        self.control_panel = self._create_control_panel()
        
        # Add to splitter
        self.main_splitter.addWidget(self.scroll_area)
        self.main_splitter.addWidget(self.control_panel)
        
        # Set initial splitter sizes: Timeline | Controls
        self.main_splitter.setStretchFactor(0, 3)  # Timeline gets 75%
        self.main_splitter.setStretchFactor(1, 1)  # Controls get 25%
        self.main_splitter.setSizes([800, 200])    # Initial pixel sizes
        
        # Style splitter
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e9ecef;
                width: 3px;
                margin: 2px;
                border-radius: 1px;
            }
            QSplitter::handle:hover {
                background-color: #4e73ff;
            }
        """)
        
        main_layout.addWidget(self.main_splitter)
    
    def _setup_timeline_area(self):
        """Setup the scrollable timeline area"""
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.container = QWidget()
        self.timeline_layout = QHBoxLayout(self.container)
        self.timeline_layout.setAlignment(Qt.AlignLeft)
        self.scroll_area.setWidget(self.container)
    
    def _create_control_panel(self) -> QWidget:
        """Create the resizable control panel"""
        panel = QWidget()
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(400)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Panel title
        title = QLabel("<b>Layer Controls</b>")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #495057;
                padding: 5px;
                background: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #e9ecef;
            }
        """)
        layout.addWidget(title)
        
        # Active layers display
        self.active_layers_label = QLabel("Active Layers: None")
        self.active_layers_label.setWordWrap(True)
        self.active_layers_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #6c757d;
                padding: 8px;
                background: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                margin: 5px 0px;
            }
        """)
        layout.addWidget(self.active_layers_label)
        
        # Edit buttons section
        self._setup_edit_buttons(layout)
        
        # Current scan info
        self.scan_info_label = QLabel("No scan selected")
        self.scan_info_label.setWordWrap(True)
        self.scan_info_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #6c757d;
                padding: 6px;
                background: #f8f9fa;
                border-radius: 3px;
                margin-top: 10px;
            }
        """)
        layout.addWidget(self.scan_info_label)
        
        layout.addStretch()
        
        return panel
    
    def _setup_edit_buttons(self, layout):
        """Setup edit buttons in control panel"""
        edit_group = QWidget()
        edit_layout = QVBoxLayout(edit_group)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        
        edit_title = QLabel("<b>Edit Options</b>")
        edit_title.setStyleSheet("font-size: 12px; color: #495057; margin-bottom: 5px;")
        edit_layout.addWidget(edit_title)
        
        # Segmentation edit button
        self.seg_edit_btn = QPushButton("Edit Segmentation")
        self.seg_edit_btn.setStyleSheet(SUCCESS_BUTTON_STYLE + """
            QPushButton {
                font-size: 11px;
                padding: 6px 8px;
                margin: 2px 0px;
            }
        """)
        self.seg_edit_btn.clicked.connect(self._open_segmentation_editor)
        edit_layout.addWidget(self.seg_edit_btn)
        
        # Hotspot edit button  
        self.hotspot_edit_btn = QPushButton("Edit Hotspot")
        self.hotspot_edit_btn.setStyleSheet(ZOOM_BUTTON_STYLE + """
            QPushButton {
                font-size: 11px;
                padding: 6px 8px;
                margin: 2px 0px;
            }
        """)
        self.hotspot_edit_btn.clicked.connect(self._open_hotspot_editor)
        edit_layout.addWidget(self.hotspot_edit_btn)
        
        layout.addWidget(edit_group)
        
        # Update button states initially
        self._update_edit_button_states()
    
    # ===== Public API =====
    def display_timeline(self, scans: List[Dict], active_index: int = -1):
        """Display timeline with scan data"""
        print(f"[DEBUG] ScanTimeline: Displaying {len(scans)} scans, active index: {active_index}")
        
        # Update data manager
        self.data_manager.set_scans_data(scans, active_index)
        
        # Reset zoom
        self._zoom_factor = 1.0
        
        # Rebuild UI
        self._rebuild_timeline()
        self._update_scan_info_display()
        self._update_edit_button_states()
    
    def set_active_view(self, view: str):
        """Set active view"""
        self.current_view = view
        self._rebuild_timeline()
        self._update_scan_info_display()
    
    def set_active_layers(self, layers: List[str]):
        """Set active layers"""
        self.data_manager.set_active_layers(layers)
        self._rebuild_timeline()
        self._update_active_layers_display()
        self._update_edit_button_states()
    
    def set_layer_opacity(self, layer: str, opacity: float):
        """Set layer opacity"""
        self.data_manager.set_layer_opacity(layer, opacity)
        self._rebuild_timeline()
    
    def set_session_code(self, session_code: str):
        """Set session code for path resolution"""
        self.data_manager.set_session_code(session_code)
    
    def get_active_layers(self) -> List[str]:
        """Get active layers"""
        return self.data_manager.get_active_layers()
    
    def is_layer_active(self, layer: str) -> bool:
        """Check if layer is active"""
        return self.data_manager.is_layer_active(layer)
    
    def has_layer_data(self, layer: str) -> bool:
        """Check if layer data is available"""
        return self.data_manager.has_layer_data(layer)
    
    def refresh_current_view(self):
        """Refresh current view"""
        self.data_manager.refresh_current_view()
        self._rebuild_timeline()
    
    # ===== Zoom Controls =====
    def zoom_in(self):
        """Zoom in timeline"""
        self._zoom_factor *= 1.2
        self._rebuild_timeline()
    
    def zoom_out(self):
        """Zoom out timeline"""
        self._zoom_factor *= 0.8
        self._rebuild_timeline()
    
    # ===== Internal Methods =====
    def _rebuild_timeline(self):
        """Rebuild timeline display"""
        self._clear_timeline()
        
        scans = self.data_manager.get_scans_data()
        active_layers = self.data_manager.get_active_layers()
        
        if not scans:
            # No scans available
            placeholder = CardFactory.create_no_scans_card()
            self.timeline_layout.addWidget(placeholder)
            return
        
        if not active_layers:
            # No layers selected
            placeholder = CardFactory.create_no_layers_card()
            self.timeline_layout.addWidget(placeholder)
            return
        
        # Create cards for each scan
        card_width = int(self.card_width * self._zoom_factor)
        
        for i, scan in enumerate(scans):
            card = self._create_scan_card(scan, i, card_width)
            self.timeline_layout.addWidget(card)
            self._cards.append(card)
        
        self.timeline_layout.addStretch()
    
    def _create_scan_card(self, scan: Dict, scan_index: int, card_width: int) -> TimelineCard:
        """Create a card for a scan"""
        # Create card
        card = CardFactory.create_scan_card(scan, scan_index, card_width, self._on_card_selected)
        
        # Set active state
        active_index = self.data_manager.get_active_scan_index()
        card.set_active(scan_index == active_index)
        
        # Load and set image
        composite_image = self.data_manager.create_composite_image(scan_index, self.current_view)
        card.set_image(composite_image)
        
        # Set status and tooltip
        active_layers = self.data_manager.get_active_layers()
        opacities = self.data_manager.get_all_opacities()
        
        card.set_status(self.current_view, active_layers)
        card.set_tooltip_info(active_layers, opacities)
        
        return card
    
    def _clear_timeline(self):
        """Clear all timeline cards"""
        while self.timeline_layout.count():
            child = self.timeline_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self._cards.clear()
    
    def _on_card_selected(self, scan_index: int):
        """Handle card selection"""
        print(f"[DEBUG] ScanTimeline: Card {scan_index} selected")
        
        # Update data manager
        self.data_manager.set_active_scan_index(scan_index)
        
        # Update card states
        for i, card in enumerate(self._cards):
            card.set_active(i == scan_index)
        
        # Update UI
        self._update_scan_info_display()
        self._update_edit_button_states()
        
        # Emit signal
        self.scan_selected.emit(scan_index)
    
    def _update_active_layers_display(self):
        """Update active layers display"""
        active_layers = self.data_manager.get_active_layers()
        
        if not active_layers:
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
            layers_text = ", ".join(active_layers)
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
        """Update edit button states"""
        active_layers = self.data_manager.get_active_layers()
        has_segmentation = "Segmentation" in active_layers
        has_hotspot = "Hotspot" in active_layers
        has_scan = self.data_manager.get_scan_count() > 0
        
        # Segmentation edit button
        if has_segmentation and has_scan:
            self.seg_edit_btn.setEnabled(True)
            self.seg_edit_btn.setStyleSheet(SUCCESS_BUTTON_STYLE + """
                QPushButton {
                    font-size: 11px;
                    padding: 6px 8px;
                    margin: 2px 0px;
                }
            """)
        else:
            self.seg_edit_btn.setEnabled(False)
            self.seg_edit_btn.setStyleSheet(GRAY_BUTTON_STYLE + """
                QPushButton {
                    font-size: 11px;
                    padding: 6px 8px;
                    margin: 2px 0px;
                    opacity: 0.6;
                }
            """)
        
        # Hotspot edit button
        if has_hotspot and has_scan:
            self.hotspot_edit_btn.setEnabled(True)
            self.hotspot_edit_btn.setStyleSheet(ZOOM_BUTTON_STYLE + """
                QPushButton {
                    font-size: 11px;
                    padding: 6px 8px;
                    margin: 2px 0px;
                }
            """)
        else:
            self.hotspot_edit_btn.setEnabled(False)
            self.hotspot_edit_btn.setStyleSheet(GRAY_BUTTON_STYLE + """
                QPushButton {
                    font-size: 11px;
                    padding: 6px 8px;
                    margin: 2px 0px;
                    opacity: 0.6;
                }
            """)
    
    def _update_scan_info_display(self):
        """Update scan info display"""
        scans = self.data_manager.get_scans_data()
        active_index = self.data_manager.get_active_scan_index()
        
        if not scans or active_index < 0 or active_index >= len(scans):
            self.scan_info_label.setText("No scan selected")
            return
        
        scan = scans[active_index]
        meta = scan["meta"]
        
        # Format scan info
        scan_num = active_index + 1
        total_scans = len(scans)
        date = meta.get("study_date", "Unknown")
        bsi = meta.get("bsi_value", "N/A")
        
        try:
            from datetime import datetime
            formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError:
            formatted_date = date
        
        info_text = f"""
        <b>Scan {scan_num}/{total_scans}</b><br>
        Date: {formatted_date}<br>
        BSI: {bsi}<br>
        View: {self.current_view}
        """
        
        self.scan_info_label.setText(info_text)
    
    # ===== Editor Dialogs =====
    def _open_segmentation_editor(self):
        """Open segmentation editor"""
        scans = self.data_manager.get_scans_data()
        active_index = self.data_manager.get_active_scan_index()
        
        if not scans or active_index < 0 or active_index >= len(scans):
            print("[DEBUG] No valid scan selected for segmentation editing")
            return
        
        scan = scans[active_index]
        print(f"[DEBUG] Opening segmentation editor for scan {active_index + 1}")
        
        dlg = SegmentationEditorDialog(scan, self.current_view, parent=self)
        if dlg.exec():
            print("[DEBUG] Segmentation editor completed, refreshing timeline")
            self.refresh_current_view()
    
    def _open_hotspot_editor(self):
        """Open hotspot editor"""
        scans = self.data_manager.get_scans_data()
        active_index = self.data_manager.get_active_scan_index()
        
        if not scans or active_index < 0 or active_index >= len(scans):
            print("[DEBUG] No valid scan selected for hotspot editing")
            return
        
        scan = scans[active_index]
        print(f"[DEBUG] Opening hotspot editor for scan {active_index + 1}")
        
        dlg = HotspotEditorDialog(scan, self.current_view, parent=self)
        if dlg.exec():
            print("[DEBUG] Hotspot editor completed, refreshing timeline")
            self.refresh_current_view()
    
    # ===== Cleanup =====
    def cleanup(self):
        """Cleanup resources"""
        print("[DEBUG] Cleaning up ScanTimelineWidget...")
        self._clear_timeline()
        self.data_manager.clear_layer_cache()
    
    # ===== Backward Compatibility =====
    def set_image_mode(self, mode: str):
        """Backward compatibility method"""
        print(f"[DEBUG] Legacy set_image_mode called with: {mode}")
        
        if mode == "Original":
            self.set_active_layers(["Original"])
        elif mode == "Segmentation":
            self.set_active_layers(["Original", "Segmentation"])
        elif mode == "Hotspot":
            self.set_active_layers(["Original", "Hotspot"])
        elif mode == "Both":
            self.set_active_layers(["Original", "Segmentation", "Hotspot"])
        else:
            self.set_active_layers([])