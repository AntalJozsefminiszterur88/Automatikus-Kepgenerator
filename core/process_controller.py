# core/process_controller.py
import time
import traceback
import os
import json

from .prompt_handler import PromptHandler
from .pyautogui_automator import PyAutoGuiAutomator
from .vpn_manager import VpnManager
from .browser_manager import BrowserManager
from .global_hotkey_listener import GlobalHotkeyListener
from utils.ip_geolocation import get_public_ip_info
from PySide6.QtCore import QMetaObject, Qt, Q_ARG, Slot, QObject, QThread, Signal
from PySide6.QtWidgets import QApplication

try:
    from gui.overlay_window import OverlayWindow
except ImportError:
    OverlayWindow = None
    print("FIGYELEM: Az OverlayWindow osztály nem tölthető be.")


class InterruptedByUserError(Exception):
    """Egyedi kivétel a felhasználói megszakítás jelzésére."""
    pass

class AutomationWorker(QObject):
    status_updated = Signal(str, bool)
    progress_updated = Signal(int, int)
    image_count_updated = Signal(int, int)
    automation_finished = Signal(str)
    show_overlay_requested = Signal()
    hide_overlay_requested = Signal()

    # *** __init__ MÓDOSÍTÁSA ***
    def __init__(self, process_controller_ref, prompt_file_path, start_line, end_line, manual_mode=False): 
        super().__init__()
        self.pc_ref = process_controller_ref
        self.prompt_file_path = prompt_file_path
        self.start_line = start_line
        self.end_line = end_line
        self.manual_mode = manual_mode # Új tagváltozó a manuális mód jelzésére
        # *** __init__ MÓDOSÍTÁSA VÉGE ***
        self._is_task_running_in_worker = False
        self._stop_requested_by_main = False
        
        if hasattr(self.pc_ref.gui_automator, 'stop_requested'):
            self.pc_ref.gui_automator.stop_requested = False
        if hasattr(self.pc_ref.gui_automator, 'page_is_prepared'):
            self.pc_ref.gui_automator.page_is_prepared = False

    def _check_pause_and_stop(self): 
        current_qthread = QThread.currentThread()
        if current_qthread:
            current_qthread.msleep(1)

        if self._stop_requested_by_main:
            self.status_updated.emit("Worker: Kemény stop kérés feldolgozva.", False)
            raise InterruptedByUserError("Kemény stop kérés.")

    @Slot()
    def request_hard_stop_from_main(self): 
        self.status_updated.emit("Worker: Kemény leállítási kérelem fogadva.", False)
        self._stop_requested_by_main = True
        if hasattr(self.pc_ref.gui_automator, 'request_stop'):
            self.pc_ref.gui_automator.request_stop()
            
    @Slot()
    def run_automation_task(self):
        mode_text = "MANUÁLIS" if self.manual_mode else "AUTOMATIKUS"
        print(f"AutomationWorker DEBUG: run_automation_task ({mode_text} mód) ELINDULT a worker szálon.")
        
        if self._is_task_running_in_worker:
            self.status_updated.emit(f"Worker ({mode_text}): run_automation_task már fut, új hívás figyelmen kívül hagyva.", True)
            print(f"AutomationWorker DEBUG ({mode_text}): run_automation_task már futott, kilépés.")
            return
        
        print(f"AutomationWorker DEBUG ({mode_text}): _is_task_running_in_worker beállítása True-ra.") 
        self._is_task_running_in_worker = True
        self._stop_requested_by_main = False
        
        if hasattr(self.pc_ref.gui_automator, 'stop_requested'): self.pc_ref.gui_automator.stop_requested = False
        if hasattr(self.pc_ref.gui_automator, 'page_is_prepared'): self.pc_ref.gui_automator.page_is_prepared = False

        # Gondoskodunk róla, hogy a felhasználó azonnal lássa az overlay ablakot,
        # még azelőtt, hogy a böngésző vagy bármely hosszabb művelet elindulna.
        self.show_overlay_requested.emit()

        self.status_updated.emit(f"Worker ({mode_text}): Folyamat indítása a workerben...", False)
        print(f"AutomationWorker DEBUG ({mode_text}): Státusz üzenet elküldve: 'Folyamat indítása a workerben...'")
        
        prompt_handler = self.pc_ref.prompt_handler
        gui_automator = self.pc_ref.gui_automator
        vpn_manager = self.pc_ref.vpn_manager
        browser_manager = self.pc_ref.browser_manager
        current_qthread = QThread.currentThread()
        
        prompts_processed_count = 0
        total_prompts_to_process = 0

        try:
            print(f"AutomationWorker DEBUG ({mode_text}): [TRY_BLOCK_START]") 
            self._check_pause_and_stop()
            print(f"AutomationWorker DEBUG ({mode_text}): [1] _check_pause_and_stop után (prompt betöltés előtt).") 
            
            # *** KOORDINÁTÁK BETÖLTÉSE A MEGFELELŐ MÓDBAN ***
            print(f"AutomationWorker DEBUG ({mode_text}): [1a] Koordináták betöltése gui_automator._load_coordinates(use_manual_coords_flag={self.manual_mode}) hívással.")
            gui_automator._load_coordinates(use_manual_coords_flag=self.manual_mode)
            
            # Ellenőrzés, hogy manuális módban sikerült-e betölteni a koordinátákat
            if self.manual_mode and not gui_automator.coordinates:
                manual_coords_file_path = gui_automator._determine_coords_file_path(True) # Segédfüggvény kell ide
                self.status_updated.emit(f"Worker Hiba ({mode_text}): Manuális koordinátafájl ({manual_coords_file_path}) nem található vagy üres. Manuális mód nem indítható.", True)
                self.automation_finished.emit(f"Manuális koordinátafájl ({os.path.basename(manual_coords_file_path)}) hiba")
                self._is_task_running_in_worker = False
                print(f"AutomationWorker DEBUG ({mode_text}): Manuális koordinátafájl hiba, worker leáll.")
                return
            print(f"AutomationWorker DEBUG ({mode_text}): [1b] Koordináták betöltve, 'self.coordinates' {'tartalmaz adatot' if gui_automator.coordinates else 'üres'}.")
            # *** KOORDINÁTÁK BETÖLTÉSE VÉGE ***

            print(f"AutomationWorker DEBUG ({mode_text}): [2] Kísérlet: 'Promptok betöltése' státusz küldése...") 
            self.status_updated.emit(f"Worker ({mode_text}): Promptok betöltése: '{os.path.basename(self.prompt_file_path)}'", False)
            print(f"AutomationWorker DEBUG ({mode_text}): [3] Státusz elküldve: 'Promptok betöltése'.") 

            prompts = prompt_handler.load_prompts(self.prompt_file_path, self.start_line, self.end_line)
            print(f"AutomationWorker DEBUG ({mode_text}): [4] Promptok betöltve (darabszám: {len(prompts) if prompts else 0}).") 
            
            if not prompts:
                self.status_updated.emit(f"Worker Hiba ({mode_text}): Nem sikerült promptokat betölteni.", True)
                self.automation_finished.emit("Sikertelen prompt betöltés")
                self._is_task_running_in_worker = False
                print(f"AutomationWorker DEBUG ({mode_text}): Nincsenek promptok, a worker befejeződik (prompt hiba).") 
                return
            
            total_prompts_to_process = len(prompts)
            self.status_updated.emit(f"Worker ({mode_text}): {total_prompts_to_process} prompt betöltve.", False)
            self.progress_updated.emit(0, total_prompts_to_process)
            self.image_count_updated.emit(0, total_prompts_to_process)
            print(f"AutomationWorker DEBUG ({mode_text}): [5] Haladás és képszám frissítve a promptok betöltése után.") 

            self._check_pause_and_stop()
            print(f"AutomationWorker DEBUG ({mode_text}): [6] _check_pause_and_stop után (VPN logika előtt).") 

            # --- VPN Logika ---
            skip_vpn_steps = False
            target_vpn_server_group = self.pc_ref.get_setting("vpn_target_server_group", "Singapore")
            target_vpn_country_code = self.pc_ref.get_setting("vpn_target_country_code", "SG")
            vpn_autostart_enabled = self.pc_ref.get_setting("launch_vpn_on_startup", True)

            if not vpn_autostart_enabled:
                skip_vpn_steps = True
                print(f"AutomationWorker DEBUG ({mode_text}): [7] VPN indítás kihagyva (kapcsoló KI).")
                self.status_updated.emit(f"Worker ({mode_text}): NordVPN indítás kihagyva (kapcsoló KI).", False)

            if not skip_vpn_steps:
                print(f"AutomationWorker DEBUG ({mode_text}): [7] IP ellenőrzés VPN előtt...")
                self.status_updated.emit(f"Worker ({mode_text}): IP ellenőrzés VPN előtt...", False)
                current_ip_info_before_vpn = get_public_ip_info()
                if current_ip_info_before_vpn:
                    if current_ip_info_before_vpn.get('country_code') == target_vpn_country_code.upper():
                        skip_vpn_steps = True
                        self.status_updated.emit(f"Worker ({mode_text}): Már a célországban ({target_vpn_country_code}). VPN kihagyva.", False)
                print(f"AutomationWorker DEBUG ({mode_text}): [8] IP ellenőrzés kész, skip_vpn_steps: {skip_vpn_steps}.")

            self._check_pause_and_stop()

            if not skip_vpn_steps:
                print(f"AutomationWorker DEBUG ({mode_text}): [9] VPN csatlakozás kísérlet...")
                if vpn_manager and vpn_manager.nordvpn_executable_path:
                    self.status_updated.emit(f"Worker ({mode_text}): VPN kapcsolat ({target_vpn_server_group})...", False)
                    if not vpn_manager.connect_to_server(target_vpn_server_group, target_vpn_country_code):
                        if not self._stop_requested_by_main:
                             self.status_updated.emit(f"Worker ({mode_text}) Figyelmeztetés: VPN csatlakozás sikertelennek tűnik.", True)
                    else: 
                        if not self._stop_requested_by_main:
                            self.status_updated.emit(f"Worker ({mode_text}): VPN csatlakozás sikeresnek tűnik.", False)
                print(f"AutomationWorker DEBUG ({mode_text}): [10] VPN csatlakozási kísérlet vége.") 
            
            self._check_pause_and_stop()
            print(f"AutomationWorker DEBUG ({mode_text}): [11] _check_pause_and_stop után (Böngésző logika előtt).") 

            # --- Böngésző Logika ---
            browser_launch_enabled = True
            browser_launch_skipped = False

            if self.manual_mode:
                manual_settings = gui_automator.coordinates if (gui_automator and isinstance(gui_automator.coordinates, dict)) else {}
                browser_launch_enabled = bool(manual_settings.get("start_with_browser", True))
                if not browser_launch_enabled:
                    browser_launch_skipped = True
                    skip_msg = f"Worker ({mode_text}): Böngésző automatikus indítása kikapcsolva (manuális beállítás)."
                    self.status_updated.emit(skip_msg, False)
                    print(f"AutomationWorker DEBUG ({mode_text}): [11a] {skip_msg}")

            browser_opened_successfully = False
            if browser_manager and browser_launch_enabled:
                print(f"AutomationWorker DEBUG ({mode_text}): [12] Böngésző indítási kísérlet...")
                self.status_updated.emit(f"Worker ({mode_text}): Böngésző indítása...", False)
                if browser_manager.open_target_url():
                    browser_opened_successfully = True
                    print(f"AutomationWorker DEBUG ({mode_text}): [13] Böngésző sikeresen megnyitva. Overlay megjelenítése kérése...")
                    self.show_overlay_requested.emit()

                    wait_s = 15
                    self.status_updated.emit(f"Worker ({mode_text}): Várakozás a böngészőre ({wait_s}s)...", False)
                    for i in range(wait_s):
                        self._check_pause_and_stop()
                        if current_qthread:
                            current_qthread.msleep(1000)
                        else:
                            time.sleep(1)
                        if (i + 1) % 5 == 0 or i == wait_s - 1:
                            print(f"AutomationWorker DEBUG ({mode_text}): [13a] Böngésző várakozás... ({wait_s - 1 - i}s hátra)")
                            self.status_updated.emit(f"Worker ({mode_text}): Böngésző töltődik... ({wait_s - 1 - i}s)", False)
                    print(f"AutomationWorker DEBUG ({mode_text}): [14] Böngésző várakozási idő letelt.")
                else:
                    if not self._stop_requested_by_main:
                        self.status_updated.emit(f"Worker ({mode_text}) Hiba: Böngésző megnyitása sikertelen.", True)
                        print(f"AutomationWorker DEBUG ({mode_text}): [13b] Böngésző megnyitása sikertelen.")
            elif browser_launch_skipped:
                browser_opened_successfully = True
                print(f"AutomationWorker DEBUG ({mode_text}): [12a] Böngésző indítása kihagyva a felhasználói beállítás miatt.")
            elif not browser_manager:
                print(f"AutomationWorker DEBUG ({mode_text}): [12b] Nincs BrowserManager, böngésző indítás nem lehetséges.")

            self._check_pause_and_stop()
            if not browser_opened_successfully and not self._stop_requested_by_main:
                self.automation_finished.emit("Böngészőhiba")
                self._is_task_running_in_worker = False
                print(f"AutomationWorker DEBUG ({mode_text}): Nincs nyitott böngésző, a worker befejeződik (böngészőhiba).") 
                return
            print(f"AutomationWorker DEBUG ({mode_text}): [15] Böngésző logika vége.") 

            # --- PyAutoGUI Előkészítés ---
            initial_gui_setup_success = False
            if gui_automator and browser_opened_successfully:
                self._check_pause_and_stop()
                print(f"AutomationWorker DEBUG ({mode_text}): [16] Oldal előkészítés (PyAutoGUI) indítása...") 
                self.status_updated.emit(f"Worker ({mode_text}): Oldal előkészítése (PyAutoGUI)...", False)
                # A gui_automator.initial_page_setup() már a helyes (manuális vagy auto) koordinátákat fogja használni,
                # mert a _load_coordinates már lefutott.
                if gui_automator.initial_page_setup(): 
                    initial_gui_setup_success = True
                    self.status_updated.emit(f"Worker ({mode_text}): Oldal előkészítve.", False)
                    print(f"AutomationWorker DEBUG ({mode_text}): [17] Oldal sikeresen előkészítve.") 
                else: 
                    if not self._stop_requested_by_main and not (hasattr(gui_automator, 'stop_requested') and gui_automator.stop_requested):
                        self.status_updated.emit(f"Worker ({mode_text}) Hiba: Oldal előkészítése sikertelen.", True)
                    print(f"AutomationWorker DEBUG ({mode_text}): [17a] Oldal előkészítése sikertelen.") 
            
            self._check_pause_and_stop()
            if not initial_gui_setup_success and not self._stop_requested_by_main and browser_opened_successfully:
                self.automation_finished.emit("PyAutoGUI előkészítési hiba")
                self._is_task_running_in_worker = False
                print(f"AutomationWorker DEBUG ({mode_text}): PyAutoGUI előkészítés sikertelen, worker befejeződik.") 
                return
            print(f"AutomationWorker DEBUG ({mode_text}): [18] PyAutoGUI előkészítés vége.") 
            
            # --- Prompt Feldolgozási Ciklus ---
            if browser_opened_successfully and initial_gui_setup_success:
                print(f"AutomationWorker DEBUG ({mode_text}): [19] Prompt feldolgozási ciklus indítása...") 
                self.status_updated.emit(f"Worker ({mode_text}): Promptok feldolgozásának indítása...", False)
                for i, prompt_text in enumerate(prompts):
                    self._check_pause_and_stop() 
                    current_prompt_no = self.start_line + i
                    print(f"AutomationWorker DEBUG ({mode_text}): [20] Feldolgozás: Prompt #{current_prompt_no} ({i+1}/{total_prompts_to_process})") 
                    self.status_updated.emit(f"Worker ({mode_text}): Feldolgozás: Prompt #{current_prompt_no} ({i+1}/{total_prompts_to_process})", False)
                    self.image_count_updated.emit(i + 1, total_prompts_to_process)

                    if gui_automator.process_single_prompt(prompt_text): 
                        prompts_processed_count += 1
                        self.progress_updated.emit(prompts_processed_count, total_prompts_to_process)
                        print(f"AutomationWorker DEBUG ({mode_text}): [21] Prompt #{current_prompt_no} sikeresen feldolgozva.") 
                    else: 
                        if self._stop_requested_by_main or (hasattr(gui_automator, 'stop_requested') and gui_automator.stop_requested):
                            self.status_updated.emit(f"Worker ({mode_text}): Prompt #{current_prompt_no} feldolgozása megszakítva.", False)
                            print(f"AutomationWorker DEBUG ({mode_text}): [21a] Prompt #{current_prompt_no} feldolgozása megszakítva felhasználó által.") 
                            break 
                        else: 
                            self.status_updated.emit(f"Worker ({mode_text}) Hiba: Prompt #{current_prompt_no} feldolgozásakor. Kihagyva.", True)
                            print(f"AutomationWorker DEBUG ({mode_text}): [21b] Hiba Prompt #{current_prompt_no} feldolgozásakor.") 
                    
                    self._check_pause_and_stop() 
                    if i < total_prompts_to_process - 1:
                        self._check_pause_and_stop()
                        pause_s = self.pc_ref.get_setting("pause_between_prompts_s", 2) # Beállításból
                        print(f"AutomationWorker DEBUG ({mode_text}): [22] Szünet ({pause_s}s) a promptok között...") 
                        self.status_updated.emit(f"Worker ({mode_text}): Szünet ({pause_s}s)...", False)
                        for _sec_idx in range(pause_s):
                            self._check_pause_and_stop() 
                            if current_qthread: current_qthread.msleep(1000)
                            else: time.sleep(1) 
                print(f"AutomationWorker DEBUG ({mode_text}): [23] Prompt feldolgozási ciklus vége.") 
            
            self._check_pause_and_stop() 
            summary_msg_end = f"Feldolgozva: {prompts_processed_count}/{total_prompts_to_process}."
            if self._stop_requested_by_main : 
                summary_msg_end = f"Felhasználó által leállítva. {summary_msg_end}"
            self.automation_finished.emit(summary_msg_end)
            print(f"AutomationWorker DEBUG ({mode_text}): [24] Automatizálás befejezve. Üzenet: {summary_msg_end}") 

        except InterruptedByUserError as e:
            self.status_updated.emit(f"Worker ({mode_text}): Folyamat megszakítva - {e}", False) 
            self.automation_finished.emit(f"Felhasználó által leállítva. Feldolgozva: {prompts_processed_count}/{total_prompts_to_process}.")
            print(f"AutomationWorker DEBUG ({mode_text}): [EXCEPT] Folyamat megszakítva felhasználó által: {e}") 
        except Exception as e:
            error_msg = f"Worker ({mode_text}) Kritikus Hiba: {e}"
            self.status_updated.emit(error_msg, True)
            print(f"WORKER ({mode_text}) KRITIKUS HIBA: {e}\n{traceback.format_exc()}")
            self.automation_finished.emit(f"Kritikus hiba. Feldolgozva: {prompts_processed_count}/{total_prompts_to_process}.")
            print(f"AutomationWorker DEBUG ({mode_text}): [EXCEPT] Kritikus hiba: {e}") 
        finally:
            self._is_task_running_in_worker = False
            self.hide_overlay_requested.emit()
            print(f"AutomationWorker DEBUG ({mode_text}): [FINALLY] run_automation_task finally blokk lefutott.") 


