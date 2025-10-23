# core/image_flow_handler.py
import os
import pyautogui
import time

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

    def _is_manual_run(self):
        process_controller = getattr(self.automator, 'process_controller', None)
        worker = getattr(process_controller, 'worker', None) if process_controller else None
        if worker and hasattr(worker, 'manual_mode'):
            return bool(worker.manual_mode)
        return False

    def _get_current_image_index(self):
        process_controller = getattr(self.automator, 'process_controller', None)
        if process_controller and hasattr(process_controller, 'current_image_index'):
            try:
                index_value = int(process_controller.current_image_index)
            except (TypeError, ValueError):
                return None
            if index_value > 0:
                return index_value
        return None

    def _extract_generation_status_region(self):
        region = self.automator.coordinates.get("generation_status_region")
        if isinstance(region, dict):
            try:
                left = int(region.get("left"))
                top = int(region.get("top"))
                width = int(region.get("width"))
                height = int(region.get("height"))
            except (TypeError, ValueError):
                return None
            if width > 2 and height > 2:
                return left, top, width, height
        return None

    def _determine_generation_status_pixel(self):
        pixel_x_to_watch = self.automator.coordinates.get("generation_status_pixel_x")
        pixel_y_to_watch = self.automator.coordinates.get("generation_status_pixel_y")
        if pixel_x_to_watch is not None and pixel_y_to_watch is not None:
            try:
                return int(pixel_x_to_watch), int(pixel_y_to_watch)
            except (TypeError, ValueError):
                pass

        if self._is_manual_run():
            self._notify_status("HIBA (Manuális mód): A manuális koordinátafájl nem tartalmazta a 'generation_status' területet vagy pixelt.", is_error=True)
            return None

        fallback_x = 890
        fallback_y = 487
        self._notify_status(
            f"FIGYELEM: A generálási státusz terület/pixel koordinátái nem voltak betöltve. Fallback pozíció használata: X={fallback_x}, Y={fallback_y}",
            is_error=True
        )
        return fallback_x, fallback_y

    def _watch_generation_by_region(self, region, stable_required_s=2.0, max_wait_s=60.0, check_interval_s=0.3):
        left, top, width, height = region
        self._notify_status(
            f"Generálási státusz terület figyelése (X:{left}, Y:{top}, Szél:{width}, Mag:{height}). "
            f"A folyamat akkor folytatódik, ha {stable_required_s}s-ig nincs mozgás a területen."
        )
        start_time = time.time()
        last_change_time = start_time
        last_frame_bytes = None
        movement_detected = False
        info_sent = False

        while time.time() - start_time < max_wait_s:
            if self._check_for_stop_request():
                self._notify_status("Terület figyelése megszakítva felhasználói kéréssel.", is_error=True)
                print("ImageFlowHandler DEBUG: Terület figyelés megszakítva stop kéréssel.")
                return False

            try:
                screenshot = pyautogui.screenshot(region=(left, top, width, height))
                current_frame = screenshot.tobytes()
            except Exception as e_region:
                self._notify_status(
                    f"Hiba a generálási terület rögzítése közben (X:{left}, Y:{top}, Szél:{width}, Mag:{height}): {e_region}",
                    is_error=True
                )
                time.sleep(check_interval_s * 2)
                continue

            now = time.time()
            if last_frame_bytes is None:
                last_frame_bytes = current_frame
                last_change_time = now
                continue

            if current_frame != last_frame_bytes:
                if not movement_detected:
                    self._notify_status("Mozgás észlelve a generálási területen. Stabil állapot figyelése...")
                movement_detected = True
                info_sent = False
                last_change_time = now
                last_frame_bytes = current_frame
            else:
                if movement_detected:
                    stable_time = now - last_change_time
                    if stable_time >= stable_required_s:
                        self._notify_status(
                            f"Generálási terület stabil (mozgás nélkül {stable_time:.1f}s). Generálás befejeződött."
                        )
                        print("ImageFlowHandler DEBUG: Terület figyelés SIKERES (stabil állapot).")
                        return True
                    elif not info_sent and stable_required_s - stable_time <= 1.0:
                        remaining = max(0.0, stable_required_s - stable_time)
                        self._notify_status(
                            f"Generálási terület stabilizálódik... {remaining:.1f}s még szükséges a megerősítéshez."
                        )
                        info_sent = True

            time.sleep(check_interval_s)

        if movement_detected:
            self._notify_status(
                f"Időtúllépés: A generálási terület nem maradt mozdulatlan {stable_required_s}s-ig a {max_wait_s}s-es limit alatt.",
                is_error=True
            )
        else:
            self._notify_status(
                f"Időtúllépés: A generálási területen nem észleltünk mozgást {max_wait_s}s alatt.",
                is_error=True
            )
        print("ImageFlowHandler DEBUG: Terület figyelés TIMEOUT.")
        return False

    def _watch_generation_by_pixel(self, pixel_x_to_watch, pixel_y_to_watch,
                                   expected_color_during_generation=(217, 217, 217),
                                   max_wait_s_for_pixel_change=45, check_interval_s=0.5):
        self._notify_status(
            f"Pixel ({pixel_x_to_watch},{pixel_y_to_watch}) színének figyelése. Várt szín generálás közben: {expected_color_during_generation}."
        )
        start_pixel_watch_time = time.time()

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
                    print("ImageFlowHandler DEBUG: Pixel figyelés SIKERES (szín megváltozott).")
                    return True
                else:
                    remaining_time = int(max_wait_s_for_pixel_change - (time.time() - start_pixel_watch_time))
                    if remaining_time % 5 == 0 or remaining_time < 5:
                        self._notify_status(f"Generálás még folyamatban (pixel színe: {current_pixel_color})... ({remaining_time}s hátra a timeout-ig)")
            except Exception as e_pixel:
                self._notify_status(f"Hiba a pixel ({pixel_x_to_watch},{pixel_y_to_watch}) színének olvasása közben: {e_pixel}", is_error=True)
                time.sleep(check_interval_s * 2)
            time.sleep(check_interval_s)

        self._notify_status(
            f"Időtúllépés: A pixel színe nem változott meg {max_wait_s_for_pixel_change}s alatt.",
            is_error=True
        )
        print("ImageFlowHandler DEBUG: Pixel figyelés TIMEOUT.")
        return False

    def _smart_scan_and_click_download(self, region, fallback_x, fallback_y,
                                       scan_step_fraction=6,
                                       movement_check_pause_s=0.08,
                                       icon_search_timeout_s=4.0,
                                       icon_search_interval_s=0.35):
        left, top, width, height = region
        if width <= 0 or height <= 0:
            return False

        self._notify_status("Okos letöltés keresés indítása a generálási területen belül...")
        step_x = max(20, int(width / max(1, scan_step_fraction)))
        step_y = max(20, int(height / max(1, scan_step_fraction)))
        bottom = top + height - 1

        previous_frame = None
        movement_detected = False

        for x in range(left, left + width, step_x):
            if self._check_for_stop_request():
                self._notify_status("Okos letöltés keresés megszakítva felhasználói kérésre.", is_error=True)
                return False
            for y_offset in range(0, height, step_y):
                current_y = bottom - y_offset
                try:
                    pyautogui.moveTo(x, current_y, duration=0.05)
                except Exception as move_error:
                    self._notify_status(
                        f"Okos letöltés keresés: Hiba az egér mozgatásakor ({x},{current_y}): {move_error}",
                        is_error=True
                    )
                    return False
                time.sleep(movement_check_pause_s)
                try:
                    current_frame = pyautogui.screenshot(region=(left, top, width, height)).tobytes()
                except Exception as screen_error:
                    self._notify_status(
                        f"Okos letöltés keresés: Hiba a terület rögzítésekor: {screen_error}",
                        is_error=True
                    )
                    return False

                if previous_frame is not None and current_frame != previous_frame:
                    movement_detected = True
                    break
                previous_frame = current_frame
            if movement_detected:
                break

        if not movement_detected:
            self._notify_status(
                "Okos letöltés keresés: Nem észleltünk mozgást a területen, fallback koordináták következnek."
            )
            return False

        self._notify_status("Okos letöltés keresés: Mozgás érzékelve. Letöltés ikon keresése a területen belül...")
        icon_path = os.path.join(os.path.dirname(__file__), "..", "utils", "letoltes ikon.png")
        icon_path = os.path.abspath(icon_path)
        if not os.path.exists(icon_path):
            self._notify_status(
                "Okos letöltés keresés: Letöltés ikon képe nem található (utils/letoltes ikon.png). Fallback koordináták használata.",
                is_error=True
            )
            return False

        search_start = time.time()
        while time.time() - search_start <= icon_search_timeout_s:
            if self._check_for_stop_request():
                self._notify_status("Okos letöltés ikon keresés megszakítva felhasználói kérésre.", is_error=True)
                return False
            try:
                icon_location = pyautogui.locateOnScreen(icon_path, region=(left, top, width, height))
            except Exception as locate_error:
                self._notify_status(
                    f"Okos letöltés keresés: Hiba a letöltés ikon keresésekor: {locate_error}",
                    is_error=True
                )
                icon_location = None

            if icon_location:
                icon_center = pyautogui.center(icon_location)
                try:
                    pyautogui.moveTo(icon_center.x, icon_center.y, duration=0.12)
                    pyautogui.click()
                except Exception as click_error:
                    self._notify_status(
                        f"Okos letöltés keresés: Hiba a letöltés ikon megnyomásakor: {click_error}",
                        is_error=True
                    )
                    return False
                self._notify_status(
                    f"Okos letöltés keresés: Letöltés ikon megtalálva és megnyomva (X={icon_center.x}, Y={icon_center.y})."
                )
                return True

            time.sleep(icon_search_interval_s)

        self._notify_status(
            "Okos letöltés keresés: Nem sikerült megtalálni a letöltés ikont a megadott időn belül. Fallback koordináták használata."
        )
        try:
            pyautogui.moveTo(fallback_x, fallback_y, duration=0.2)
        except Exception as move_error:
            self._notify_status(
                f"Okos letöltés keresés: Hiba a fallback koordináták megközelítésekor ({fallback_x},{fallback_y}): {move_error}",
                is_error=True
            )
            return False
        return False

    def monitor_generation_and_download(self):
        print("ImageFlowHandler DEBUG: monitor_generation_and_download KEZDÉS.")
        if self._check_for_stop_request():
            print("ImageFlowHandler DEBUG: Stop kérés a metódus elején.")
            return False

        self._notify_status("KÉP FELDOLGOZÁS: Generálás figyelése és letöltés indítása...")
        region_to_watch = self._extract_generation_status_region()
        if region_to_watch:
            self._notify_status("Kép generálásának figyelése a kijelölt terület mozgása alapján...")
        else:
            self._notify_status("Kép generálásának figyelése pixel alapján...")
        initial_wait_after_generate_click_s = 2
        self._notify_status(f"Várakozás {initial_wait_after_generate_click_s}s a generálás tényleges megkezdésére...")
        time.sleep(initial_wait_after_generate_click_s)
        if self._check_for_stop_request():
            print("ImageFlowHandler DEBUG: Stop kérés a kezdeti várakozás után.")
            return False

        completion_source_text = "pixel figyelés alapján"
        wait_after_color_change_s = 1
        max_wait_s_for_completion = 60

        if region_to_watch:
            region_success = self._watch_generation_by_region(region_to_watch, stable_required_s=2.0,
                                                              max_wait_s=max_wait_s_for_completion,
                                                              check_interval_s=0.3)
            if not region_success:
                return False
            completion_source_text = "terület figyelése alapján"
        else:
            pixel_coords = self._determine_generation_status_pixel()
            if not pixel_coords:
                return False
            pixel_x_to_watch, pixel_y_to_watch = pixel_coords
            pixel_success = self._watch_generation_by_pixel(
                pixel_x_to_watch,
                pixel_y_to_watch,
                expected_color_during_generation=(217, 217, 217),
                max_wait_s_for_pixel_change=max_wait_s_for_completion,
                check_interval_s=0.5
            )
            if not pixel_success:
                return False

        self._notify_status(f"Generálás befejeződött ({completion_source_text}). Várakozás {wait_after_color_change_s}s a letöltés előtt...")
        time.sleep(wait_after_color_change_s)
        if self._check_for_stop_request():
            print("ImageFlowHandler DEBUG: Stop kérés a színváltozás utáni várakozáskor.")
            return False

        self._notify_status(f"Kép elkészült ({completion_source_text}). Letöltés következik...")

        manual_mode_active = self._is_manual_run()
        download_button_x = None
        download_button_y = None
        if "download_button_click_x" in self.automator.coordinates and \
           "download_button_click_y" in self.automator.coordinates:
            download_button_x = self.automator.coordinates["download_button_click_x"]
            download_button_y = self.automator.coordinates["download_button_click_y"]
            self._notify_status(f"Betöltött letöltés gomb pozíció használata: X={download_button_x}, Y={download_button_y}")
        else:
            if manual_mode_active:
                self._notify_status(f"HIBA (Manuális mód): 'download_button_click' koordináták hiányoznak a manuális fájlból!", is_error=True)
                return False
            else:
                download_button_x = 925
                download_button_y = 704
                self._notify_status(f"FIGYELEM: Letöltés gomb koordinátái nem voltak betöltve. Fallback pozíció használata: X={download_button_x}, Y={download_button_y}. Ez valószínűleg hiba a koordináták kezelésében!", is_error=True)

        click_completed = False
        smart_search_used = False
        if region_to_watch and not manual_mode_active:
            smart_search_used = self._smart_scan_and_click_download(region_to_watch, download_button_x, download_button_y)
            click_completed = smart_search_used

        if click_completed:
            self._notify_status("Letöltés gomb aktiválva az okos kereséssel.")
            self._notify_status("Letöltés gombra kattintva.")
        else:
            self._notify_status(f"Kattintás a letöltés gombra: X={download_button_x}, Y={download_button_y}")
            try:
                print(f"ImageFlowHandler DEBUG: Kattintás a letöltés gombra: X={download_button_x}, Y={download_button_y}")
                pyautogui.moveTo(download_button_x, download_button_y, duration=0.2)
                if manual_mode_active:
                    pre_click_wait_s = 0.5
                    self._notify_status(
                        f"Manuális mód: Várakozás {pre_click_wait_s:.1f}s a letöltés gomb megnyomása előtt..."
                    )
                    time.sleep(pre_click_wait_s)
                if manual_mode_active:
                    icon_search_timeout_s = 5
                    icon_search_interval_s = 0.5
                    icon_path = os.path.join(os.path.dirname(__file__), "..", "utils", "letoltes ikon.png")
                    icon_path = os.path.abspath(icon_path)
                    if os.path.exists(icon_path):
                        self._notify_status(
                            f"Manuális mód: Letöltés ikon keresése a képernyőn (max {icon_search_timeout_s}s)..."
                        )
                        search_start = time.time()
                        while time.time() - search_start <= icon_search_timeout_s:
                            if self._check_for_stop_request():
                                print("ImageFlowHandler DEBUG: Stop kérés a letöltés ikon keresése közben.")
                                return False
                            try:
                                icon_location = pyautogui.locateOnScreen(icon_path)
                            except Exception as locate_error:
                                print(
                                    "ImageFlowHandler DEBUG: Hiba a letöltés ikon keresése közben:",
                                    locate_error,
                                )
                                icon_location = None
                            if icon_location:
                                icon_center = pyautogui.center(icon_location)
                                self._notify_status(
                                    f"Manuális mód: Letöltés ikon megtalálva a képernyőn: X={icon_center.x}, Y={icon_center.y}."
                                )
                                pyautogui.moveTo(icon_center.x, icon_center.y, duration=0.15)
                                pyautogui.click()
                                click_completed = True
                                break
                            time.sleep(icon_search_interval_s)
                        if not click_completed:
                            self._notify_status(
                                "Manuális mód: Letöltés ikon nem található 5s alatt, fallback koordináták használata."
                            )
                    else:
                        self._notify_status(
                            "Manuális mód: Letöltés ikon képe nem található a projektben (utils/letoltes ikon.png). Fallback koordináták használata.",
                            is_error=True,
                        )
                if not click_completed:
                    pyautogui.click()
                    click_completed = True
                self._notify_status("Letöltés gombra kattintva.")
                print("ImageFlowHandler DEBUG: Letöltés gombra kattintás SIKERES.")
            except Exception as e_click_download:
                self._notify_status(f"Hiba történt a letöltés gombra való kattintás közben (X:{download_button_x}, Y:{download_button_y}): {e_click_download}", is_error=True)
                print(f"ImageFlowHandler DEBUG: Hiba a letöltés gombra kattintáskor: {e_click_download}")
                return False

        if smart_search_used:
            print("ImageFlowHandler DEBUG: Letöltés gombra kattintás SIKERES (okos kereséssel).")

        download_confirmation_wait_s = 1
        manual_wait_duration_s = 0
        if manual_mode_active:
            wait_before_typing_s = 1.0
            wait_before_enter_s = 1.0
            manual_wait_duration_s = wait_before_typing_s + wait_before_enter_s
            self._notify_status(
                f"Manuális mód: Várakozás {wait_before_typing_s:.0f}s a letöltés gomb megnyomása után a képsorszám beviteléhez..."
            )
            time.sleep(wait_before_typing_s)

            current_image_index = self._get_current_image_index()
            if current_image_index is None:
                self._notify_status("HIBA (Manuális mód): A képsorszám nem érhető el a billentyűzeti bevitelhez.", is_error=True)
                return False

            try:
                self._notify_status(f"Manuális mód: Képsorszám '{current_image_index}' bevitele és Enter lenyomása...")
                pyautogui.typewrite(str(current_image_index))
                self._notify_status(
                    f"Manuális mód: Várakozás {wait_before_enter_s:.0f}s az Enter lenyomása előtt..."
                )
                time.sleep(wait_before_enter_s)
                pyautogui.press('enter')
                self._notify_status("Manuális mód: Képsorszám bevitele sikeres.")
            except Exception as e_typewrite:
                self._notify_status(f"Hiba (Manuális mód): A képsorszám bevitele sikertelen: {e_typewrite}", is_error=True)
                return False

        remaining_confirmation_wait_s = download_confirmation_wait_s
        if manual_wait_duration_s > 0:
            remaining_confirmation_wait_s = max(0, download_confirmation_wait_s - manual_wait_duration_s)

        if remaining_confirmation_wait_s > 0:
            wait_value_for_message = remaining_confirmation_wait_s
            if isinstance(wait_value_for_message, float) and wait_value_for_message.is_integer():
                wait_value_for_message = int(wait_value_for_message)
            self._notify_status(f"Rövid várakozás ({wait_value_for_message}s) a letöltés elindulására...")
            time.sleep(remaining_confirmation_wait_s)

        self._notify_status("Kép letöltése elindítva (feltételezett).")
        self._notify_status("KÉP FELDOLGOZÁS: Sikeres.") 
        print("ImageFlowHandler DEBUG: monitor_generation_and_download SIKERES.") 
        return True
