"""
Entry-point launcher.
Jalankan dengan:  python -m frontend.app   atau   python frontend/app.py
"""
import sys
from PyQt5.QtWidgets import QApplication
from .widgets.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)

    # --- global style -----------------------------------------------------
    # (gunakan font Poppins kalau tersedia, fallback ke default sans-serif)
    app.setStyleSheet("""
        * { font-family: 'Poppins', sans-serif; font-size: 11pt; }
        QToolBar { background:#f5f6fa; border:none; }
        QLabel   { color:#333; }
        QLineEdit[readOnly="true"] { background:#f0f0f0;
                                     border:1px solid #ccc; padding:2px 4px; }
    """)

    mw = MainWindow()
    mw.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
