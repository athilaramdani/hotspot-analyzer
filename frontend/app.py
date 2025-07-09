import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor

# ── jendela utama untuk SPECT dan PET ────────────────
from .widgets.main_window import MainWindow           # SPECT
from .widgets.main_window_pet import MainWindowPet    # PET  (pastikan file ini ada)

from .widgets.patient_selection_dialog import PatientSelectionDialog

# ----- Tema (light palette) --------------------------
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

# -----------------------------------------------------
def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(make_light_palette())
    app.setStyleSheet("""
        * { font-family:'Poppins', sans-serif; font-size:11pt; }
        QLabel { color:inherit; }
    """)

    # ── dialog pemilihan pasien + modalitas ───────────
    dlg = PatientSelectionDialog()
    if not dlg.exec():
        sys.exit(0)                       # user menutup dialog

    session_code    = dlg.selected_patient_id
    selected_mod    = dlg.selected_modality   # "SPECT" | "PET"
    data_dir        = Path("data")            # sesuaikan jika perlu

    # ── buka window sesuai modalitas ──────────────────
    if selected_mod == "SPECT":
        mw = MainWindow(session_code=session_code, data_root=data_dir)
    else:  # "PET"
        mw = MainWindowPet(session_code=session_code, data_root=data_dir)

    mw.show()
    sys.exit(app.exec())

# -----------------------------------------------------
if __name__ == "__main__":
    main()
