from PyQt5.QtCore   import Qt
from PyQt5.QtGui    import QFont
from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QLabel, QLineEdit, QComboBox
)


class PatientInfoBar(QWidget):
    """Bar metadata yang lebih tinggi & nyaman dibaca."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)

        grid = QGridLayout(self)
        grid.setContentsMargins(16, 8, 16, 8)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)

        bold = QFont("Poppins", 10, QFont.Bold)

        def lab(text, row, col):
            l = QLabel(text, self)
            l.setFont(bold)
            l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(l, row, col)

        # kolom label ada di ganjil, widget di genap —> dua baris
        self.id_combo   = QComboBox()
        self.name_edit  = QLineEdit(readOnly=True)
        self.birth_edit = QLineEdit(readOnly=True)
        self.sex_edit   = QLineEdit(readOnly=True)
        self.study_edit = QLineEdit(readOnly=True)

        widgets = [self.id_combo, self.name_edit,
                   self.birth_edit, self.sex_edit, self.study_edit]
        for w in widgets:
            w.setFont(QFont("Poppins", 10))

        lab("Patient ID:",   0, 0); grid.addWidget(self.id_combo,   0, 1)
        lab("Name:",         0, 2); grid.addWidget(self.name_edit,  0, 3)
        lab("Birth:",        1, 0); grid.addWidget(self.birth_edit, 1, 1)
        lab("Sex:",          1, 2); grid.addWidget(self.sex_edit,   1, 3)
        lab("Study Date:",   1, 4); grid.addWidget(self.study_edit, 1, 5)
        grid.setColumnStretch(6, 1)   # dorong ke kiri

    # ------------------------------------------------ API
    def set_patient_meta(self, meta: dict):
        self.name_edit.setText(meta.get("patient_name", ""))
        self.birth_edit.setText(meta.get("patient_birth", ""))
        self.sex_edit.setText(meta.get("patient_sex", ""))
        self.study_edit.setText(meta.get("study_date", ""))
