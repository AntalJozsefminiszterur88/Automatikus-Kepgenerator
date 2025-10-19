# gui/main_window.py
import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QApplication,
                               QSizePolicy)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QScreen, QIcon, QColor, QPalette
from .widgets.title_widget import TitleWidget
from .widgets.prompt_input_widget import PromptInputWidget
from .widgets.music_player_widget import MusicPlayerWidget
from core.process_controller import ProcessController
from .manual_coords_window import ManualCoordsWindow 


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automatikus Képgenerátor") 
        
        try: 
            current_file_path = os.path.abspath(__file__) 
            gui_directory_path = os.path.dirname(current_file_path) 
            project_root_path = os.path.dirname(gui_directory_path) 
            icon_path = os.path.join(project_root_path, "logo.ico") 

            if os.path.exists(icon_path): 
                self.setWindowIcon(QIcon(icon_path)) 
                print(f"Programikon sikeresen beállítva innen: {icon_path}") 
            else: 
                print(f"Figyelmeztetés: Programikon (logo.ico) nem található a projekt gyökérkönyvtárában: {icon_path}") 
        except Exception as e: 
            print(f"Hiba történt a programikon beállítása közben: {e}") 

        desired_width = 800
        desired_height = 800
        self.setGeometry(100, 100, desired_width, desired_height)


        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self._apply_discord_background_theme()
        self.main_layout = QVBoxLayout(self.central_widget)

        self._create_widgets()
        self.process_controller = ProcessController(self)
        self._setup_layout()
        self._connect_signals() 

        self.center_on_screen()
        print("MainWindow inicializálva és középre igazítva.")

        self.manual_coords_win = None

    def _apply_discord_background_theme(self):
        """Ensure the GUI always uses a Discord-like dark grey background."""
        discord_gray = "#2F3136"

        palette = QPalette(self.palette())
        discord_color = QColor(discord_gray)

        palette.setColor(QPalette.ColorRole.Window, discord_color)
        palette.setColor(QPalette.ColorRole.Base, discord_color)
        palette.setColor(QPalette.ColorRole.AlternateBase, discord_color)
        palette.setColor(QPalette.ColorRole.WindowText, Qt.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.white)
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.white)
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#B9BBBE"))

        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self.central_widget.setStyleSheet(
            f"background-color: {discord_gray}; color: white;"
        )

    def _create_widgets(self): 
        print("Widgetek létrehozása...")
        self.title_widget = TitleWidget()
        self.prompt_input_widget = PromptInputWidget() 
        
        self.music_player_widget = MusicPlayerWidget(parent=self)

        self.status_label = QLabel("Állapot: Indítás...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        font = self.status_label.font()
        font.setPointSize(10)
        self.status_label.setFont(font)
        self.status_label.setWordWrap(True)

    def _setup_layout(self): 
        print("Elrendezés beállítása...")
        self.main_layout.addWidget(self.title_widget)
        self.main_layout.addSpacing(15)
        self.main_layout.addWidget(self.prompt_input_widget) 
        self.main_layout.addSpacing(15)
        self.main_layout.addWidget(self.status_label) 
        self.main_layout.addStretch(1) 
        self.main_layout.addWidget(self.music_player_widget)

        self.central_widget.setLayout(self.main_layout)
    
    def _connect_signals(self):
        print("Jelzések összekötése...")
        if hasattr(self.prompt_input_widget, 'start_button'):
            self.prompt_input_widget.start_button.clicked.connect(self.handle_start_process)
        
        # *** ÚJ SIGNAL ÖSSZEKÖTÉSE ***
        if hasattr(self.prompt_input_widget, 'start_manual_button'):
            self.prompt_input_widget.start_manual_automation_requested.connect(self.handle_start_manual_process)
        # *** ÚJ SIGNAL ÖSSZEKÖTÉSE VÉGE ***

        if hasattr(self.prompt_input_widget, 'manual_mode_button'): 
            self.prompt_input_widget.manual_mode_requested.connect(self.handle_manual_mode_requested)

    @Slot()
    def handle_manual_mode_requested(self):
        print("Manuális mód ablak megnyitása kérése...")
        if not self.manual_coords_win: 
            self.manual_coords_win = ManualCoordsWindow(parent_main_window=self) 
        
        if self.manual_coords_win.isHidden():
            self.manual_coords_win.show()
            self.manual_coords_win.activateWindow() 
        elif not self.manual_coords_win.isVisible():
             self.manual_coords_win.show()
             self.manual_coords_win.activateWindow()
        else: 
            self.manual_coords_win.activateWindow()
        
        self.manual_coords_win.center_on_screen() 

    def center_on_screen(self): 
        try:
            screen = QApplication.primaryScreen()
            if not screen:
                print("Hiba: Nem található elsődleges képernyő a középre igazításhoz.")
                return

            screen_geometry = screen.availableGeometry()
            window_rect = self.frameGeometry()

            center_x = screen_geometry.center().x() - window_rect.width() / 2
            center_y = screen_geometry.center().y() - window_rect.height() / 2
            
            self.move(int(center_x), int(center_y))
        except Exception as e:
            print(f"Hiba történt az ablak középre igazítása közben: {e}")

    def _start_automation_common(self, manual_mode=False):
        """Közös logika az automatizálás indításához."""
        file_path = self.prompt_input_widget.get_file_path()
        start_line = self.prompt_input_widget.get_start_line()
        end_line = self.prompt_input_widget.get_end_line()

        if not file_path:
            self.update_status("Hiba: Nincs prompt fájl kiválasztva!")
            print("Indítási kísérlet fájl nélkül.")
            return

        if start_line <= 0 or end_line < start_line:
            self.update_status("Hiba: Érvénytelen kezdő vagy befejező sor!")
            print(f"Érvénytelen sorok: Start: {start_line}, End: {end_line}")
            return
        
        mode_text = "MANUÁLIS" if manual_mode else "AUTOMATIKUS"
        print(f"{mode_text} indítás kérése: {file_path}, Start: {start_line}, End: {end_line}")
        self.update_status(f"{mode_text} folyamat indítása a '{os.path.basename(file_path)}' fájllal ({start_line}-{end_line}. sor)...")
        
        if self.process_controller:
            # *** manual_mode PARAMÉTER ÁTADÁSA ***
            self.process_controller.start_full_automation_process(file_path, start_line, end_line, manual_mode=manual_mode)
        else:
            self.update_status("Hiba: ProcessController nincs inicializálva!")
            print(f"Hiba: ProcessController nincs inicializálva a {mode_text} handle_start_process-ben.")

    @Slot()
    def handle_start_process(self): 
        print("MainWindow: handle_start_process (automatikus) hívva.")
        self._start_automation_common(manual_mode=False)

    # *** ÚJ KEZELŐFÜGGVÉNY ***
    @Slot()
    def handle_start_manual_process(self):
        print("MainWindow: handle_start_manual_process hívva.")
        self._start_automation_common(manual_mode=True)
    # *** ÚJ KEZELŐFÜGGVÉNY VÉGE ***

    @Slot(str)
    def update_status(self, message: str): 
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"Állapot: {message}")
        else:
            print(f"[MainWindow KORAI STÁTUSZ - HIBA!]: {message}")
        
    def closeEvent(self, event): 
        print("Ablak bezárási esemény (MainWindow)...")
        
        if self.manual_coords_win and self.manual_coords_win.isVisible():
            print("Manuális koordináta ablak bezárása a főablak bezárásakor.")
            self.manual_coords_win.close()

        if self.process_controller and hasattr(self.process_controller, 'cleanup_on_exit'):
            self.process_controller.cleanup_on_exit()

        if hasattr(self, 'music_player_widget') and self.music_player_widget and \
           hasattr(self.music_player_widget, 'player') and \
           self.music_player_widget.player.playbackState() == self.music_player_widget.player.PlaybackState.PlayingState:
            print("Főablak bezárása: Saját zenelejátszó leállítása.")
            self.music_player_widget.player.stop()
        
        if self.process_controller and hasattr(self.process_controller, 'is_running') and self.process_controller.is_running():
            print("Futó folyamat leállítása kérése az ablak bezárásakor (másodlagos ellenőrzés)...")
            if hasattr(self.process_controller, 'stop_automation_process'):
                self.process_controller.stop_automation_process()
        
        event.accept()
