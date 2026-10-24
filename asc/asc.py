#!/usr/bin/env python3
# Ficha do ScaleAI no App Store Connect pela API oficial (chave da integracao "Codemagic Baratice").
# Uso: python3 asc.py ler | preencher
# Nunca imprime chaves nem senhas.
import os, sys, json, time, hashlib, glob, textwrap
import jwt, requests

APP_ID = "6826369919"
API = "https://api.appstoreconnect.apple.com/v1"

def chave():
    k = os.environ["APP_STORE_CONNECT_PRIVATE_KEY"].strip()
    if k.startswith("@file:"): k = open(os.path.expanduser(k[6:])).read()
    elif k.startswith("@env:"): k = os.environ[k[5:]]
    elif os.path.isfile(k): k = open(k).read()
    k = k.replace("\\n", "\n").strip()
    if "BEGIN" not in k:
        import base64
        try:
            d = base64.b64decode(k).decode()
            if "BEGIN" in d: k = d
        except Exception: pass
    if "BEGIN" not in k:
        k = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(textwrap.wrap(k.replace(" ", ""), 64)) + "\n-----END PRIVATE KEY-----"
    return k

def token():
    k = chave()
    return jwt.encode({"iss": os.environ["APP_STORE_CONNECT_ISSUER_ID"], "iat": int(time.time()), "exp": int(time.time()) + 1100, "aud": "appstoreconnect-v1"},
                      k, algorithm="ES256", headers={"kid": os.environ["APP_STORE_CONNECT_KEY_IDENTIFIER"], "typ": "JWT"})

S = requests.Session()
def h(): return {"Authorization": "Bearer " + token(), "Content-Type": "application/json"}
def get(p, **q):
    r = S.get(p if p.startswith("http") else API + p, headers=h(), params=q); 
    if r.status_code >= 300: print("ERRO GET", p, r.status_code, r.text[:600]); return {}
    return r.json()
def send(m, p, body):
    r = S.request(m, API + p, headers=h(), data=json.dumps(body))
    ok = r.status_code < 300
    print(("OK " if ok else "ERRO ") + m, p, r.status_code, "" if ok else r.text[:900])
    return r.json() if ok and r.text else {}

