# core/image_automation.py

import pyautogui
import time
import os # Szükséges lehet, ha a régi szkript használt fájlútvonalakat

# A pynput importját egyelőre nem vesszük át,
# mert a stop_program logikát a ProcessController fogja kezelni.
# A billentyűzetfigyelést is átgondolhatjuk, hogy szükséges-e ebben a formában.

class ImageAutomationController:
    """
    Felelős a weboldalon történő kép generálási és letöltési folyamat
    automatizálásáért a pyautogui segítségével.
    """
    def __init__(self, process_controller_ref=None):
        self.process_controller = process_controller_ref
        self.stop_requested = False # Ezt a ProcessController állíthatja True-ra

        # A googleprompt.py-ból átvett és adaptált beállítások
        # Ezeket később a config fájlból is betölthetjük, vagy a GUI-n keresztül állíthatjuk
        
        # Fix koordináták (Figyelem: Ezek nagyon érzékenyek a képernyőfelbontásra és ablakelrendezésre!)
        # Ezeket mindenképp konfigurálhatóvá kell tenni, vagy egy kalibrációs lépést bevezetni.
        self.input_field_position = (1008, 871)      # Írás előtti koordináta
        self.arrow_guide_position = (1461, 973)      # Arrow (korábbi segéd) ikon koordinátája
        self.download_icon_coords = (953, 706)       # Letöltés ikon koordinátája
        
        # Várakozási idők
        self.wait_before_download_click_s = 2.0 
        self.wait_time_for_image_creation_s = 20
        
        # Egyéb belső állapotok
        self.current_prompt_text = ""

        print("ImageAutomationController inicializálva.")

    def _notify_status(self, message):
        """Segédfüggvény a státusz közlésére a ProcessControlleren keresztül."""
        if self.process_controller and hasattr(self.process_controller, 'update_gui_status'):
            self.process_controller.update_gui_status(message)
        else:
            print(f"[ImageAutomationController]: {message}")

    def request_stop(self):
        """Külső kérés a folyamat leállítására."""
        self._notify_status("Kép automatizálási folyamat leállítási kérelem érkezett.")
        self.stop_requested = True

    def _check_for_stop_request(self):
        """Ellenőrzi, hogy érkezett-e leállítási kérelem."""
        if self.process_controller and hasattr(self.process_controller, 'is_running'):
            if not self.process_controller.is_running(): # Ha a fő controller leállt
                self.stop_requested = True
        
        if self.stop_requested:
            self._notify_status("Leállítási kérelem észlelve, művelet megszakítva.")
        return self.stop_requested

    def type_prompt_and_click_arrow(self, prompt_text):
        """
        Beírja a promptot a megadott mezőbe és rákattint a generáló nyílra.
        A googleprompt.py 'type_prompt_and_click_arrow' függvényének adaptációja.
        """
        self.current_prompt_text = prompt_text
        self._notify_status(f"Prompt beírása ({self.current_prompt_text[:30]}...) és nyílra kattintás előkészítése.")

        if self._check_for_stop_request(): return False

        try:
            self._notify_status(f"Kattintás a prompt mező pozíciójára: {self.input_field_position}")
            pyautogui.moveTo(self.input_field_position[0], self.input_field_position[1], duration=0.5)
            if self._check_for_stop_request(): return False
            pyautogui.click()
            time.sleep(0.5) # Rövid várakozás a kattintás után
            if self._check_for_stop_request(): return False

            # Mező tartalmának törlése (Ctrl+A, Backspace)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            if self._check_for_stop_request(): return False
            pyautogui.press('backspace')
            time.sleep(0.2)
            if self._check_for_stop_request(): return False

            self._notify_status(f"Prompt beírása: {self.current_prompt_text[:30]}...")
            pyautogui.typewrite(self.current_prompt_text, interval=0.05) # interval a karakterenkénti várakozás
            time.sleep(0.3)
            if self._check_for_stop_request(): return False

            self._notify_status(f"Kattintás az 'arrow guide' pozícióra: {self.arrow_guide_position}...")
            pyautogui.moveTo(self.arrow_guide_position[0], self.arrow_guide_position[1], duration=0.3)
            if self._check_for_stop_request(): return False
            pyautogui.click()
            time.sleep(0.5) # Várakozás a kattintás után, hogy a weboldal reagálhasson
            
            if self._check_for_stop_request(): return False

            self._notify_status("Prompt beírva és 'arrow guide' pozícióra kattintva.")
            return True

        except Exception as e:
            error_msg = f"Hiba a prompt beírása vagy a nyílra kattintás közben: {e}"
            self._notify_status(error_msg)
            print(error_msg)
            # Itt lehetne pyautogui.FailSafeException-t is figyelni, ha be van kapcsolva
            return False

    def wait_for_image_generation(self):
        """
        Várakozik a képalkotásra a beállított ideig.
        A googleprompt.py fix várakozási logikájának adaptációja.
        """
        self._notify_status(f"Képalkotás folyamatban, várakozás: {self.wait_time_for_image_creation_s} másodperc...")
        
        start_wait_time = time.time()
        while time.time() - start_wait_time < self.wait_time_for_image_creation_s:
            if self._check_for_stop_request():
                self._notify_status("Várakozás megszakítva a képalkotás alatt.")
                return False
            # GUI frissítés a hátralévő idővel (ProcessControlleren keresztül)
            remaining_time = int(self.wait_time_for_image_creation_s - (time.time() - start_wait_time))
            self._notify_status(f"Képalkotás folyamatban... ({remaining_time}s hátra)") # Ezt gyakran küldheti
            time.sleep(0.5) # Rövid időközönként ellenőrizzük a stop kérést

        if self._check_for_stop_request():
            self._notify_status(f"Várakozás megszakítva a {self.wait_time_for_image_creation_s}mp után.")
            return False
            
        self._notify_status("Képalkotási várakozási idő letelt.")
        return True

    def click_download_image(self):
        """
        Rákattint a letöltés ikonra a megadott koordinátákon.
        A googleprompt.py 'click_download_at_coordinates' függvényének adaptációja.
        """
        self._notify_status("Letöltés ikonra kattintás előkészítése...")
        if self._check_for_stop_request(): return False

        try:
            self._notify_status(f"Egér mozgatása a letöltés ikonhoz: {self.download_icon_coords}...")
            pyautogui.moveTo(self.download_icon_coords[0], self.download_icon_coords[1], duration=0.3)
            if self._check_for_stop_request(): return False

            if self.wait_before_download_click_s > 0:
                self._notify_status(f"Várakozás {self.wait_before_download_click_s} másodperc a letöltés ikonra kattintás előtt...")
                start_wait_dl = time.time()
                while time.time() - start_wait_dl < self.wait_before_download_click_s:
                    if self._check_for_stop_request():
                        self._notify_status("Várakozás megszakítva a letöltés ikonra kattintás előtt.")
                        return False
                    remaining_time_dl = int(self.wait_before_download_click_s - (time.time() - start_wait_dl))
                    self._notify_status(f"Várakozás a letöltés előtt ({remaining_time_dl}s)...")
                    time.sleep(0.1)
            
            if self._check_for_stop_request(): return False
            
            self._notify_status(f"Kattintás a letöltés ikonra ({self.download_icon_coords})")
            pyautogui.click(button='left') # Feltételezzük, hogy bal klikk kell
            self._notify_status("Letöltés ikonra kattintás megtörtént.")
            time.sleep(1.5) # Rövid várakozás a kattintás után, hogy a letöltés elindulhasson
            return True

        except Exception as e:
            error_msg = f"Hiba a letöltés ikonra kattintás során ({self.download_icon_coords}): {e}"
            self._notify_status(error_msg)
            print(error_msg)
            return False

    def clear_prompt_field_after_download(self):
        """
        Kitörli a prompt mezőt a letöltés után (ha szükséges).
        A googleprompt.py 'clear_prompt_field' függvényének adaptációja.
        """
        self._notify_status("Prompt mező törlésének előkészítése letöltés után...")
        if self._check_for_stop_request(): return

        try:
            self._notify_status(f"Kattintás a prompt mező pozíciójára ({self.input_field_position}) a törléshez.")
            pyautogui.moveTo(self.input_field_position[0], self.input_field_position[1], duration=0.3)
            if self._check_for_stop_request(): return
            pyautogui.click()
            time.sleep(0.3)
            if self._check_for_stop_request(): return

            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            if self._check_for_stop_request(): return
            pyautogui.press('backspace')
            time.sleep(0.2)
            self._notify_status("Prompt mező tartalma törölve letöltés után.")
        
        except Exception as e:
            error_msg = f"Hiba a prompt mező törlése közben: {e}"
            self._notify_status(error_msg)
            print(error_msg)
            
    def process_single_prompt(self, prompt_text):
        """
        Végrehajtja a teljes ciklust egyetlen promptra: beírás, generálás, várakozás, letöltés.
        """
        self.stop_requested = False # Minden új promptnál alaphelyzetbe állítjuk
        self.current_prompt_text = prompt_text

        if not self.type_prompt_and_click_arrow(prompt_text):
            if not self._check_for_stop_request(): # Csak akkor logoljunk hibaként, ha nem mi állítottuk le
                 self._notify_status(f"Hiba a prompt ({prompt_text[:30]}...) beírása közben. Ez a prompt kimarad.")
            return False # Hiba vagy megszakítás

        if not self.wait_for_image_generation():
            if not self._check_for_stop_request():
                self._notify_status(f"Hiba a kép generálási várakozás közben a ({prompt_text[:30]}...) promptnál. Ez a prompt kimarad.")
            return False

        if not self.click_download_image():
            if not self._check_for_stop_request():
                self._notify_status(f"Hiba a kép letöltése közben a ({prompt_text[:30]}...) promptnál. Ez a prompt kimarad.")
            return False
        
        # A prompt mező törlése opcionális lehet, vagy a ciklus elején történik
        # A googleprompt.py a letöltés után törölt.
        self.clear_prompt_field_after_download()
        if self._check_for_stop_request(): return False # Ha a törlés közben állították le

        self._notify_status(f"Prompt ({prompt_text[:30]}...) sikeresen feldolgozva és kép letöltve.")
        return True
