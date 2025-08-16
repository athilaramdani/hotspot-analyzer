# main.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPalette, QColor, QFont

# Import jendela utama - PLANAR only
from features.spect_viewer.gui.main_window_spect import MainWindowSpect
from features.dicom_import.gui.doctor_selection_dialog import DoctorSelectionDialog

def make_light_palette() -> QPalette:
    """Create light theme palette"""
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

def main():
    """Main application function"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(make_light_palette())
    app.setFont(QFont("Poppins"))

    windows = []  # Keep references to prevent garbage collection

    def start_new_session():
        """Start a new session with doctor selection"""
        dlg = DoctorSelectionDialog()
        if not dlg.exec():
            print("[DEBUG] Dialog cancelled, exiting application")
            app.quit()
            return

        session_code = dlg.selected_doctor_id
        selected_modality = dlg.selected_modality
        data_dir = Path("data")

        # Only PLANAR modality is supported now
        if selected_modality == "Planar":
            window = MainWindowSpect(session_code=session_code, data_root=data_dir)
        else:
            QMessageBox.critical(None, "Error", f"Modality '{selected_modality}' is not supported")
            QTimer.singleShot(100, start_new_session)
            return

        def handle_logout():
            """Handle logout and start new session"""
            print("[DEBUG] Logout clicked")
            window.hide()
            window.deleteLater()
            QTimer.singleShot(200, start_new_session)

        # Connect logout signal
        if hasattr(window, 'logout_requested'):
            window.logout_requested.connect(handle_logout)
        
        window.show()
        windows.append(window)

    # Start the first session
    start_new_session()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()