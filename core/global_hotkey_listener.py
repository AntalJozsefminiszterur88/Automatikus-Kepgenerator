# core/global_hotkey_listener.py
import threading
from pynput import keyboard
from PySide6.QtCore import QObject, Signal

# Konfiguráció a te diagnosztikai kimeneted alapján:
# Numpad +: VK 107 (és char '+') -> '+'
# Numpad 6: VK 102 -> <102>
# Numpad 4: VK 100 -> <100>
# Numpad 8: VK 104 -> <104>
# Numpad 2: VK 98 -> <98>

CONFIG = {
    # Numpad 0 -> Pause/Resume Automation (ELTÁVOLÍTVA)
    # "PAUSE_RESUME_KEY": keyboard.KeyCode.from_vk(96),
    "STOP_AUTOMATION_KEY": keyboard.Key.esc,
    # Numpad + -> Play/Pause Music
    "PLAY_PAUSE_KEY": keyboard.KeyCode(char='+'),
    # Numpad 6 -> Next Track
    "NEXT_TRACK_KEY_NUMPAD": keyboard.KeyCode.from_vk(102),
    # Numpad 4 -> Previous Track
    "PREV_TRACK_KEY_NUMPAD": keyboard.KeyCode.from_vk(100),
    # Numpad 8 -> Volume Up
    "VOLUME_UP_KEY_NUMPAD": keyboard.KeyCode.from_vk(104),
    # Numpad 2 -> Volume Down
    "VOLUME_DOWN_KEY_NUMPAD": keyboard.KeyCode.from_vk(98),
}

class HotkeyEmitter(QObject):
    # pause_resume_requested = Signal() # ELTÁVOLÍTVA
    stop_automation_requested = Signal()
    music_play_pause_requested = Signal()
    music_next_track_requested = Signal()
    music_prev_track_requested = Signal()
    music_volume_up_requested = Signal()
    music_volume_down_requested = Signal()

class GlobalHotkeyListener:
    def __init__(self):
        self.emitter = HotkeyEmitter()
        self._listener_thread = None
        self._listener_control = None
        self.running = False
        print("GlobalHotkeyListener inicializálva.")

    def _on_press(self, key):
        try:
            pressed_key_char = key.char if hasattr(key, 'char') else None
            pressed_key_vk = key.vk if hasattr(key, 'vk') else None
            # pressed_key_name = key.name if hasattr(key, 'name') else None # Logoláshoz elég a vk és char
            # print(f"RAW KEY PRESS (main app): Char: {pressed_key_char}, VK: {pressed_key_vk}, Name: {pressed_key_name}, Full Key: {key}")
        except Exception: # as e:
            # print(f"RAW KEY PRESS (main app, error in logging): {key}, Error: {e}")
            return

        if not self.running:
            return

        action_to_emit = None
        action_name_for_log = None

        if hasattr(key, 'vk') and key.vk is not None:
            # PAUSE_RESUME_KEY logika eltávolítva innen
            if key.vk == CONFIG["NEXT_TRACK_KEY_NUMPAD"].vk and CONFIG["NEXT_TRACK_KEY_NUMPAD"].char is None and pressed_key_char is None:
                action_to_emit = "music_next_track_requested"
                action_name_for_log = "NEXT TRACK (Num6)"
            elif key.vk == CONFIG["PREV_TRACK_KEY_NUMPAD"].vk and CONFIG["PREV_TRACK_KEY_NUMPAD"].char is None and pressed_key_char is None:
                action_to_emit = "music_prev_track_requested"
                action_name_for_log = "PREVIOUS TRACK (Num4)"
            elif key.vk == CONFIG["VOLUME_UP_KEY_NUMPAD"].vk and CONFIG["VOLUME_UP_KEY_NUMPAD"].char is None and pressed_key_char is None:
                action_to_emit = "music_volume_up_requested"
                action_name_for_log = "VOLUME UP (Num8)"
            elif key.vk == CONFIG["VOLUME_DOWN_KEY_NUMPAD"].vk and CONFIG["VOLUME_DOWN_KEY_NUMPAD"].char is None and pressed_key_char is None:
                action_to_emit = "music_volume_down_requested"
                action_name_for_log = "VOLUME DOWN (Num2)"
            elif key == CONFIG["STOP_AUTOMATION_KEY"]:
                action_to_emit = "stop_automation_requested"
                action_name_for_log = "STOP AUTOMATION (Esc)"

        if not action_to_emit and hasattr(key, 'char') and key.char is not None and \
           key.char == CONFIG["PLAY_PAUSE_KEY"].char:
            if hasattr(key, 'vk') and key.vk == 107:
                action_to_emit = "music_play_pause_requested"
                action_name_for_log = "PLAY/PAUSE MUSIC (Num+)"


        if action_to_emit:
            print(f"Hotkey (main app): Matched {action_name_for_log} for key {key}")
            getattr(self.emitter, action_to_emit).emit()
        # else:
            # print(f"No configured action for key: {key} (Raw VK: {getattr(key, 'vk', None)}, Raw Char: {getattr(key, 'char', None)})")


    def _listener_loop(self):
        with keyboard.Listener(on_press=self._on_press, suppress=False) as l:
            self._listener_control = l
            print("pynput billentyűfigyelő elindult a háttérszálon (fő alkalmazás).")
            l.join()
        print("pynput billentyűfigyelő leállt a háttérszálon (fő alkalmazás).")
        self._listener_control = None

    def start(self):
        if not self.running:
            self.running = True
            if self._listener_thread is None or not self._listener_thread.is_alive():
                self._listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
                self._listener_thread.start()
                print("Globális billentyűfigyelő szál elindítva (fő alkalmazás).")

    def stop(self):
        if self.running:
            self.running = False
            if self._listener_control:
                print("pynput listener leállítása (fő alkalmazás)...")
                self._listener_control.stop()
        self._listener_thread = None
        print("Globális billentyűfigyelő leállítási kérelem kiadva (fő alkalmazás).")

if __name__ == '__main__':
    import time
    print("Globális billentyűfigyelő tesztelése (közvetlen futtatás).")
    config_str = ", ".join([f"{k}={v}" for k, v in CONFIG.items()])
    print(f"Figyelt billentyűk: {config_str}")
    print("Nyomd meg a konfigurált billentyűket. Kilépés: Ctrl+C a konzolon.")

    listener = GlobalHotkeyListener()

    # A pause_resume_requested esemény tesztje eltávolítva
    # listener.emitter.pause_resume_requested.connect(
    #     lambda: print("TESZT ESEMÉNY: Pause/Resume kérés!")
    # )
    listener.emitter.music_play_pause_requested.connect(
        lambda: print("TESZT ESEMÉNY: Zene Play/Pause kérés!")
    )
    listener.emitter.music_next_track_requested.connect(
        lambda: print("TESZT ESEMÉNY: Zene Következő kérés!")
    )
    listener.emitter.music_prev_track_requested.connect(
        lambda: print("TESZT ESEMÉNY: Zene Előző kérés!")
    )
    listener.emitter.music_volume_up_requested.connect(
        lambda: print("TESZT ESEMÉNY: Zene Hangerő Fel kérés!")
    )
    listener.emitter.music_volume_down_requested.connect(
        lambda: print("TESZT ESEMÉNY: Zene Hangerő Le kérés!")
    )

    listener.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Teszt felhasználó által leállítva (Ctrl+C).")
    finally:
        listener.stop()
        print("Teszt vége (közvetlen futtatás).")
