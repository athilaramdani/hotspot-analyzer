# features/spect_viewer/gui/mode_selector.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, 
    QSlider, QLabel, QGroupBox
)
from core.gui.ui_constants import GROUP_BOX_STYLE, OPACITY_SLIDER_STYLE, OPACITY_VALUE_LABEL_STYLE


class ModeSelector(QWidget):
    """
    Checkbox-based mode selector with layer opacity controls:
    - Individual checkboxes: Original, Segmentation, Hotspot, Both
    - Opacity sliders for each layer
    - "Both" checkbox toggles all others
    - Real-time updates
    """
    layers_changed = Signal(list)                 # List of active layer names
    opacity_changed = Signal(str, float)          # layer_name, opacity_value (0.0-1.0)
    
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        
        # State variables
        self._active_layers = []  # List of currently active layers
        self._opacities = {
            "Original": 1.0,
            "Segmentation": 0.7,
            "Hotspot": 0.8
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
        
        # Create checkboxes
        self._checkboxes = {}
        layer_options = ["Original", "Segmentation", "Hotspot", "All"]
        
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
        
        # Create sliders for each layer (excluding )
        slider_layers = ["Original", "Segmentation", "Hotspot"]
        
        for layer in slider_layers:
            # Layer container
            layer_container = QWidget()
            layer_layout_inner = QHBoxLayout(layer_container)
            layer_layout_inner.setContentsMargins(0, 0, 0, 0)
            
            # Layer label
            label = QLabel(f"{layer}:")
            label.setMinimumWidth(80)
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
        info_label = QLabel("""
        <b>Layer System (bottom → top):</b><br>
        • <span style="color: #6c757d;">Layer 1:</span> Original (base)<br>
        • <span style="color: #4CAF50;">Layer 2:</span> Segmentation (middle)<br>
        • <span style="color: #FF9800;">Layer 3:</span> Hotspot (top)<br>
        <br><i>Note: Black areas (#000000) in Segmentation and Hotspot<br>will be transparent for better viewing.</i>
        """)
        info_label.setStyleSheet("""
            QLabel {
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                padding: 8px;
                font-size: 10px;
                color: #6c757d;
            }
        """)
        main_layout.addWidget(info_label)
        
        main_layout.addStretch()
    
    def _connect_signals(self):
        """Connect all signals"""
        # Checkbox signals
        for layer, checkbox in self._checkboxes.items():
            checkbox.toggled.connect(lambda checked, l=layer: self._on_checkbox_toggled(l, checked))
        
        # Slider signals
        for layer, slider in self._sliders.items():
            slider.valueChanged.connect(lambda value, l=layer: self._on_opacity_changed(l, value))
    
    def _on_checkbox_toggled(self, layer: str, checked: bool):
        """Handle checkbox toggle"""
        print(f"[DEBUG] Checkbox {layer} toggled: {checked}")
        
        if layer == "All":
            self._handle__checkbox(checked)
        else:
            self._handle_individual_checkbox(layer, checked)
        
        # Update active layers and emit signal
        self._update_active_layers()
        self._update_slider_states()
    
    def _handle__checkbox(self, checked: bool):
        """Handle '' checkbox logic"""
        if checked:
            # When Both is checked, disable and uncheck all individual checkboxes
            for layer_name in ["Original", "Segmentation", "Hotspot"]:
                checkbox = self._checkboxes[layer_name]
                checkbox.blockSignals(True)  # Prevent recursive signals
                checkbox.setChecked(False)
                checkbox.setEnabled(False)
                checkbox.blockSignals(False)
        else:
            # When Both is unchecked, re-enable individual checkboxes
            for layer_name in ["Original", "Segmentation", "Hotspot"]:
                checkbox = self._checkboxes[layer_name]
                checkbox.setEnabled(True)
    
    def _handle_individual_checkbox(self, layer: str, checked: bool):
        """Handle individual checkbox logic"""
        # If any individual checkbox is checked, uncheck "Both"
        if checked:
            all_checkbox = self._checkboxes["All"]
            if all_checkbox.isChecked():
                all_checkbox.blockSignals(True)
                all_checkbox.setChecked(False)
                all_checkbox.blockSignals(False)
                # Re-enable all individual checkboxes
                for layer_name in ["Original", "Segmentation", "Hotspot"]:
                    self._checkboxes[layer_name].setEnabled(True)
    
    def _update_active_layers(self):
        """Update the list of active layers"""
        self._active_layers = []
        
        if self._checkboxes["All"].isChecked():
            # Both mode - show all three layers
            self._active_layers = ["Original", "Segmentation", "Hotspot"]
        else:
            # Individual mode - show only checked layers
            for layer in ["Original", "Segmentation", "Hotspot"]:
                if self._checkboxes[layer].isChecked():
                    self._active_layers.append(layer)
        
        print(f"[DEBUG] Active layers: {self._active_layers}")
        self.layers_changed.emit(self._active_layers)
    
    def _update_slider_states(self):
        """Update slider enabled/disabled states"""
        # Enable sliders only for active layers
        for layer, slider in self._sliders.items():
            is_active = layer in self._active_layers
            slider.setEnabled(is_active)
            
            # Update label opacity based on enabled state
            label = self._opacity_labels[layer]
            if is_active:
                label.setStyleSheet(OPACITY_VALUE_LABEL_STYLE)
            else:
                label.setStyleSheet(OPACITY_VALUE_LABEL_STYLE + "opacity: 0.5;")
    
    def _on_opacity_changed(self, layer: str, value: int):
        """Handle opacity slider changes"""
        opacity = value / 100.0
        self._opacities[layer] = opacity
        
        # Update label
        self._opacity_labels[layer].setText(f"{value}%")
        
        print(f"[DEBUG] {layer} opacity changed to: {opacity:.2f}")
        
        # Only emit signal if layer is active
        if layer in self._active_layers:
            self.opacity_changed.emit(layer, opacity)
    
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
        if layer in self._checkboxes:
            self._checkboxes[layer].setChecked(active)
    
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
            "Original": 1.0,
            "Segmentation": 0.7,
            "Hotspot": 0.8
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
        """Check if in 'Both' mode"""
        return self._checkboxes["All"].isChecked()
    
    def has_any_active_layers(self) -> bool:
        """Check if any layers are active"""
        return len(self._active_layers) > 0