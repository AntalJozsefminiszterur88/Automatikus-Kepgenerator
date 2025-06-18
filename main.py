# main.py
import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow

def run_app():
    """
    Inicializálja és elindítja a PySide6 alkalmazást.
    """
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    # Ide jöhetnek kezdeti beállítások, pl. naplózás konfigurálása
    # from utils.logger import setup_logging
    # setup_logging() # Ezt majd később implementáljuk

    print("Alkalmazás indítása...")
    run_app()
