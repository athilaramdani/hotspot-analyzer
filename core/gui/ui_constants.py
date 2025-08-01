# core/gui/ui_constants.py
"""Reusable Qt stylesheet constants for the Hotspot‑Analyzer GUI.

Enhanced version with support for new mode selector components including
radio buttons, sliders, and layered display indicators.

Import the constants you need, e.g.::

    from core.gui.ui_constants import PRIMARY_BUTTON_STYLE, RADIO_BUTTON_STYLE
    my_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
    my_radio.setStyleSheet(RADIO_BUTTON_STYLE)

This keeps styling centralised so multiple widgets share the same look.
"""

# ---------- Base helpers ----------
_BUTTON_BASE = (
    """
    QPushButton {
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
    }
    """
)

# ---------- Primary / action buttons ----------
PRIMARY_BUTTON_STYLE = _BUTTON_BASE + (
    """
    QPushButton {
        background-color: #4e73ff;
        color: white;
    }
    QPushButton:hover {
        background-color: #3e63e6;
    }
    QPushButton:pressed {
        background-color: #324fc7;
    }
    """
)

# ---------- Success / confirm buttons ----------
SUCCESS_BUTTON_STYLE = _BUTTON_BASE + (
    """
    QPushButton {
        background-color: #4CAF50;
        color: white;
    }
    QPushButton:hover {
        background-color: #45a049;
    }
    QPushButton:pressed {
        background-color: #3d8b40;
    }
    """
)

# ---------- Neutral / secondary buttons ----------
GRAY_BUTTON_STYLE = _BUTTON_BASE + (
    """
    QPushButton {
        background-color: #6c757d;
        color: white;
    }
    QPushButton:hover {
        background-color: #5a6268;
    }
    """
)

# ---------- Zoom buttons (orange) ----------
ZOOM_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #FF9800;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 3px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #F57C00;
    }
    QPushButton:pressed {
        background-color: #E65100;
    }
    """
)

# ---------- Scan‑selector buttons (purple, checkable) ----------
SCAN_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #9C27B0;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 3px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #7B1FA2;
    }
    QPushButton:checked {
        background-color: #4A148C;
    }
    QPushButton:pressed {
        background-color: #4A148C;
    }
    """
)

# ---------- NEW: Dialog-specific button styles ----------
DIALOG_IMPORT_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #2196F3;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover {
        background-color: #1976D2;
    }
    QPushButton:pressed {
        background-color: #0D47A1;
    }
    """
)

DIALOG_START_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover:enabled {
        background-color: #45a049;
    }
    QPushButton:pressed:enabled {
        background-color: #3d8b40;
    }
    QPushButton:disabled {
        background-color: #cccccc;
        color: #666666;
    }
    """
)

DIALOG_CANCEL_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #f44336;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover {
        background-color: #da190b;
    }
    QPushButton:pressed {
        background-color: #b71c1c;
    }
    """
)

DIALOG_REMOVE_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #f44336;
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: bold;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: #d32f2f;
    }
    """
)

# ---------- NEW: Dialog layout styles ----------
DIALOG_TITLE_STYLE = (
    """
    QLabel {
        font-size: 16px; 
        font-weight: bold; 
        margin: 10px 0px 5px 0px;
        color: #2c3e50;
        padding: 5px;
    }
    """
)

DIALOG_SUBTITLE_STYLE = (
    """
    QLabel {
        font-size: 12px; 
        color: #7f8c8d; 
        margin: 0px 0px 10px 0px;
        padding: 2px 5px;
        font-style: italic;
    }
    """
)

DIALOG_PANEL_HEADER_STYLE = (
    """
    QLabel {
        font-weight: bold; 
        padding: 8px;
        background-color: #ecf0f1;
        border: 1px solid #bdc3c7;
        border-radius: 4px 4px 0px 0px;
        color: #2c3e50;
        font-size: 13px;
    }
    """
)

DIALOG_FILE_LIST_STYLE = (
    """
    QListWidget {
        border: 1px solid #bdc3c7;
        border-radius: 0px 0px 4px 4px;
        background-color: #f8f9fa;
        alternate-background-color: #ffffff;
        selection-background-color: #e3f2fd;
        font-size: 12px;
    }
    QListWidget::item {
        padding: 4px;
        border-bottom: 1px solid #ecf0f1;
        min-height: 32px;
    }
    QListWidget::item:selected {
        background-color: #e3f2fd;
    }
    QListWidget::item:hover {
        background-color: #f5f5f5;
    }
    """
)

