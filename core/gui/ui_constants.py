# core/gui/ui_constants.py - UPDATED with BSI styles
"""Reusable Qt stylesheet constants for the Hotspot‑Analyzer GUI.

Enhanced version with support for BSI quantification components including
canvas styles, panel layouts, and quantification-specific UI elements.

Import the constants you need, e.g.::

    from core.gui.ui_constants import PRIMARY_BUTTON_STYLE, BSI_PANEL_STYLE
    my_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
    my_panel.setStyleSheet(BSI_PANEL_STYLE)

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

# ---------- Primary / action buttons (from UI guide) ----------
PRIMARY_BUTTON_STYLE = _BUTTON_BASE + (
    """
    QPushButton {
        background-color: #3B82F6;
        color: white;
    }
    QPushButton:hover {
        background-color: #2563EB;
    }
    QPushButton:pressed {
        background-color: #1D4ED8;
    }
    """
)

# ---------- Destructive / danger buttons (from UI guide) ----------
DANGER_BUTTON_STYLE = _BUTTON_BASE + (
    """
    QPushButton {
        background-color: #EF4444;
        color: white;
    }
    QPushButton:hover {
        background-color: #DC2626;
    }
    QPushButton:pressed {
        background-color: #B91C1C;
    }
    """
)

# ---------- Success / confirm buttons (from UI guide) ----------
SUCCESS_BUTTON_STYLE = _BUTTON_BASE + (
    """
    QPushButton {
        background-color: #22C55E;
        color: white;
    }
    QPushButton:hover {
        background-color: #16A34A;
    }
    QPushButton:pressed {
        background-color: #15803D;
    }
    """
)

# ---------- Neutral / secondary buttons (from UI guide) ----------
GRAY_BUTTON_STYLE = _BUTTON_BASE + (
    """
    QPushButton {
        background-color: #E5E7EB;
        color: #495057;
    }
    QPushButton:hover {
        background-color: #D1D5DB;
    }
    QPushButton:pressed {
        background-color: #A1A1AA;
    }
    QPushButton:disabled {
        background-color: #F3F4F6;
        color: #A1A1AA;
    }
    """
)

# ---------- Other neutral buttons (to match medical theme) ----------
ZOOM_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #A1A1AA;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 3px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #7D7D83;
    }
    QPushButton:pressed {
        background-color: #616166;
    }
    """
)

# ---------- Scan‑selector buttons (neutral, checkable) ----------
SCAN_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #E5E7EB;
        color: #495057;
        border: none;
        padding: 6px 12px;
        border-radius: 3px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #D1D5DB;
    }
    QPushButton:checked {
        background-color: #A1A1AA;
        color: white;
    }
    QPushButton:pressed {
        background-color: #A1A1AA;
    }
    """
)

# ---------- NEW: Dialog-specific button styles ----------
DIALOG_IMPORT_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #3B82F6;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover {
        background-color: #2563EB;
    }
    QPushButton:pressed {
        background-color: #1D4ED8;
    }
    """
)

DIALOG_START_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #22C55E;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover:enabled {
        background-color: #16A34A;
    }
    QPushButton:pressed:enabled {
        background-color: #15803D;
    }
    QPushButton:disabled {
        background-color: #F3F4F6;
        color: #A1A1AA;
        border: 1px solid #D1D5DB;
    }
    """
)

DIALOG_DISABLED_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #F3F4F6;
        color: #A1A1AA;
        border: 1px solid #D1D5DB;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 13px;
        font-weight: bold;
    }
    """
)

