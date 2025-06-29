# frontend/app.py
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui      import QPalette, QColor

# ──────────────── PALETTE HELPERS ────────────────────────────────────────────
def make_light_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window       , QColor("#f5f6fa"))
    pal.setColor(QPalette.WindowText   , QColor("#222"))
    pal.setColor(QPalette.Base         , QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f0f0f0"))
    pal.setColor(QPalette.Text         , QColor("#222"))
    pal.setColor(QPalette.Button       , QColor("#ebecef"))
    pal.setColor(QPalette.ButtonText   , QColor("#222"))
    pal.setColor(QPalette.Highlight    , QColor("#4e73ff"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return pal


def make_dark_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window       , QColor("#1e1f22"))
    pal.setColor(QPalette.WindowText   , QColor("#f5f6fa"))
    pal.setColor(QPalette.Base         , QColor("#2a2b2f"))
    pal.setColor(QPalette.AlternateBase, QColor("#1e1f22"))
    pal.setColor(QPalette.Text         , QColor("#f5f6fa"))
    pal.setColor(QPalette.Button       , QColor("#32333a"))
    pal.setColor(QPalette.ButtonText   , QColor("#f5f6fa"))
    pal.setColor(QPalette.Highlight    , QColor("#4e73ff"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return pal
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")                    # cross-platform

    # default = light
    app.setPalette(make_light_palette())

    # stylesheet global – warna teks utk widget yang override bg
    app.setStyleSheet("""
        *            { font-family:'Poppins', sans-serif; font-size:11pt; }
        QToolBar     { background:transparent; border:none; padding:2px; }
        QLabel       { color:inherit; }
        QLineEdit[readOnly="true"] {
            background:palette(alternate-base);
            border:1px solid palette(mid); padding:2px 4px;
        }
        QToolButton  { padding:4px; border:0px; }
        QToolButton:hover { background:rgba(0,0,0,0.07); }
        QToolButton:checked { background:palette(highlight); color:white; }
    """)

    from .widgets.main_window import MainWindow   # import setelah QApplication
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