DIALOG_LOG_STYLE = (
    """
    QTextEdit {
        border: 1px solid #bdc3c7;
        border-radius: 0px 0px 4px 4px;
        background-color: #2c3e50;
        color: #ecf0f1;
        font-family: 'Courier New', 'Consolas', monospace;
        font-size: 12px;
        line-height: 1.4;
    }
    """
)

DIALOG_PROGRESS_BAR_STYLE = (
    """
    QProgressBar {
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        text-align: center;
        height: 22px;
        font-size: 12px;
        color: #2c3e50;
        font-weight: bold;
    }
    QProgressBar::chunk {
        background-color: #27ae60;
        border-radius: 3px;
        margin: 1px;
    }
    """
)

DIALOG_FRAME_STYLE = (
    """
    QFrame {
        border: 1px solid #bdc3c7;
        border-radius: 6px;
        background-color: #ffffff;
        margin: 2px;
    }
    """
)

# ---------- NEW: File item widget styles ----------
FILE_ITEM_NAME_STYLE = (
    """
    QLabel {
        color: #2c3e50; 
        font-weight: bold;
        font-size: 12px;
    }
    """
)

FILE_ITEM_PATH_STYLE = (
    """
    QLabel {
        color: #7f8c8d; 
        font-size: 10px;
        font-style: italic;
    }
    """
)

# ---------- NEW: Radio button styles ----------
RADIO_BUTTON_STYLE = (
    """
    QRadioButton {
        font-weight: bold;
        padding: 5px 8px;
        spacing: 8px;
    }
    QRadioButton::indicator {
        width: 16px;
        height: 16px;
    }
    QRadioButton::indicator:unchecked {
        border: 2px solid #ccc;
        border-radius: 9px;
        background: white;
    }
    QRadioButton::indicator:unchecked:hover {
        border: 2px solid #4e73ff;
        background: #f0f4ff;
    }
    QRadioButton::indicator:checked {
        border: 2px solid #4e73ff;
        border-radius: 9px;
        background: #4e73ff;
    }
    QRadioButton::indicator:checked:hover {
        background: #3e63e6;
        border: 2px solid #3e63e6;
    }
    """
)

# ---------- NEW: Slider styles ----------
OPACITY_SLIDER_STYLE = (
    """
    QSlider::groove:horizontal {
        border: 1px solid #bbb;
        background: #f8f9fa;
        height: 8px;
        border-radius: 4px;
        margin: 2px 0;
    }
    QSlider::sub-page:horizontal {
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 #4e73ff, stop: 1 #7da3ff);
        border: 1px solid #777;
        height: 8px;
        border-radius: 4px;
    }
    QSlider::add-page:horizontal {
        background: #e9ecef;
        border: 1px solid #777;
        height: 8px;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        background: #4e73ff;
        border: 2px solid #ffffff;
        width: 20px;
        height: 20px;
        margin: -6px 0;
        border-radius: 10px;
        box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.2);
    }
    QSlider::handle:horizontal:hover {
        background: #3e63e6;
        border: 2px solid #ffffff;
    }
    QSlider::handle:horizontal:pressed {
        background: #324fc7;
    }
    """
)

# ---------- NEW: Group box styles ----------
GROUP_BOX_STYLE = (
    """
    QGroupBox {
        font-weight: bold;
        border: 2px solid #e9ecef;
        border-radius: 6px;
        margin-top: 8px;
        padding-top: 4px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 8px 0 8px;
        background: white;
        color: #495057;
    }
    """
)

# ---------- NEW: Info/status label styles ----------
INFO_LABEL_STYLE = (
    """
    QLabel {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 4px;
        padding: 8px;
        font-size: 11px;
        color: #6c757d;
    }
    """
)

# ---------- NEW: Opacity value label styles ----------
OPACITY_VALUE_LABEL_STYLE = (
    """
    QLabel {
        border: 1px solid #dee2e6;
        border-radius: 3px;
        padding: 4px 6px;
        background: #f8f9fa;
        font-weight: bold;
        color: #495057;
        font-size: 12px;
        min-width: 35px;
        max-width: 45px;
    }
    """
)

