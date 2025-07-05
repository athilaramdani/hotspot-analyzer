from __future__ import annotations
from pathlib import Path
print(">>> Loaded DicomImportDialog from:", __file__)

from PySide6.QtCore import Signal, QCoreApplication
from PySide6.QtWidgets import QDialog, QFileDialog, QVBoxLayout, QProgressBar, QLabel, QApplication

from backend.input_data import process_files

class DicomImportDialog(QDialog):
    files_imported = Signal()
    
    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        print(f"[DEBUG] session_code = {session_code}")
        print(">>> DicomImportDialog.__init__ CALLED")
        super().__init__(parent)
        self.setWindowTitle("Import File DICOM")
        self.session_code = session_code
        self.data_root = data_root
        
        layout = QVBoxLayout(self)
        self.label = QLabel("Memilih file untuk diimpor...")
        self.progress_bar = QProgressBar()
        layout.addWidget(self.label)
        layout.addWidget(self.progress_bar)
        
        self._open_file_dialog()

    def _open_file_dialog(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih file DICOM", "", "DICOM Files (*.dcm);;All Files (*)"
        )

        if file_paths:
            self.progress_bar.setMaximum(len(file_paths))
            process_files(
                paths=[Path(p) for p in file_paths], 
                data_root=self.data_root, 
                session_code=self.session_code,
                progress_cb=self._update_progress
            )
            self.files_imported.emit()
            self.accept()
        else:
            self.reject()

    def _update_progress(self, current: int, total: int, filename: str):
        self.progress_bar.setValue(current)
        self.label.setText(f"Memproses: {Path(filename).name}")
        QCoreApplication.processEvents()