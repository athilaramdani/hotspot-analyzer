# features/spect_viewer/gui/mode_selector.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, 
    QSlider, QLabel, QGroupBox
)
import logging
from core.gui.ui_constants import GROUP_BOX_STYLE, OPACITY_SLIDER_STYLE, OPACITY_VALUE_LABEL_STYLE
OPACITY_SLIDER_STYLE_DISABLED = """
    QSlider::groove:horizontal {
        /* Bentuk, border, tinggi, dan radius sama persis dengan style aktif */
        border: 1px solid #bbb;
        background: #f8f9fa;
        height: 8px;
        border-radius: 4px;
        margin: 2px 0;
    }
    QSlider::sub-page:horizontal {
        /* Bagian "terisi" dengan gradien abu-abu */
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 #b0b0b0, stop: 1 #cccccc);
        border: 1px solid #777;
        height: 8px;
        border-radius: 4px;
    }
    QSlider::add-page:horizontal {
        /* Bagian "kosong" dengan warna abu-abu terang */
        background: #e9ecef;
        border: 1px solid #777;
        height: 8px;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        /* Handle abu-abu dengan border putih dan bayangan, sama seperti aktif */
        background: #b0b0b0;
        border: 2px solid #ffffff;
        width: 20px;
        height: 20px;
        margin: -6px 0;
        border-radius: 10px;
        box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.2);
    }
    QSlider::handle:horizontal:hover {
        /* Efek hover yang lebih gelap sedikit */
        background: #a0a0a0;
        border: 2px solid #ffffff;
    }
    QSlider::handle:horizontal:pressed {
        /* Efek saat ditekan */
        background: #888888;
    }
"""


