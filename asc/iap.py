#!/usr/bin/env python3
# Assinaturas do ScaleAI na App Store (compra dentro do app, exigencia 3.1.1 da Apple, 02/11/2026).
# Uso: python3 iap.py ler | criar | revisao | nota | notificacoes | testflight
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
        if atual and os.environ.get("SUBSTITUIR") == "1":
            send("DELETE", f"/subscriptionAppStoreReviewScreenshots/{atual['id']}", None); atual = None
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

def nota():
    # So a nota do revisor (asc/ficha.json "notas") na versao em edicao; nao mexe no resto da ficha.
    F = json.load(open(os.path.join(os.path.dirname(__file__), "ficha.json")))
    for v in todos(f"/apps/{APP_ID}/appStoreVersions", limit=20):
        if v["attributes"].get("appStoreState") in ("READY_FOR_SALE", "REMOVED_FROM_SALE"): continue
        rd = get(f"/appStoreVersions/{v['id']}/appStoreReviewDetail").get("data")
        if not rd: print("SEM_REVIEW_DETAIL", v["id"]); continue
        send("PATCH", f"/appStoreReviewDetails/{rd['id']}", {"data": {"type": "appStoreReviewDetails", "id": rd["id"], "attributes": {"notes": F["notas"]}}})
        print("NOTA_OK", v["attributes"].get("versionString"), v["attributes"].get("appStoreState"))
        break

URL_NOTIF = "https://scaleaimarketing.com/api/apps/6a8f510d5d31706c1bf917be/functions/appleCompra"

def notificacoes():
    # URL das notificacoes do servidor da App Store (V2), producao e sandbox.
    send("PATCH", f"/apps/{APP_ID}", {"data": {"type": "apps", "id": APP_ID, "attributes": {
        "subscriptionStatusUrl": URL_NOTIF, "subscriptionStatusUrlVersion": "V2",
        "subscriptionStatusUrlForSandbox": URL_NOTIF, "subscriptionStatusUrlVersionForSandbox": "V2"}}})
    a = get(f"/apps/{APP_ID}").get("data", {}).get("attributes", {})
    print("NOTIF", {k: a.get(k) for k in ("subscriptionStatusUrl", "subscriptionStatusUrlVersion", "subscriptionStatusUrlForSandbox", "subscriptionStatusUrlVersionForSandbox")})

def testflight():
    # Grupo interno "Equipe" com acesso a todos os builds e o titular da conta como tester.
    gid = None
    for g in todos(f"/apps/{APP_ID}/betaGroups", limit=50):
        a = g["attributes"]
        print("BETA_GRUPO", g["id"], a.get("name"), "interno", a.get("isInternalGroup"))
        if a.get("name") == "Equipe": gid = g["id"]
    if not gid:
        r = send("POST", "/betaGroups", {"data": {"type": "betaGroups", "attributes": {"name": "Equipe", "isInternalGroup": True, "hasAccessToAllBuilds": True},
            "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}}}})
        gid = r.get("data", {}).get("id")
    print("GRUPO_EQUIPE", gid)
    if not gid: return
    usuarios = todos("/users", limit=50)
    for u in usuarios:
        a = u["attributes"]
        print("USUARIO", u["id"], a.get("firstName"), a.get("roles"), "email_ok", bool(a.get("username")))
    titular = next((u for u in usuarios if "ACCOUNT_HOLDER" in (u["attributes"].get("roles") or [])), usuarios[0] if usuarios else None)
    if not titular: print("SEM_USUARIO"); return
    a = titular["attributes"]
    send("POST", "/betaTesters", {"data": {"type": "betaTesters", "attributes": {"email": a.get("username"), "firstName": a.get("firstName") or "Carlos", "lastName": a.get("lastName") or "Bezerra"},
        "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": gid}]}}}})
    ts = todos(f"/betaGroups/{gid}/betaTesters", limit=50)
    print("TESTERS_NO_GRUPO", len(ts), [t["attributes"].get("inviteType") for t in ts])
    for b in todos("/builds", **{"filter[app]": APP_ID, "sort": "-uploadedDate", "limit": 5}):
        print("BUILD", b["attributes"].get("version"), b["attributes"].get("processingState"))

def diag():
    # O que falta para as assinaturas ficarem prontas para envio.
    gid = grupo()
    for l in todos(f"/subscriptionGroups/{gid}/subscriptionGroupLocalizations", limit=50):
        print("LOC_GRUPO", l["attributes"].get("locale"), l["attributes"].get("state"))
    for s_ in todos(f"/subscriptionGroups/{gid}/subscriptions", limit=50):
        sid = s_["id"]; a = s_["attributes"]
        print("ASSIN", a.get("productId"), a.get("state"), "periodo", a.get("subscriptionPeriod"), "nota", bool(a.get("reviewNote")))
        for l in todos(f"/subscriptions/{sid}/subscriptionLocalizations", limit=50):
            print("  LOC", l["attributes"].get("locale"), l["attributes"].get("state"), len(l["attributes"].get("description") or ""))
        cap = get(f"/subscriptions/{sid}/appStoreReviewScreenshot").get("data") or {}
        ca = cap.get("attributes", {})
        print("  CAPTURA", ca.get("fileName"), ca.get("assetDeliveryState"), (ca.get("imageAsset") or {}).get("width"), (ca.get("imageAsset") or {}).get("height"))
        disp = get(f"/subscriptions/{sid}/subscriptionAvailability", include="availableTerritories").get("data") or {}
        print("  DISP", (disp.get("relationships", {}).get("availableTerritories", {}).get("meta") or {}))
        pr = get(f"/subscriptions/{sid}/prices", **{"filter[territory]": "BRA", "include": "subscriptionPricePoint"})
        inc = pr.get("included", [])
        print("  PRECO_BRA", [x["attributes"].get("customerPrice") for x in inc], [p_["attributes"].get("startDate") for p_ in pr.get("data", [])])
    try:
        print("APP_PRIVACIDADE", [l["attributes"].get("privacyPolicyUrl") for l in todos(f"/appInfos/226749c2-5c69-42a8-9075-5f8e68476dc0/appInfoLocalizations", limit=20)])
    except Exception as e: print("ERRO_APPINFO", repr(e)[:200])

def recalcular():
    # Salva de novo cada assinatura (mesma nota e mesmo nivel) para a Apple recalcular o status.
    gid = grupo()
    for s_ in todos(f"/subscriptionGroups/{gid}/subscriptions", limit=50):
        a = s_["attributes"]
        send("PATCH", f"/subscriptions/{s_['id']}", {"data": {"type": "subscriptions", "id": s_["id"], "attributes": {"reviewNote": NOTA, "familySharable": False}}})
    for s_ in todos(f"/subscriptionGroups/{gid}/subscriptions", limit=50):
        print("DEPOIS", s_["attributes"].get("productId"), s_["attributes"].get("state"))

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
    {"ler": ler, "criar": criar, "revisao": revisao, "nota": nota, "notificacoes": notificacoes, "testflight": testflight, "diag": diag, "recalcular": recalcular}.get(sys.argv[1] if len(sys.argv) > 1 else "ler", ler)()
    ler()
