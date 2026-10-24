#!/usr/bin/env python3
# Preco (gratis) e disponibilidade do ScaleAI na App Store. Uso: python3 disp.py ver | aplicar
# Padrao: todos os paises, MENOS a Uniao Europeia (la a Apple exige o status de comerciante/DSA).
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from asc import get, send, S, h, API, APP_ID

UE = {"AUT","BEL","BGR","HRV","CYP","CZE","DNK","EST","FIN","FRA","DEU","GRC","HUN","IRL","ITA","LVA","LTU","LUX","MLT","NLD","POL","PRT","ROU","SVK","SVN","ESP","SWE"}

def ver():
    mp = get(f"/appPriceSchedules/{APP_ID}/manualPrices", **{"include": "appPricePoint,territory", "limit": 5})
    print("PRECOS_MANUAIS", json.dumps(mp.get("data", []))[:600], json.dumps(mp.get("included", []))[:600])
    print("BASE", json.dumps(get(f"/appPriceSchedules/{APP_ID}/baseTerritory").get("data"))[:300])
    av = get(f"/apps/{APP_ID}/appAvailabilityV2")
    print("DISP", json.dumps(av)[:400])

def aplicar():
    # 1) Preco gratis (territorio base EUA)
    mp = get(f"/appPriceSchedules/{APP_ID}/manualPrices", **{"limit": 5}).get("data", [])
    if not mp:
        pp = None; url = f"/apps/{APP_ID}/appPricePoints"; q = {"filter[territory]": "USA", "limit": 200}
        while url and not pp:
            d = get(url, **q); q = {}
            for p in d.get("data", []):
                if str(p["attributes"].get("customerPrice")) in ("0", "0.0", "0.00"): pp = p["id"]; break
            url = d.get("links", {}).get("next")
        print("PONTO_GRATIS", bool(pp))
        if pp:
            send("POST", "/appPriceSchedules", {"data": {"type": "appPriceSchedules", "relationships": {
                "app": {"data": {"type": "apps", "id": APP_ID}},
                "baseTerritory": {"data": {"type": "territories", "id": "USA"}},
                "manualPrices": {"data": [{"type": "appPrices", "id": "${preco1}"}]}}},
                "included": [{"type": "appPrices", "id": "${preco1}", "attributes": {"startDate": None},
                    "relationships": {"appPricePoint": {"data": {"type": "appPricePoints", "id": pp}}}}]})
    else:
        print("PRECO_JA_DEFINIDO")
    # 2) Disponibilidade
    terr = []; url = "/territories"; q = {"limit": 200}
    while url:
        d = get(url, **q); q = {}
        terr += [t["id"] for t in d.get("data", [])]
        url = d.get("links", {}).get("next")
    print("TERRITORIOS", len(terr))
    inc = []; refs = []
    for i, t in enumerate(terr):
        lid = "${t%d}" % i
        refs.append({"type": "territoryAvailabilities", "id": lid})
        inc.append({"type": "territoryAvailabilities", "id": lid, "attributes": {"available": t not in UE},
                    "relationships": {"territory": {"data": {"type": "territories", "id": t}}}})
    r = S.post(API.replace("/v1", "/v2") + "/appAvailabilities", headers=h(), data=json.dumps({"data": {"type": "appAvailabilities",
        "attributes": {"availableInNewTerritories": True},
        "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}, "territoryAvailabilities": {"data": refs}}}, "included": inc}))
    print("DISPONIBILIDADE", r.status_code, r.text[:700])

if __name__ == "__main__":
    {"ver": ver, "aplicar": aplicar}[sys.argv[1] if len(sys.argv) > 1 else "ver"]()
    ver()
