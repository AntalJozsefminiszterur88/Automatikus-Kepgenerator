# utils/ui_scanner.py
import pyautogui
import time

# Színkonstansok
PROMPT_AREA_WHITE_COLOR_TUPLE = (255, 255, 255) # Egzakt fehér
# A PROMPT_AREA_MIN_BRIGHTNESS konstansra így már nincs szükség, ha csak egzakt fehéret keresünk.

# FONTOS: Ellenőrizd ezt a színt a generálás gombon a pyautogui.mouseInfo() segítségével!
GENERATE_BUTTON_COLOR_TARGET = (41, 25, 32) 

def get_screen_size_util():
    return pyautogui.size()

def get_pixel_color_safe_util(x, y, screen_width, screen_height):
    if not (0 <= x < screen_width and 0 <= y < screen_height):
        return None
    try:
        return pyautogui.pixel(x, y)
    except Exception:
        return None

def is_color_prompt_area_like(color_tuple): # <<< MÓDOSÍTOTT FÜGGVÉNY
    """Ellenőrzi, hogy a szín pontosan fehér-e."""
    if color_tuple is None: return False
    return color_tuple == PROMPT_AREA_WHITE_COLOR_TUPLE # Csak az egzakt fehéret fogadja el

def find_prompt_area_dynamically(screen_width, screen_height, notify_callback=None):
    if notify_callback is None:
        notify_callback = lambda msg, error=False: print(f"UI_SCANNER: {msg}")

    seed_x = screen_width // 2
    seed_y = -1

    scan_start_y_for_seed = int(screen_height * 0.60) # Kicsit lejjebb kezdjük a keresést
    scan_end_y_for_seed = int(screen_height * 0.90) 
    
    notify_callback(f"Prompt terület 'mag' pixelének keresése (cél szín: {PROMPT_AREA_WHITE_COLOR_TUPLE}) X={seed_x} oszlopban, Y tartomány: [{scan_start_y_for_seed} - {scan_end_y_for_seed}]")

    # 1. Lefelé pásztázás a "mag" pixelért
    for y_current in range(scan_start_y_for_seed, scan_end_y_for_seed, 20):
        color = get_pixel_color_safe_util(seed_x, y_current, screen_width, screen_height)
        if notify_callback and y_current % (20*2) == 0 : # Ritkított logolás
            notify_callback(f"  Lefelé pásztázás Y={y_current}, talált szín: {color}")
        if is_color_prompt_area_like(color): # Most már csak (255,255,255)-re lesz True
            seed_y = y_current
            notify_callback(f"Fehér 'mag' pixel (lefelé pásztázva) található itt: ({seed_x}, {seed_y})")
            break
        # time.sleep(0.005) # Kivéve a gyorsaság miatt

    # 2. Ha lefelé nem találtuk, felfelé az aljától
    if seed_y == -1:
        notify_callback("Lefelé pásztázás sikertelen a középső X oszlopban. Felfelé pásztázás az aljától...", is_error=False)
        scan_start_y_bottom_up = screen_height - 20 
        # A felső határ legyen a korábbi lefelé pásztázás kezdőpontja
        scan_end_y_bottom_up_limit = scan_start_y_for_seed 
        for y_current in range(scan_start_y_bottom_up, scan_end_y_bottom_up_limit, -20):
            if y_current < 0 : break
            color = get_pixel_color_safe_util(seed_x, y_current, screen_width, screen_height)
            if notify_callback and y_current % (20*2) == 0 :
                notify_callback(f"  Felfelé pásztázás Y={y_current}, talált szín: {color}")
            if is_color_prompt_area_like(color):
                seed_y = y_current
                notify_callback(f"Fehér 'mag' pixel (felfelé pásztázva) található itt: ({seed_x}, {seed_y})")
                break
            # time.sleep(0.005)

    # 3. Ha a középső X oszlopban nem találtunk magot, kiterjesztett keresés X irányban
    if seed_y == -1:
        notify_callback(f"Függőleges pásztázás X={seed_x}-ben sikertelen. Kiterjesztett keresés X irányban Y={int(screen_height * 0.73)} körül...", is_error=False)
        # Egy valószínű Y magasságon (pl. 73%) próbálunk X irányban fehér pixelt keresni
        target_y_for_horizontal_seed_search = int(screen_height * 0.73)
        found_seed_in_row = False
        for x_offset in range(0, screen_width // 4, 10): # X irányú keresés +/- 25% szélességben
            for sign in [0, 1, -1]:
                if x_offset == 0 and sign != 0: continue
                current_x = seed_x + x_offset * sign
                if 0 <= current_x < screen_width:
                    color = get_pixel_color_safe_util(current_x, target_y_for_horizontal_seed_search, screen_width, screen_height)
                    if is_color_prompt_area_like(color):
                        seed_x = current_x # Új X mag
                        seed_y = target_y_for_horizontal_seed_search # Y mag
                        notify_callback(f"Fehér 'mag' pixel (oldalsó pásztázással) található itt: ({seed_x}, {seed_y})")
                        found_seed_in_row = True
                        break
            if found_seed_in_row: break
        if not found_seed_in_row:
            notify_callback("Nem található fehér 'mag' pixel a prompt terület azonosításához (kiterjesztett keresés sem).", is_error=True)
            return None
    
    notify_callback(f"Fehér 'mag' pont véglegesítve: ({seed_x}, {seed_y}). Határok keresése...")
    
    # Határok "kiterjesztése" a mag ponttól (pixelenként)
    l_x = seed_x
    while l_x > 0 and is_color_prompt_area_like(get_pixel_color_safe_util(l_x - 1, seed_y, screen_width, screen_height)):
        l_x -= 1
    r_x = seed_x
    while r_x < screen_width - 1 and is_color_prompt_area_like(get_pixel_color_safe_util(r_x + 1, seed_y, screen_width, screen_height)):
        r_x += 1
    
    horizontal_mid_x = (l_x + r_x) // 2
    t_y = seed_y
    while t_y > 0 and is_color_prompt_area_like(get_pixel_color_safe_util(horizontal_mid_x, t_y - 1, screen_width, screen_height)):
        t_y -= 1
    b_y = seed_y
    while b_y < screen_height - 1 and is_color_prompt_area_like(get_pixel_color_safe_util(horizontal_mid_x, b_y + 1, screen_width, screen_height)):
        b_y += 1

    if r_x > l_x and b_y > t_y:
        width = r_x - l_x + 1
        height = b_y - t_y + 1
        
        min_expected_width = int(screen_width * 0.30)
        max_expected_width = int(screen_width * 0.90)
        min_expected_height = int(screen_height * 0.10)
        max_expected_height = int(screen_height * 0.35) # Ezt a határt a logodban lévő (278) magassághoz igazítottam, ami kb 25% 1080p-n

        notify_callback(f"Talált terület mérete: {width}x{height}. Várt határok: W:[{min_expected_width}-{max_expected_width}], H:[{min_expected_height}-{max_expected_height}]")

        if not (min_expected_width <= width <= max_expected_width and \
                min_expected_height <= height <= max_expected_height):
            notify_callback(f"Talált világos terület mérete ({width}x{height}) kívül esik a várható prompt mező méretein.", is_error=True)
            return None
        
        prompt_rect = {'x': l_x, 'y': t_y, 'width': width, 'height': height,
                       'center_x': l_x + width // 2, 'center_y': t_y + height // 2}
        notify_callback(f"Prompt terület dinamikusan azonosítva: {prompt_rect}")
        return prompt_rect
    else:
        notify_callback(f"Nem sikerült érvényes határokat találni a prompt területhez. L:{l_x} R:{r_x} T:{t_y} B:{b_y}", is_error=True)
        return None

# ... (a find_generate_button_dynamic és a többi rész az ui_scanner.py-ban változatlan marad) ...
def find_generate_button_dynamic(prompt_rect, screen_width, screen_height, notify_callback=None):
    if not prompt_rect:
        if notify_callback: notify_callback("Generálás gomb keresés: Nincs érvényes prompt terület.", is_error=True)
        return None
    if notify_callback is None:
        notify_callback = lambda msg, error=False: print(f"UI_SCANNER: {msg}")

    x_scan_start = prompt_rect['x'] + prompt_rect['width'] - 1
    x_scan_width_percentage = 0.25 
    x_end_limit = prompt_rect['x'] + int(prompt_rect['width'] * (1 - x_scan_width_percentage))
    
    y_scan_start = prompt_rect['y'] + prompt_rect['height'] - 1
    y_scan_height_percentage = 0.50 
    y_end_limit = prompt_rect['y'] + int(prompt_rect['height'] * (1 - y_scan_height_percentage))

    notify_callback(f"Generálás gomb keresése ({GENERATE_BUTTON_COLOR_TARGET} színnel) X:[{x_scan_start}->{x_end_limit}], Y:[{y_scan_start}->{y_end_limit}] tartományban.")

    pixel_scan_count = 0
    for x_current in range(x_scan_start, max(prompt_rect['x']-1, x_end_limit -1), -1): 
        for y_current in range(y_scan_start, max(prompt_rect['y']-1, y_end_limit -1), -1): 
            pixel_scan_count +=1
            if pixel_scan_count % 500 == 0: 
                notify_callback(f"  Gen.gomb scan: ({x_current},{y_current})")

            color = get_pixel_color_safe_util(x_current, y_current, screen_width, screen_height)
            if color == GENERATE_BUTTON_COLOR_TARGET:
                notify_callback(f"Generálás gomb színe ({GENERATE_BUTTON_COLOR_TARGET}) MEGTALÁLVA itt: ({x_current}, {y_current})")
                click_x = max(0, x_current - 2)
                click_y = max(0, y_current - 2)
                return (click_x, click_y)
    
    notify_callback(f"Generálás gomb színe ({GENERATE_BUTTON_COLOR_TARGET}) nem található a relatív régióban ({pixel_scan_count} pixel ellenőrizve).", is_error=True)
    return None
