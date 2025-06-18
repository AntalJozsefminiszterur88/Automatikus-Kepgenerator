# core/browser_manager.py
import webbrowser
import platform
import subprocess
import time
from utils.system_helper import find_executable_path

class BrowserManager:
    def __init__(self, process_controller_ref=None):
        self.process_controller = process_controller_ref
        self.preferred_browsers_windows = [
            {"name": "Opera", "executable": "opera.exe", "path_key_env": "OPERA_PATH"}, # Opera GX-nek lehet más neve
            {"name": "Chrome", "executable": "chrome.exe", "path_key_env": "CHROME_PATH"}
        ]
        # macOS és Linux esetén a `webbrowser` modul gyakran jobban kezeli a böngészőválasztást,
        # de itt is lehetne explicit keresést implementálni, ha szükséges.
        # pl. macOS: "Google Chrome.app", "Opera.app"
        self.target_url = "https://labs.google/fx/tools/whisk" # Ezt később configból is vehetnénk

        print("BrowserManager inicializálva.")

    def _notify_status(self, message, is_error=False):
        if self.process_controller and hasattr(self.process_controller, 'update_gui_status'):
            prefix = "Böngésző Hiba: " if is_error else "Böngésző Info: "
            self.process_controller.update_gui_status(f"{prefix}{message}")
        else:
            print(f"[BrowserManager]: {message}")

    def _launch_browser_explicitly(self, browser_executable_path, url):
        """Megpróbálja elindítani a böngészőt a megadott elérési útvonallal és URL-lel."""
        try:
            self._notify_status(f"Böngésző indítása ({browser_executable_path}) a következő URL-lel: {url}")
            # Windows-on a Popen jobb lehet, hogy ne blokkoljon, és új ablakot nyisson.
            # A `webbrowser.register` és `webbrowser.get(using=...).open_new_tab(url)`
            # egy komplexebb, de platformfüggetlenebb megoldás lehetne, ha a böngészőt regisztráljuk.
            # Egyelőre a subprocess.Popen-t használjuk az explicit indításhoz.
            subprocess.Popen([browser_executable_path, url])
            self._notify_status("Böngésző indítási parancs kiadva.")
            return True
        except Exception as e:
            self._notify_status(f"Hiba a(z) '{browser_executable_path}' böngésző explicit indítása közben: {e}", is_error=True)
            return False

    def open_target_url(self):
        """
        Megnyitja a cél URL-t az előnyben részesített böngészővel,
        vagy az alapértelmezett böngészővel.
        """
        self._notify_status(f"Cél URL megnyitási kísérlet: {self.target_url}")

        # Specifikus böngészők keresése és indítása (Windows példa)
        if platform.system() == "Windows":
            for browser_info in self.preferred_browsers_windows:
                browser_name = browser_info["name"]
                browser_exe = browser_info["executable"]
                
                self._notify_status(f"{browser_name} keresése...")
                browser_path = find_executable_path(browser_exe)
                
                if browser_path:
                    self._notify_status(f"{browser_name} megtalálva itt: {browser_path}")
                    if self._launch_browser_explicitly(browser_path, self.target_url):
                        self._notify_status(f"{browser_name} sikeresen elindítva a cél URL-lel.")
                        return True # Sikeres indítás az egyik preferált böngészővel
                    else:
                        self._notify_status(f"Nem sikerült elindítani a(z) {browser_name}-t. Próbálkozás a következővel...", is_error=True)
                else:
                    self._notify_status(f"{browser_name} ('{browser_exe}') nem található ismert helyeken vagy a PATH-ban.")
        
        # Ha a specifikus böngészők egyike sem indítható, vagy nem Windows a platform,
        # próbálkozzunk az alapértelmezett böngészővel a `webbrowser` modulon keresztül.
        self._notify_status("Próbálkozás az alapértelmezett rendszerböngészővel...")
        try:
            # A webbrowser.open_new_tab() megpróbál új lapot nyitni, ha lehetséges,
            # vagy új ablakot, ha az nem.
            if webbrowser.open_new_tab(self.target_url):
                self._notify_status(f"Cél URL sikeresen megnyitva az alapértelmezett böngészőben (vagy új lapon).")
                return True
            else:
                self._notify_status("Az alapértelmezett böngésző nem tudta megnyitni az URL-t (open_new_tab False-t adott vissza).", is_error=True)
                return False
        except webbrowser.Error as e:
            self._notify_status(f"Hiba az alapértelmezett böngésző használata közben: {e}", is_error=True)
            return False
        except Exception as e: # Egyéb váratlan hibák
             self._notify_status(f"Váratlan hiba a böngésző megnyitása közben: {e}", is_error=True)
             return False
