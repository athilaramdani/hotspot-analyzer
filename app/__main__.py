import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox, QMainWindow
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QPalette, QColor
from PySide6.QtGui import QFont
# Import jendela utama
from features.spect_viewer.gui.main_window_spect import MainWindowSpect           # SPECT
from features.pet_viewer.gui.main_window_pet import MainWindowPet    # PET
from features.dicom_import.gui.patient_selection_dialog import PatientSelectionDialog

# Tema light
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

# Fungsi utama
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(make_light_palette())
    app.setFont(QFont("Poppins"))

    windows = []  # simpan referensi agar window tidak di-GC

    def start_new_session():
        dlg = PatientSelectionDialog()
        if not dlg.exec():
            print("[DEBUG] Dialog dibatalkan, keluar aplikasi")
            app.quit()
            return

        session_code = dlg.selected_patient_id
        selected_mod = dlg.selected_modality
        data_dir = Path("data")  # Pastikan ini Path, bukan string

        if selected_mod == "SPECT":
            window = MainWindowSpect(session_code=session_code, data_root=data_dir)
        elif selected_mod == "PET":
            window = MainWindowPet(session_code=session_code, data_root=data_dir)
        else:
            QMessageBox.critical(None, "Error", "Modality tidak dikenal")
            QTimer.singleShot(100, start_new_session)
            return

        def handle_logout():
            print("[DEBUG] Logout diklik")
            window.hide()
            window.deleteLater()
            QTimer.singleShot(200, start_new_session)

        window.logout_requested.connect(handle_logout)
        window.show()
        windows.append(window)

    start_new_session()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
