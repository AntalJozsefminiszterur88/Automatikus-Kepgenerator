# utils/ip_geolocation.py
import json
try:
    import requests
except ImportError:
    print("FIGYELEM: A 'requests' könyvtár nincs telepítve. Az IP alapú geolokáció nem fog működni.")
    print("Telepítsd: pip install requests")
    requests = None

# Opcionálisan itt definiálhatnánk egy loggert, ha a fő loggerünket akarjuk használni
# import logging
# logger = logging.getLogger(__name__) # Vagy a fő logger referenciája

def get_public_ip_info(timeout_s=5):
    """
    Lekérdezi az aktuális publikus IP címet és országkódot több külső API-n keresztül.
    Visszaad egy dictionary-t {"ip": "x.x.x.x", "country_code": "XX"} formában,
    vagy None-t, ha nem sikerült.
    """
    if not requests:
        # print("Hiba: A 'requests' könyvtár nem érhető el az IP ellenőrzéshez.") # Ezt már az importnál jeleztük
        return None
    
    # API-k listája (URL, JSON kulcs az országkódhoz)
    # Az ipinfo.io néha token-t kérhet nagyobb forgalomnál, de az alap ingyenes.
    apis_to_try = [
        {"url": "https://ipinfo.io/json", "ip_key": "ip", "country_key": "country"},
        {"url": "https://ip-api.com/json/?fields=status,message,countryCode,query", "ip_key": "query", "country_key": "countryCode"},
        {"url": "https://freeipapi.com/api/json/", "ip_key": "ipAddress", "country_key": "countryCode"}
    ]
    
    for api_details in apis_to_try:
        url = api_details["url"]
        ip_key = api_details["ip_key"]
        country_key = api_details["country_key"]
        
        # print(f"IP lekérdezési kísérlet: {url}") # Debug üzenet
        try:
            response = requests.get(url, timeout=timeout_s)
            response.raise_for_status() # HTTP hibák esetén kivételt dob (4xx, 5xx)
            data = response.json()
            
            # Ellenőrzés, hogy az API sikeres választ adott-e (az ip-api.com esetében)
            if "status" in data and data["status"] == "fail":
                # print(f"IP API ({url}) 'fail' státuszt adott: {data.get('message', 'Ismeretlen hiba')}")
                continue # Próbálkozzunk a következő API-val

            ip_address = data.get(ip_key)
            country_code = data.get(country_key)
            
            if ip_address and country_code:
                # print(f"Sikeres IP lekérdezés: {ip_address}, Országkód: {country_code} (Forrás: {url.split('/')[2]})")
                return {"ip": ip_address, "country_code": str(country_code).upper()}
        except requests.exceptions.Timeout:
            # print(f"Időtúllépés az IP API ({url}) elérése közben.")
            pass # Csak logoljuk, vagy hagyjuk, hogy a hívó kezelje, ha mindegyik sikertelen
        except requests.exceptions.RequestException as e:
            # print(f"Hálózati hiba az IP API ({url}) elérése közben: {e}")
            pass
        except json.JSONDecodeError:
            # print(f"JSON dekódolási hiba az IP API ({url}) válaszában.")
            pass
        except Exception as e: # Bármilyen egyéb váratlan hiba
            # print(f"Váratlan hiba az IP API ({url}) használata közben: {e}")
            pass
            
    # Ha egyik API sem adott sikeres választ
    # print("Nem sikerült lekérdezni az IP információkat egyetlen API-ról sem.")
    return None

if __name__ == '__main__':
    # Tesztelés, ha a fájlt közvetlenül futtatjuk
    print("IP Geolokációs modul tesztelése...")
    info = get_public_ip_info()
    if info:
        print(f"  Lekérdezett IP: {info.get('ip')}")
        print(f"  Országkód: {info.get('country_code')}")
    else:
        print("  Nem sikerült lekérdezni az IP információkat.")
