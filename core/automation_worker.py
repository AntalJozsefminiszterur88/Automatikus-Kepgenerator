# core/automation_worker.py
from PySide6.QtCore import QObject, Signal, Slot, QThread # QThread importálva, ha msleep-et használnánk
import time
import traceback
import os
# import threading # <<< ELTÁVOLÍTVA

class InterruptedByUserError(Exception):
    pass

class AutomationWorker(QObject):
    status_updated = Signal(str, bool)
    progress_updated = Signal(int, int)
    image_count_updated = Signal(int, int)
    automation_finished = Signal(str)
    show_overlay_requested = Signal()
    hide_overlay_requested = Signal()

    def __init__(self, process_controller_ref, prompt_file_path, start_line, end_line):
        super().__init__()
        self.pc_ref = process_controller_ref
        self.prompt_file_path = prompt_file_path
        self.start_line = start_line
        self.end_line = end_line
        
        self._is_task_running_in_worker = False
        self._stop_requested_by_main = False # Kemény stop kérés a ProcessControllertől
        
        # _is_paused és _pause_event eltávolítva
        # self._is_paused = False
        # self._pause_event = threading.Event()
        # self._pause_event.set()

        if hasattr(self.pc_ref.gui_automator, 'stop_requested'):
            self.pc_ref.gui_automator.stop_requested = False
        if hasattr(self.pc_ref.gui_automator, 'page_is_prepared'):
            self.pc_ref.gui_automator.page_is_prepared = False

    def _check_pause_and_stop(self):
        """ Ellenőrzi a kemény stop kérést. """
        # A QThread.msleep(1) itt nem feltétlenül szükséges, ha a hívó ciklus tartalmaz time.sleep-et
        # vagy ha a Qt eseményhurok más módon kezeli a worker szálat.
        # Ha a ProcessController-ben lévő AutomationWorker használja, ott meghagyható.

        if self._stop_requested_by_main: # Kemény stop prioritást élvez
            self.status_updated.emit("Worker: Kemény stop kérés feldolgozva.", False)
            raise InterruptedByUserError("Kemény stop kérés.")

        # A szüneteltetés (_is_paused) ellenőrzése és a _pause_event.wait() eltávolítva
        # if self._is_paused:
        #     self.status_updated.emit("Automatizálás szünetel...", False) # Egyszerűsített üzenet
        #     self._pause_event.wait()
        #
        # if self._stop_requested_by_main: # Ez a második ellenőrzés is redundáns lett
        #     raise InterruptedByUserError("Megszakítva szüneteltetés feloldása után (kemény stop).")


    @Slot()
    def request_hard_stop_from_main(self):
        """Ezt a slotot hívja meg a ProcessController a fő szálról, hogy végleg leállítsa a munkát."""
        self.status_updated.emit("Worker: Kemény leállítási kérelem fogadva.", False)
        self._stop_requested_by_main = True
        
        # Ha szünetel, fel kell oldani a blokkolást... -> Ez a rész már nem releváns
        # if self._is_paused:
        #     self._is_paused = False
        #     self._pause_event.set()

        if hasattr(self.pc_ref.gui_automator, 'request_stop'):
            self.pc_ref.gui_automator.request_stop()

    # A toggle_pause_resume_state metódus TELJESEN ELTÁVOLÍTVA
    # @Slot()
    # def toggle_pause_resume_state(self):
    #     ...

    @Slot()
    def run_automation_task(self):
        if self._is_task_running_in_worker:
            return
        self._is_task_running_in_worker = True
        self._stop_requested_by_main = False
        # self._is_paused = False # Eltávolítva
        # self._pause_event.set()   # Eltávolítva

        prompt_handler = self.pc_ref.prompt_handler
        gui_automator = self.pc_ref.gui_automator
        # vpn_manager = self.pc_ref.vpn_manager # Feltételezzük, hogy ezek léteznek a pc_ref-en
        browser_manager = self.pc_ref.browser_manager
        
        if hasattr(gui_automator, 'stop_requested'): gui_automator.stop_requested = False
        if hasattr(gui_automator, 'page_is_prepared'): gui_automator.page_is_prepared = False
        
        self.status_updated.emit("Automatizálási folyamat elindítva (worker szálon)...", False)
        prompts_processed_count = 0
        total_prompts_to_process = 0

        try:
            self._check_pause_and_stop()
            self.status_updated.emit(f"Promptok betöltése: '{os.path.basename(self.prompt_file_path)}'", False)
            prompts = prompt_handler.load_prompts(self.prompt_file_path, self.start_line, self.end_line)
            if not prompts:
                self.status_updated.emit("Hiba: Nem sikerült promptokat betölteni.", True)
                self.automation_finished.emit("Sikertelen prompt betöltés")
                self._is_task_running_in_worker = False
                return
            
            total_prompts_to_process = len(prompts)
            self.status_updated.emit(f"{total_prompts_to_process} prompt betöltve.", False)
            self.progress_updated.emit(0, total_prompts_to_process)
            self.image_count_updated.emit(0, total_prompts_to_process)

            # VPN és Böngésző szakaszok
            # Itt a _check_pause_and_stop hívások maradnak, csak a "pause" részük nem aktív már.
            # Példa: browser_manager.open_target_url() hívása utáni várakozás
            browser_opened_successfully = False # Ezt a változót a böngészőkezelő logikájának kell beállítania
            if browser_manager: # Feltételezve, hogy a browser_manager a pc_ref része
                 if browser_manager.open_target_url():
                    browser_opened_successfully = True
            
            if browser_opened_successfully:
                self.show_overlay_requested.emit()
                wait_s = 15 # Ez csak egy példa várakozási idő
                self.status_updated.emit(f"Várakozás a böngészőre ({wait_s}s)...", False)
                for i in range(wait_s):
                    self._check_pause_and_stop()
                    # Itt QThread.msleep használható, ha a worker QThread-ben fut,
                    # egyébként sima time.sleep. A ProcessController kezeli a QThread-et.
                    current_qthread = QThread.currentThread()
                    if current_qthread:
                        current_qthread.msleep(1000) 
                    else:
                        time.sleep(1) # Fallback, ha valamiért nem QThread környezetben lenne
                    if (i + 1) % 3 == 0 or i == wait_s -1 :
                        self.status_updated.emit(f"Böngésző töltődik... ({wait_s - 1 - i}s)", False)


            self._check_pause_and_stop()
            if gui_automator:
                # Az initial_page_setup-nak is tartalmaznia kell belső _check_pause_and_stop hívásokat
                # vagy a pc_ref._stop_requested_by_user-t kellene figyelnie.
                # Jelenleg a PyAutoGuiAutomator _check_for_stop_request metódusa ezt kezeli.
                if not gui_automator.initial_page_setup(): # Feltételezve, hogy ez False-t ad hiba esetén
                    if not self._stop_requested_by_main: # Csak akkor jelezzük hibaként, ha nem mi állítottuk le
                        self.status_updated.emit("Hiba az oldal előkészítése során.", True)
                    # Lehet, hogy itt abba kellene hagyni a folyamatot
                    # self.automation_finished.emit("Oldal előkészítési hiba")
                    # self._is_task_running_in_worker = False
                    # return

            self.status_updated.emit("Promptok feldolgozásának indítása...", False)
            for i, prompt_text in enumerate(prompts):
                self._check_pause_and_stop()
                # ... (prompt feldolgozása, process_single_prompt hívása) ...
                # A process_single_prompt-nak is figyelnie kell a stop állapotot.
                # A PyAutoGuiAutomator.process_single_prompt ezt kezeli.
                current_prompt_no = self.start_line + i
                self.status_updated.emit(f"Feldolgozás: Prompt #{current_prompt_no} ({i+1}/{total_prompts_to_process})", False)
                self.image_count_updated.emit(i + 1, total_prompts_to_process)

                if gui_automator.process_single_prompt(prompt_text):
                    prompts_processed_count += 1
                    self.progress_updated.emit(prompts_processed_count, total_prompts_to_process)
                else:
                    if self._stop_requested_by_main: # Ha a leállítás miatt nem sikerült
                        self.status_updated.emit(f"Prompt #{current_prompt_no} feldolgozása megszakítva.", False)
                        break # Kilépés a ciklusból
                    else: # Ha más hiba történt
                        self.status_updated.emit(f"Hiba a Prompt #{current_prompt_no} feldolgozása közben. Kihagyva.", True)
                        # Itt dönthetünk, hogy folytatjuk-e a következő prompttal, vagy leállunk. Jelenleg folytatja.

                if i < total_prompts_to_process - 1:
                    self._check_pause_and_stop()
                    pause_s = 2 # Ez a promptok közötti szünet, nem a felhasználói szüneteltetés
                    self.status_updated.emit(f"Szünet ({pause_s}s)...", False)
                    for _ in range(pause_s):
                        self._check_pause_and_stop()
                        current_qthread = QThread.currentThread()
                        if current_qthread: current_qthread.msleep(1000)
                        else: time.sleep(1)
            
            summary_msg = f"Feldolgozva: {prompts_processed_count}/{total_prompts_to_process}."
            if self._stop_requested_by_main :
                summary_msg = f"Felhasználó által leállítva. {summary_msg}"
            self.automation_finished.emit(summary_msg)

        except InterruptedByUserError as e:
            # A szüneteltetésre vonatkozó üzenet már nem releváns itt, csak a leállítás
            self.status_updated.emit(f"Folyamat megszakítva: {e}", False)
            self.automation_finished.emit(f"Felhasználó által leállítva. Feldolgozva: {prompts_processed_count}/{total_prompts_to_process}.")
        except Exception as e:
            error_msg = f"Kritikus Hiba a workerben: {e}"
            self.status_updated.emit(error_msg, True)
            print(f"WORKER KRITIKUS HIBA: {e}\n{traceback.format_exc()}")
            self.automation_finished.emit(f"Kritikus hiba. Feldolgozva: {prompts_processed_count}/{total_prompts_to_process}.")
        finally:
            self._is_task_running_in_worker = False
            self.hide_overlay_requested.emit()
            # self._is_paused = False # Eltávolítva
            # self._pause_event.set() # Eltávolítva
