import json
import re
import time
from datetime import datetime, timezone

import requests

# Ruwe sheet-exports uit de VehicleUpdates-repo (geen belasting op de website zelf)
SHEET_URL = "https://raw.githubusercontent.com/HulpdienstVoertuigenBeNeLux/VehicleUpdates/refs/heads/master/raw/sheets/{}.json"
COUNTRIES = [("NL", "Nederland"), ("BE", "België"), ("LUX", "Luxemburg")]
OUTPUT = "fotodekking.json"


def get_rows(code):
    """Haalt de rijen van één land op, met een paar nieuwe pogingen."""
    for i in range(3):
        try:
            response = requests.get(SHEET_URL.format(code), timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("values", data) if isinstance(data, dict) else data
        except Exception as e:
            print(f"{code}: poging {i+1} mislukt: {e}")
            time.sleep(5)
    return None


def region_sort_key(name):
    # Genummerde veiligheidsregio's op nummer, daarna de rest op naam, "(geen regio)" achteraan
    m = re.match(r"(\d+)\s*-", name)
    if m:
        return (0, int(m.group(1)), name)
    return (2 if name == "(geen regio)" else 1, 0, name.lower())


def count_country(rows):
    # Kolommen op naam opzoeken; de ID-kolom (POST-… / VEH-…) heeft geen kopnaam en staat achteraan
    header = [str(h).strip().lower() for h in rows[0]]
    i_regio = header.index("regio")
    i_foto = header.index("fotoboek")
    regions = {}
    for row in rows[1:]:
        if not isinstance(row, list) or not row:
            continue
        row_id = str(row[-1]).strip() if len(row) >= len(header) else ""
        if row_id.startswith("POST"):
            kind = "posten"
        elif row_id.startswith("VEH"):
            kind = "voertuigen"
        else:
            continue
        regio = str(row[i_regio]).strip() if len(row) > i_regio else ""
        foto = bool(str(row[i_foto]).strip()) if len(row) > i_foto else False
        r = regions.setdefault(regio or "(geen regio)", {"posten": [0, 0], "voertuigen": [0, 0]})
        r[kind][0] += 1
        r[kind][1] += foto

    result = []
    for name in sorted(regions, key=region_sort_key):
        r = regions[name]
        result.append({
            "regio": name,
            "posten": r["posten"][0], "posten_foto": r["posten"][1],
            "voertuigen": r["voertuigen"][0], "voertuigen_foto": r["voertuigen"][1],
        })
    return result


def process():
    countries = []
    for code, name in COUNTRIES:
        rows = get_rows(code)
        if not rows:
            print(f"{code}: geen data ontvangen; {OUTPUT} blijft ongewijzigd.")
            return False
        try:
            regions = count_country(rows)
        except ValueError as e:
            print(f"{code}: kolom Regio/Fotoboek niet gevonden ({e}); {OUTPUT} blijft ongewijzigd.")
            return False
        if not regions:
            print(f"{code}: geen posten of voertuigen geteld; {OUTPUT} blijft ongewijzigd.")
            return False
        totals = {k: sum(r[k] for r in regions) for k in ("posten", "posten_foto", "voertuigen", "voertuigen_foto")}
        countries.append({"code": code, "naam": name, "totaal": totals, "regios": regions})
        print(f"{code}: {len(regions)} regio's, {totals['voertuigen_foto']}/{totals['voertuigen']} voertuigen met foto")

    # Bestand alleen herschrijven als de cijfers veranderen (anders elke run een commit door de datum)
    try:
        with open(OUTPUT, "r", encoding="utf-8") as f:
            if json.load(f).get("landen") == countries:
                print("Geen wijzigingen in de cijfers.")
                return True
    except (OSError, ValueError):
        pass

    data = {"bijgewerkt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "landen": countries}
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Succes! {OUTPUT} bijgewerkt.")
    return True


if __name__ == "__main__":
    # Mislukte run laten zien in GitHub Actions in plaats van stil oude cijfers te houden
    if not process():
        raise SystemExit(1)
