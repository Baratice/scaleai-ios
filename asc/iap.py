#!/usr/bin/env python3
# Assinaturas do ScaleAI na App Store (compra dentro do app, exigencia 3.1.1 da Apple, 02/11/2026).
# Uso: python3 iap.py ler | criar | revisao
#  - criar: grupo "ScaleAI Planos" + Starter, Pro e Agency mensais, textos pt-BR/en-US/es-MX,
#           disponibilidade (todos os paises menos a UE) e precos (BRL 97,90 / 197,90 / 297,90 no
#           Brasil; demais paises pelo equivalente da propria Apple). Idempotente.
#  - revisao: envia a captura de revisao (capturas/assinatura-revisao.png) de cada assinatura.
# Mesmo padrao de asc.py: chave da integracao "Codemagic Baratice". Nunca imprime chaves.
import os, sys, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from asc import get, send, S, h, API, APP_ID

UE = {"AUT","BEL","BGR","HRV","CYP","CZE","DNK","EST","FIN","FRA","DEU","GRC","HUN","IRL","ITA","LVA","LTU","LUX","MLT","NLD","POL","PRT","ROU","SVK","SVN","ESP","SWE"}
GRUPO = "ScaleAI Planos"
# groupLevel: 1 = nivel mais alto (Agency). Trocar para nivel mais alto = upgrade imediato.
PLANOS = [
    {"id": "scaleai.starter.mensal", "ref": "ScaleAI Starter mensal", "nivel": 3, "brl": "97.90",
     "loc": {"pt-BR": ("ScaleAI Starter", "500 creditos de IA e 5 videos por mes"),
             "en-US": ("ScaleAI Starter", "500 AI credits and 5 videos per month"),
             "es-MX": ("ScaleAI Starter", "500 creditos de IA y 5 videos al mes")}},
    {"id": "scaleai.pro.mensal", "ref": "ScaleAI Pro mensal", "nivel": 2, "brl": "197.90",
     "loc": {"pt-BR": ("ScaleAI Pro", "2.000 creditos de IA, 15 videos e agentes"),
             "en-US": ("ScaleAI Pro", "2,000 AI credits, 15 videos and AI agents"),
             "es-MX": ("ScaleAI Pro", "2.000 creditos de IA, 15 videos y agentes")}},
    {"id": "scaleai.agency.mensal", "ref": "ScaleAI Agency mensal", "nivel": 1, "brl": "297.90",
     "loc": {"pt-BR": ("ScaleAI Agency", "5.000 creditos de IA, 30 videos e tudo"),
             "en-US": ("ScaleAI Agency", "5,000 AI credits, 30 videos and everything"),
             "es-MX": ("ScaleAI Agency", "5.000 creditos de IA, 30 videos y todo")}},
]
NOTA = ("Monthly auto-renewing subscription. Unlocks the plan's monthly AI and video credits, product and campaign "
        "limits. Subscribe in the app: More > Perfil > Escolha seu plano. Restore purchases is on the same screen. "
        "The demo account already has an active complimentary plan, so use a Sandbox account to test the purchase.")

def todos(url, **q):
    out = []
    while url:
        d = get(url, **q); q = {}
        out += d.get("data", [])
        url = d.get("links", {}).get("next")
    return out

