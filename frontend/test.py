from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget
import sys

def show_gui():
    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle("Tes GUI Pertama")
    window.setGeometry(100, 100, 300, 150)

    label = QLabel("Halo dari PyQt!", window)
    button = QPushButton("Klik Aku", window)

    layout = QVBoxLayout()
    layout.addWidget(label)
    layout.addWidget(button)
    window.setLayout(layout)

    window.show()
    sys.exit(app.exec_())
