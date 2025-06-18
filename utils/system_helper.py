# utils/system_helper.py
import shutil
import subprocess
import platform
import os

def find_executable_path(executable_name):
    """
    Megkeresi egy futtatható fájl elérési útvonalát.
    Először a shutil.which (PATH) segítségével próbálkozik.
    Windows esetén expliciten ellenőrzi a gyakori NordVPN, Opera, és Chrome
    telepítési helyeket is.
    Visszaadja az elérési utat stringként, vagy None-t, ha nem található.
    """
    # 1. Próbálkozás a shutil.which-csel (PATH alapú keresés)
    path_from_which = shutil.which(executable_name)
    if path_from_which:
        # print(f"DEBUG: '{executable_name}' megtalálva a PATH-ban: {path_from_which}")
        return path_from_which

    # 2. Platformspecifikus keresés, ha a shutil.which nem talált semmit
    if platform.system() == "Windows":
        # Környezeti változók a Program Files mappákhoz
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")

        # Kifejezetten a NordVPN CLI (`nordvpn.exe`) keresése
        if executable_name.lower() == "nordvpn.exe":
            potential_paths_nordvpn = [
                os.path.join(program_files, "NordVPN", "nordvpn.exe"),
                os.path.join(program_files_x86, "NordVPN", "nordvpn.exe")
            ]
            for potential_path in potential_paths_nordvpn:
                if os.path.exists(potential_path) and os.path.isfile(potential_path):
                    return potential_path
        
        # Opera keresése (launcher.exe az elsődleges, majd opera.exe)
        elif executable_name.lower() == "opera.exe" or executable_name.lower() == "launcher.exe": # Az Opera launcher.exe-t használhat
            # Az Opera gyakran a felhasználó AppData\Local mappájába települ
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            
            # Prioritási sorrend Opera esetén
            # 1. Újabb Opera telepítések (felhasználói profil) - launcher.exe
            # 2. Régebbi/rendszerszintű telepítések - launcher.exe
            # 3. Ha van opera.exe közvetlenül (kevésbé valószínű, de megpróbáljuk)
            opera_checks = [
                {"path": os.path.join(local_app_data, "Programs", "Opera", "launcher.exe"), "name": "Opera Launcher (User)"},
                {"path": os.path.join(local_app_data, "Programs", "Opera GX Browser", "launcher.exe"), "name": "Opera GX Launcher (User)"}, # Opera GX
                {"path": os.path.join(program_files, "Opera", "launcher.exe"), "name": "Opera Launcher (ProgramFiles)"},
                {"path": os.path.join(program_files, "Opera GX Browser", "launcher.exe"), "name": "Opera GX Launcher (ProgramFiles)"},
                {"path": os.path.join(program_files, "Opera", "opera.exe"), "name": "Opera.exe (ProgramFiles)"}, # Régebbi vagy alternatív
                {"path": os.path.join(program_files_x86, "Opera", "launcher.exe"), "name": "Opera Launcher (ProgramFiles x86)"},
                {"path": os.path.join(program_files_x86, "Opera", "opera.exe"), "name": "Opera.exe (ProgramFiles x86)"},
            ]
            for check in opera_checks:
                if os.path.exists(check["path"]) and os.path.isfile(check["path"]):
                    # print(f"DEBUG: Windows - Opera megtalálva ({check['name']}): {check['path']}")
                    # Ha opera.exe-t kerestünk, de launcher.exe-t találtunk (vagy fordítva), az is jó lehet,
                    # a BrowserManagerben a böngésző nevét használjuk a logoláshoz.
                    return check["path"]

        # Chrome keresése
        elif executable_name.lower() == "chrome.exe":
            potential_paths_chrome = [
                os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe")
            ]
            for potential_path in potential_paths_chrome:
                if os.path.exists(potential_path) and os.path.isfile(potential_path):
                    return potential_path
        
    elif platform.system() == "Darwin": # macOS
        # macOS-en a `shutil.which` általában jobban működik a .app csomagokon belüli futtathatókra,
        # ha a parancssori aliasok helyesen vannak beállítva, vagy ha a teljes elérési utat adjuk meg.
        # Például a Chrome: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
        # Opera: /Applications/Opera.app/Contents/MacOS/Opera
        # A `webbrowser` modul macOS-en is jól kezeli az alapértelmezett és regisztrált böngészőket.
        # Ha specifikus böngészőt akarunk, és a `shutil.which` nem találja, akkor itt lehetne
        # az /Applications mappában keresni.
        if executable_name.lower() == "google chrome" or executable_name.lower() == "chrome":
            potential_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if os.path.exists(potential_path): return potential_path
        elif executable_name.lower() == "opera":
            potential_path = "/Applications/Opera.app/Contents/MacOS/Opera"
            if os.path.exists(potential_path): return potential_path
        # NordVPN CLI macOS-en: a `shutil.which("nordvpn")` kellene, hogy működjön, ha telepítve van (pl. Homebrew-val)

    # print(f"DEBUG: '{executable_name}' nem található sem a PATH-ban, sem ismert platformspecifikus helyeken.")
    return None


def minimize_window_windows(window_title_substring):
    """
    Megpróbálja minimalizálni az ablakot Windows-on a címe alapján.
    """
    try:
        import pygetwindow as gw
        # Kis- és nagybetű érzéketlen kereséshez a címet is lekérjük és összehasonlítjuk
        target_window = None
        for window in gw.getAllWindows():
            if window_title_substring.lower() in window.title.lower():
                target_window = window
                break
        
        if target_window:
            if target_window.isMaximized:
                target_window.restore()
            if not target_window.isMinimized: # Csak akkor minimalizáljuk, ha még nincs
                 target_window.minimize()
            # print(f"Ablak '{target_window.title}' minimalizálva vagy már minimalizált.")
            return True
        else:
            # print(f"Nem található ablak '{window_title_substring}' címmel/részlettel a minimalizáláshoz.")
            return False
    except ImportError:
        # print("A 'pygetwindow' könyvtár nincs telepítve. Ablakminimalizálás Windows-on nem érhető el.")
        # print("Telepítés: pip install pygetwindow")
        return False
    except Exception as e:
        # print(f"Hiba az ablak minimalizálása közben: {e}")
        return False