class ModeSelector(QWidget):
    """
    Checkbox-based mode selector with layer opacity controls:
    - Individual checkboxes: Original, Segmentation, Hotspot Layer, Hotspot Bounding Box, All
    - Opacity sliders for each layer
    - "All" checkbox toggles all others
    - Real-time updates
    """
    layers_changed = Signal(list)                 # List of active layer names
    opacity_changed = Signal(str, float)          # layer_name, opacity_value (0.0-1.0)
    
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        
        # State variables
        self._active_layers = []  # List of currently active layers
        self._opacities = {
            "Image": 1.0,
            "Segmentation": 0.4,      # Updated to 40%
            "Hotspot": 0.5,           # Updated to 50%
            "HotspotBBox": 1.0
        }
        
        self._build_ui()
        self._connect_signals()
        
    def _build_ui(self):
        """Build the UI with checkboxes and opacity sliders"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)
        
        # === Layer Selection Group ===
        layer_group = QGroupBox("Layer Selection")
        layer_group.setStyleSheet(GROUP_BOX_STYLE)
        layer_layout = QVBoxLayout(layer_group)
        
        # Create checkboxes - UPDATED with new options
        self._checkboxes = {}
        self._individual_layers = ["Image", "Segmentation", "Hotspot"] 
        layer_options =  ["All"] + self._individual_layers
        
        for layer in layer_options:
            checkbox = QCheckBox(layer)
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-weight: bold;
                    padding: 5px;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                }
                QCheckBox::indicator:unchecked {
                    border: 2px solid #ccc;
                    border-radius: 3px;
                    background: white;
                }
                QCheckBox::indicator:unchecked:hover {
                    border: 2px solid #4e73ff;
                    background: #f0f4ff;
                }
                QCheckBox::indicator:checked {
                    border: 2px solid #4e73ff;
                    border-radius: 3px;
                    background: #4e73ff;
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
                }
                QCheckBox::indicator:checked:hover {
                    background: #3e63e6;
                    border: 2px solid #3e63e6;
                }
                QCheckBox:disabled {
                    color: #adb5bd;
                }
                QCheckBox::indicator:disabled {
                    border: 2px solid #adb5bd;
                    background: #f8f9fa;
                }
            """)
            
            self._checkboxes[layer] = checkbox
            layer_layout.addWidget(checkbox)
        
        main_layout.addWidget(layer_group)
        
        # === Opacity Controls Group ===
        opacity_group = QGroupBox("Layer Opacity Controls")
        opacity_group.setStyleSheet(GROUP_BOX_STYLE)
        opacity_layout = QVBoxLayout(opacity_group)
        
        self._sliders = {}
        self._opacity_labels = {}
        
        # Create sliders for each layer - UPDATED with new layer
        slider_layers = ["Image", "Segmentation", "Hotspot"]  # Removed HotspotBBox
        slider_labels = ["Image", "Segmentation", "Hotspot"]  # Removed Hotspot BBox
        
        for layer, display_name in zip(slider_layers, slider_labels):
            # Layer container
            layer_container = QWidget()
            layer_layout_inner = QHBoxLayout(layer_container)
            layer_layout_inner.setContentsMargins(0, 0, 0, 0)
            
            # Layer label
            label = QLabel(f"{display_name}:")
            label.setMinimumWidth(90)  # Slightly wider for "Hotspot BBox"
            label.setStyleSheet("font-weight: bold; color: #495057;")
            
            # Slider
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(int(self._opacities[layer] * 100))
            slider.setStyleSheet(OPACITY_SLIDER_STYLE)
            
            # Opacity value label
            opacity_label = QLabel(f"{int(self._opacities[layer] * 100)}%")
            opacity_label.setMinimumWidth(35)
            opacity_label.setAlignment(Qt.AlignCenter)
            opacity_label.setStyleSheet(OPACITY_VALUE_LABEL_STYLE)
            
            # Add to layout
            layer_layout_inner.addWidget(label)
            layer_layout_inner.addWidget(slider, 1)  # Stretch factor 1
            layer_layout_inner.addWidget(opacity_label)
            
            # Store references
            self._sliders[layer] = slider
            self._opacity_labels[layer] = opacity_label
            
            opacity_layout.addWidget(layer_container)
        
        main_layout.addWidget(opacity_group)
        
        # === Layer Information ===
        # info_label = QLabel("""
        # <b>Layer System (bottom → top):</b><br>
        # • <span style="color: #6c757d;">Layer 1:</span> Original (base)<br>
        # • <span style="color: #4CAF50;">Layer 2:</span> Segmentation (middle)<br>
        # • <span style="color: #FF9800;">Layer 3:</span> Hotspot (overlay)<br>
        # • <span style="color: #f44336;">Layer 4:</span> Hotspot BBox (overlay)<br>
        # <br><i>Note: Hotspot BBox shows XML bounding boxes.<br>Hotspot shows processed hotspot mask.</i>
        # """)
        # info_label.setStyleSheet("""
        #     QLabel {
        #         background: #f8f9fa;
        #         border: 1px solid #e9ecef;
        #         border-radius: 4px;
        #         padding: 8px;
        #         font-size: 10px;
        #         color: #6c757d;
        #     }
        # """)
        # main_layout.addWidget(info_label)
        
        main_layout.addStretch()
    
    def _connect_signals(self):
        """Connect all signals with separate logic for 'All' and individual layers."""
        # Hubungkan checkbox 'All' ke slot khususnya
        self._checkboxes["All"].toggled.connect(self._on_all_toggled)
        
        # Hubungkan checkbox individual ke slot khususnya
        for layer in self._individual_layers:
            self._checkboxes[layer].toggled.connect(self._on_layer_toggled)
        
        # Slider signals (tidak berubah)
        for layer, slider in self._sliders.items():
            slider.valueChanged.connect(lambda value, l=layer: self._on_opacity_changed(l, value))
        
    # def _on_checkbox_toggled(self, layer: str, checked: bool):
    #     """Handle checkbox toggle"""
    #     logging.info(f"[DEBUG] Checkbox {layer} toggled: {checked}")
        
    #     if layer == "All":
    #         self._handle_all_checkbox(checked)
    #     else:
    #         self._handle_individual_checkbox(layer, checked)
        
    #     # Update active layers and emit signal
    #     self._update_active_layers()
    #     self._update_slider_states()
    
    # def _handle_all_checkbox(self, checked: bool):
    #     """Handle 'All' checkbox logic"""
    #     if checked:
    #         # When All is checked, disable and uncheck all individual checkboxes
    #         for layer_name in ["Image", "Segmentation", "Hotspot"]:  # Removed Hotspot BBox
    #             checkbox = self._checkboxes[layer_name]
    #             checkbox.blockSignals(True)  # Prevent recursive signals
    #             checkbox.setChecked(False)
    #             checkbox.setEnabled(False)
    #             checkbox.blockSignals(False)
    #     else:
    #         # When All is unchecked, re-enable individual checkboxes
    #         for layer_name in ["Image", "Segmentation", "Hotspot"]:  # Removed Hotspot BBox
    #             checkbox = self._checkboxes[layer_name]
    #             checkbox.setEnabled(True)
    
    # def _handle_individual_checkbox(self, layer: str, checked: bool):
    #     """Handle individual checkbox logic"""
    #     # If any individual checkbox is checked, uncheck "All"
    #     if checked:
    #         all_checkbox = self._checkboxes["All"]
    #         if all_checkbox.isChecked():
    #             all_checkbox.blockSignals(True)
    #             all_checkbox.setChecked(False)
    #             all_checkbox.blockSignals(False)
    #             # Re-enable all individual checkboxes
    #             for layer_name in ["Image", "Segmentation", "Hotspot"]:  # Removed Hotspot BBox
    #                 self._checkboxes[layer_name].setEnabled(True)
    def _on_all_toggled(self, checked: bool):
        """Dipanggil HANYA saat checkbox 'All' diubah."""
        # Jika 'All' dicentang, kita paksa semua layer lain untuk ikut tercentang.
        if checked:
            for layer in self._individual_layers:
                self._checkboxes[layer].blockSignals(True)  # Cegah infinite loop
                self._checkboxes[layer].setChecked(True)
                self._checkboxes[layer].blockSignals(False)

        # Perbarui state dan kirim sinyal setelah semua perubahan selesai
        self._update_and_emit_all_states()

    def _on_layer_toggled(self):
        """Dipanggil saat checkbox individual (Image, Seg, Hotspot) diubah."""
        # Cek apakah semua checkbox individual tercentang
        all_checked = all(self._checkboxes[layer].isChecked() for layer in self._individual_layers)
        
        # Sinkronkan status checkbox 'All' tanpa memicu sinyal balik
        self._checkboxes["All"].blockSignals(True)
        self._checkboxes["All"].setChecked(all_checked)
        self._checkboxes["All"].blockSignals(False)
        
        # Perbarui state dan kirim sinyal
        self._update_and_emit_all_states()
    def _update_and_emit_all_states(self):
        """
        Helper untuk menghitung ulang layer aktif, memperbarui UI (slider),
        dan mengirim sinyal 'layers_changed'.
        """
        self._active_layers = []
        for layer in self._individual_layers:
            if self._checkboxes[layer].isChecked():
                self._active_layers.append(layer)

        logging.info(f"[DEBUG] Active layers: {self._active_layers}")
        self.layers_changed.emit(self._active_layers)
        self._update_slider_states() # Panggil pembaruan state slider di sini
        
    def _update_slider_states(self):
        """Update slider enabled/disabled states"""
        # Map display layers to internal layers
        layer_mapping = {
            "Image": "Image",
            "Segmentation": "Segmentation", 
            "Hotspot": "Hotspot",
            "HotspotBBox": "HotspotBBox"
        }
        
        # Enable sliders only for active layers
        for slider_key, slider in self._sliders.items():
            is_active = layer_mapping[slider_key] in self._active_layers
            slider.setEnabled(is_active)
            
            # Update label opacity based on enabled state
            label = self._opacity_labels[slider_key]
            if is_active:
                # Jika aktif, gunakan style normal dan label terang
                slider.setStyleSheet(OPACITY_SLIDER_STYLE)
                label.setStyleSheet(OPACITY_VALUE_LABEL_STYLE)
            else:
                # Jika tidak aktif, gunakan style abu-abu dan label redup
                slider.setStyleSheet(OPACITY_SLIDER_STYLE_DISABLED)
                label.setStyleSheet(OPACITY_VALUE_LABEL_STYLE + " color: #adb5bd;")
        
    def _on_opacity_changed(self, layer: str, value: int):
        """Handle opacity slider changes"""
        opacity = value / 100.0
        self._opacities[layer] = opacity
        
        # Update label
        self._opacity_labels[layer].setText(f"{value}%")
        
        logging.info(f"[DEBUG] {layer} opacity changed to: {opacity:.2f}")
        
        # Map slider layer to active layer name for emission
        layer_mapping = {
            "Image": "Image",
            "Segmentation": "Segmentation",
            "Hotspot": "Hotspot", 
            "HotspotBBox": "HotspotBBox"
        }
        
        # Only emit signal if layer is active
        if layer_mapping[layer] in self._active_layers:
            self.opacity_changed.emit(layer_mapping[layer], opacity)
    
    # === Public API ===
    def get_active_layers(self) -> list:
        """Get list of currently active layers"""
        return self._active_layers.copy()
    
    def get_opacity(self, layer: str) -> float:
        """Get opacity for specific layer"""
        return self._opacities.get(layer, 1.0)
    
    def get_all_opacities(self) -> dict:
        """Get all layer opacities"""
        return self._opacities.copy()
    
    def set_layer_active(self, layer: str, active: bool):
        """Programmatically set layer active state"""
        # Handle mapping from internal layer names to checkbox names
        checkbox_mapping = {
            "Image": "Image",
            "Segmentation": "Segmentation",
            "Hotspot": "Hotspot",
            "HotspotBBox": "Hotspot BBox",
            "All": "All"
        }
        
        checkbox_name = checkbox_mapping.get(layer, layer)
        if checkbox_name in self._checkboxes:
            self._checkboxes[checkbox_name].setChecked(active)
    
    def set_opacity(self, layer: str, opacity: float):
        """Programmatically set layer opacity"""
        if layer in self._sliders:
            value = int(opacity * 100)
            self._sliders[layer].setValue(value)
            self._opacities[layer] = opacity
    
    def reset_to_defaults(self):
        """Reset to default values"""
        # Uncheck all checkboxes
        for checkbox in self._checkboxes.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.setEnabled(True)
            checkbox.blockSignals(False)
        
        # Reset opacities
        self._opacities = {
            "Image": 1.0,
            "Segmentation": 0.4,
            "Hotspot": 0.5,
            "HotspotBBox": 1.0
        }
        
        # Update sliders
        for layer, opacity in self._opacities.items():
            if layer in self._sliders:
                self._sliders[layer].setValue(int(opacity * 100))
                self._opacity_labels[layer].setText(f"{int(opacity * 100)}%")
        
        # Update state
        self._active_layers = []
        self._update_slider_states()
        self.layers_changed.emit(self._active_layers)
    
    def is_both_mode(self) -> bool:
        """Check if in 'All' mode"""
        return self._checkboxes["All"].isChecked()
    
    def has_any_active_layers(self) -> bool:
        """Check if any layers are active"""
        return len(self._active_layers) > 0