# gui/widgets/music_player_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QStyle
from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import os

class MusicPlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 5, 10, 10)

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7) # Alapértelmezett hangerő (0.0 - 1.0)

        self.track_info_label = QLabel("Nincs zene betöltve")
        self.track_info_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.track_info_label)

        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.layout.addWidget(self.position_slider)

        self.time_label_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.total_time_label = QLabel("00:00")
        self.time_label_layout.addWidget(self.current_time_label)
        self.time_label_layout.addStretch()
        self.time_label_layout.addWidget(self.total_time_label)
        self.layout.addLayout(self.time_label_layout)

        # Vezérlőgombok
        controls_layout = QHBoxLayout()
        
        self.prev_button = QPushButton()
        self.prev_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.prev_button.clicked.connect(self.previous_track_action)
        controls_layout.addWidget(self.prev_button)

        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.play_pause_action) # Átnevezve toggle_play_pause-ról
        controls_layout.addWidget(self.play_button)

        self.stop_button = QPushButton() # A stop gomb megmarad
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.stop_button)

        self.next_button = QPushButton()
        self.next_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.next_button.clicked.connect(self.next_track_action)
        controls_layout.addWidget(self.next_button)
        
        self.layout.addLayout(controls_layout)

        # Hangerőszabályzó csúszka
        volume_layout = QHBoxLayout()
        volume_icon_label = QLabel() # Hangerő ikon
        volume_icon_label.setPixmap(self.style().standardIcon(QStyle.SP_MediaVolume).pixmap(16, 16)) # Méret beállítása
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100) # Hangerő 0-100%
        self.volume_slider.setValue(int(self.audio_output.volume() * 100))
        self.volume_slider.valueChanged.connect(self.set_player_volume_from_slider)

        volume_layout.addWidget(volume_icon_label)
        volume_layout.addWidget(self.volume_slider)
        self.layout.addLayout(volume_layout)

        # A "Zene betöltése" gomb eltávolítva innen

        self.player.playbackStateChanged.connect(self.update_play_button_icon)
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.errorOccurred.connect(self.handle_error)

        self.music_files = []
        self.current_track_index = -1
        self._load_default_music_folder()

        self.setLayout(self.layout)
        print("MusicPlayerWidget inicializálva (frissített vezérlőkkel).")

    def _load_default_music_folder(self): #
        music_dir_relative = "gui/assets/music"
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        music_dir = os.path.join(base_path, music_dir_relative)

        if os.path.exists(music_dir):
            for filename in sorted(os.listdir(music_dir)): # Sorba rendezzük a fájlokat
                if filename.lower().endswith(('.mp3', '.wav', '.ogg', '.flac')):
                    self.music_files.append(os.path.join(music_dir, filename))
            
            if self.music_files:
                self.current_track_index = 0
                self.set_current_track(self.music_files[self.current_track_index])
                print(f"Alapértelmezett zenék betöltve: {len(self.music_files)} db.")
            else:
                self.track_info_label.setText("Nincs zene a mappában")
                print(f"Nem található zene a '{music_dir}' mappában.")
        else:
            self.track_info_label.setText("Zene mappa nem található")
            print(f"Zene mappa nem található: '{music_dir}'")

    def set_current_track(self, file_path): #
        if not os.path.exists(file_path):
            self.track_info_label.setText(f"Hiba: Fájl nem található")
            print(f"Hiba: Zenefájl nem található - {file_path}")
            return
        
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.track_info_label.setText(f"{os.path.basename(file_path)}")
        if not self.player.audioOutput():
             self.player.setAudioOutput(self.audio_output)
        print(f"Zenefájl beállítva: {file_path}")

    def play_pause_action(self): # Korábban toggle_play_pause volt
        if not self.player.source().isValid() or self.player.source().isEmpty():
             print("Nincs érvényes zene betöltve a lejátszáshoz.")
             if self.music_files: # Ha van lista, próbálja az aktuális indexűt, vagy az elsőt
                if self.current_track_index == -1 and len(self.music_files) > 0:
                    self.current_track_index = 0
                if 0 <= self.current_track_index < len(self.music_files):
                    self.set_current_track(self.music_files[self.current_track_index])
                    self.player.play()
                else:
                    self.track_info_label.setText("Nincs mit lejátszani.")
             return

        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop_playback(self): #
        self.player.stop()

    def next_track_action(self):
        if not self.music_files:
            return
        if self.current_track_index < len(self.music_files) - 1:
            self.current_track_index += 1
        else:
            self.current_track_index = 0 # Visszaugrik az elejére
        
        self.set_current_track(self.music_files[self.current_track_index])
        self.player.play()

    def previous_track_action(self):
        if not self.music_files:
            return
        if self.current_track_index > 0:
            self.current_track_index -= 1
        else:
            self.current_track_index = len(self.music_files) - 1 # Az utolsóra ugrik
        
        self.set_current_track(self.music_files[self.current_track_index])
        self.player.play()

    def set_player_volume_from_slider(self, value): # Slider 0-100
        volume = float(value / 100.0)
        self.audio_output.setVolume(volume)
        print(f"Hangerő beállítva (slider): {value}%")

    def increase_volume_action(self, increment=0.1): # 0.0-1.0 skálán
        current_volume = self.audio_output.volume()
        new_volume = min(current_volume + increment, 1.0)
        self.audio_output.setVolume(new_volume)
        self.volume_slider.setValue(int(new_volume * 100)) # Slider frissítése
        print(f"Hangerő növelve: {int(new_volume * 100)}%")

    def decrease_volume_action(self, decrement=0.1): # 0.0-1.0 skálán
        current_volume = self.audio_output.volume()
        new_volume = max(current_volume - decrement, 0.0)
        self.audio_output.setVolume(new_volume)
        self.volume_slider.setValue(int(new_volume * 100)) # Slider frissítése
        print(f"Hangerő csökkentve: {int(new_volume * 100)}%")

    def update_play_button_icon(self, state): #
        if state == QMediaPlayer.PlayingState:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def update_position(self, position): #
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        self.current_time_label.setText(self.format_time(position))

    def update_duration(self, duration): #
        self.position_slider.setRange(0, duration)
        self.total_time_label.setText(self.format_time(duration))

    def set_position(self, position): #
        self.player.setPosition(position)

    def format_time(self, ms): #
        s = round(ms / 1000)
        m, s = divmod(s, 60)
        return f"{m:02d}:{s:02d}"

    def handle_error(self): #
        error_string = self.player.errorString()
        print(f"Hiba a zenelejátszóban: {self.player.error()} - {error_string}")
        self.track_info_label.setText(f"Lejátszási hiba") # Rövidebb hibaüzenet a GUI-n

    def stop_playback_on_close(self): #
        print("Zenelejátszó leállítása bezáráskor.")
        self.player.stop()
