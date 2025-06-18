# gui/widgets/prompt_input_widget.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                               QLineEdit, QSpinBox, QHBoxLayout, QFileDialog,
                               QListWidget, QSizePolicy)
from PySide6.QtCore import Qt, Signal
import os

class PromptInputWidget(QWidget):
    manual_mode_requested = Signal()
    # *** ÚJ SIGNAL ***
    start_manual_automation_requested = Signal()
    # *** ÚJ SIGNAL VÉGE ***

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.selected_file_path = "" # Inicializáljuk itt

        # --- 1. Fájl kiválasztása ---
        self.file_path_label = QLabel("Prompt fájl (.txt): Még nincs kiválasztva")
        self.file_path_button = QPushButton("Fájl kiválasztása...")
        self.file_path_button.clicked.connect(self.select_file)
        self.file_path_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_path_label, 1)
        file_layout.addWidget(self.file_path_button, 0)
        self.layout.addLayout(file_layout)

        # --- 2. Sorszámok ---
        self.start_line_label = QLabel("Kezdő sor:")
        self.start_line_spinbox = QSpinBox()
        self.start_line_spinbox.setMinimum(1)
        self.start_line_spinbox.setValue(1)
        self.start_line_spinbox.valueChanged.connect(self._ensure_value_constraints)

        self.end_line_label = QLabel("Befejező sor (meddig):")
        self.end_line_spinbox = QSpinBox()
        self.end_line_spinbox.setMinimum(1)
        self.end_line_spinbox.setValue(10)
        self.end_line_spinbox.valueChanged.connect(self._ensure_value_constraints)

        line_layout = QHBoxLayout()
        line_layout.addWidget(self.start_line_label)
        line_layout.addWidget(self.start_line_spinbox)
        line_layout.addSpacing(20)
        line_layout.addWidget(self.end_line_label)
        line_layout.addWidget(self.end_line_spinbox)
        self.layout.addLayout(line_layout)

        # --- 3. Betöltött Promptok Lista ---
        self.prompt_list_label = QLabel("Promptok:") 
        self.layout.addWidget(self.prompt_list_label)

        self.prompt_list_widget = QListWidget()
        self.prompt_list_widget.setFixedHeight(200) 
        self.prompt_list_widget.addItem("Nincs prompt fájl betöltve.") 
        self.prompt_list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #555; border-radius: 4px;
                background-color: #2E2E2E; color: white;
            }
            QListWidget::item { padding: 3px; }
            QListWidget::item:selected { background-color: #4CAF50; color: white; }
        """)
        self.layout.addWidget(self.prompt_list_widget)
        
        # --- 4. Gombok (Indítás és Manuális mód) ---
        self.start_button = QPushButton("Automatizálás Indítása")
        self.start_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 10px; font-size: 16px; border-radius: 5px; min-height: 40px; }")
        
        # *** ÚJ MANUÁLIS INDÍTÁS GOMB ***
        self.start_manual_button = QPushButton("Indítás (Manuális)")
        self.start_manual_button.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 10px; font-size: 16px; border-radius: 5px; min-height: 40px; }") # Kék gomb
        self.start_manual_button.clicked.connect(self.start_manual_automation_requested.emit)
        # *** ÚJ MANUÁLIS INDÍTÁS GOMB VÉGE ***

        self.manual_mode_button = QPushButton("Manuális Koordináták") # Átnevezés a jobb érthetőségért
        self.manual_mode_button.setStyleSheet("QPushButton { background-color: #4682B4; color: white; padding: 10px; font-size: 16px; border-radius: 5px; min-height: 40px; }")
        self.manual_mode_button.clicked.connect(self.manual_mode_requested.emit)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch() 
        buttons_layout.addWidget(self.start_button)
        # *** ÚJ GOMB HOZZÁADÁSA AZ ELRENDEZÉSHEZ ***
        buttons_layout.addWidget(self.start_manual_button)
        # *** ÚJ GOMB HOZZÁADÁSA VÉGE ***
        buttons_layout.addWidget(self.manual_mode_button) 
        buttons_layout.addStretch() 
        
        self.layout.addLayout(buttons_layout)

        self.setLayout(self.layout)
        print("PromptInputWidget inicializálva (új manuális indítás gombbal).")

    def _count_lines_in_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line for line in f if line.strip()]
            return len(lines)
        except Exception as e:
            print(f"Hiba a sorok számolása közben ({file_path}): {e}")
            return 0

    def _read_prompts_for_display(self, file_path):
        prompts = []
        if not file_path or not os.path.exists(file_path):
            return prompts
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line:
                        prompts.append(stripped_line)
            return prompts
        except Exception as e:
            print(f"Hiba a promptok listájának beolvasása közben ({file_path}): {e}")
            return []

    def populate_prompt_list(self, file_path):
        self.prompt_list_widget.clear() 
        prompts_for_display = self._read_prompts_for_display(file_path)

        if prompts_for_display:
            self.prompt_list_widget.addItems(prompts_for_display)
        else:
            self.prompt_list_widget.addItem("A fájl üres, vagy nem tartalmazott feldolgozható promptokat.")

    def select_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Prompt fájl kiválasztása", "", "Text files (*.txt)")
        if file_name:
            self.selected_file_path = file_name
            display_name = os.path.basename(file_name) 
            self.file_path_label.setText(f"Kiválasztott fájl: {display_name}") 
            print(f"Fájl kiválasztva: {self.selected_file_path}")

            num_lines = self._count_lines_in_file(self.selected_file_path)

            self.start_line_spinbox.blockSignals(True)
            self.end_line_spinbox.blockSignals(True)

            if num_lines > 0:
                self.start_line_spinbox.setRange(1, num_lines)
                self.end_line_spinbox.setRange(1, num_lines)
                
                current_start = self.start_line_spinbox.value()
                current_end = self.end_line_spinbox.value()
                new_start_value = min(max(1, current_start), num_lines)
                new_end_value = current_end
                if current_end == 10 and num_lines < 10: # Alapértelmezett 'end' érték, ha kisebb a fájl
                    new_end_value = num_lines
                else:
                    new_end_value = min(max(1, current_end), num_lines)
                
                if new_end_value < new_start_value: # Biztosítja, hogy end >= start
                    new_end_value = new_start_value
                
                self.start_line_spinbox.setValue(new_start_value)
                self.end_line_spinbox.setValue(new_end_value)
                
                print(f"Fájl sorainak száma: {num_lines}.")
            else: 
                self.start_line_spinbox.setRange(1, 1)
                self.end_line_spinbox.setRange(1, 1)
                self.start_line_spinbox.setValue(1)
                self.end_line_spinbox.setValue(1)
                print("A fájl üres vagy hiba történt. Spinboxok alapértelmezettre (1-1).")

            self.start_line_spinbox.blockSignals(False)
            self.end_line_spinbox.blockSignals(False)
            
            self.populate_prompt_list(self.selected_file_path) 
            
        else: 
            self.selected_file_path = ""
            self.file_path_label.setText("Prompt fájl (.txt): Még nincs kiválasztva")
            self.prompt_list_widget.clear()
            self.prompt_list_widget.addItem("Nincs prompt fájl betöltve.") 
            
            self.start_line_spinbox.blockSignals(True)
            self.end_line_spinbox.blockSignals(True)
            self.start_line_spinbox.setRange(1, 99) 
            self.end_line_spinbox.setRange(1, 99)
            self.start_line_spinbox.setValue(1)
            self.end_line_spinbox.setValue(10)
            self.start_line_spinbox.blockSignals(False)
            self.end_line_spinbox.blockSignals(False)

    def _ensure_value_constraints(self):
        sender_widget = self.sender()
        if sender_widget not in [self.start_line_spinbox, self.end_line_spinbox]:
            return

        start_sb = self.start_line_spinbox
        end_sb = self.end_line_spinbox

        current_start_val = start_sb.value()
        current_end_val = end_sb.value()
        
        if sender_widget == start_sb:
            if current_start_val > current_end_val:
                end_sb.blockSignals(True)
                end_sb.setValue(current_start_val)
                end_sb.blockSignals(False)
        elif sender_widget == end_sb:
            if current_end_val < current_start_val:
                start_sb.blockSignals(True)
                start_sb.setValue(current_end_val)
                start_sb.blockSignals(False)

    def get_file_path(self):
        return self.selected_file_path

    def get_start_line(self):
        return self.start_line_spinbox.value()

    def get_end_line(self):
        return self.end_line_spinbox.value()