DIALOG_CANCEL_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #EF4444;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover {
        background-color: #DC2626;
    }
    QPushButton:pressed {
        background-color: #B91C1C;
    }
    """
)

DIALOG_REMOVE_BUTTON_STYLE = (
    """
    QPushButton {
        background-color: #EF4444;
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: bold;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: #DC2626;
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
        selection-background-color: #E5E7EB;
        font-size: 12px;
    }
    QListWidget::item {
        padding: 4px;
        border-bottom: 1px solid #ecf0f1;
        min-height: 32px;
    }
    QListWidget::item:selected {
        background-color: #D1D5DB;
    }
    QListWidget::item:hover {
        background-color: #F3F4F6;
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
        background-color: #22C55E;
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
        border: 2px solid #D1D5DB;
        border-radius: 9px;
        background: white;
    }
    QRadioButton::indicator:unchecked:hover {
        border: 2px solid #3B82F6;
        background: #EFF6FF;
    }
    QRadioButton::indicator:checked {
        border: 2px solid #3B82F6;
        border-radius: 9px;
        background: #3B82F6;
    }
    QRadioButton::indicator:checked:hover {
        background: #2563EB;
        border: 2px solid #2563EB;
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
            stop: 0 #3B82F6, stop: 1 #5F96FF);
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
        background: #3B82F6;
        border: 2px solid #ffffff;
        width: 20px;
        height: 20px;
        margin: -6px 0;
        border-radius: 10px;
        box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.2);
    }
    QSlider::handle:horizontal:hover {
        background: #2563EB;
        border: 2px solid #ffffff;
    }
    QSlider::handle:horizontal:pressed {
        background: #1D4ED8;
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

# ---------- NEW: BSI-specific styles ----------
BSI_PANEL_STYLE = (
    """
    QWidget {
        background: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 6px;
    }
    """
)

BSI_TITLE_STYLE = (
    """
    QLabel {
        font-size: 16px;
        font-weight: bold;
        color: #2c3e50;
        padding: 8px 12px;
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    """
)

BSI_SCORE_LABEL_STYLE = (
    """
    QLabel {
        font-size: 18px;
        font-weight: bold;
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        border: 2px solid #dee2e6;
        margin: 4px 0px;
    }
    """
)

BSI_SCORE_HIGH_STYLE = (
    """
    QLabel {
        font-size: 18px;
        font-weight: bold;
        color: #EF4444;
        background: #FEF2F2;
        border: 2px solid #FCA5A5;
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        margin: 4px 0px;
    }
    """
)

BSI_SCORE_MEDIUM_STYLE = (
    """
    QLabel {
        font-size: 18px;
        font-weight: bold;
        color: #FBBF24;
        background: #FFFBEB;
        border: 2px solid #FDE68A;
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        margin: 4px 0px;
    }
    """
)

BSI_SCORE_LOW_STYLE = (
    """
    QLabel {
        font-size: 18px;
        font-weight: bold;
        color: #22C55E;
        background: #F0FDF4;
        border: 2px solid #B7E4C7;
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        margin: 4px 0px;
    }
    """
)

BSI_INFO_ITEM_STYLE = (
    """
    QLabel {
        font-size: 12px;
        color: #495057;
        padding: 6px 8px;
        margin: 2px 0px;
        background: #f8f9fa;
        border-radius: 4px;
        border: 1px solid #e9ecef;
    }
    """
)

BSI_COMMENTS_STYLE = (
    """
    QTextEdit {
        background: #ffffff;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        padding: 12px;
        font-size: 11px;
        color: #495057;
        line-height: 1.5;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    """
)

BSI_CANVAS_FRAME_STYLE = (
    """
    QFrame {
        background: #ffffff;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 8px;
    }
    """
)

BSI_EXPORT_BUTTON_STYLE = _BUTTON_BASE + (
    """
    QPushButton {
        background-color: #A1A1AA;
        color: white;
        font-size: 11px;
        padding: 6px 12px;
    }
    QPushButton:hover {
        background-color: #7D7D83;
    }
    QPushButton:pressed {
        background-color: #616166;
    }
    QPushButton:disabled {
        background-color: #F3F4F6;
        color: #A1A1AA;
    }
    """
)

BSI_STATUS_SUCCESS_STYLE = (
    """
    QLabel {
        font-size: 10px;
        color: #16A34A;
        font-style: italic;
        font-weight: bold;
        padding: 4px 8px;
        background: #F0FDF4;
        border: 1px solid #B7E4C7;
        border-radius: 3px;
    }
    """
)

BSI_STATUS_ERROR_STYLE = (
    """
    QLabel {
        font-size: 10px;
        color: #DC2626;
        font-style: italic;
        font-weight: bold;
        padding: 4px 8px;
        background: #FEF2F2;
        border: 1px solid #FCA5A5;
        border-radius: 3px;
    }
    """
)

BSI_STATUS_WARNING_STYLE = (
    """
    QLabel {
        font-size: 10px;
        color: #856404;
        font-style: italic;
        font-weight: bold;
        padding: 4px 8px;
        background: #fff3cd;
        border: 1px solid #ffeeba;
        border-radius: 3px;
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
            background: #22C55E;
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
            background: #FBBF24;
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
                stop: 0 #6c757d, stop: 0.33 #22C55E, stop: 0.66 #FBBF24, stop: 1 #3B82F6);
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
    PRIMARY = "#3B82F6"
    PRIMARY_HOVER = "#2563EB"
    PRIMARY_PRESSED = "#1D4ED8"
    
    SUCCESS = "#22C55E"
    SUCCESS_HOVER = "#16A34A"
    SUCCESS_PRESSED = "#15803D"
    
    WARNING = "#FBBF24"
    WARNING_HOVER = "#F59E0B"
    
    DANGER = "#EF4444"
    DANGER_HOVER = "#DC2626"
    DANGER_PRESSED = "#B91C1C"
    
    SECONDARY = "#E5E7EB"
    SECONDARY_HOVER = "#D1D5DB"
    SECONDARY_PRESSED = "#A1A1AA"
    
    LIGHT_GRAY = "#F3F4F6"
    MEDIUM_GRAY = "#A1A1AA"
    DARK_GRAY = "#495057"
    
    BORDER_LIGHT = "#dee2e6"
    BORDER_MEDIUM = "#ccc"
    
    # Layer-specific colors
    ORIGINAL_COLOR = "#6c757d"
    SEGMENTATION_COLOR = "#22C55E"
    HOTSPOT_COLOR = "#FBBF24"
    
    # Dialog-specific colors
    DIALOG_BG = "#ffffff"
    DIALOG_BORDER = "#bdc3c7"
    DIALOG_TEXT = "#2c3e50"
    DIALOG_SUBTITLE = "#7f8c8d"
    
    # BSI-specific colors
    BSI_HIGH = "#EF4444"
    BSI_MEDIUM = "#FBBF24"
    BSI_LOW = "#22C55E"
    BSI_BACKGROUND = "#f8f9fa"
    BSI_BORDER = "#e9ecef"

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

def get_bsi_score_style(bsi_score: float) -> str:
    """Get appropriate style for BSI score based on value"""
    if bsi_score > 5.0:
        return BSI_SCORE_HIGH_STYLE
    elif bsi_score > 2.0:
        return BSI_SCORE_MEDIUM_STYLE
    else:
        return BSI_SCORE_LOW_STYLE

def get_bsi_status_style(status_type: str) -> str:
    """Get appropriate status style for BSI panel"""
    status_map = {
        "success": BSI_STATUS_SUCCESS_STYLE,
        "error": BSI_STATUS_ERROR_STYLE,
        "warning": BSI_STATUS_WARNING_STYLE
    }
    return status_map.get(status_type, BSI_STATUS_WARNING_STYLE)

# ---------- BSI-specific utility functions ----------
def format_bsi_score(bsi_score: float) -> str:
    """Format BSI score with appropriate precision"""
    return f"{bsi_score:.2f}%"

def get_bsi_severity_text(bsi_score: float) -> str:
    """Get severity text for BSI score"""
    if bsi_score > 8.0:
        return "Very High"
    elif bsi_score > 5.0:
        return "High"
    elif bsi_score > 2.0:
        return "Moderate"
    elif bsi_score > 1.0:
        return "Mild"
    else:
        return "Low"

def get_bsi_severity_color(bsi_score: float) -> str:
    """Get color for BSI severity"""
    if bsi_score > 5.0:
        return Colors.BSI_HIGH
    elif bsi_score > 2.0:
        return Colors.BSI_MEDIUM
    else:
        return Colors.BSI_LOW

# ---------- View Selector Dialog Styles ----------
VIEW_SELECTOR_TITLE_STYLE = (
    """
    QLabel {
        font-size: 18px; 
        font-weight: bold; 
        margin: 10px 0px 8px 0px;
        color: #2c3e50;
        padding: 8px;
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 #f8f9fa, stop: 1 #e9ecef);
        border-radius: 6px;
    }
    """
)

VIEW_SELECTOR_INSTRUCTIONS_STYLE = (
    """
    QLabel {
        background: #F0F4FF;
        border: 1px solid #D1D5DB;
        border-radius: 6px;
        padding: 12px;
        font-size: 12px;
        color: #1D4ED8;
        line-height: 1.5;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    """
)

FRAME_PREVIEW_STYLE = (
    """
    QLabel {
        border: 2px solid #dee2e6;
        border-radius: 8px;
        background: #f8f9fa;
        padding: 4px;
    }
    QLabel:hover {
        border-color: #3B82F6;
        background: #f0f4ff;
    }
    """
)

FRAME_WIDGET_STYLE = (
    """
    QWidget {
        background: white;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 8px;
        margin: 4px;
    }
    QWidget:hover {
        border-color: #3B82F6;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.1);
    }
    """
)

DICOM_FILE_HEADER_STYLE = (
    """
    QFrame {
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 #f8f9fa, stop: 1 #ffffff);
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 8px;
        margin-bottom: 8px;
    }
    """
)

VIEW_CHECKBOX_STYLE = (
    """
    QCheckBox {
        font-size: 12px;
        font-weight: bold;
        color: #495057;
        spacing: 6px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 4px;
    }
    QCheckBox::indicator:unchecked {
        border: 2px solid #D1D5DB;
        background: white;
    }
    QCheckBox::indicator:unchecked:hover {
        border: 2px solid #3B82F6;
        background: #f0f4ff;
    }
    QCheckBox::indicator:checked {
        border: 2px solid #3B82F6;
        background: #3B82F6;
        image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xMC42IDEuNkw0LjYwMDA1IDcuNkwxLjQgNC40IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
    }
    QCheckBox::indicator:checked:hover {
        background: #2563EB;
        border: 2px solid #2563EB;
    }
    """
)

AUTO_DETECTED_BADGE_STYLE = (
    """
    QLabel {
        background: #F0FDF4;
        color: #16A34A;
        border: 1px solid #B7E4C7;
        border-radius: 12px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: bold;
        max-width: 80px;
    }
    """
)

MANUAL_REQUIRED_BADGE_STYLE = (
    """
    QLabel {
        background: #fff3cd;
        color: #856404;
        border: 1px solid #ffeeba;
        border-radius: 12px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: bold;
        max-width: 120px;
    }
    """
)

VALIDATION_STATUS_SUCCESS_STYLE = (
    """
    QLabel {
        color: #22C55E;
        font-size: 12px;
        font-weight: bold;
        padding: 4px 8px;
        background: #F0FDF4;
        border: 1px solid #B7E4C7;
        border-radius: 4px;
    }
    """
)

VALIDATION_STATUS_WARNING_STYLE = (
    """
    QLabel {
        color: #856404;
        font-size: 12px;
        font-weight: bold;
        padding: 4px 8px;
        background: #fff3cd;
        border: 1px solid #ffeeba;
        border-radius: 4px;
    }
    """
)

CONFIRM_PROCESS_BUTTON_STYLE = (
    """
    QPushButton {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
            stop: 0 #22C55E, stop: 1 #16A34A);
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton:hover:enabled {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
            stop: 0 #16A34A, stop: 1 #15803D);
        box-shadow: 0 2px 4px rgba(34, 197, 94, 0.3);
    }
    QPushButton:pressed:enabled {
        background: #15803D;
    }
    QPushButton:disabled {
        background: #F3F4F6;
        color: #A1A1AA;
    }
    """
)

LOADING_OVERLAY_STYLE = (
    """
    QWidget {
        background: rgba(255, 255, 255, 0.9);
        border-radius: 8px;
    }
    """
)

FRAME_INFO_LABEL_STYLE = (
    """
    QLabel {
        color: #6c757d;
        font-size: 10px;
        font-weight: bold;
        text-align: center;
        padding: 4px;
        background: rgba(108, 117, 125, 0.1);
        border-radius: 4px;
    }
    """
)

# Enhanced workflow styles
ENHANCED_WORKFLOW_BADGE_STYLE = (
    """
    QLabel {
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 #3B82F6, stop: 1 #5F96FF);
        color: white;
        border-radius: 12px;
        padding: 4px 12px;
        font-size: 11px;
        font-weight: bold;
    }
    """
)

WORKFLOW_STEP_INDICATOR_STYLE = (
    """
    QLabel {
        background: #f8f9fa;
        border: 2px solid #e9ecef;
        border-radius: 20px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: bold;
        color: #495057;
        min-width: 20px;
        max-width: 40px;
        text-align: center;
    }
    """
)

WORKFLOW_STEP_ACTIVE_STYLE = (
    """
    QLabel {
        background: #3B82F6;
        border: 2px solid #2563EB;
        border-radius: 20px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: bold;
        color: white;
        min-width: 20px;
        max-width: 40px;
        text-align: center;
    }
    """
)

WORKFLOW_STEP_COMPLETE_STYLE = (
    """
    QLabel {
        background: #22C55E;
        border: 2px solid #16A34A;
        border-radius: 20px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: bold;
        color: white;
        min-width: 20px;
        max-width: 40px;
        text-align: center;
    }
    """
)

# Add to the Colors class
class ViewSelectorColors:
    """Colors specific to view selector components"""
    DETECTED_BG = "#F0FDF4"
    DETECTED_TEXT = "#16A34A"
    DETECTED_BORDER = "#B7E4C7"
    
    MANUAL_BG = "#fff3cd"
    MANUAL_TEXT = "#856404"
    MANUAL_BORDER = "#ffeeba"
    
    FRAME_BORDER = "#dee2e6"
    FRAME_BORDER_HOVER = "#3B82F6"
    FRAME_BG = "#f8f9fa"
    FRAME_BG_HOVER = "#f0f4ff"
    
    CHECKBOX_UNCHECKED = "#D1D5DB"
    CHECKBOX_CHECKED = "#3B82F6"
    CHECKBOX_HOVER = "#2563EB"

# Utility functions for view selector
def get_detection_status_style(has_auto_detection: bool) -> str:
    """Get style for detection status badge"""
    if has_auto_detection:
        return AUTO_DETECTED_BADGE_STYLE
    else:
        return MANUAL_REQUIRED_BADGE_STYLE

def get_validation_status_style(is_valid: bool) -> str:
    """Get style for validation status"""
    if is_valid:
        return VALIDATION_STATUS_SUCCESS_STYLE
    else:
        return VALIDATION_STATUS_WARNING_STYLE

def get_workflow_step_style(step_status: str) -> str:
    """Get style for workflow step indicator"""
    styles = {
        "pending": WORKFLOW_STEP_INDICATOR_STYLE,
        "active": WORKFLOW_STEP_ACTIVE_STYLE,
        "complete": WORKFLOW_STEP_COMPLETE_STYLE
    }
    return styles.get(step_status, WORKFLOW_STEP_INDICATOR_STYLE)

PATIENT_INFO_FIELD_STYLE = (
    """
    QLineEdit {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 3px;
        padding: 4px 6px;
        font-size: 11px;
        color: #495057;
        selection-background-color: #3B82F6;
    }
    QLineEdit:read-only {
        background: #f8f9fa;
        color: #6c757d;
    }
    """
)

PATIENT_INFO_LABEL_STYLE = (
    """
    QLabel {
        font-weight: bold;
        color: #495057;
        font-size: 10px;
        padding: 2px 4px;
    }
    """
)

__all__ = [
    # Existing button styles
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
    # NEW: BSI-specific styles
    "BSI_PANEL_STYLE",
    "BSI_TITLE_STYLE",
    "BSI_SCORE_LABEL_STYLE",
    "BSI_SCORE_HIGH_STYLE",
    "BSI_SCORE_MEDIUM_STYLE", 
    "BSI_SCORE_LOW_STYLE",
    "BSI_INFO_ITEM_STYLE",
    "BSI_COMMENTS_STYLE",
    "BSI_CANVAS_FRAME_STYLE",
    "BSI_EXPORT_BUTTON_STYLE",
    "BSI_STATUS_SUCCESS_STYLE",
    "BSI_STATUS_ERROR_STYLE",
    "BSI_STATUS_WARNING_STYLE",
    # Utilities
    "Colors",
    "get_layer_color",
    "create_layer_indicator_style",
    "truncate_text",
    # NEW: BSI utilities
    "get_bsi_score_style",
    "get_bsi_status_style",
    "format_bsi_score",
    "get_bsi_severity_text",
    "get_bsi_severity_color",
    # View selector styles
    "VIEW_SELECTOR_TITLE_STYLE",
    "VIEW_SELECTOR_INSTRUCTIONS_STYLE",
    "FRAME_PREVIEW_STYLE",
    "FRAME_WIDGET_STYLE",
    "DICOM_FILE_HEADER_STYLE",
    "VIEW_CHECKBOX_STYLE",
    "AUTO_DETECTED_BADGE_STYLE", 
    "MANUAL_REQUIRED_BADGE_STYLE",
    "VALIDATION_STATUS_SUCCESS_STYLE",
    "VALIDATION_STATUS_WARNING_STYLE",
    "CONFIRM_PROCESS_BUTTON_STYLE",
    "LOADING_OVERLAY_STYLE",
    "FRAME_INFO_LABEL_STYLE",
    
    # Enhanced workflow styles
    "ENHANCED_WORKFLOW_BADGE_STYLE",
    "WORKFLOW_STEP_INDICATOR_STYLE",
    "WORKFLOW_STEP_ACTIVE_STYLE", 
    "WORKFLOW_STEP_COMPLETE_STYLE",
    
    # Colors and utilities
    "ViewSelectorColors",
    "get_detection_status_style",
    "get_validation_status_style",
    "get_workflow_step_style",
]
