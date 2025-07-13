"""Reusable Qt stylesheet constants for the Hotspot‑Analyzer GUI.

Import the constants you need, e.g.::

    from core.gui.ui_constants import PRIMARY_BUTTON_STYLE
    my_button.setStyleSheet(PRIMARY_BUTTON_STYLE)

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

__all__ = [
    "PRIMARY_BUTTON_STYLE",
    "SUCCESS_BUTTON_STYLE",
    "GRAY_BUTTON_STYLE",
    "ZOOM_BUTTON_STYLE",
    "SCAN_BUTTON_STYLE",
]
