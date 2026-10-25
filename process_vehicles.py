import json
import requests
import time

def get_data():
    """Haalt de ruwe data op van de API."""
    url = "https://hulpdienstvoertuigenbenelux.nl/fetch-sheet?region=NL"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://hulpdienstvoertuigenbenelux.nl/",
        "Accept": "application/json"
    }
    for i in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Poging {i+1} mislukt: {e}")
            time.sleep(5)
    return None

def process():
    # 1. Laad Afkortingen.json voor de sortering
    try:
        with open('Afkortingen.json', 'r', encoding='utf-8') as f:
            sort_order_data = json.load(f)
            # Map: {"AFK": index}
            sort_map = {str(item['afkorting']).strip().upper(): i for i, item in enumerate(sort_order_data)}
    except Exception as e:
        print(f"Fout bij laden Afkortingen.json (sorteerlijst ontbreekt of leeg): {e}")
        sort_map = {}

    # 2. Haal de data op
    data = get_data()
    if not data:
        print("Geen data ontvangen van API.")
        return False

    # Normaliseer data naar een lijst van rijen
    rows = data.get("values", data) if isinstance(data, dict) else data

    # 3. Kolommen opzoeken op naam (de volgorde in de sheet kan veranderen)
    header = [str(h).strip().lower() for h in rows[0]] if rows and isinstance(rows[0], list) else []
    try:
        i_afk = header.index("afkorting")
        i_typ = header.index("typevoertuig")
        i_hd = header.index("hulpdienst")
    except ValueError:
        print(f"Kolommen Afkorting/TypeVoertuig/Hulpdienst niet gevonden in de kopregel: {header}")
        return False

    # 4. Tellen van de voertuigen
    counts = {}
    # We starten bij [1:] om de header-rij over te slaan
    for row in rows[1:]:
        if isinstance(row, list) and len(row) > max(i_afk, i_typ, i_hd):
            hulpdienst = str(row[i_hd]).strip().lower()
            afk = str(row[i_afk]).strip()
            typ = str(row[i_typ]).strip()
            
            # Filter: Brandweer en vereiste velden ingevuld
            if hulpdienst == "brandweer" and afk and typ:
                key = (afk.upper(), typ)
                counts[key] = counts.get(key, 0) + 1

    # Lege uitkomst betekent dat er iets mis is met de data: bestaand bestand niet overschrijven
    if not counts:
        print("Geen brandweervoertuigen geteld; vehicle_counts.json blijft ongewijzigd.")
        return False
    
    # 5. Sorteren met fallback naar 999 voor onbekende afkortingen
    def sort_key(item):
        afk = item[0][0].upper()
        return sort_map.get(afk, 999)

    sorted_items = sorted(counts.items(), key=sort_key)
    
    # 6. Resultaat opbouwen
    result = []
    for (afk, typ), aantal in sorted_items:
        result.append({
            "afkorting": afk, 
            "type": typ, 
            "aantal": aantal
        })
    
    # 7. Opslaan
    with open('vehicle_counts.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Succes! {len(result)} voertuigtypes verwerkt.")
    return True

if __name__ == "__main__":
    # Mislukte run laten zien in GitHub Actions in plaats van stil een lege lijst te houden
    if not process():
        raise SystemExit(1)