def grupo():
    for g in todos(f"/apps/{APP_ID}/subscriptionGroups", limit=50):
        if g["attributes"].get("referenceName") == GRUPO: return g["id"]
    r = send("POST", "/subscriptionGroups", {"data": {"type": "subscriptionGroups", "attributes": {"referenceName": GRUPO},
        "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}}}})
    return r.get("data", {}).get("id")

def loc_grupo(gid):
    ja = {l["attributes"]["locale"] for l in todos(f"/subscriptionGroups/{gid}/subscriptionGroupLocalizations", limit=50)}
    for loc, nome in {"pt-BR": "Planos ScaleAI", "en-US": "ScaleAI Plans", "es-MX": "Planes ScaleAI"}.items():
        if loc in ja: continue
        send("POST", "/subscriptionGroupLocalizations", {"data": {"type": "subscriptionGroupLocalizations",
            "attributes": {"locale": loc, "name": nome, "customAppName": "ScaleAI"},
            "relationships": {"subscriptionGroup": {"data": {"type": "subscriptionGroups", "id": gid}}}}})

def assinatura(gid, p):
    for s in todos(f"/subscriptionGroups/{gid}/subscriptions", limit=50):
        if s["attributes"].get("productId") == p["id"]: return s["id"]
    r = send("POST", "/subscriptions", {"data": {"type": "subscriptions", "attributes": {
        "name": p["ref"], "productId": p["id"], "subscriptionPeriod": "ONE_MONTH", "groupLevel": p["nivel"],
        "familySharable": False, "reviewNote": NOTA},
        "relationships": {"group": {"data": {"type": "subscriptionGroups", "id": gid}}}}})
    return r.get("data", {}).get("id")

def loc_assinatura(sid, p):
    ja = {l["attributes"]["locale"] for l in todos(f"/subscriptions/{sid}/subscriptionLocalizations", limit=50)}
    for loc, (nome, desc) in p["loc"].items():
        if loc in ja: continue
        send("POST", "/subscriptionLocalizations", {"data": {"type": "subscriptionLocalizations",
            "attributes": {"locale": loc, "name": nome, "description": desc[:55]},
            "relationships": {"subscription": {"data": {"type": "subscriptions", "id": sid}}}}})

def territorios():
    return [t["id"] for t in todos("/territories", limit=200) if t["id"] not in UE]

def disponibilidade(sid, terrs):
    d = get(f"/subscriptions/{sid}/subscriptionAvailability")
    if d.get("data"):
        print("DISP_JA_DEFINIDA", sid); return
    send("POST", "/subscriptionAvailabilities", {"data": {"type": "subscriptionAvailabilities",
        "attributes": {"availableInNewTerritories": False},
        "relationships": {"subscription": {"data": {"type": "subscriptions", "id": sid}},
            "availableTerritories": {"data": [{"type": "territories", "id": t} for t in terrs]}}}})

def precos(sid, p, terrs):
    ja = todos(f"/subscriptions/{sid}/prices", limit=200, include="territory")
    if len(ja) >= len(terrs) - 2:
        print("PRECOS_JA_DEFINIDOS", sid, len(ja)); return
    pts = todos(f"/subscriptions/{sid}/pricePoints", **{"filter[territory]": "BRA", "limit": 200})
    alvo = float(p["brl"])
    melhor = min(pts, key=lambda x: abs(float(x["attributes"]["customerPrice"]) - alvo)) if pts else None
    if not melhor: print("SEM_PONTO_BRA", sid); return
    print("PONTO_BRA", p["id"], melhor["attributes"]["customerPrice"], "proceeds", melhor["attributes"].get("proceeds"))
    eq = todos(f"/subscriptionPricePoints/{melhor['id']}/equalizations", limit=200, include="territory")
    por_terr = {"BRA": melhor["id"]}
    for e in eq:
        t = (e.get("relationships", {}).get("territory", {}).get("data") or {}).get("id")
        if t: por_terr[t] = e["id"]
    feitos = falhas = 0
    for t in terrs:
        ppid = por_terr.get(t)
        if not ppid: continue
        r = S.post(API + "/subscriptionPrices", headers=h(), data=json.dumps({"data": {"type": "subscriptionPrices",
            "attributes": {"startDate": None, "preserveCurrentPrice": False},
            "relationships": {"subscription": {"data": {"type": "subscriptions", "id": sid}},
                "subscriptionPricePoint": {"data": {"type": "subscriptionPricePoints", "id": ppid}},
                "territory": {"data": {"type": "territories", "id": t}}}}}))
        if r.status_code < 300: feitos += 1
        else:
            falhas += 1
            if falhas <= 3: print("ERRO_PRECO", t, r.status_code, r.text[:300])
    print("PRECOS", p["id"], "feitos", feitos, "falhas", falhas, "de", len(terrs))

def criar():
    gid = grupo(); print("GRUPO", gid)
    if not gid: return
    loc_grupo(gid)
    terrs = territorios(); print("TERRITORIOS_SEM_UE", len(terrs))
    for p in PLANOS:
        sid = assinatura(gid, p); print("ASSINATURA", p["id"], sid)
        if not sid: continue
        loc_assinatura(sid, p)
        disponibilidade(sid, terrs)
        precos(sid, p, terrs)

def revisao():
    arq = os.path.join(os.path.dirname(__file__), "..", "capturas", "assinatura-revisao.png")
    if not os.path.isfile(arq): print("SEM_CAPTURA", arq); return
    dados = open(arq, "rb").read()
    gid = grupo()
    for s in todos(f"/subscriptionGroups/{gid}/subscriptions", limit=50):
        sid = s["id"]
        atual = get(f"/subscriptions/{sid}/appStoreReviewScreenshot").get("data")
        if atual: print("CAPTURA_JA_EXISTE", s["attributes"]["productId"]); continue
        r = send("POST", "/subscriptionAppStoreReviewScreenshots", {"data": {"type": "subscriptionAppStoreReviewScreenshots",
            "attributes": {"fileName": "assinatura-revisao.png", "fileSize": len(dados)},
            "relationships": {"subscription": {"data": {"type": "subscriptions", "id": sid}}}}})
        d = r.get("data")
        if not d: continue
        for op in d["attributes"].get("uploadOperations", []):
            parte = dados[op["offset"]:op["offset"] + op["length"]]
            hd = {x["name"]: x["value"] for x in op.get("requestHeaders", [])}
            u = S.request(op["method"], op["url"], headers=hd, data=parte)
            print("UPLOAD", u.status_code)
        send("PATCH", f"/subscriptionAppStoreReviewScreenshots/{d['id']}", {"data": {"type": "subscriptionAppStoreReviewScreenshots",
            "id": d["id"], "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(dados).hexdigest()}}})

def ler():
    gid = None
    for g in todos(f"/apps/{APP_ID}/subscriptionGroups", limit=50):
        print("GRUPO", g["id"], g["attributes"])
        gid = g["id"]
        for s in todos(f"/subscriptionGroups/{gid}/subscriptions", limit=50):
            a = s["attributes"]
            np = len(todos(f"/subscriptions/{s['id']}/prices", limit=200))
            cap = bool(get(f"/subscriptions/{s['id']}/appStoreReviewScreenshot").get("data"))
            print("  ASSINATURA", s["id"], a.get("productId"), a.get("state"), "nivel", a.get("groupLevel"), "precos", np, "captura", cap)
    if not gid: print("NENHUM_GRUPO")

if __name__ == "__main__":
    {"ler": ler, "criar": criar, "revisao": revisao}.get(sys.argv[1] if len(sys.argv) > 1 else "ler", ler)()
    ler()
