"""Cruza os leads da planilha (período) com as conversas do Chatwoot (somente GET) e salva as transcrições.

Uso: python extract_cw.py <pasta_saida> [AAAA-MM-DD inicio] [AAAA-MM-DD fim] [id_cliente ...]
Só entram leads que estão na planilha do cliente; conversas sem lead na planilha são ignoradas.
"""
import concurrent.futures as cf
import datetime
import json
import os
import re
import sys
import time

import requests

import metrics as M
from clients import CLIENTS

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
REPO = os.path.dirname(os.path.abspath(__file__))
env = {}
for line in open(os.path.join(REPO, ".env"), encoding="utf-8"):
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip().lstrip("﻿")] = v.strip()
BASE = env["CHATWOOT_BASE"]
H = {"access-token": env["CHATWOOT_ACCESS_TOKEN"], "client": env["CHATWOOT_CLIENT"], "uid": env["CHATWOOT_UID"],
     "token-type": env.get("CHATWOOT_TOKEN_TYPE", "Bearer")}
S = requests.Session()


def get(path, **params):
    for attempt in range(5):
        try:
            r = S.get(f"{BASE}/api/v1/accounts/1/{path}", headers=H, params=params, timeout=40)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return None


def list_convs(inbox, since_ts):
    out, page = [], 1
    while page <= 80:
        j = get("conversations", inbox_id=inbox, status="all", page=page)
        pl = ((j or {}).get("data") or {}).get("payload") or []
        if not pl:
            break
        out += pl
        if min(c.get("last_activity_at") or 0 for c in pl) < since_ts or len(pl) < 25:
            break
        page += 1
    return out


def messages(cid):
    msgs, before = [], None
    for _ in range(40):
        j = get(f"conversations/{cid}/messages", **({"before": before} if before else {}))
        pl = (j or {}).get("payload") or []
        if not pl:
            break
        msgs = pl + msgs
        nb = min(m["id"] for m in pl)
        if nb == before or len(pl) < 20:
            break
        before = nb
    return msgs


def compact(msgs):
    out = []
    for m in msgs:
        t = m.get("message_type")
        if t == 2 or m.get("private"):
            continue
        txt = re.sub(r"\s+", " ", m.get("content") or "").strip()
        if not txt:
            att = m.get("attachments") or []
            txt = f"[{att[0].get('file_type', 'anexo')}]" if att else ""
        if not txt:
            continue
        out.append({"w": "L" if t == 0 else "E", "t": m.get("created_at"), "x": txt[:400]})
    return out


def features(tr, now_ts):
    ins = [m for m in tr if m["w"] == "L"]
    outs = [m for m in tr if m["w"] == "E"]
    f = {"n_lead": len(ins), "n_equipe": len(outs)}
    if ins:
        t0 = ins[0]["t"]
        first_out = next((m["t"] for m in outs if m["t"] >= t0), None)
        f["resp_h"] = round((first_out - t0) / 3600, 1) if first_out else None
        after = [m for m in ins if first_out and m["t"] > first_out]
        f["lead_respondeu"] = len(after) >= 1
        f["lead_engajou"] = len(after) >= 2
    else:
        f["resp_h"], f["lead_respondeu"], f["lead_engajou"] = None, False, False
    if tr:
        f["ultimo"] = tr[-1]["w"]
        f["horas_desde_ultimo"] = round((now_ts - tr[-1]["t"]) / 3600, 1)
    return f


def run_client(cid, name, inboxes, sheet_id, start, end, outdir):
    csv_text = M.fetch_csv(sheet_id)
    leads = [l for l in M.parse_leads(csv_text) if start <= l["data"] <= end]
    res = {"id": cid, "nome": name, "periodo": [str(start), str(end)], "inboxes": inboxes, "leads": []}
    if not leads:
        json.dump(res, open(os.path.join(outdir, cid + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
        return cid, 0, 0
    by_suffix, by_name = {}, {}
    since = int(datetime.datetime.combine(start - datetime.timedelta(days=3), datetime.time()).timestamp())
    for ib in inboxes:
        for c in list_convs(ib, since):
            s = (c.get("meta") or {}).get("sender") or {}
            ph = re.sub(r"\D", "", s.get("phone_number") or "")
            if len(ph) >= 8:
                by_suffix.setdefault(ph[-8:], c)
            nm = re.sub(r"[^\w\s]", "", s.get("name") or "").strip().lower()
            if len(nm) > 3:
                by_name.setdefault(nm, c)
    now_ts = int(time.time())
    matched = 0
    for l in leads:
        nm = re.sub(r"[^\w\s]", "", l["nome"]).strip().lower()
        c = by_suffix.get(l["key"]) or (by_name.get(nm) if len(nm) > 3 else None)
        rec = {k: (str(v) if k == "data" else v) for k, v in l.items()}
        if c:
            matched += 1
            tr = compact(messages(c["id"]))
            rec.update({"conv_id": c["id"], "inbox": c.get("inbox_id"), "status_cw": c.get("status"),
                        "labels": c.get("labels"), "agente": ((c.get("meta") or {}).get("assignee") or {}).get("name"),
                        "transcript": tr, "feat": features(tr, now_ts)})
        res["leads"].append(rec)
    json.dump(res, open(os.path.join(outdir, cid + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    return cid, len(leads), matched


if __name__ == "__main__":
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    start = datetime.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else datetime.date(2026, 10, 1)
    end = datetime.date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else datetime.date.today()
    only = set(sys.argv[4:])
    todo = [c for c in CLIENTS if (not only or c[0] in only) and c[3]]
    with cf.ThreadPoolExecutor(4) as ex:
        futs = [ex.submit(run_client, cid, n, ib, sid, start, end, outdir) for cid, n, _s, ib, sid in todo]
        for f in cf.as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # um cliente com falha não derruba os demais
                print("ERRO", e, flush=True)
