import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor

from .widgets.main_window import MainWindow
from .widgets.patient_selection_dialog import PatientSelectionDialog

# ----------------- (Fungsi make_light_palette & make_dark_palette Anda) -----------------
def make_light_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f5f6fa"))
    pal.setColor(QPalette.WindowText, QColor("#222"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f0f0f0"))
    pal.setColor(QPalette.Text, QColor("#222"))
    pal.setColor(QPalette.Button, QColor("#ebecef"))
    pal.setColor(QPalette.ButtonText, QColor("#222"))
    pal.setColor(QPalette.Highlight, QColor("#4e73ff"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return pal

# ... (make_dark_palette jika ada) ...
# ------------------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(make_light_palette())
    app.setStyleSheet("""
        * { font-family:'Poppins', sans-serif; font-size:11pt; }
        QLabel { color:inherit; }
    """)

    selection_dialog = PatientSelectionDialog()
    
    if selection_dialog.exec():
        session_code = selection_dialog.selected_patient_id
        data_dir = Path("data")
        
        mw = MainWindow(session_code=session_code, data_root=data_dir)
        mw.show()
        
        sys.exit(app.exec())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()