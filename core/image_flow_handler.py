# core/image_flow_handler.py
import pyautogui
import time
# import os

class ImageFlowHandler:
    def __init__(self, automator_ref):
        self.automator = automator_ref

    def _notify_status(self, message, is_error=False):
        mode_prefix = ""
        if self.automator.process_controller and \
           self.automator.process_controller.worker and \
           hasattr(self.automator.process_controller.worker, 'manual_mode'):
            current_mode_text = "MANUÁLIS" if self.automator.process_controller.worker.manual_mode else "AUTOMATIKUS"
            if f"({current_mode_text.lower()})" not in message.lower() and \
               not any(p in message.lower() for p in ["easyocr", "vpn", "böngésző", "prompthandler", "pyautogui"]):
                 mode_prefix = f" ({current_mode_text}) "
        
        if message.startswith("ImageFlowHandler"):
            final_message = message
        else:
            final_message = f"ImageFlowHandler{mode_prefix}: {message}"
            
        self.automator._notify_status(final_message, is_error)


    def _check_for_stop_request(self):
        return self.automator._check_for_stop_request()

    def monitor_generation_and_download(self):
        print("ImageFlowHandler DEBUG: monitor_generation_and_download KEZDÉS.") 
        if self._check_for_stop_request():
            print("ImageFlowHandler DEBUG: Stop kérés a metódus elején.") 
            return False
        
        self._notify_status("KÉP FELDOLGOZÁS: Generálás figyelése és letöltés indítása...")
        
        self._notify_status("Kép generálásának figyelése pixel alapján...")
        initial_wait_after_generate_click_s = 2 
        self._notify_status(f"Várakozás {initial_wait_after_generate_click_s}s a generálás tényleges megkezdésére...") 
        time.sleep(initial_wait_after_generate_click_s) 
        if self._check_for_stop_request():
            print("ImageFlowHandler DEBUG: Stop kérés a kezdeti várakozás után.") 
            return False

        pixel_x_to_watch = 890 
        pixel_y_to_watch = 487 
        expected_color_during_generation = (217, 217, 217) 
        max_wait_s_for_pixel_change = 45 
        check_interval_s = 0.5 

        self._notify_status(f"Pixel ({pixel_x_to_watch},{pixel_y_to_watch}) színének figyelése. Várt szín generálás közben: {expected_color_during_generation}.") 
        start_pixel_watch_time = time.time() 
        color_changed = False 
        
        pixel_watch_success = False 
        while time.time() - start_pixel_watch_time < max_wait_s_for_pixel_change: 
            if self._check_for_stop_request():
                self._notify_status("Pixel figyelés megszakítva felhasználói kéréssel.", is_error=True) 
                print("ImageFlowHandler DEBUG: Pixel figyelés megszakítva stop kéréssel.") 
                return False
            try:
                current_pixel_color = pyautogui.pixel(pixel_x_to_watch, pixel_y_to_watch) 
                if current_pixel_color[0] != expected_color_during_generation[0] or \
                   current_pixel_color[1] != expected_color_during_generation[1] or \
                   current_pixel_color[2] != expected_color_during_generation[2]: 
                    self._notify_status(f"Pixel színe megváltozott! (Új szín: {current_pixel_color}). Generálás befejeződött.") 
                    color_changed = True 
                    pixel_watch_success = True 
                    break 
                else:
                    remaining_time = int(max_wait_s_for_pixel_change - (time.time() - start_pixel_watch_time)) 
                    if remaining_time % 5 == 0 or remaining_time < 5 : 
                        self._notify_status(f"Generálás még folyamatban (pixel színe: {current_pixel_color})... ({remaining_time}s hátra a timeout-ig)") 
            except Exception as e_pixel:
                self._notify_status(f"Hiba a pixel ({pixel_x_to_watch},{pixel_y_to_watch}) színének olvasása közben: {e_pixel}", is_error=True) 
                time.sleep(check_interval_s * 2) 
            time.sleep(check_interval_s) 
        
        if not pixel_watch_success: 
            self._notify_status(f"Időtúllépés: A pixel színe nem változott meg {max_wait_s_for_pixel_change}s alatt.", is_error=True) 
            print("ImageFlowHandler DEBUG: Pixel figyelés TIMEOUT.") 
            return False
        print("ImageFlowHandler DEBUG: Pixel figyelés SIKERES (szín megváltozott).") 

        wait_after_color_change_s = 1 
        self._notify_status(f"Generálás befejeződött (pixel szín alapján). Várakozás {wait_after_color_change_s}s a letöltés előtt...") 
        time.sleep(wait_after_color_change_s) 
        if self._check_for_stop_request():
            print("ImageFlowHandler DEBUG: Stop kérés a színváltozás utáni várakozáskor.") 
            return False
        
        self._notify_status("Kép elkészült (pixel figyelés alapján). Letöltés következik...") 

        download_button_x = None
        download_button_y = None
        if "download_button_click_x" in self.automator.coordinates and \
           "download_button_click_y" in self.automator.coordinates: 
            download_button_x = self.automator.coordinates["download_button_click_x"] 
            download_button_y = self.automator.coordinates["download_button_click_y"] 
            self._notify_status(f"Betöltött letöltés gomb pozíció használata: X={download_button_x}, Y={download_button_y}") 
        else:
            is_manual_run = self.automator.process_controller.worker.manual_mode if self.automator.process_controller.worker else False
            if is_manual_run:
                self._notify_status(f"HIBA (Manuális mód): 'download_button_click' koordináták hiányoznak a manuális fájlból!", is_error=True)
                return False
            else:
                download_button_x = 925 
                download_button_y = 704 
                self._notify_status(f"FIGYELEM: Letöltés gomb koordinátái nem voltak betöltve. Fallback pozíció használata: X={download_button_x}, Y={download_button_y}. Ez valószínűleg hiba a koordináták kezelésében!", is_error=True)

        self._notify_status(f"Kattintás a letöltés gombra: X={download_button_x}, Y={download_button_y}") 
        try:
            print(f"ImageFlowHandler DEBUG: Kattintás a letöltés gombra: X={download_button_x}, Y={download_button_y}") 
            pyautogui.moveTo(download_button_x, download_button_y, duration=0.2) 
            pyautogui.click() 
            self._notify_status("Letöltés gombra kattintva.") 
            print("ImageFlowHandler DEBUG: Letöltés gombra kattintás SIKERES.") 
        except Exception as e_click_download:
            self._notify_status(f"Hiba történt a letöltés gombra való kattintás közben (X:{download_button_x}, Y:{download_button_y}): {e_click_download}", is_error=True) 
            print(f"ImageFlowHandler DEBUG: Hiba a letöltés gombra kattintáskor: {e_click_download}") 
            return False

        download_confirmation_wait_s = 1
        # *** JAVÍTÁS ITT: A komment és az 'if' külön sorba került ***
        # Előzőleg itt volt a hiba: # *** MÓDOSÍTÁS VÉGE *** if download_confirmation_wait_s > 0:                                         
        if download_confirmation_wait_s > 0:                                         
            self._notify_status(f"Rövid várakozás ({download_confirmation_wait_s}s) a letöltés elindulására...") 
            time.sleep(download_confirmation_wait_s)  
        # *** JAVÍTÁS VÉGE ***
        
        self._notify_status("Kép letöltése elindítva (feltételezett).") 
        self._notify_status("KÉP FELDOLGOZÁS: Sikeres.") 
        print("ImageFlowHandler DEBUG: monitor_generation_and_download SIKERES.") 
        return True
