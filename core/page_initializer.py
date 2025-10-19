# core/page_initializer.py
import pyautogui
import time
import os
import numpy as np # Az _find_text_with_easyocr_and_click metódushoz kell

# EasyOCR importálása (a PyAutoGuiAutomator adja át az ocr_reader-t)

class PageInitializer:
    def __init__(self, automator_ref):
        """
        Inicializáló.
        Args:
            automator_ref: Hivatkozás a fő PyAutoGuiAutomator példányra,
                           hogy elérje annak segédfüggvényeit és tagváltozóit.
        """
        self.automator = automator_ref
        self.ocr_reader = self.automator.ocr_reader

    def _notify_status(self, message, is_error=False):
        self.automator._notify_status(message, is_error=is_error)

    def _check_for_stop_request(self):
        return self.automator._check_for_stop_request()

    def _find_text_with_easyocr_and_click(self, target_text, description,
                                          timeout_s=20,
                                          initial_confidence_threshold=0.6,
                                          min_confidence_threshold=0.2,
                                          confidence_step=0.1,
                                          click_element=True,
                                          search_region=None):
        if self._check_for_stop_request(): return None
        if not self.ocr_reader:
            self._notify_status("HIBA: EasyOCR olvasó nincs inicializálva a szövegkereséshez (PageInitializer).", is_error=True)
            return None

        region_log_str = f"({search_region[0]},{search_region[1]},{search_region[2]},{search_region[3]})" if search_region else "Teljes képernyő"
        self._notify_status(f"Szöveg keresése (PageInitializer): '{target_text}' ({description}) (max {timeout_s}s, régió: {region_log_str}). Kezdeti konf.: {initial_confidence_threshold:.2f}")

        overall_start_time = time.time()
        attempt_confidence = initial_confidence_threshold
        last_screenshot_pil = None

        while attempt_confidence >= min_confidence_threshold:
            if self._check_for_stop_request(): return None

            elapsed_time = time.time() - overall_start_time
            if elapsed_time > timeout_s:
                self._notify_status(f"Időkorlát ({timeout_s}s) lejárt '{target_text}' keresése közben (utolsó konf.: {attempt_confidence:.2f}).", is_error=True) # is_error=True helyett lehetne False, ha ez csak egy próbálkozás a sok közül
                break

            # Logolás ritkítása, vagy csak ha a konfidencia változik
            # self._notify_status(f"Keresés '{target_text}' ({description}) konfidenciával: {attempt_confidence:.2f}. Fennmaradó idő: {max(0, timeout_s - elapsed_time):.1f}s")

            try:
                last_screenshot_pil = pyautogui.screenshot(region=search_region)
                if self._check_for_stop_request(): return None

                screenshot_np = np.array(last_screenshot_pil)
                ocr_results = self.ocr_reader.readtext(screenshot_np, detail=1, paragraph=False)

                best_match_for_current_confidence = None

                for (bbox, text, prob) in ocr_results:
                    if self._check_for_stop_request(): return None
                    text_strip = text.strip()
                    if prob >= attempt_confidence and target_text.lower() in text_strip.lower():
                        x_coords = [p[0] for p in bbox]
                        y_coords = [p[1] for p in bbox]
                        min_x_rel, max_x_rel = min(x_coords), max(x_coords)
                        min_y_rel, max_y_rel = min(y_coords), max(y_coords)

                        center_x_rel = (min_x_rel + max_x_rel) // 2
                        center_y_rel = (min_y_rel + max_y_rel) // 2

                        abs_center_x = center_x_rel + (search_region[0] if search_region else 0)
                        abs_center_y = center_y_rel + (search_region[1] if search_region else 0)

                        current_match = {"x": abs_center_x, "y": abs_center_y, "text": text_strip, "prob": prob}
                        if best_match_for_current_confidence is None or prob > best_match_for_current_confidence["prob"]:
                            best_match_for_current_confidence = current_match

                if best_match_for_current_confidence:
                    found_text_info = best_match_for_current_confidence
                    self._notify_status(f"Szöveg '{found_text_info['text']}' (cél: '{target_text}') MEGTALÁLVA itt: ({found_text_info['x']}, {found_text_info['y']}) konfidenciával: {found_text_info['prob']:.2f} (keresési konf.: {attempt_confidence:.2f})")
                    if click_element:
                        pyautogui.moveTo(found_text_info['x'], found_text_info['y'], duration=0.1)
                        pyautogui.click()
                        self._notify_status(f"'{description}' (EasyOCR alapján) gombra/helyre kattintva.")
                    return (found_text_info['x'], found_text_info['y'])

            except Exception as e_ocr_loop:
                self._notify_status(f"Hiba az EasyOCR feldolgozási ciklusban (konf: {attempt_confidence:.2f}): {e_ocr_loop}", is_error=True)
                time.sleep(0.3)

            attempt_confidence -= confidence_step
            if attempt_confidence < min_confidence_threshold and min_confidence_threshold > 0: # Hogy a ciklus lefusson a min_confidence_threshold értéken is.
                if abs(attempt_confidence + confidence_step - min_confidence_threshold) < 0.001 : # Ha pont a min_confidence_threshold volt az előző
                     break
                attempt_confidence = min_confidence_threshold # Utolsó próba a minimális konfidenciával

        # self._notify_status(f"'{target_text}' szöveg nem található EasyOCR-rel {timeout_s} másodperc alatt, még {min_confidence_threshold:.2f} minimális konfidenciával sem a(z) {'Teljes képernyő' if not search_region else str(search_region)} régióban.", is_error=True) # Ezt csak akkor jelezzük, ha az összes kísérlet sikertelen volt.
        # Hibakereső kép mentése (opcionális, de hasznos lehet)
        # Ezt a hívó oldalon kellene kezelni, ha az ÖSSZES próbálkozás sikertelen.
        # Itt csak akkor mentjük, ha EZ a konkrét keresés (ezzel a target_text-tel) volt sikertelen.
        # De mivel ezt egy ciklusban hívjuk, a debug kép mentése jobb, ha a ciklus végén történik, ha semmi sem lett találva.
        # Egyelőre hagyjuk itt, de tudatában vagyunk, hogy többször is menthet.
        try:
            if last_screenshot_pil and self.automator.assets_dir and os.path.exists(self.automator.assets_dir):
                region_str_file = f"region_{search_region[0]}_{search_region[1]}_{search_region[2]}_{search_region[3]}" if search_region else "fullscreen"
                ts = time.strftime("%Y%m%d_%H%M%S")
                safe_target_text = "".join(c if c.isalnum() else "_" for c in target_text[:20])
                debug_img_name = f"debug_ocr_PI_indiv_fail_{safe_target_text}_{region_str_file}_{ts}.png"
                debug_screenshot_path = os.path.join(self.automator.assets_dir, debug_img_name)
                last_screenshot_pil.save(debug_screenshot_path)
                self._notify_status(f"Hibakeresési képernyőkép mentve (PageInitializer, egyedi OCR sikertelen: '{target_text}'): {debug_screenshot_path}", is_error=False) # is_error=False, mert ez csak egy részleges hiba lehet
        except Exception as e_screenshot:
            self._notify_status(f"Hiba a hibakeresési képernyőkép mentése közben (PageInitializer): {e_screenshot}", is_error=True)
        return None

    def run_initial_tool_opening_sequence(self):
        """
        Elvégzi az oldal kezdeti előkészítését: a megfelelő gombra ("ESZKÖZ MEGNYITÁSA" vagy "ENTER TOOL")
        kattint, vár az oldal betöltődésére, majd aktiválja a prompt mezőt.
        """
        is_manual_run = False
        if self.automator.process_controller and self.automator.process_controller.worker:
            is_manual_run = bool(getattr(self.automator.process_controller.worker, 'manual_mode', False))

        if is_manual_run and not bool(self.automator.coordinates.get("perform_tool_open_click", True)):
            self._notify_status("Manuális mód: 'Eszköz megnyitása' lépés kihagyva a beállítás alapján.")
            return True

        if self._check_for_stop_request(): return False

        self._notify_status("OLDAL ELŐKÉSZÍTÉS: Kezdeti műveletek indítása...")
        initial_wait_s = 3
        self._notify_status(f"Extra várakozás {initial_wait_s}s az oldalinterakció előtt...")
        for _ in range(initial_wait_s):
            if self._check_for_stop_request(): return False
            time.sleep(1)
        self._notify_status("Oldal stabilizálódott (feltételezett).")

        # Keresési paraméterek
        open_tool_region_top = int(self.automator.screen_height * 0.33)
        open_tool_region_left = int(self.automator.screen_width * 0.28)
        open_tool_region_width = int(self.automator.screen_width * 0.44)
        open_tool_region_height = int(self.automator.screen_height * 0.15)
        precise_open_tool_region = (open_tool_region_left, open_tool_region_top, open_tool_region_width, open_tool_region_height)

        texts_to_find = [
            {"text": "ESZKÖZ MEGNYITÁSA", "lang": "HU"},
            {"text": "ENTER TOOL", "lang": "EN"}
        ]
        button_pos = None
        search_timeout_per_attempt = 10 # Másodperc minden egyes _find_text_with_easyocr_and_click hívásra

        # 1. Keresés a pontosított régióban
        self._notify_status(f"Gomb keresése a pontosított régióban ({precise_open_tool_region})...")
        for item in texts_to_find:
            if self._check_for_stop_request(): return False
            # self._notify_status(f"'{item['text']}' ({item['lang']}) keresése a pontosított régióban...") # Ezt a _find_text_... már logolja
            button_pos = self._find_text_with_easyocr_and_click(
                target_text=item['text'],
                description=f"'{item['text']}' ({item['lang']}) gomb (EasyOCR, pontosított régió)",
                timeout_s=search_timeout_per_attempt,
                initial_confidence_threshold=0.60,
                min_confidence_threshold=0.25,
                confidence_step=0.1,
                search_region=precise_open_tool_region,
                click_element=True
            )
            if button_pos:
                self._notify_status(f"'{item['text']}' ({item['lang']}) gomb MEGTALÁLVA a pontosított régióban.")
                break

        # 2. Ha nem található a pontosított régióban, keresés teljes képernyőn
        if not button_pos:
            if self._check_for_stop_request(): return False
            self._notify_status("Gomb nem található a pontosított régióban. Keresés teljes képernyőn...", is_error=False)
            for item in texts_to_find:
                if self._check_for_stop_request(): return False
                # self._notify_status(f"'{item['text']}' ({item['lang']}) keresése teljes képernyőn...") # Ezt a _find_text_... már logolja
                button_pos = self._find_text_with_easyocr_and_click(
                    target_text=item['text'],
                    description=f"'{item['text']}' ({item['lang']}) gomb (EasyOCR, fallback teljes képernyő)",
                    timeout_s=search_timeout_per_attempt, # Növelhetjük a timeout-ot teljes képernyős keresésnél, pl. 15s
                    initial_confidence_threshold=0.55,
                    min_confidence_threshold=0.20,
                    confidence_step=0.1,
                    search_region=None, # Teljes képernyő
                    click_element=True
                )
                if button_pos:
                    self._notify_status(f"'{item['text']}' ({item['lang']}) gomb MEGTALÁLVA teljes képernyőn.")
                    break

        # 3. Ellenőrzés, hogy megtaláltuk-e végül
        if not button_pos:
            # if self._check_for_stop_request(): return False # A ciklusokban már ellenőriztük
            self._notify_status("HIBA: Sem az 'ESZKÖZ MEGNYITÁSA', sem az 'ENTER TOOL' gombot nem sikerült megtalálni. Az automatizálás nem folytatható.", is_error=True)
            # Itt is menthetnénk egy utolsó képernyőképet, ha van `last_screenshot_pil` a `_find_text_with_easyocr_and_click`-ből (de az lokális ott)
            # Egy általános képernyőmentés itt:
            try:
                if self.automator.assets_dir and os.path.exists(self.automator.assets_dir):
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    debug_img_name = f"debug_ocr_PI_overall_fail_{ts}.png"
                    debug_screenshot_path = os.path.join(self.automator.assets_dir, debug_img_name)
                    pyautogui.screenshot(debug_screenshot_path)
                    self._notify_status(f"Hibakeresési képernyőkép mentve (PageInitializer, teljes gombkeresés sikertelen): {debug_screenshot_path}", is_error=True)
            except Exception as e_screenshot_fail:
                self._notify_status(f"Hiba a hibakeresési képernyőkép mentése közben (teljes gombkeresés sikertelen): {e_screenshot_fail}", is_error=True)
            return False

        self._notify_status("'ESZKÖZ MEGNYITÁSA' / 'ENTER TOOL' gombra kattintás sikeresnek tűnik.")
        wait_after_button_click_s = 8
        self._notify_status(f"Várakozás {wait_after_button_click_s}s az eszköz felületének betöltődésére...")
        for _ in range(wait_after_button_click_s):
            if self._check_for_stop_request(): return False
            time.sleep(1)
        self._notify_status("Eszköz felülete betöltődött (feltételezett).")

        self._notify_status("OLDAL ELŐKÉSZÍTÉS: Sikeres (ESZKÖZ MEGNYITÁSA / ENTER TOOL megtörtént).")
        return True
