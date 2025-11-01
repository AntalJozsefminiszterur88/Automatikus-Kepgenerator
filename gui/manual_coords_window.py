# gui/manual_coords_window.py
import os
import json
import time 
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGridLayout, QApplication, QWidget,
                               QTextEdit, QScrollArea, QMessageBox, QCheckBox) # QMessageBox importálva
from PySide6.QtCore import Qt, Signal, QObject, QThread, Slot, QRect
from PySide6.QtGui import QScreen, QPainter, QColor, QPen

try:
    from pynput import keyboard
    import pyautogui 
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("FIGYELEM: A 'pynput' és/vagy 'pyautogui' könyvtár nincs telepítve. A manuális koordináta rögzítés CTRL gombbal nem lesz elérhető.")
    print("Telepítés: pip install pynput pyautogui")


# --- ÚJ SEGÉDOSZTÁLY A TERÜLET KIJELÖLÉSÉHEZ ---
class ScreenRegionSelector(QWidget):
    region_selected = Signal(int, int, int, int)  # left, top, width, height
    selection_canceled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self._start_point_global = None
        self._current_point_global = None
        self._selecting = False

        # Teljes asztalterület lefedése (több monitor esetén is)
        desktop_rect = None
        for screen in QApplication.screens():
            if desktop_rect is None:
                desktop_rect = QRect(screen.geometry())
            else:
                desktop_rect = desktop_rect.united(screen.geometry())
        if desktop_rect:
            self.setGeometry(desktop_rect)

    def _current_selection_rect(self):
        if not self._start_point_global or not self._current_point_global:
            return QRect()
        start_local = self.mapFromGlobal(self._start_point_global)
        current_local = self.mapFromGlobal(self._current_point_global)
        rect = QRect(start_local, current_local).normalized()
        return rect

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_point_global = event.globalPosition().toPoint()
            self._current_point_global = self._start_point_global
            self._selecting = True
            self.update()
        elif event.button() == Qt.RightButton:
            self.selection_canceled.emit()
            self.close()

    def mouseMoveEvent(self, event):
        if self._selecting:
            self._current_point_global = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._selecting:
            self._current_point_global = event.globalPosition().toPoint()
            rect = QRect(self._start_point_global, self._current_point_global).normalized()
            self._selecting = False
            if rect.width() >= 3 and rect.height() >= 3:
                self.region_selected.emit(rect.left(), rect.top(), rect.width(), rect.height())
            else:
                self.selection_canceled.emit()
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.selection_canceled.emit()
            self.close()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        translucent_black = QColor(0, 0, 0, 120)
        painter.fillRect(self.rect(), translucent_black)

        if self._selecting and self._start_point_global and self._current_point_global:
            selection_rect = self._current_selection_rect()
            highlight_color = QColor(0, 170, 255, 80)
            border_pen = QPen(QColor(0, 170, 255), 2, Qt.SolidLine)

            painter.fillRect(selection_rect, highlight_color)
            painter.setPen(border_pen)
            painter.drawRect(selection_rect)

        # Tájékoztató szöveg
        info_text = "Bal egér: kijelölés | Jobb egér vagy ESC: megszakítás"
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(self.rect().adjusted(10, 10, -10, -10), Qt.AlignLeft | Qt.AlignTop, info_text)