# ---------- NEW: Layer indicator styles ----------
LAYER_INDICATOR_STYLES = {
    "Original": (
        """
        QLabel {
            background: #6c757d;
            color: white;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: bold;
        }
        """
    ),
    "Segmentation": (
        """
        QLabel {
            background: #4CAF50;
            color: white;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: bold;
        }
        """
    ),
    "Hotspot": (
        """
        QLabel {
            background: #FF9800;
            color: white;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: bold;
        }
        """
    ),
    "Both": (
        """
        QLabel {
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 #6c757d, stop: 0.33 #4CAF50, stop: 0.66 #FF9800, stop: 1 #4e73ff);
            color: white;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: bold;
        }
        """
    )
}

# ---------- NEW: Disabled control styles ----------
DISABLED_CONTROL_STYLE = (
    """
    QSlider {
        opacity: 0.5;
    }
    QSlider::groove:horizontal {
        background: #f1f3f4;
    }
    QSlider::sub-page:horizontal {
        background: #cbd3da;
    }
    QSlider::handle:horizontal {
        background: #adb5bd;
    }
    """
)

# ---------- Color constants for programmatic use ----------
class Colors:
    PRIMARY = "#4e73ff"
    PRIMARY_HOVER = "#3e63e6"
    PRIMARY_PRESSED = "#324fc7"
    
    SUCCESS = "#4CAF50"
    SUCCESS_HOVER = "#45a049"
    
    WARNING = "#FF9800"
    WARNING_HOVER = "#F57C00"
    
    SECONDARY = "#6c757d"
    SECONDARY_HOVER = "#5a6268"
    
    LIGHT_GRAY = "#f8f9fa"
    MEDIUM_GRAY = "#e9ecef"
    DARK_GRAY = "#495057"
    
    BORDER_LIGHT = "#dee2e6"
    BORDER_MEDIUM = "#ccc"
    
    # Layer-specific colors
    ORIGINAL_COLOR = "#6c757d"
    SEGMENTATION_COLOR = "#4CAF50"
    HOTSPOT_COLOR = "#FF9800"
    
    # Dialog-specific colors
    DIALOG_BG = "#ffffff"
    DIALOG_BORDER = "#bdc3c7"
    DIALOG_TEXT = "#2c3e50"
    DIALOG_SUBTITLE = "#7f8c8d"

# ---------- Text truncation utility ----------
def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if too long"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

# ---------- Utility functions ----------
def get_layer_color(layer_name: str) -> str:
    """Get the appropriate color for a layer"""
    color_map = {
        "Original": Colors.ORIGINAL_COLOR,
        "Segmentation": Colors.SEGMENTATION_COLOR,
        "Hotspot": Colors.HOTSPOT_COLOR
    }
    return color_map.get(layer_name, Colors.SECONDARY)

def create_layer_indicator_style(layer_name: str, opacity: float = 1.0) -> str:
    """Create a dynamic layer indicator style with opacity"""
    color = get_layer_color(layer_name)
    return f"""
    QLabel {{
        background: {color};
        color: white;
        border-radius: 3px;
        padding: 2px 6px;
        font-size: 10px;
        font-weight: bold;
        opacity: {opacity:.2f};
    }}
    """

__all__ = [
    "PRIMARY_BUTTON_STYLE",
    "SUCCESS_BUTTON_STYLE", 
    "GRAY_BUTTON_STYLE",
    "ZOOM_BUTTON_STYLE",
    "SCAN_BUTTON_STYLE",
    "RADIO_BUTTON_STYLE",
    "OPACITY_SLIDER_STYLE",
    "GROUP_BOX_STYLE",
    "INFO_LABEL_STYLE",
    "OPACITY_VALUE_LABEL_STYLE",
    "LAYER_INDICATOR_STYLES",
    "DISABLED_CONTROL_STYLE",
    # Dialog-specific styles
    "DIALOG_IMPORT_BUTTON_STYLE",
    "DIALOG_START_BUTTON_STYLE", 
    "DIALOG_CANCEL_BUTTON_STYLE",
    "DIALOG_REMOVE_BUTTON_STYLE",
    "DIALOG_TITLE_STYLE",
    "DIALOG_SUBTITLE_STYLE",
    "DIALOG_PANEL_HEADER_STYLE",
    "DIALOG_FILE_LIST_STYLE",
    "DIALOG_LOG_STYLE",
    "DIALOG_PROGRESS_BAR_STYLE",
    "DIALOG_FRAME_STYLE",
    "FILE_ITEM_NAME_STYLE",
    "FILE_ITEM_PATH_STYLE",
    # Utilities
    "Colors",
    "get_layer_color",
    "create_layer_indicator_style",
    "truncate_text"
]