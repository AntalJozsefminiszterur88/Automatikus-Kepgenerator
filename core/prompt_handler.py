# core/prompt_handler.py
import re # <<< HOZZÁADVA: Reguláris kifejezésekhez

class PromptHandler:
    def __init__(self, process_controller_ref=None):
        self.process_controller = process_controller_ref #
        print("PromptHandler inicializálva.") #

    def _notify_status(self, message):
        if self.process_controller and hasattr(self.process_controller, 'update_gui_status'): #
            self.process_controller.update_gui_status(message) #
        else:
            print(f"[PromptHandler]: {message}") #

    def _strip_numbering(self, line_text: str) -> str: # <<< ÚJ SEGÉDFÜGGVÉNY
        """
        Eltávolítja a sor eleji sorszámozást.
        Példák: "1. Szöveg" -> "Szöveg", "01) Szöveg" -> "Szöveg", "  1 - Szöveg" -> "Szöveg"
        A sorszámot számjegyek alkotják, amit pont, zárójel vagy kötőjel követ,
        majd legalább egy whitespace karakter.
        """
        # Regex:
        # ^        : Sor eleje
        # \s* : Opcionális whitespace karakterek (szóközök, tabulátorok)
        # \d+      : Egy vagy több számjegy (a sorszám)
        # [\.\)\-] : Egy karakter a csoportból: pont, zárójel bezáró, vagy kötőjel
        # \s+      : Legalább egy whitespace karakter (a sorszám és a szöveg között)
        pattern = r"^\s*\d+[\.\)\-]\s+"
        stripped_line = re.sub(pattern, '', line_text)
        return stripped_line

    def load_prompts(self, file_path, start_line, end_line): # <<< MÓDOSÍTOTT METÓDUS
        prompts_to_process = [] #
        if not file_path: #
            self._notify_status("Hiba: Nincs megadva prompt fájl elérési útja.") #
            return prompts_to_process #

        try:
            with open(file_path, 'r', encoding='utf-8') as f: #
                all_lines = [line.strip() for line in f if line.strip()] # Üres sorok kihagyása #
        except FileNotFoundError: #
            self._notify_status(f"Hiba: A '{file_path}' fájl nem található.") #
            return prompts_to_process #
        except Exception as e: #
            self._notify_status(f"Hiba a '{file_path}' fájl olvasása közben: {e}") #
            return prompts_to_process #

        total_prompts_in_file = len(all_lines) #
        if total_prompts_in_file == 0: #
            self._notify_status(f"Hiba: A '{file_path}' fájl üres vagy csak üres sorokat tartalmaz.") #
            return prompts_to_process #

        actual_start_index = start_line - 1 #
        effective_end_index = min(end_line, total_prompts_in_file) #

        if actual_start_index < 0: #
            self._notify_status("Hiba: A kezdő sorszám érvénytelen (túl kicsi).") #
            return prompts_to_process #
        
        if actual_start_index >= total_prompts_in_file: #
            self._notify_status(f"Hiba: A kezdő sorszám ({start_line}) nagyobb, mint a fájlban lévő promptok száma ({total_prompts_in_file}).") #
            return prompts_to_process #

        if actual_start_index >= effective_end_index: #
             self._notify_status(f"Hiba: A kezdő sor ({start_line}) nem kisebb, mint a befejező sor ({effective_end_index}) a fájl tartalmához igazítva.") #
             return prompts_to_process #

        selected_prompts = all_lines[actual_start_index:effective_end_index] #
        
        # <<< ÚJ: Sorszámok eltávolítása
        prompts_without_numbering = []
        if selected_prompts:
            for prompt_text in selected_prompts:
                prompts_without_numbering.append(self._strip_numbering(prompt_text))
            
            if not prompts_without_numbering:
                self._notify_status("Figyelmeztetés: A sorszámok eltávolítása után nem maradtak feldolgozandó promptok.")
                return []
            
            self._notify_status(f"{len(prompts_without_numbering)} prompt sikeresen betöltve (sorszámok eltávolítva, ha voltak) a(z) '{file_path.split('/')[-1]}' fájlból ({start_line}-{effective_end_index}. sor).")
            return prompts_without_numbering
        else:
            self._notify_status("Nincsenek feldolgozandó promptok a megadott tartományban.") #
            return []
