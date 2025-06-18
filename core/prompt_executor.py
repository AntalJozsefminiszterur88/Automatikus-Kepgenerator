# core/prompt_executor.py
import pyautogui
import time
# import os # Nem tűnik használtnak itt közvetlenül

try:
    from utils.ui_scanner import (find_generate_button_dynamic, 
                                  GENERATE_BUTTON_COLOR_TARGET)
except ImportError:
    print("FIGYELEM: Az 'utils.ui_scanner' modul nem található (PromptExecutor).")
    find_generate_button_dynamic = None
    GENERATE_BUTTON_COLOR_TARGET = None 

class PromptExecutor:
    def __init__(self, automator_ref):
        self.automator = automator_ref

    def _notify_status(self, message, is_error=False):
        # Ez a metódus már létezik és használva van, a hívásainak kellene megjelenniük.
        # A biztonság kedvéért itt is kiírjuk konzolra.
        print(f"PromptExecutor {'HIBA' if is_error else 'INFO'}: {message}")
        self.automator._notify_status(message, is_error)

    def _check_for_stop_request(self):
        return self.automator._check_for_stop_request()

    def enter_prompt_and_initiate_generation(self, prompt_text):
        print(f"PromptExecutor DEBUG: enter_prompt_and_initiate_generation KEZDÉS, prompt: '{prompt_text[:20]}...'") # ÚJ DEBUG
        if self._check_for_stop_request():
            print("PromptExecutor DEBUG: Stop kérés a metódus elején.") # ÚJ DEBUG
            return False
        
        self._notify_status(f"PROMPT VÉGREHAJTÁS: Kezdés ('{prompt_text[:20]}...')")

        print("PromptExecutor DEBUG: Kísérlet a prompt mező aktiválására...") # ÚJ DEBUG
        if not self.automator._find_and_activate_prompt_field(): 
            self._notify_status("HIBA: Nem sikerült újra-aktiválni a prompt mezőt a beírás előtt (PromptExecutor).", is_error=True)
            print("PromptExecutor DEBUG: _find_and_activate_prompt_field SIKERTELEN.") # ÚJ DEBUG
            return False
        print("PromptExecutor DEBUG: Prompt mező aktiválva.") # ÚJ DEBUG

        self._notify_status(f"Prompt beírása: '{prompt_text[:30]}...'")
        try:
            print(f"PromptExecutor DEBUG: Prompt beírása pyautogui-val: '{prompt_text[:30]}...'") # ÚJ DEBUG
            pyautogui.hotkey('ctrl', 'a'); time.sleep(0.05) 
            pyautogui.press('delete'); time.sleep(0.1) 
            pyautogui.typewrite(prompt_text, interval=0.01); time.sleep(0.2)
            print("PromptExecutor DEBUG: Prompt beírása kész.") # ÚJ DEBUG
        except Exception as e_type:
            self._notify_status(f"Hiba a prompt beírása közben: {e_type}", is_error=True)
            print(f"PromptExecutor DEBUG: Hiba a prompt beírása közben: {e_type}") # ÚJ DEBUG
            return False

        # ... (Generálás Gomb kezelése változatlan, de a _notify_status hívásai miatt már tartalmaznak print-et) ...
        # A generálás gomb kezelésének végén is jó lenne egy debug print, hogy tudjuk, sikeres volt-e.
        gen_x, gen_y = None, None
        action_taken_for_generate_button = False

        if "generate_button_click_x" in self.automator.coordinates and \
           "generate_button_click_y" in self.automator.coordinates:
            gen_x = self.automator.coordinates["generate_button_click_x"]
            gen_y = self.automator.coordinates["generate_button_click_y"]
            self._notify_status(f"Mentett generálás gomb pozíció használata: X={gen_x}, Y={gen_y}")
            action_taken_for_generate_button = True
        elif find_generate_button_dynamic and self.automator.last_known_prompt_rect and GENERATE_BUTTON_COLOR_TARGET:
            self._notify_status(f"Generálás gomb dinamikus keresése szín ({GENERATE_BUTTON_COLOR_TARGET}) alapján...") #
            pos = find_generate_button_dynamic(
                self.automator.last_known_prompt_rect, 
                self.automator.screen_width, 
                self.automator.screen_height, 
                notify_callback=self._notify_status
            )
            if pos:
                gen_x, gen_y = pos
                self.automator.coordinates["generate_button_click_x"] = gen_x #
                self.automator.coordinates["generate_button_click_y"] = gen_y #
                self.automator._save_coordinates() 
                self._notify_status(f"Dinamikusan talált generálás gomb. Kattintás ide: X={gen_x}, Y={gen_y}") #
                action_taken_for_generate_button = True
            else: 
                self._notify_status("HIBA: Generálás gombot nem sikerült dinamikusan megtalálni.", is_error=True) #
                print("PromptExecutor DEBUG: Generálás gomb dinamikus keresése SIKERTELEN.") # ÚJ DEBUG
                return False
        else:
            self._notify_status("HIBA: Generálás gomb pozíciója nem ismert (dinamikus kereső nem elérhető/konfigurálva, vagy a prompt terület ismeretlen, és nincs mentett).", is_error=True) #
            print("PromptExecutor DEBUG: Generálás gomb pozíciója ISMERETLEN.") # ÚJ DEBUG
            return False

        if not action_taken_for_generate_button or gen_x is None:
            self._notify_status("HIBA: Nem sikerült meghatározni a generálás gomb pozícióját a kattintáshoz.", is_error=True) #
            print("PromptExecutor DEBUG: Generálás gomb pozíció VÉGÜL SEM MEGHATÁROZOTT.") # ÚJ DEBUG
            return False

        try:
            print(f"PromptExecutor DEBUG: Kattintás a generálás gombra: X={gen_x}, Y={gen_y}") # ÚJ DEBUG
            pyautogui.moveTo(gen_x, gen_y, duration=0.2) #
            pyautogui.click() #
            self._notify_status("Generálás elindítva.") #
            self._notify_status("PROMPT VÉGREHAJTÁS: Sikeres (Prompt beírva, generálás elindítva).")
            print("PromptExecutor DEBUG: enter_prompt_and_initiate_generation SIKERES.") # ÚJ DEBUG
            return True
        except Exception as e_click_generate:
            self._notify_status(f"Hiba történt a generálás gombra való kattintás közben (X:{gen_x}, Y:{gen_y}): {e_click_generate}", is_error=True) #
            if "generate_button_click_x" in self.automator.coordinates: del self.automator.coordinates["generate_button_click_x"] #
            if "generate_button_click_y" in self.automator.coordinates: del self.automator.coordinates["generate_button_click_y"] #
            self.automator._save_coordinates() #
            print(f"PromptExecutor DEBUG: Hiba a generálás gombra kattintáskor: {e_click_generate}") # ÚJ DEBUG
            return False
