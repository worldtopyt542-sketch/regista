# ==== Buffer API (GraphQL): diagnosi della struttura e dei canali collegati ====
import json, os, sys
import requests

API = "https://api.buffer.com"


def gql(query, variabili=None):
    r = requests.post(API, json={"query": query, "variables": variabili or {}}, timeout=120,
                      headers={"Authorization": "Bearer " + os.environ["BUFFER_API_KEY"]})
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Buffer HTTP {r.status_code}: {r.text[:300]}")
    if j.get("errors"):
        raise RuntimeError("Buffer: " + json.dumps(j["errors"])[:600])
    return j["data"]


TIPO = "name kind ofType { name kind ofType { name kind ofType { name kind } } }"


def descrivi(nome):
    t = gql(f'{{ __type(name: "{nome}") {{ name kind inputFields {{ name type {{ {TIPO} }} }} '
            f'fields {{ name args {{ name type {{ {TIPO} }} }} type {{ {TIPO} }} }} enumValues {{ name }} possibleTypes {{ name }} }} }}')["__type"]
    return t


def nome_tipo(t):
    while t and not t.get("name"):
        t = t.get("ofType")
    return t.get("name") if t else None


def diagnosi():
    s = gql("{ __schema { queryType { name } mutationType { name } } }")["__schema"]
    visti, coda = set(), [s["queryType"]["name"], s["mutationType"]["name"]]
    interessanti = ("post", "channel", "asset", "upload", "organization", "account", "media", "video", "schedul")
    while coda:
        n = coda.pop(0)
        if not n or n in visti or n.startswith("__") or n in ("String", "Int", "Boolean", "ID", "Float"):
            continue
        visti.add(n)
        t = descrivi(n)
        if not t:
            continue
        righe = []
        for f in (t.get("fields") or []) + (t.get("inputFields") or []):
            tn = nome_tipo(f["type"])
            args = ", ".join(f"{a['name']}:{nome_tipo(a['type'])}" for a in f.get("args") or [])
            righe.append(f"  {f['name']}({args}) -> {tn}")
            if n in (s["queryType"]["name"], s["mutationType"]["name"]) and not any(k in f["name"].lower() for k in interessanti):
                continue
            coda.append(tn)
            coda += [nome_tipo(a["type"]) for a in f.get("args") or []]
        if t.get("enumValues"):
            righe.append("  enum: " + ", ".join(e["name"] for e in t["enumValues"]))
        print(f"{t['kind']} {n}\n" + "\n".join(righe))
        if len(visti) > 60:
            break


CREA = """mutation($i: CreatePostInput!) { createPost(input: $i) { __typename
  ... on PostActionSuccess { post { id status externalLink } }
  ... on LimitReachedError { message } ... on InvalidInputError { message } } }"""


def metadati(servizio, titolo):
    if servizio == "youtube":
        return {"youtube": {"title": titolo[:100], "privacy": "public", "type": "short", "categoryId": "20",
                            "madeForKids": False, "notifySubscribers": True}}
    if servizio == "instagram":
        return {"instagram": {"type": "reel", "shouldShareToFeed": True}}
    if servizio == "tiktok":
        return {"tiktok": {"title": titolo[:90]}}
    return {}


def pubblica(url_video, titolo, testo, servizi=("tiktok", "instagram", "youtube"), ammessi=None):
    """Pubblica subito il video (link pubblico) sui canali Buffer dei servizi scelti.
    ammessi: lista di id canale (una lingua = le sue pagine); None = tutti i canali."""
    esiti = []
    for c in canali():
        if c["service"] not in servizi or c["isDisconnected"]:
            continue
        if ammessi is not None and c["id"] not in ammessi:
            continue
        inp = {"channelId": c["id"], "text": testo, "mode": "shareNow", "schedulingType": "automatic",
               "assets": [{"video": {"url": url_video, "metadata": {"title": titolo[:100]}}}],
               "metadata": metadati(c["service"], titolo)}
        try:
            r = gql(CREA, {"i": inp})["createPost"]
            if r["__typename"] == "PostActionSuccess":
                esiti.append({"servizio": c["service"], "ok": True, "id": r["post"]["id"]})
            else:
                esiti.append({"servizio": c["service"], "ok": False, "errore": f"{r['__typename']}: {r.get('message', '')}"})
        except Exception as e:
            esiti.append({"servizio": c["service"], "ok": False, "errore": str(e)[:200]})
    if not esiti:
        raise RuntimeError("nessun canale Buffer collegato")
    return esiti


def visualizzazioni(post_ids):
    """Somma delle views dei post Buffer (se l'API le espone)."""
    tot = 0
    for pid in post_ids:
        try:
            m = gql("query($i: PostInput!){ post(input: $i) { metrics { type value } } }", {"i": {"id": pid}})
            tot += sum(x["value"] or 0 for x in (m["post"].get("metrics") or []) if x["type"] == "views")
        except Exception:
            pass
    return int(tot)


def mostra(nomi):
    for n in nomi:
        t = descrivi(n)
        if not t:
            print("?", n); continue
        print(t["kind"], n)
        for f in (t.get("fields") or []) + (t.get("inputFields") or []):
            print(f"  {f['name']} -> {nome_tipo(f['type'])} ({f['type']['kind']})")
        if t.get("enumValues"):
            print("  enum:", ", ".join(e["name"] for e in t["enumValues"]))
        if t.get("possibleTypes"):
            print("  union:", ", ".join(e["name"] for e in t["possibleTypes"]))


def canali():
    org = gql("{ account { organizations { id name } } }")["account"]["organizations"]
    out = []
    for o in org:
        for c in gql("query($i: ChannelsInput!){ channels(input: $i) { id name service isDisconnected } }",
                     {"i": {"organizationId": o["id"]}})["channels"]:
            out.append({**c, "org": o["id"]})
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1:
        mostra(sys.argv[1:])
        print("CANALI (copia gli id in config.json -> pubblica.canali -> lingua):")
        for c in canali():
            print(f"  {c['id']}  {c['service']:<10} {c['name']}{'  (scollegato)' if c['isDisconnected'] else ''}")
    else:
        diagnosi()