def versao():
    d = get(f"/apps/{APP_ID}/appStoreVersions", **{"filter[platform]": "IOS", "limit": 10})
    vs = d.get("data", [])
    for v in vs: print("VERSAO", v["id"], v["attributes"]["versionString"], v["attributes"]["appStoreState"])
    edit = [v for v in vs if v["attributes"]["appStoreState"] in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED")]
    return edit[0] if edit else (vs[0] if vs else None)

def ler():
    k0 = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY", "")
    print("FORMATO_CHAVE", {"tam": len(k0), "begin": "BEGIN" in k0, "barra_n": "\\n" in k0, "arroba": k0[:6] if k0.startswith("@") else "", "linhas": k0.count("\n")})
    print("ENV", {k: bool(os.environ.get(k)) for k in ["APP_STORE_CONNECT_PRIVATE_KEY", "APP_STORE_CONNECT_ISSUER_ID", "APP_STORE_CONNECT_KEY_IDENTIFIER", "DEMO_EMAIL", "DEMO_SENHA"]})
    app = get(f"/apps/{APP_ID}")
    a = app.get("data", {}).get("attributes", {})
    print("APP", {k: a.get(k) for k in ["name", "bundleId", "primaryLocale", "contentRightsDeclaration", "isOrEverWasMadeForKids"]})
    for i in get(f"/apps/{APP_ID}/appInfos").get("data", []):
        print("APPINFO", i["id"], i["attributes"].get("appStoreState"), i["attributes"].get("appStoreAgeRating"))
        for c in ["primaryCategory", "secondaryCategory"]:
            print("  ", c, get(f"/appInfos/{i['id']}/{c}").get("data"))
        for l in get(f"/appInfos/{i['id']}/appInfoLocalizations").get("data", []):
            print("  INFO_LOC", l["id"], {k: l["attributes"].get(k) for k in ["locale", "name", "subtitle", "privacyPolicyUrl"]})
        ar = get(f"/appInfos/{i['id']}/ageRatingDeclaration").get("data")
        print("  AGE", ar and ar["id"], ar and ar["attributes"])
    v = versao()
    if not v: return
    vid = v["id"]
    print("VATTR", v["attributes"])
    print("BUILD_DA_VERSAO", get(f"/appStoreVersions/{vid}/build").get("data"))
    for b in get("/builds", **{"filter[app]": APP_ID, "limit": 10, "sort": "-uploadedDate"}).get("data", []):
        print("BUILD", b["id"], b["attributes"].get("version"), b["attributes"].get("processingState"), b["attributes"].get("uploadedDate"), b["attributes"].get("usesNonExemptEncryption"))
    for l in get(f"/appStoreVersions/{vid}/appStoreVersionLocalizations").get("data", []):
        at = l["attributes"]
        print("LOC", l["id"], at.get("locale"), {k: (at.get(k) or "")[:80] for k in ["description", "keywords", "promotionalText", "supportUrl", "marketingUrl", "whatsNew"]})
        for s in get(f"/appStoreVersionLocalizations/{l['id']}/appScreenshotSets").get("data", []):
            n = len(get(f"/appScreenshotSets/{s['id']}/appScreenshots").get("data", []))
            print("   SET", s["id"], s["attributes"]["screenshotDisplayType"], n)
    rd = get(f"/appStoreVersions/{vid}/appStoreReviewDetail").get("data")
    if rd:
        at = dict(rd["attributes"]); 
        if at.get("demoAccountPassword"): at["demoAccountPassword"] = "***"
        print("REVIEW", rd["id"], at)
    else: print("REVIEW nenhum")
    print("PRECO", get(f"/apps/{APP_ID}/appPriceSchedule").get("data"))
    print("DISPONIBILIDADE", get(f"/apps/{APP_ID}/appAvailabilityV2").get("data"))

def rel(tipo, id_): return {"data": {"type": tipo, "id": id_}}

def preencher():
    vid = None; loc = None; iid = None
    F = json.load(open(os.path.join(os.path.dirname(__file__), "ficha.json")))
    try:
        # 1) App: direitos de conteudo de terceiros
        send("PATCH", f"/apps/{APP_ID}", {"data": {"type": "apps", "id": APP_ID, "attributes": {"contentRightsDeclaration": "USES_THIRD_PARTY_CONTENT"}}})
    except Exception as e: print("ERRO_PASSO", repr(e)[:300])
    try:
        # 2) App info: categorias, subtitulo, privacidade, classificacao etaria
        infos = get(f"/apps/{APP_ID}/appInfos").get("data", [])
        info = [i for i in infos if i["attributes"].get("appStoreState") in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED")] or infos
        iid = info[0]["id"]
        send("PATCH", f"/appInfos/{iid}", {"data": {"type": "appInfos", "id": iid, "relationships": {
            "primaryCategory": rel("appCategories", F["categoria1"]), "secondaryCategory": rel("appCategories", F["categoria2"])}}})
        for l in get(f"/appInfos/{iid}/appInfoLocalizations").get("data", []):
            if l["attributes"]["locale"] == "pt-BR":
                send("PATCH", f"/appInfoLocalizations/{l['id']}", {"data": {"type": "appInfoLocalizations", "id": l["id"], "attributes": {
                    "subtitle": F["subtitle"], "privacyPolicyUrl": F["privacyPolicyUrl"]}}})
        ar = get(f"/appInfos/{iid}/ageRatingDeclaration").get("data")
        if ar:
            enums = ["alcoholTobaccoOrDrugUseOrReferences", "contests", "gamblingSimulated", "gunsOrOtherWeapons", "medicalOrTreatmentInformation",
                     "profanityOrCrudeHumor", "sexualContentGraphicAndNudity", "sexualContentOrNudity", "horrorOrFearThemes", "matureOrSuggestiveThemes",
                     "violenceCartoonOrFantasy", "violenceRealisticProlongedGraphicOrSadistic", "violenceRealistic"]
            bools = ["advertising", "gambling", "healthOrWellnessTopics", "lootBox", "messagingAndChat", "parentalControls", "ageAssurance",
                     "socialMedia", "socialMediaAgeRestricted", "unrestrictedWebAccess", "userGeneratedContent"]
            at = {k: "NONE" for k in enums if k in ar["attributes"]}
            at.update({k: False for k in bools if k in ar["attributes"]})
            r = send("PATCH", f"/ageRatingDeclarations/{ar['id']}", {"data": {"type": "ageRatingDeclarations", "id": ar["id"], "attributes": at}})
            if not r:
                for k, v in at.items():
                    if not send("PATCH", f"/ageRatingDeclarations/{ar['id']}", {"data": {"type": "ageRatingDeclarations", "id": ar["id"], "attributes": {k: v}}}):
                        alt = (not v) if isinstance(v, bool) else False
                        send("PATCH", f"/ageRatingDeclarations/{ar['id']}", {"data": {"type": "ageRatingDeclarations", "id": ar["id"], "attributes": {k: alt}}})
    except Exception as e: print("ERRO_PASSO", repr(e)[:300])
    try:
        # 3) Versao: copyright, lancamento manual, build
        v = versao(); vid = v["id"]
        send("PATCH", f"/appStoreVersions/{vid}", {"data": {"type": "appStoreVersions", "id": vid, "attributes": {"copyright": F["copyright"], "releaseType": "MANUAL"}}})
        builds = [b for b in get("/builds", **{"filter[app]": APP_ID, "filter[processingState]": "VALID", "limit": 20, "sort": "-uploadedDate"}).get("data", [])]
        if builds:
            b = builds[0]
            if b["attributes"].get("usesNonExemptEncryption") is None:
                send("PATCH", f"/builds/{b['id']}", {"data": {"type": "builds", "id": b["id"], "attributes": {"usesNonExemptEncryption": False}}})
            send("PATCH", f"/appStoreVersions/{vid}/relationships/build", rel("builds", b["id"]))
            print("BUILD_ESCOLHIDO", b["attributes"].get("version"))
    except Exception as e: print("ERRO_PASSO", repr(e)[:300])
    try:
        # 4) Textos da ficha (pt-BR)
        locs = get(f"/appStoreVersions/{vid}/appStoreVersionLocalizations").get("data", [])
        loc = [l for l in locs if l["attributes"]["locale"] == "pt-BR"][0]
        send("PATCH", f"/appStoreVersionLocalizations/{loc['id']}", {"data": {"type": "appStoreVersionLocalizations", "id": loc["id"], "attributes": {
            "description": F["description"], "keywords": F["keywords"], "promotionalText": F["promotionalText"],
            "supportUrl": F["supportUrl"], "marketingUrl": F["marketingUrl"]}}})
    except Exception as e: print("ERRO_PASSO", repr(e)[:300])
    try:
        # 5) Capturas de iPhone 6,9" (1320x2868)
        arquivos = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "capturas", "*.png")))
        if arquivos:
            sets = get(f"/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets").get("data", [])
            st = [s for s in sets if s["attributes"]["screenshotDisplayType"] == "APP_IPHONE_67"]
            if st:
                sid = st[0]["id"]
                for a in get(f"/appScreenshotSets/{sid}/appScreenshots").get("data", []):
                    r = S.delete(API + f"/appScreenshots/{a['id']}", headers=h()); print("APAGA_CAPTURA", r.status_code)
            else:
                sid = send("POST", "/appScreenshotSets", {"data": {"type": "appScreenshotSets", "attributes": {"screenshotDisplayType": "APP_IPHONE_67"},
                    "relationships": {"appStoreVersionLocalization": rel("appStoreVersionLocalizations", loc["id"])}}})["data"]["id"]
            for f in arquivos:
                dados = open(f, "rb").read()
                nome = os.path.basename(f)
                sc = send("POST", "/appScreenshots", {"data": {"type": "appScreenshots", "attributes": {"fileName": nome, "fileSize": len(dados)},
                    "relationships": {"appScreenshotSet": rel("appScreenshotSets", sid)}}})["data"]
                for op in sc["attributes"]["uploadOperations"]:
                    hd = {x["name"]: x["value"] for x in op.get("requestHeaders", [])}
                    r = requests.request(op["method"], op["url"], headers=hd, data=dados[op["offset"]:op["offset"] + op["length"]])
                    if r.status_code >= 300: print("ERRO UPLOAD", nome, r.status_code, r.text[:300])
                send("PATCH", f"/appScreenshots/{sc['id']}", {"data": {"type": "appScreenshots", "id": sc["id"], "attributes": {
                    "uploaded": True, "sourceFileChecksum": hashlib.md5(dados).hexdigest()}}})
                print("CAPTURA_ENVIADA", nome)
    except Exception as e: print("ERRO_PASSO", repr(e)[:300])
    try:
        # 6) Informacoes para a revisao (conta de demonstracao)
        att = dict(F["contato"]); att.update({"demoAccountRequired": True, "demoAccountName": os.environ.get("DEMO_EMAIL", ""),
            "demoAccountPassword": os.environ.get("DEMO_SENHA", ""), "notes": F["notas"]})
        if os.environ.get("CONTATO_TELEFONE"): att["contactPhone"] = os.environ["CONTATO_TELEFONE"]
        rd = get(f"/appStoreVersions/{vid}/appStoreReviewDetail").get("data")
        if rd: send("PATCH", f"/appStoreReviewDetails/{rd['id']}", {"data": {"type": "appStoreReviewDetails", "id": rd["id"], "attributes": att}})
        else: send("POST", "/appStoreReviewDetails", {"data": {"type": "appStoreReviewDetails", "attributes": att, "relationships": {"appStoreVersion": rel("appStoreVersions", vid)}}})
    except Exception as e: print("ERRO_PASSO", repr(e)[:300])
    try:
        # 7) Preco e disponibilidade (so leitura, para conferir)
        print("PRECO", json.dumps(get(f"/apps/{APP_ID}/appPriceSchedule", **{"include": "manualPrices,baseTerritory"}))[:1500])
        print("DISPONIBILIDADE", json.dumps(get(f"/apps/{APP_ID}/appAvailabilityV2"))[:800])
    except Exception as e: print("ERRO_PASSO", repr(e)[:300])
    print("FIM_PREENCHER")

if __name__ == "__main__":
    {"ler": ler, "preencher": preencher}.get(sys.argv[1] if len(sys.argv) > 1 else "ler", ler)()