class CoordCaptureThread(QThread):
    coordinate_captured = Signal(int, int, str) # x, y, coord_id
    capture_complete_signal = Signal()          # Jelzi a figyelés végét (siker vagy hiba)

    def __init__(self, parent_window_to_hide, manual_window_to_hide, coord_id_being_captured):
        super().__init__()
        self.pynput_listener = None 
        self.parent_window = parent_window_to_hide
        self.manual_window = manual_window_to_hide
        self.coord_id = coord_id_being_captured
        self._running = False

    def run(self):
        if not PYNPUT_AVAILABLE:
            print("CoordCaptureThread HIBAB: PYNPUT nem elérhető.")
            self.capture_complete_signal.emit() 
            return

        self._running = True
        print("CoordCaptureThread DEBUG: Ablakok elrejtése...")
        
        if self.manual_window:
            self.manual_window.hide()
        if self.parent_window:
            self.parent_window.hide()
        
        QThread.msleep(300) 

        def on_press(key):
            if not self._running:
                print("CoordCaptureThread.on_press DEBUG: Figyelő leállítva (kulcs esemény közben).")
                return False 
            
            print(f"CoordCaptureThread.on_press DEBUG: Billentyű lenyomva: {key}")
            try:
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r or \
                   key == keyboard.Key.ctrl: 
                    print("CoordCaptureThread.on_press DEBUG: CTRL billentyű észlelve.")
                    x, y = pyautogui.position()
                    print(f"CoordCaptureThread.on_press DEBUG: Pozíció rögzítve: ({x},{y}) ehhez: {self.coord_id}")
                    self.coordinate_captured.emit(x, y, self.coord_id)
                    self._running = False 
                    print("CoordCaptureThread.on_press DEBUG: coordinate_captured signal elküldve. Listener leállítása (return False).")
                    return False  
            except AttributeError: 
                pass 
            except Exception as e:
                print(f"CoordCaptureThread.on_press DEBUG: Hiba: {e}")
                self._running = False 
                return False 
            return True 

        print("CoordCaptureThread DEBUG: Billentyűzetfigyelő indítása...")
        self.pynput_listener = keyboard.Listener(on_press=on_press, suppress=False)
        self.pynput_listener.start()
        self.pynput_listener.join() 
        
        print("CoordCaptureThread DEBUG: Billentyűzetfigyelő leállt és join-olt.")
        self.capture_complete_signal.emit() 
        print("CoordCaptureThread DEBUG: capture_complete_signal elküldve.")

    def stop_capture(self): 
        print("CoordCaptureThread DEBUG: stop_capture hívva.")
        self._running = False
        if self.pynput_listener:
            print("CoordCaptureThread DEBUG: pynput_listener.stop() hívása.")
            self.pynput_listener.stop()


