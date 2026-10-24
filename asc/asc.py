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

if __name__ == "__main__":
    {"ler": ler}.get(sys.argv[1] if len(sys.argv) > 1 else "ler", ler)()
