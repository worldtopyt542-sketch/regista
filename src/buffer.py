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
        print("CANALI:", json.dumps([{k: c[k] for k in ("name", "service", "isDisconnected")} for c in canali()]))
    else:
        diagnosi()