class ProcessController(QObject):
    def __init__(self, main_window_ref): 
        super().__init__()
        self.main_window = main_window_ref
        self.overlay_window = None
        self._is_automation_active = False
        self._stop_requested_by_user = False
        self.settings = {} # Beállítások tárolására

        # Aktuálisan feldolgozott kép sorszámának követése
        self.current_image_index = 0
        self.total_images_to_process = 0

        self.automation_thread = None
        self.worker = None
        
        try:
            current_file_path = os.path.abspath(__file__)
            core_dir_path = os.path.dirname(current_file_path)
            self.project_root_path = os.path.dirname(core_dir_path)
        except Exception: self.project_root_path = os.getcwd()
        
        self.downloads_dir = os.path.join(self.project_root_path, "downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)
        
        self._load_settings() # Beállítások betöltése

        self.prompt_handler = PromptHandler(self)
        self.gui_automator = PyAutoGuiAutomator(self) 
        self.vpn_manager = VpnManager(self)
        self.browser_manager = BrowserManager(self)

        self.hotkey_listener = GlobalHotkeyListener()
        self._connect_hotkey_signals()
        self.hotkey_listener.start()
        
        print(f"ProcessController inicializálva. Letöltési mappa: {self.downloads_dir}")

    def _load_settings(self):
        settings_file = self._settings_file_path()
        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        default_settings = {
            "pause_between_prompts_s": 2,
            "vpn_target_server_group": "Singapore",
            "vpn_target_country_code": "SG",
            "launch_vpn_on_startup": True,
            "last_prompt_file_path": ""
            # Ide jöhetnek további alapértelmezett értékek
        }
        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self.settings = {**default_settings, **loaded_settings} # Alapértelmezett felülírása a betöltöttel
                    print(f"Beállítások betöltve innen: {settings_file}")
            else:
                self.settings = default_settings
                print(f"Beállítási fájl ({settings_file}) nem található, alapértelmezett értékek használva.")
        except Exception as e:
            print(f"Hiba a beállítások betöltése közben: {e}. Alapértelmezett értékek használva.")
            self.settings = default_settings

    def get_setting(self, key, default_value=None):
        return self.settings.get(key, default_value)

    def update_setting(self, key, value, persist=True):
        self.settings[key] = value
        if persist:
            self._save_settings()

    def _settings_file_path(self):
        return os.path.join(self.project_root_path, "config", "settings.json")

    def _save_settings(self):
        settings_file = self._settings_file_path()
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
            print(f"Beállítások elmentve ide: {settings_file}")
        except Exception as e:
            print(f"Hiba a beállítások mentésekor: {e}")

    def _connect_hotkey_signals(self): 
        if self.hotkey_listener:
            # ... (a hotkey signalok összekötése változatlan)
            self.hotkey_listener.emitter.stop_automation_requested.connect(self.handle_stop_automation_hotkey)
            self.hotkey_listener.emitter.music_play_pause_requested.connect(self.handle_music_play_pause)
            self.hotkey_listener.emitter.music_next_track_requested.connect(self.handle_music_next_track)
            self.hotkey_listener.emitter.music_prev_track_requested.connect(self.handle_music_prev_track)
            self.hotkey_listener.emitter.music_volume_up_requested.connect(self.handle_music_volume_up)
            self.hotkey_listener.emitter.music_volume_down_requested.connect(self.handle_music_volume_down)
            print("ProcessController: Globális billentyűparancs signálok összekötve.")

    def _focus_main_window(self):
        if not self.main_window:
            return
        if self.main_window.isMinimized():
            self.main_window.showNormal()
        self.main_window.raise_()
        self.main_window.activateWindow()

    @Slot()
    def handle_stop_automation_hotkey(self):
        if not self._is_automation_active:
            self.update_gui_status("Nincs futó automatizálás leállításhoz (Esc).", False)
            self._focus_main_window()
            return

        mode_text = "MANUÁLIS" if (self.worker and self.worker.manual_mode) else "AUTOMATIKUS"
        self.update_gui_status(f"{mode_text} automatizálás leállítása (Esc)...", False)
        self.stop_automation_process()
        self._handle_hide_overlay_request()
        self._focus_main_window()

    @Slot()
    def handle_music_play_pause(self): #
        player_widget = self._get_active_music_player_widget()
        if player_widget: player_widget.play_pause_action()

    @Slot()
    def handle_music_next_track(self): #
        player_widget = self._get_active_music_player_widget()
        if player_widget: player_widget.next_track_action()

    @Slot()
    def handle_music_prev_track(self): #
        player_widget = self._get_active_music_player_widget()
        if player_widget: player_widget.previous_track_action()

    @Slot()
    def handle_music_volume_up(self): #
        player_widget = self._get_active_music_player_widget()
        if player_widget: player_widget.increase_volume_action()

    @Slot()
    def handle_music_volume_down(self): #
        player_widget = self._get_active_music_player_widget()
        if player_widget: player_widget.decrease_volume_action()
        
    def _get_active_music_player_widget(self): 
        if self.overlay_window and self.overlay_window.isVisible() and hasattr(self.overlay_window, 'music_player_widget'):
            return self.overlay_window.music_player_widget
        elif self.main_window and hasattr(self.main_window, 'music_player_widget'):
            return self.main_window.music_player_widget
        return None
        
    @Slot(str, bool)
    def _handle_worker_status_update(self, message, is_error): 
        self.update_gui_status(message, is_error)

    @Slot(int, int)
    def _handle_worker_progress_update(self, current_step, total_steps): 
        if self.overlay_window:
            self._update_overlay_progress(current_step, total_steps)

    @Slot(int, int)
    def _handle_worker_image_count_update(self, current_image, total_images):
        self.current_image_index = current_image
        self.total_images_to_process = total_images
        if self.overlay_window:
            self._update_overlay_image_count(current_image, total_images)

    @Slot(str)
    def _handle_automation_finished(self, summary_message):
        mode_text = "MANUÁLIS" if (self.worker and self.worker.manual_mode) else "AUTOMATIKUS"
        self.update_gui_status(f"{mode_text} automatizálás befejeződött: {summary_message}", False)
        self._is_automation_active = False
        self._stop_requested_by_user = False
        self.current_image_index = 0
        self.total_images_to_process = 0
        self._focus_main_window()

        if hasattr(self.gui_automator, 'close_browser'):
            self.gui_automator.close_browser()

        if self.vpn_manager and hasattr(self.vpn_manager, 'is_connected_to_target_server') and self.vpn_manager.is_connected_to_target_server:
            self.update_gui_status("VPN kapcsolat bontása a folyamat végén (ha aktív)...", False)
            self.vpn_manager.disconnect_vpn()

        if self.automation_thread:
            if self.automation_thread.isRunning():
                self.automation_thread.quit()
                if not self.automation_thread.wait(1500):
                    print("ProcessController Figyelmeztetés: Autom. szál nem állt le, terminate.")
                    self.automation_thread.terminate()
                    self.automation_thread.wait()
            self.automation_thread.deleteLater() # Biztosítjuk a QThread törlését
            self.automation_thread = None
        if self.worker:
            self.worker.deleteLater()
            self.worker = None


    @Slot()
    def _handle_show_overlay_request(self):
        if OverlayWindow and self.main_window:
            if not self.overlay_window:
                print("ProcessController DEBUG: Új OverlayWindow példány létrehozása (worker kérésére).")
                self.overlay_window = OverlayWindow()
                self.overlay_window.stop_requested_signal.connect(self.handle_stop_automation_hotkey)
            print("ProcessController DEBUG: OverlayWindow.show() hívása (worker kérésére).")
            self.overlay_window.show()
            QApplication.processEvents()

    @Slot()
    def _handle_hide_overlay_request(self): 
        if self.overlay_window:
            print("ProcessController DEBUG: OverlayWindow.close() hívása (worker kérésére).") 
            self.overlay_window.close()
            # self.overlay_window.deleteLater() # Jobb, ha itt töröljük, ha már nem kell
            self.overlay_window = None

    # *** start_full_automation_process MÓDOSÍTÁSA ***
    def start_full_automation_process(self, prompt_file_path, start_line, end_line, manual_mode=False):
        mode_text = "MANUÁLIS" if manual_mode else "AUTOMATIKUS"
        if self._is_automation_active or (self.automation_thread and self.automation_thread.isRunning()):
            self.update_gui_status(f"Egy automatizálási folyamat ({mode_text} mód) már fut!", True)
            print(f"ProcessController DEBUG ({mode_text}): start_full_automation_process - Már fut, új indítás blokkolva.")
            return

        print(f"ProcessController DEBUG ({mode_text}): start_full_automation_process hívva, új worker és szál létrehozása.")
        self._is_automation_active = True
        self._stop_requested_by_user = False
        self.current_image_index = 0
        self.total_images_to_process = 0

        self.automation_thread = QThread(self)
        # *** manual_mode ÁTADÁSA A WORKERNEK ***
        self.worker = AutomationWorker(self, prompt_file_path, start_line, end_line, manual_mode)
        self.worker.moveToThread(self.automation_thread)
        print(f"ProcessController DEBUG ({mode_text}): Worker létrehozva és szálhoz rendelve.") 

        self.worker.status_updated.connect(self._handle_worker_status_update)
        self.worker.progress_updated.connect(self._handle_worker_progress_update)
        self.worker.image_count_updated.connect(self._handle_worker_image_count_update)
        self.worker.automation_finished.connect(self._handle_automation_finished)
        self.worker.show_overlay_requested.connect(self._handle_show_overlay_request)
        self.worker.hide_overlay_requested.connect(self._handle_hide_overlay_request)
        print(f"ProcessController DEBUG ({mode_text}): Worker signalok összekötve.") 
        
        self.automation_thread.started.connect(self.worker.run_automation_task)
        # Biztosítjuk, hogy a worker és a thread is törlődjön a futás végén
        self.worker.automation_finished.connect(self.automation_thread.quit) # Leállítja a threadet, ha a worker végzett
        self.automation_thread.finished.connect(self.worker.deleteLater) # Törli a workert, ha a thread leállt
        self.automation_thread.finished.connect(self.automation_thread.deleteLater) # Törli magát a threadet
        print(f"ProcessController DEBUG ({mode_text}): Szál 'started' és 'finished' signalok összekötve a megfelelő törlésekkel.") 

        self.update_gui_status(f"{mode_text} automatizálási szál indítása...", False)
        self.automation_thread.start()
        print(f"ProcessController DEBUG ({mode_text}): Automatizálási szál elindítva (automation_thread.start() hívva).") 
    # *** start_full_automation_process MÓDOSÍTÁSÁNAK VÉGE ***

    def stop_automation_process(self): 
        mode_text = "MANUÁLIS" if (self.worker and self.worker.manual_mode) else "AUTOMATIKUS"
        self._stop_requested_by_user = True
        if hasattr(self.gui_automator, 'request_stop'):
             self.gui_automator.request_stop()

        if self.worker and self.automation_thread and self.automation_thread.isRunning():
            self.update_gui_status(f"{mode_text} automatizálás KEMÉNY leállítási kérelme elküldve a workernek...", False)
            QMetaObject.invokeMethod(self.worker, "request_hard_stop_from_main", Qt.QueuedConnection)
        elif not self._is_automation_active:
             self.update_gui_status("Nincs aktívan futó automatizálási folyamat a kemény leállításhoz.", False)

    def update_gui_status(self, message, is_error=False): 
        if self.main_window and hasattr(self.main_window, 'update_status'):
            display_message = message
            # Egységesítjük a hibaüzenetek prefixét
            error_prefixes = ["hiba:", "vpn hiba:", "web hiba:", "böngésző hiba:", "automatizálási hiba:", "worker hiba:", "worker hiba (manuális):", "worker hiba (automatikus):"]
            is_already_prefixed_as_error = any(message.lower().startswith(p) for p in error_prefixes)
            
            if is_error and not is_already_prefixed_as_error:
                # Meghatározzuk a módot, ha a workerből jön az üzenet
                mode_prefix = ""
                if "worker" in message.lower(): # Csak ha a workerrel kapcsolatos
                    current_mode = "MANUÁLIS" if (self.worker and hasattr(self.worker, 'manual_mode') and self.worker.manual_mode) else "AUTOMATIKUS"
                    if not any(m in message.lower() for m in ["(manuális)", "(automatikus)"]): # Ha még nincs benne a mód
                         mode_prefix = f" ({current_mode.capitalize()})"


                # Ha a message már tartalmaz "Hiba:" vagy hasonló jelzést (pl. "Worker Hiba:"), akkor nem adjuk hozzá újra.
                if not message.lower().startswith("hiba:"):
                     display_message = f"Hiba{mode_prefix}: {message}"
                elif mode_prefix: # Ha már "Hiba:"-val kezdődik, de a módot hozzá akarjuk adni
                    # Óvatosan adjuk hozzá, hogy ne duplikáljuk a "Hiba:" részt
                    if message.startswith("Hiba: "):
                        display_message = f"Hiba{mode_prefix}: {message[len('Hiba: '):]}"
                    else: # Ha pl. "Worker Hiba:"
                        parts = message.split(":", 1)
                        if len(parts) > 1:
                            display_message = f"{parts[0]}{mode_prefix}: {parts[1].strip()}"
                        else: # Nem várt formátum, csak hozzáadjuk
                            display_message = f"{message}{mode_prefix}"


            QMetaObject.invokeMethod(self.main_window, "update_status", Qt.QueuedConnection, Q_ARG(str, display_message))

        if self.overlay_window and hasattr(self.overlay_window, 'update_action_label') and self.overlay_window.isVisible():
            QMetaObject.invokeMethod(self.overlay_window, "update_action_label", Qt.QueuedConnection, Q_ARG(str, message))

    def _update_overlay_progress(self, current_step, total_steps): 
        if self.overlay_window and hasattr(self.overlay_window, 'update_progress_bar') and self.overlay_window.isVisible():
            QMetaObject.invokeMethod(self.overlay_window, "update_progress_bar", Qt.QueuedConnection,
                                     Q_ARG(int, current_step), Q_ARG(int, total_steps))

    def _update_overlay_image_count(self, current_image, total_images): 
        if self.overlay_window and hasattr(self.overlay_window, 'update_image_count_label') and self.overlay_window.isVisible():
            QMetaObject.invokeMethod(self.overlay_window, "update_image_count_label", Qt.QueuedConnection,
                                     Q_ARG(int, current_image), Q_ARG(int, total_images))
                                     
    def cleanup_on_exit(self): 
        print("ProcessController: Cleanup on exit indítása...")
        if self.hotkey_listener:
            print("ProcessController: Globális billentyűfigyelő leállítása...")
            self.hotkey_listener.stop()
        
        if self._is_automation_active and self.worker and self.automation_thread and self.automation_thread.isRunning():
            print("ProcessController: Aktív automatizálás leállítása a cleanup során...")
            self._stop_requested_by_user = True
            if hasattr(self.gui_automator, 'request_stop'): self.gui_automator.request_stop()
            QMetaObject.invokeMethod(self.worker, "request_hard_stop_from_main", Qt.QueuedConnection)
            if self.automation_thread:
                if not self.automation_thread.wait(3000): # Növelt várakozási idő
                    print("ProcessController Figyelmeztetés: Worker szál nem állt le a cleanup során időben, terminate.")
                    self.automation_thread.terminate()
                    self.automation_thread.wait() # Várjuk meg a terminate befejezését
        elif self.automation_thread and self.automation_thread.isRunning(): # Ha nincs aktív worker, de a szál fut
             print("ProcessController: Nem aktív worker, de futó szál leállítása...")
             self.automation_thread.quit()
             if not self.automation_thread.wait(1000): 
                 print("ProcessController Figyelmeztetés: Szál nem állt le quit-re, terminate.")
                 self.automation_thread.terminate()
                 self.automation_thread.wait()
        
        # Explicit törlés kérése a QObject-eknek, ha még léteznek
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.automation_thread:
            self.automation_thread.deleteLater()
            self.automation_thread = None
            
        print("ProcessController: VPN bontás ellenőrzése cleanup során...")
        if self.vpn_manager and hasattr(self.vpn_manager, 'is_connected_to_target_server') and self.vpn_manager.is_connected_to_target_server:
            self.update_gui_status("VPN kapcsolat bontása kilépéskor...", False)
            self.vpn_manager.disconnect_vpn()

        print("ProcessController: Cleanup on exit befejezve.")


    def is_running(self): 
        return self._is_automation_active
