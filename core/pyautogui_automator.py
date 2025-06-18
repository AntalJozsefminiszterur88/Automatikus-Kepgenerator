# core/pyautogui_automator.py
import pyautogui
import time
import os
import json
import numpy as np

easyocr = None 
try:
    import easyocr 
except ImportError:
    print("FIGYELEM: Az 'easyocr' könyvtár nincs telepítve. Telepítsd: pip install easyocr")
except Exception as e: 
    print(f"FIGYELEM: Hiba történt az 'easyocr' könyvtár importálása közben: {e}")

try:
    from utils.ui_scanner import (find_prompt_area_dynamically,
                                  find_generate_button_dynamic,
                                  get_screen_size_util,
                                  GENERATE_BUTTON_COLOR_TARGET)
    print("PyAutoGuiAutomator INFO: utils.ui_scanner sikeresen importálva.") 
except ImportError:
    print("PyAutoGuiAutomator FIGYELEM: Az 'utils.ui_scanner' modul nem található vagy hibás. Dinamikus UI elemkeresés nem lesz elérhető.") 
    find_prompt_area_dynamically = None
    find_generate_button_dynamic = None
    get_screen_size_util = lambda: pyautogui.size() # Fallback
    GENERATE_BUTTON_COLOR_TARGET = None


from .page_initializer import PageInitializer
from .prompt_executor import PromptExecutor
from .image_flow_handler import ImageFlowHandler


