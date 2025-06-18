from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class TitleWidget(QWidget):
    """
    Egy widget a program főcímének és az alcímnek a megjelenítésére.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0) # Nincs extra margó a widgeten belül
        layout.setSpacing(5) # Kis térköz a címek között

        # Főcím
        self.main_title_label = QLabel("Automatikus Képgenerátor")
        main_title_font = QFont()
        main_title_font.setPointSize(24) # Nagyobb betűméret
        main_title_font.setBold(True)
        self.main_title_label.setFont(main_title_font)
        self.main_title_label.setAlignment(Qt.AlignCenter)

        # Alcím
        self.subtitle_label = QLabel("powered by UMKGL Solutions")
        subtitle_font = QFont()
        subtitle_font.setPointSize(10) # Kisebb betűméret
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setAlignment(Qt.AlignCenter) # Balra igazítás a főcím alatt

        layout.addWidget(self.main_title_label)
        layout.addWidget(self.subtitle_label)

        self.setLayout(layout)
        print("TitleWidget inicializálva.")
