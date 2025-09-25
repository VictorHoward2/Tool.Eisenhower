import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    # Set application icon
    icon = QIcon("./src/assets/matrix.ico")
    app.setWindowIcon(icon)
    win = MainWindow()
    win.setWindowIcon(icon)  # <-- Thêm dòng này
    win.resize(1000, 700)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