class PyAutoGuiAutomator:
    def __init__(self, process_controller_ref=None):
        self.process_controller = process_controller_ref
        self.stop_requested = False
        self.page_is_prepared = False
        self.coordinates = {} # Kezdetben üres, a _load_coordinates tölti fel

        try:
            documents_path = os.path.join(os.path.expanduser('~'), 'Documents')
            umkgl_solutions_folder = os.path.join(documents_path, "UMKGL Solutions")
            app_specific_folder = os.path.join(umkgl_solutions_folder, "Automatikus-Kepgenerator")
            self.config_dir = os.path.join(app_specific_folder, "Config")
            
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            self.project_root = os.path.dirname(self.script_dir)
            self.assets_dir = os.path.join(self.project_root, "automation_assets")

            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir, exist_ok=True)
            if not os.path.exists(self.assets_dir): # Assets mappa létrehozása, ha hiányzik
                os.makedirs(self.assets_dir, exist_ok=True)

        except Exception as e_path:
            self._notify_status(f"Hiba a konfigurációs útvonalak beállítása közben (Dokumentumok mappa): {e_path}. Visszaállás alapértelmezett projektmappára.", is_error=True)
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            self.project_root = os.path.dirname(self.script_dir)
            self.config_dir = os.path.join(self.project_root, "config") # Fallback config
            self.assets_dir = os.path.join(self.project_root, "automation_assets") # Fallback assets
            try:
                if not os.path.exists(self.config_dir): os.makedirs(self.config_dir, exist_ok=True)
                if not os.path.exists(self.assets_dir): os.makedirs(self.assets_dir, exist_ok=True)
            except Exception as e_mkdir_fallback:
                self._notify_status(f"Hiba a fallback config/assets mappa létrehozásakor: {e_mkdir_fallback}", is_error=True)
        
        # A konkrét ui_coords_file-t a _load_coordinates fogja meghatározni a mód alapján.
        # self.ui_coords_file_auto = os.path.join(self.config_dir, "ui_coordinates.json")
        # self.ui_coords_file_manual = os.path.join(self.config_dir, "ui_coordinates_manual.json")


        self.ocr_reader = None
        if easyocr:
            try:
                self._notify_status("EasyOCR olvasó inicializálása ('en', 'hu')...")
                self.ocr_reader = easyocr.Reader(['en', 'hu'], gpu=False) # GPU False alapértelmezetten
                self._notify_status("EasyOCR olvasó sikeresen inicializálva.")
            except Exception as e_ocr_init:
                self._notify_status(f"Hiba az EasyOCR olvasó inicializálásakor: {e_ocr_init}", is_error=True)
                self.ocr_reader = None 
        else:
            self._notify_status("EasyOCR modul nem érhető el, OCR funkciók korlátozottak (PyAutoGuiAutomator init).", is_error=False)


        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1 # Alapértelmezett PyAutoGUI szünet
        
        screen_util_func = get_screen_size_util if 'get_screen_size_util' in globals() and callable(globals()['get_screen_size_util']) else None
        
        if screen_util_func:
            try:
                self.screen_width, self.screen_height = screen_util_func()
            except Exception as e_screen:
                 self._notify_status(f"Figyelmeztetés: get_screen_size_util hiba ({e_screen}), pyautogui.size() használata.", is_error=True)
                 self.screen_width, self.screen_height = pyautogui.size()
        else: # Ha a ui_scanner nem importálódott helyesen
             self._notify_status("Figyelmeztetés: get_screen_size_util nem elérhető (ui_scanner hiba?), pyautogui.size() használata.", is_error=True)
             self.screen_width, self.screen_height = pyautogui.size()
            
        # A self.coordinates-t a _load_coordinates fogja feltölteni a megfelelő fájlból.
        self.last_known_prompt_rect = None # Ezt is a _load_coordinates után állítjuk be

        self.page_initializer = PageInitializer(self)
        self.prompt_executor = PromptExecutor(self)
        self.image_flow_handler = ImageFlowHandler(self)
        self._notify_status("PyAutoGuiAutomator sikeresen inicializálva.")


    # *** ÚJ SEGÉDFÜGGVÉNY ***
    def _determine_coords_file_path(self, use_manual_coords_flag=False):
        """Meghatározza a használandó koordinátafájl elérési útját."""
        if use_manual_coords_flag:
            return os.path.join(self.config_dir, "ui_coordinates_manual.json")
        else:
            return os.path.join(self.config_dir, "ui_coordinates.json")

    # *** _load_coordinates MÓDOSÍTÁSA ***
    def _load_coordinates(self, use_manual_coords_flag=False):
        """
        Betölti a UI koordinátákat a megadott módnak megfelelő fájlból.
        Frissíti a self.coordinates és self.last_known_prompt_rect tagváltozókat.
        Visszaadja a betöltött koordinátákat (dict) vagy üres dict-et hiba/hiány esetén.
        """
        coords_file_to_load = self._determine_coords_file_path(use_manual_coords_flag)
        mode_str = "MANUÁLIS" if use_manual_coords_flag else "AUTOMATIKUS"
        
        self.coordinates = {} # Alaphelyzetbe állítás minden betöltés előtt
        self.last_known_prompt_rect = None

        try:
            if os.path.exists(coords_file_to_load):
                with open(coords_file_to_load, 'r', encoding='utf-8') as f:
                    coords = json.load(f)
                    if coords and isinstance(coords, dict) :
                        self._notify_status(f"UI koordináták ({mode_str} mód) betöltve innen: {coords_file_to_load}")
                        self.coordinates = coords
                        # last_known_prompt_rect frissítése, ha létezik a betöltött adatokban
                        if "prompt_rect" in self.coordinates and isinstance(self.coordinates.get("prompt_rect"), dict):
                            self.last_known_prompt_rect = self.coordinates["prompt_rect"]
                            self._notify_status(f"  -> last_known_prompt_rect beállítva: {self.last_known_prompt_rect}", is_error=False)
                        else:
                             self._notify_status(f"  -> 'prompt_rect' nem található vagy nem dict a betöltött ({mode_str}) koordinátákban.", is_error=False)
                        return self.coordinates 
                    else:
                        self._notify_status(f"Koordináta fájl ({coords_file_to_load}, {mode_str} mód) üres vagy hibás formátumú.", is_error=True)
            else:
                self._notify_status(f"Koordináta fájl ({coords_file_to_load}, {mode_str} mód) nem található. Dinamikus keresés lehet szükséges (ha auto módban van).", is_error=False) # Nem feltétlen hiba
        except json.JSONDecodeError as e_json:
            self._notify_status(f"JSON dekódolási hiba a(z) '{coords_file_to_load}' ({mode_str} mód) fájlban: {e_json}", is_error=True)
        except Exception as e:
            self._notify_status(f"Általános hiba a koordináták betöltése közben ({coords_file_to_load}, {mode_str} mód): {e}", is_error=True)
        
        # Ha idáig eljut, a betöltés nem sikerült, vagy a fájl nem létezett
        return self.coordinates # Visszaadja a (valószínűleg üres) self.coordinates-t


    def _save_coordinates(self):
        """
        Elmenti az aktuális self.coordinates tartalmát az AUTOMATIKUS módhoz tartozó
        `ui_coordinates.json` fájlba. Ezt tipikusan a dinamikus keresés eredményeinek
        mentésére használjuk. A manuális koordinátákat a ManualCoordsWindow menti.
        """
        auto_coords_file = self._determine_coords_file_path(use_manual_coords_flag=False)
        try:
            if not self.coordinates: # Csak akkor mentünk, ha van mit
                self._notify_status("Nincsenek érvényes koordináták a mentéshez (self.coordinates üres) az automatikus fájlba.", is_error=True)
                return
            
            # Biztosítjuk, hogy a config mappa létezzen
            if not os.path.exists(self.config_dir): 
                os.makedirs(self.config_dir, exist_ok=True) 
                self._notify_status(f"Config mappa létrehozva: {self.config_dir}", is_error=False)

            with open(auto_coords_file, 'w', encoding='utf-8') as f:
                json.dump(self.coordinates, f, indent=4)
            self._notify_status(f"UI koordináták (automatikus/dinamikus eredmény) elmentve ide: {auto_coords_file}")
        except Exception as e:
            self._notify_status(f"Hiba az UI koordináták (automatikus) mentése közben ({auto_coords_file}): {e}", is_error=True)

    def _notify_status(self, message, is_error=False):
        if self.process_controller and hasattr(self.process_controller, 'update_gui_status'):
            # Meghatározzuk az aktuális futási módot a worker alapján, ha van worker és manual_mode attribútuma
            mode_prefix = ""
            if self.process_controller.worker and hasattr(self.process_controller.worker, 'manual_mode'):
                current_mode_text = "MANUÁLIS" if self.process_controller.worker.manual_mode else "AUTOMATIKUS"
                # Csak akkor adjuk hozzá, ha még nincs benne a szövegben, és releváns (pl. PyAutoGUI üzenet)
                if f"({current_mode_text.lower()})" not in message.lower() and \
                   not any(p in message.lower() for p in ["easyocr", "vpn", "böngésző", "prompthandler"]): # Ne minden üzenethez
                    if "pyautogui" in message.lower() or "koordinát" in message.lower() or "oldal" in message.lower() or "prompt mező" in message.lower():
                         mode_prefix = f" ({current_mode_text}) "


            # Összefűzzük a PyAutoGUI prefixet, a mód prefixet és az üzenetet
            # Elkerüljük a "PyAutoGuiAutomator PyAutoGuiAutomator" duplikációt
            if message.startswith("PyAutoGuiAutomator"):
                base_message = message
            else:
                base_message = f"PyAutoGuiAutomator{mode_prefix}: {message}"

            self.process_controller.update_gui_status(base_message, is_error=is_error)
        else:
            # Konzolra is kiírjuk
            prefix = "PyAutoGuiAutomator "
            if is_error: prefix += "HIBA: "
            elif "FIGYELEM" in message: prefix += "FIGYELEM: "
            elif "INFO" not in message: prefix += "INFO: "
            
            final_message = message if message.startswith("PyAutoGuiAutomator") else f"{prefix}{message}"
            print(final_message)


    def request_stop(self):
        self._notify_status("PyAutoGUI automatizálási folyamat leállítási kérelem érkezett.")
        self.stop_requested = True

    def _check_for_stop_request(self):
        if self.process_controller and hasattr(self.process_controller, '_stop_requested_by_user') and self.process_controller._stop_requested_by_user:
            self.stop_requested = True
        return self.stop_requested
    
    def _find_and_activate_prompt_field(self):
        # Ez a metódus a self.coordinates-t használja, amit a _load_coordinates már feltöltött
        # a megfelelő (manuális vagy auto) fájlból.
        self._notify_status("Prompt mező keresése és aktiválása folyamatban...", is_error=False)
        
        if self._check_for_stop_request():
            self._notify_status("Prompt mező keresés megszakítva felhasználói kéréssel.", is_error=True)
            return False
        
        click_x, click_y = None, None
        prompt_field_found_via_coords = False

        # 1. Próbálkozás a már betöltött self.coordinates alapján
        # A self.coordinates-t a run_automation_task-ban hívott _load_coordinates tölti fel a módnak megfelelően.
        if "prompt_click_x" in self.coordinates and "prompt_click_y" in self.coordinates:
            click_x = self.coordinates["prompt_click_x"]
            click_y = self.coordinates["prompt_click_y"]
            # A last_known_prompt_rect már be lett állítva a _load_coordinates-ben, ha létezett.
            # Ha nem létezett, akkor itt None lesz, ami jelzi a dinamikus keresés szükségességét, ha auto módban vagyunk.
            self._notify_status(f"Betöltött prompt mező kattintási pozíció használata: X={click_x}, Y={click_y}. (last_known_prompt_rect: {'van' if self.last_known_prompt_rect else 'nincs'})", is_error=False)
            prompt_field_found_via_coords = True
        else:
            self._notify_status("Nincsenek (teljes) betöltött prompt kattintási koordináták. Dinamikus keresés (ha auto mód) vagy hiba (ha manuális mód és a fájl hiányos).", is_error=False)

        # 2. Ha a betöltött koordináták nem elegendőek, ÉS NEM manuális módban vagyunk (vagy manuális, de nem volt adat),
        #    akkor próbálkozunk dinamikus kereséssel.
        #    A self.process_controller.worker.manual_mode jelzi az aktuális futási módot.
        is_manual_run = self.process_controller.worker.manual_mode if self.process_controller.worker else False

        if not prompt_field_found_via_coords:
            if not is_manual_run: # Csak automatikus módban futtatunk dinamikus keresést itt
                self._notify_status("Automatikus mód: Dinamikus prompt mező keresés INDUL...", is_error=False)
                if find_prompt_area_dynamically: # Ellenőrizzük, hogy elérhető-e
                    rect = find_prompt_area_dynamically(self.screen_width, self.screen_height, notify_callback=self._notify_status)
                    if rect:
                        self._notify_status(f"Dinamikusan talált prompt terület: {rect}. Kattintási pont számítása és koordináták frissítése/mentése...", is_error=False)
                        self.last_known_prompt_rect = rect
                        click_x = rect['x'] + rect['width'] // 2
                        # A kattintási Y legyen a terület felső 30%-a, hogy biztosan a beviteli mezőbe essen.
                        click_y = rect['y'] + int(rect['height'] * 0.30) 
                        click_x = max(0, min(click_x, self.screen_width - 1))
                        click_y = max(0, min(click_y, self.screen_height - 1))
                        
                        # Frissítjük a self.coordinates-t a dinamikusan talált adatokkal
                        self.coordinates["prompt_click_x"] = click_x
                        self.coordinates["prompt_click_y"] = click_y
                        self.coordinates["prompt_rect"] = rect 
                        self._save_coordinates() # Elmenti az új, dinamikusan talált koordinátákat az ui_coordinates.json-be
                        self._notify_status(f"Dinamikusan talált és AUTOMATIKUS fájlba mentett prompt terület. Kattintás ide: X={click_x}, Y={click_y}", is_error=False)
                        prompt_field_found_via_coords = True # Most már van koordinátánk
                    else:
                        self._notify_status("HIBA (Automatikus mód): A prompt területet dinamikus kereséssel sem sikerült megtalálni.", is_error=True)
                else:
                     self._notify_status("HIBA (Automatikus mód): Dinamikus prompt kereső (utils.ui_scanner) nem elérhető.", is_error=True)
            else: # Manuális mód, de nem voltak koordináták a fájlban
                self._notify_status("HIBA (Manuális mód): A manuális koordinátafájl nem tartalmazta a 'prompt_click_x'/'prompt_click_y' értékeket.", is_error=True)
                return False # Manuális módban, ha nincs explicit koordináta, ne keressen dinamikusan.

        # 3. Végső ellenőrzés és kattintás
        if prompt_field_found_via_coords and click_x is not None and click_y is not None:
            try:
                self._notify_status(f"Kattintás a prompt mezőre: X={click_x}, Y={click_y}", is_error=False)
                pyautogui.moveTo(click_x, click_y, duration=0.1)
                pyautogui.click()
                time.sleep(0.3) # Rövid várakozás az aktiválódásra
                self._notify_status("Prompt mező sikeresen aktiválva.", is_error=False)
                return True
            except Exception as e:
                self._notify_status(f"Hiba a prompt mezőre való kattintás közben (X:{click_x}, Y:{click_y}): {e}", is_error=True)
                return False
        else:
            self._notify_status("HIBA (Végső): Nem sikerült meghatározni és aktiválni a prompt mezőt.", is_error=True)
            return False


    def initial_page_setup(self):
        if self._check_for_stop_request(): return False
        # A self.coordinates már a megfelelő (manuális/auto) adatokat tartalmazza
        # a run_automation_task-ban történt _load_coordinates hívás miatt.
        if not self.page_is_prepared:
            self._notify_status(f"Oldal előkészítés indítása (page_is_prepared: {self.page_is_prepared}). Koordináták: {' vannak ' if self.coordinates else ' nincsenek betöltve'}")
            if self.page_initializer.run_initial_tool_opening_sequence(): # Ez használja a self.coordinates-t, ha van benne tool_open_click
                self.page_is_prepared = True
                self._notify_status("Oldal kezdeti beállítása sikeres (PageInitializer).")
                return True
            else:
                self.page_is_prepared = False
                self._notify_status("HIBA: Oldal kezdeti beállítása sikertelen (PageInitializer).", is_error=True)
                return False
        self._notify_status("Az oldal kezdeti beállítása már korábban megtörtént.")
        return True

    def process_single_prompt(self, prompt_text):
        self.stop_requested = False 
        if self._check_for_stop_request(): return False

        if not self.page_is_prepared:
            self._notify_status("HIBA: Az oldal nincs előkészítve a prompt feldolgozásához. Az initial_page_setup nem futott le sikeresen vagy nem lett újra ellenőrizve.", is_error=True)
            # Megpróbáljuk újra az oldal előkészítését, hátha csak állapotvesztés történt
            if not self.initial_page_setup():
                 self._notify_status("HIBA: Ismételt oldal előkészítési kísérlet is sikertelen. Prompt feldolgozása leáll.", is_error=True)
                 return False
            self._notify_status("Oldal sikeresen újra-előkészítve. Folytatás...")


        # A prompt_executor és image_flow_handler a self.automator (ami ez a PyAutoGuiAutomator példány)
        # self.coordinates tagváltozóját fogja használni, ami már a helyes módban van.
        if not self.prompt_executor.enter_prompt_and_initiate_generation(prompt_text):
            return False # Hibaüzenetet a PromptExecutor már küldött
        if self._check_for_stop_request(): return False
        
        if not self.image_flow_handler.monitor_generation_and_download():
            return False # Hibaüzenetet az ImageFlowHandler már küldött
            
        self._notify_status(f"Prompt ('{prompt_text[:30]}...') sikeresen feldolgozva PyAutoGUI-val.")
        return True
    
    def close_browser(self): # Ennek a funkciója egyelőre nincs implementálva
        self._notify_status("PyAutoGUI böngészőműveletek befejezve (close_browser hívva, de nincs konkrét művelet).")
        pass