class ManualCoordsWindow(QDialog):
    def __init__(self, parent_main_window=None):
        super().__init__(parent_main_window)
        self.parent_main_window = parent_main_window
        self.setWindowTitle("Manuális Koordináta Beállítás")
        self.setMinimumSize(550, 480) 
        self.setModal(True)

        try:
            documents_path = os.path.join(os.path.expanduser('~'), 'Documents')
            umkgl_solutions_folder = os.path.join(documents_path, "UMKGL Solutions")
            app_specific_folder = os.path.join(umkgl_solutions_folder, "Automatikus-Kepgenerator")
            self.config_dir = os.path.join(app_specific_folder, "Config")
            # *** MÓDOSÍTÁS ITT ***
            self.ui_coords_file = os.path.join(self.config_dir, "ui_coordinates_manual.json") 
            # *** MÓDOSÍTÁS VÉGE ***
            os.makedirs(self.config_dir, exist_ok=True)
            print(f"ManualCoordsWindow: Manuális koordináta fájl helye: {self.ui_coords_file}")
        except Exception as e:
            print(f"Hiba a konfigurációs útvonal létrehozásakor a ManualCoordsWindow-ban: {e}")
            self.ui_coords_file = "ui_coordinates_manual_fallback.json" 
            print(f"Fallback manuális koordináta fájl használata: {self.ui_coords_file}")


        self.coordinates_data = {}
        self.capture_thread = None
        self.currently_capturing_id = None
        self.region_selector = None

        self._setup_ui()
        self.load_and_display_coords()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(15)

        description_label = QLabel(
            "<b>Manuális Koordináta Beállítás:</b><br>"
            "1. Kattints a 'Pozíció Kijelölése' gombra a beállítani kívánt elem mellett.<br>"
            "2. Az alkalmazás ablakai (ez és a főablak) el lesznek rejtve.<br>"
            "3. Vidd az egeret a célalkalmazásban a kívánt gombra/mezőre.<br>"
            "4. Nyomd meg a <b>CTRL</b> (Control) billentyűt a pozíció rögzítéséhez.<br>"
            "5. A koordináták rögzítésre és mentésre kerülnek, az ablakok újra megjelennek.<br>"
            "6. A 'Generálási státusz terület' gomb esetén húzz egy téglalapot a figyelni kívánt rész köré a megjelenő átlátszó képernyőn.<br>"
            "<i>Megjegyzés: A 'Prompt mező helye' a prompt beviteli mezőre való kattintás helyét jelöli.</i>"
        )
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignLeft) 
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(description_label)
        scroll_area.setFixedHeight(130) 
        self.main_layout.addWidget(scroll_area)

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)

        self.coord_widgets = {}

        coord_definitions = [
            {"label_text": "Eszköz megnyitása Gomb:", "id": "tool_open_click"},
            {"label_text": "Prompt mező helye:", "id": "prompt_click"},
            {"label_text": "Generálás gomb:", "id": "generate_button_click"},
            {"label_text": "Letöltés gomb:", "id": "download_button_click"},
            {"label_text": "Generálási státusz terület:", "id": "generation_status_region"}
        ]

        for i, definition in enumerate(coord_definitions):
            text_label = QLabel(definition["label_text"])
            coords_display_label = QLabel("Nincs beállítva")
            coords_display_label.setMinimumWidth(120)
            capture_button = QPushButton("Pozíció Kijelölése")
            if not PYNPUT_AVAILABLE:
                capture_button.setDisabled(True)
                capture_button.setToolTip("A pynput és/vagy pyautogui könyvtár hiányzik a működéshez.")

            self.coord_widgets[definition["id"]] = {
                "display_label": coords_display_label,
                "button": capture_button
            }
            
            capture_button.clicked.connect(lambda checked=False, coord_id=definition["id"]: self.initiate_coordinate_capture(coord_id))

            self.grid_layout.addWidget(text_label, i, 0)
            self.grid_layout.addWidget(coords_display_label, i, 1)
            self.grid_layout.addWidget(capture_button, i, 2)
        
        self.main_layout.addLayout(self.grid_layout)

        toggle_container = QVBoxLayout()
        toggle_container.setSpacing(6)

        toggle_title = QLabel("<b>Automatizálási lépések beállításai:</b>")
        toggle_title.setWordWrap(True)
        toggle_container.addWidget(toggle_title)

        self.start_browser_checkbox = QCheckBox(
            "Induláskor automatikusan nyissa meg a böngészőt és töltse be a céloldalt"
        )
        self.start_browser_checkbox.toggled.connect(
            lambda checked: self._on_toggle_changed("start_with_browser", checked)
        )
        toggle_container.addWidget(self.start_browser_checkbox)

        self.perform_tool_open_checkbox = QCheckBox(
            "Végezze el automatikusan az 'Eszköz megnyitása' gomb kattintását"
        )
        self.perform_tool_open_checkbox.toggled.connect(
            lambda checked: self._on_toggle_changed("perform_tool_open_click", checked)
        )
        toggle_container.addWidget(self.perform_tool_open_checkbox)

        self.perform_download_checkbox = QCheckBox(
            "Végezze el automatikusan a 'Letöltés' gomb kattintását"
        )
        self.perform_download_checkbox.toggled.connect(
            lambda checked: self._on_toggle_changed("perform_download_click", checked)
        )
        toggle_container.addWidget(self.perform_download_checkbox)

        note_label = QLabel(
            "<i>Ha bármelyik lépést kikapcsolod, a folyamat azt a részt kihagyja és a következő művelettel folytatódik.</i>"
        )
        note_label.setWordWrap(True)
        toggle_container.addWidget(note_label)

        self.main_layout.addLayout(toggle_container)
        self.main_layout.addStretch()

        self.close_button = QPushButton("Bezárás és Mentés")
        self.close_button.clicked.connect(self.accept)
        self.main_layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignRight)

    def load_and_display_coords(self):
        try:
            if os.path.exists(self.ui_coords_file):
                with open(self.ui_coords_file, 'r') as f:
                    self.coordinates_data = json.load(f)
                print(f"Manuális koordináták betöltve innen: {self.ui_coords_file}")
            else:
                self.coordinates_data = {}
                print(f"Manuális koordináta fájl nem található ({self.ui_coords_file}). Új fájl lesz létrehozva mentéskor.")
        except Exception as e:
            print(f"Hiba a manuális koordináták betöltése közben: {e}")
            self.coordinates_data = {}

        migrated = self._migrate_old_generation_status_keys()
        if migrated:
            self._save_coordinates_to_file()

        # Alapértelmezett értékek biztosítása a manuális lépésekhez
        if "start_with_browser" not in self.coordinates_data:
            self.coordinates_data["start_with_browser"] = True
        if "perform_tool_open_click" not in self.coordinates_data:
            self.coordinates_data["perform_tool_open_click"] = True
        if "perform_download_click" not in self.coordinates_data:
            self.coordinates_data["perform_download_click"] = True

        for coord_id, widgets in self.coord_widgets.items():
            if coord_id == "generation_status_region":
                region = self.coordinates_data.get("generation_status_region")
                if region and isinstance(region, dict):
                    left = region.get("left")
                    top = region.get("top")
                    width = region.get("width")
                    height = region.get("height")
                    if None not in (left, top, width, height):
                        widgets["display_label"].setText(
                            f"X: {left}, Y: {top}, Szél: {width}, Mag: {height}"
                        )
                        continue
                widgets["display_label"].setText("Nincs beállítva")
            else:
                key_x = f"{coord_id}_x"
                key_y = f"{coord_id}_y"
                if key_x in self.coordinates_data and key_y in self.coordinates_data:
                    x = self.coordinates_data[key_x]
                    y = self.coordinates_data[key_y]
                    widgets["display_label"].setText(f"X: {x}, Y: {y}")
                else:
                    widgets["display_label"].setText("Nincs beállítva")

        # Checkboxok frissítése a fájl alapján (jeleket ideiglenesen letiltva)
        self.start_browser_checkbox.blockSignals(True)
        self.start_browser_checkbox.setChecked(bool(self.coordinates_data.get("start_with_browser", True)))
        self.start_browser_checkbox.blockSignals(False)

        self.perform_tool_open_checkbox.blockSignals(True)
        self.perform_tool_open_checkbox.setChecked(bool(self.coordinates_data.get("perform_tool_open_click", True)))
        self.perform_tool_open_checkbox.blockSignals(False)

        self.perform_download_checkbox.blockSignals(True)
        self.perform_download_checkbox.setChecked(bool(self.coordinates_data.get("perform_download_click", True)))
        self.perform_download_checkbox.blockSignals(False)

    def _save_coordinates_to_file(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.ui_coords_file, 'w') as f:
                json.dump(self.coordinates_data, f, indent=4)
            print(f"Manuális koordináták sikeresen elmentve ide: {self.ui_coords_file}")
        except Exception as e:
            print(f"Hiba a manuális koordináták mentése közben: {e}")

    def _apply_toggle_states_to_data(self):
        self.coordinates_data["start_with_browser"] = bool(self.start_browser_checkbox.isChecked())
        self.coordinates_data["perform_tool_open_click"] = bool(self.perform_tool_open_checkbox.isChecked())
        self.coordinates_data["perform_download_click"] = bool(self.perform_download_checkbox.isChecked())

    def _on_toggle_changed(self, key, checked):
        self.coordinates_data[key] = bool(checked)
        self._save_coordinates_to_file()

    def initiate_coordinate_capture(self, coord_id_to_capture):
        if coord_id_to_capture == "generation_status_region":
            self.currently_capturing_id = coord_id_to_capture
            self._start_region_selection()
            return

        if not PYNPUT_AVAILABLE:
            if coord_id_to_capture in self.coord_widgets:
                 self.coord_widgets[coord_id_to_capture]["display_label"].setText("Hiba: Könyvtár hiányzik!")
            QMessageBox.warning(self, "Hiányzó könyvtár", "A 'pynput' és/vagy 'pyautogui' könyvtár nincs telepítve. A koordináta rögzítés nem lehetséges.")
            return

        print(f"Koordináta rögzítésének indítása ehhez: {coord_id_to_capture}")
        
        if self.capture_thread and self.capture_thread.isRunning():
            print("Már fut egy koordináta rögzítő szál. Kérlek, várj...")
            return

        self.currently_capturing_id = coord_id_to_capture 
        
        self.capture_thread = CoordCaptureThread(self.parent_main_window, self, coord_id_to_capture)
        self.capture_thread.coordinate_captured.connect(self.on_coordinate_captured_slot)
        self.capture_thread.capture_complete_signal.connect(self.on_capture_thread_finished_and_restore_windows)
        self.capture_thread.start()

    @Slot(int, int, str) 
    def on_coordinate_captured_slot(self, x, y, captured_coord_id):
        print(f"Koordináta rögzítve (slot): X={x}, Y={y} ehhez: {captured_coord_id}")
        
        if captured_coord_id == self.currently_capturing_id and captured_coord_id in self.coord_widgets:
            self.coord_widgets[captured_coord_id]["display_label"].setText(f"X: {x}, Y: {y}")

            key_x = f"{captured_coord_id}_x"
            key_y = f"{captured_coord_id}_y"
            self.coordinates_data[key_x] = x
            self.coordinates_data[key_y] = y
            
            self._save_coordinates_to_file()
        else:
            print(f"Figyelmeztetés: Koordináta érkezett ({captured_coord_id}), de másikat vártunk ({self.currently_capturing_id}) vagy az ID ismeretlen.")
        
    @Slot()
    def on_capture_thread_finished_and_restore_windows(self):
        print("ManualCoordsWindow DEBUG: Capture thread finished, ablakok visszaállítása...")
        self._restore_windows_after_capture()
        self.currently_capturing_id = None
        if self.capture_thread:
            self.capture_thread.deleteLater()
            self.capture_thread = None
        print("ManualCoordsWindow DEBUG: Ablakok visszaállítva, thread törölve.")

    def _restore_windows_after_capture(self):
        if self.parent_main_window:
            self.parent_main_window.showNormal()
            self.parent_main_window.activateWindow()

        self.showNormal()
        self.activateWindow()

    def _start_region_selection(self):
        print("ManualCoordsWindow DEBUG: Generálási státusz terület kijelölése indul.")
        if self.region_selector:
            print("ManualCoordsWindow DEBUG: Már aktív régió kiválasztó van.")
            return

        if self.parent_main_window:
            self.parent_main_window.hide()
        self.hide()

        self.region_selector = ScreenRegionSelector()
        self.region_selector.region_selected.connect(self._on_generation_status_region_selected)
        self.region_selector.selection_canceled.connect(self._on_generation_status_region_selection_canceled)
        self.region_selector.showFullScreen()
        self.region_selector.raise_()
        self.region_selector.activateWindow()

    @Slot()
    def _on_generation_status_region_selection_canceled(self):
        print("ManualCoordsWindow DEBUG: Régió kijelölés megszakítva.")
        self._cleanup_region_selector()
        self._restore_windows_after_capture()
        self.currently_capturing_id = None

    @Slot(int, int, int, int)
    def _on_generation_status_region_selected(self, left, top, width, height):
        print(f"ManualCoordsWindow DEBUG: Régió kijelölve - Left:{left}, Top:{top}, Szél:{width}, Mag:{height}")
        region_data = {
            "left": int(left),
            "top": int(top),
            "width": int(width),
            "height": int(height)
        }
        self.coordinates_data["generation_status_region"] = region_data
        # Régi pixel-alapú kulcsok eltávolítása, ha léteznek
        self.coordinates_data.pop("generation_status_pixel_x", None)
        self.coordinates_data.pop("generation_status_pixel_y", None)

        if "generation_status_region" in self.coord_widgets:
            self.coord_widgets["generation_status_region"]["display_label"].setText(
                f"X: {region_data['left']}, Y: {region_data['top']}, Szél: {region_data['width']}, Mag: {region_data['height']}"
            )

        self._save_coordinates_to_file()
        self._cleanup_region_selector()
        self._restore_windows_after_capture()
        self.currently_capturing_id = None

    def _cleanup_region_selector(self):
        if self.region_selector:
            try:
                self.region_selector.region_selected.disconnect(self._on_generation_status_region_selected)
            except (TypeError, RuntimeError):
                pass
            try:
                self.region_selector.selection_canceled.disconnect(self._on_generation_status_region_selection_canceled)
            except (TypeError, RuntimeError):
                pass
            self.region_selector.hide()
            self.region_selector.deleteLater()
            self.region_selector = None

    def _migrate_old_generation_status_keys(self):
        migrated = False
        if "generation_status_region" not in self.coordinates_data:
            old_x = self.coordinates_data.get("generation_status_pixel_x")
            old_y = self.coordinates_data.get("generation_status_pixel_y")
            if old_x is not None and old_y is not None:
                try:
                    migrated_region = {
                        "left": int(old_x),
                        "top": int(old_y),
                        "width": 20,
                        "height": 20
                    }
                except (TypeError, ValueError):
                    migrated_region = None
                if migrated_region:
                    self.coordinates_data["generation_status_region"] = migrated_region
                    migrated = True
        return migrated


    def center_on_screen(self):
        try:
            parent_geometry = self.parent().geometry() if self.parent() else QApplication.primaryScreen().availableGeometry()
            self.move(
                parent_geometry.center().x() - self.width() / 2,
                parent_geometry.center().y() - self.height() / 2
            )
        except Exception as e:
            print(f"Hiba a manuális ablak középre igazítása közben: {e}")
            try:
                screen = QApplication.primaryScreen().availableGeometry()
                self.move(screen.center().x() - self.width() / 2, screen.center().y() - self.height() / 2)
            except:
                pass


    def showEvent(self, event):
        super().showEvent(event)
        self.center_on_screen()
        self.load_and_display_coords()

    def closeEvent(self, event):
        if self.capture_thread and self.capture_thread.isRunning():
            print("Manuális ablak bezárása: Aktív koordináta rögzítő szál leállítása...")
            self.capture_thread.stop_capture()
            if not self.capture_thread.wait(1000):
                print("Figyelmeztetés: A koordináta rögzítő szál nem állt le időben.")
        if self.region_selector:
            self._cleanup_region_selector()
        self._apply_toggle_states_to_data()
        self._save_coordinates_to_file()
        super().closeEvent(event)

    def accept(self):
        self._apply_toggle_states_to_data()
        self._save_coordinates_to_file()
        super().accept()
