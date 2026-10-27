"""Sincroniza o painel: planilha CRM (fonte dos leads) + Chatwoot (só conversas dos leads da planilha).

Regras (ver metrics.py): lead = telefone único da planilha; taxas ag/leads, comp/ag, vendas/comp.
Agendamentos = marcados na planilha + confirmados na conversa (verified.json, gerado pela análise comercial).
Cache local de features por conversa (cache/) evita rebaixar mensagens que não mudaram.
"""
import concurrent.futures as cf
import datetime
import json
import os
import re
import subprocess
import sys
import time

import requests

import extract_cw as X
import metrics as M
from clients import CLIENTS

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(REPO_DIR, "sync_daily.log")
CACHE_DIR = os.path.join(REPO_DIR, "cache")
VERIFIED_PATH = os.path.join(REPO_DIR, "verified.json")
ANALYSIS_PATH = os.path.join(REPO_DIR, "analysis.json")
os.makedirs(CACHE_DIR, exist_ok=True)

MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
         "Novembro", "Dezembro"]


def log_msg(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# --- Evolution: status de conexão do WhatsApp ---------------------------------------------------
evo_live = {}
try:
    ev_base = X.env.get("EVOLUTION_BASE", "https://evo.mesusmedia.com.br")
    r = requests.get(f"{ev_base}/instance/fetchInstances", headers={"apikey": X.env.get("EVOLUTION_API_KEY", "")}, timeout=10)
    if r.status_code == 200:
        for inst in r.json():
            nm = (inst.get("name") or inst.get("instance", {}).get("instanceName") or "").strip().lower()
            st = (inst.get("connectionStatus") or inst.get("instance", {}).get("status") or inst.get("status") or "").strip().lower()
            if nm:
                evo_live[nm] = st
        log_msg(f"Evolution: {len(evo_live)} instâncias.")
except Exception as e:
    log_msg(f"Aviso Evolution: {e}")

EVO_ALIASES = {"c123-orgulhodesorrirsantos": "c123-orgulhosantos", "c123-orgulhosantos": "c123-orgulhosantos",
               "c123-orgulhosv": "c123-orgulhosaovicente"}


def evo_status(cid):
    key = EVO_ALIASES.get(cid.lower(), cid.lower())
    if key in evo_live:
        return evo_live[key]
    for k, v in evo_live.items():
        if key in k or k in key:
            return v
    return None


# --- Períodos ------------------------------------------------------------------------------------
# A planilha grava Data/Hora em UTC; "hoje" e os meses seguem a data da planilha
TODAY = datetime.datetime.utcnow().date()
TODAY_BRT = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).date()
CUR = (TODAY.year, TODAY.month)
PREV = M.prev_month(*CUR)
PREV2 = M.prev_month(*PREV)


def mkey(ym):
    return f"{ym[0]}-{ym[1]:02d}"


MONTHS = [CUR, PREV, PREV2]  # PREV2 só alimenta a coluna "mês anterior" (sem atendimento)
CW_MONTHS = [CUR, PREV]
CW_FROM = datetime.date(PREV[0], PREV[1], 1)  # janela de análise de conversas
VERIFIED = {}
if os.path.exists(VERIFIED_PATH):
    VERIFIED = json.load(open(VERIFIED_PATH, encoding="utf-8"))


def month_label(ym):
    s, e = M.month_range(ym[0], ym[1], TODAY)
    part = f"01 a {e.day:02d}/{e.month:02d}" if e < M.month_range(ym[0], ym[1])[1] else "mês fechado"
    return {"k": mkey(ym), "label": f"{MESES[ym[1]]}/{str(ym[0])[2:]}", "range": part, "hidden": ym not in CW_MONTHS}


# --- Cache de features por conversa --------------------------------------------------------------
def load_cache(cid):
    p = os.path.join(CACHE_DIR, cid + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def save_cache(cid, cache):
    json.dump(cache, open(os.path.join(CACHE_DIR, cid + ".json"), "w", encoding="utf-8"), ensure_ascii=False)


def conv_features(cache, conv):
    cid = str(conv["id"])
    la = conv.get("last_activity_at") or 0
    hit = cache.get(cid)
    if hit and hit.get("la") == la:
        return hit
    tr = X.compact(X.messages(conv["id"]))
    lead_msgs = [m for m in tr if m["w"] == "L"]
    f = X.features(tr, int(time.time()))
    rec = {"la": la, "feat": f, "first_in": lead_msgs[0]["t"] if lead_msgs else None,
           "last_lead": (lead_msgs[-1]["x"][:60] if lead_msgs else "")}
    cache[cid] = rec
    return rec


# --- Avaliação do atendimento (leads da planilha x conversas) -------------------------------------
def cw_eval(leads, convs_by_lead, cache, has_inbox, discon):
    out = {"cw_leads": len(leads), "cw_resp": 0, "cw_unresp": 0, "cw_pct_resp": 0.0, "cw_alerts": 0,
           "cw_avg_resp_h": 0.0, "cw_status": "", "unresp_leads": []}
    if not leads:
        out["cw_status"] = "Desconectado" if discon else "Sem Entrada"
        return out
    if not has_inbox:
        out["cw_status"] = "Sem Chatwoot"
        out["cw_leads"] = len(leads)
        return out
    times = []
    now = datetime.datetime.now()
    for l in leads:
        conv = convs_by_lead.get(l["key"] or l["nome"])
        concluded = l["ag"] or l["comp"] or l["venda"]
        created = datetime.datetime.combine(l["data"], datetime.time(12, 0))
        ctx = ""
        link = ""
        if conv:
            rec = conv_features(cache, conv)
            f = rec["feat"]
            link = f"{X.BASE}/app/accounts/1/conversations/{conv['id']}"
            if rec.get("first_in"):
                created = datetime.datetime.fromtimestamp(rec["first_in"])
            answered = f.get("resp_h") is not None or (f.get("n_lead", 0) == 0 and f.get("n_equipe", 0) > 0)
            if answered and f.get("resp_h") is not None and 0 <= f["resp_h"] <= 168:
                times.append(f["resp_h"])
            ok = answered or concluded
            if not ok:
                ctx = f"Lead enviou {f.get('n_lead', 0)} mensagem(ns) sem retorno da equipe"
                if rec.get("last_lead"):
                    ctx += f": '{rec['last_lead']}'"
        else:
            ok = concluded
            ctx = "Conversa não localizada no Chatwoot"
        if ok:
            out["cw_resp"] += 1
        else:
            out["cw_unresp"] += 1
            wait = round((now - created).total_seconds() / 3600, 1)
            alert = wait > 24
            out["cw_alerts"] += alert
            out["unresp_leads"].append({
                "name": l["nome"], "phone": l["phone"] or "—", "data": l["data"].strftime("%d/%m/%Y"),
                "espera_h": wait, "is_alert": alert, "contexto": ctx, "link": link or (f"https://wa.me/{l['phone']}" if l["phone"] else "")})
    n = len(leads)
    out["cw_pct_resp"] = M.pct(out["cw_resp"], n)
    out["cw_avg_resp_h"] = round(sum(times) / len(times), 1) if times else 0.0
    out["unresp_leads"].sort(key=lambda u: -u["espera_h"])
    out["unresp_leads"] = out["unresp_leads"][:60]
    if discon:
        st = "Desconectado"
    elif out["cw_pct_resp"] < 75 or (out["cw_avg_resp_h"] > 48 and n > 5):
        st = "Gargalo"
    elif out["cw_pct_resp"] < 90 or out["cw_avg_resp_h"] > 24:
        st = "Atenção"
    else:
        st = "Saudável"
    out["cw_status"] = st
    return out


def funnel(leads):
    n = len(leads)
    ag, cp, vd = sum(l["ag"] for l in leads), sum(l["comp"] for l in leads), sum(l["venda"] for l in leads)
    return {"leads": n, "agendados": ag, "tx_agend": M.pct(ag, n), "comp": cp, "tx_comp": M.pct(cp, ag),
            "vendas": vd, "tx_venda": M.pct(vd, cp), "aberto": sum(l["aberto"] for l in leads)}


PDFS = {}
_pm = os.path.join(REPO_DIR, "pdfs", "manifest.json")
if os.path.exists(_pm):
    PDFS = json.load(open(_pm, encoding="utf-8"))


def process_client(c):
    cid, name, seg, inboxes, sid = c
    st = evo_status(cid)
    discon = st in ("close", "closed", "connecting")
    leads = []
    for attempt in range(3):
        try:
            leads = M.parse_leads(M.fetch_csv(sid))
            break
        except Exception as e:
            log_msg(f"Aviso planilha {name} ({attempt + 1}/3): {e}")
            time.sleep(2)
    ver = set(VERIFIED.get(cid, {}).get("ag", []))
    for l in leads:
        if l["key"] in ver and l["data"] >= datetime.date(2026, 10, 1):
            l["ag"] = True

    convs_by_lead, cache = {}, {}
    window = [l for l in leads if l["data"] >= CW_FROM]
    if inboxes and window:
        cache = load_cache(cid)
        by_suffix, by_name = {}, {}
        since = int(datetime.datetime.combine(CW_FROM - datetime.timedelta(days=3), datetime.time()).timestamp())
        for ib in inboxes:
            for cv in X.list_convs(ib, since):
                s = (cv.get("meta") or {}).get("sender") or {}
                ph = re.sub(r"\D", "", s.get("phone_number") or "")
                if len(ph) >= 8:
                    by_suffix.setdefault(ph[-8:], cv)
                nm = re.sub(r"[^\w\s]", "", s.get("name") or "").strip().lower()
                if len(nm) > 3:
                    by_name.setdefault(nm, cv)
        for l in window:
            nm = re.sub(r"[^\w\s]", "", l["nome"]).strip().lower()
            cv = by_suffix.get(l["key"]) or (by_name.get(nm) if len(nm) > 3 else None)
            if cv:
                convs_by_lead[l["key"] or l["nome"]] = cv

    P = {}
    for ym in MONTHS:
        s, e = M.month_range(ym[0], ym[1], TODAY)
        sel = [l for l in leads if s <= l["data"] <= e]
        P[mkey(ym)] = {**funnel(sel), **(cw_eval(sel, convs_by_lead, cache, bool(inboxes), discon) if ym in CW_MONTHS else {})}
    hoje = [l for l in leads if l["data"] == TODAY]
    P["hoje"] = {**funnel(hoje), **cw_eval(hoje, convs_by_lead, cache, bool(inboxes), discon)}
    win = [l for l in leads if l["data"] >= CW_FROM]
    P["all"] = {**funnel(leads), **cw_eval(win, convs_by_lead, cache, bool(inboxes), discon)}
    if cache:
        save_cache(cid, cache)

    cur = P[mkey(CUR)]
    last = max((l["data"] for l in leads), default=None)
    alta = P["hoje"]["leads"] > 0 or cur["leads"] > 10
    return {
        "id": cid, "name": name, "seg": seg, "inbox_id": inboxes[0] if inboxes else None,
        "is_discon": discon, "evo_status": st or ("close" if discon else "open"),
        "P": P, "total": len(leads), "ult": last.strftime("%d/%m/%Y") if last else "—",
        "status": "descon" if discon else ("alta" if alta else ("mod" if cur["leads"] > 0 else "pausado")),
        "statusText": "🔴 WhatsApp Off" if discon else ("🟢 Alta Tração" if alta else ("🟡 Moderado" if cur["leads"] > 0 else "⚪ Sem Leads")),
        "pdf_url": PDFS.get(cid, ""),
    }




def sync():
    log_msg("Iniciando varredura: planilhas CRM + Chatwoot (somente leads da planilha)...")
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        compiled = list(ex.map(process_client, CLIENTS))
    mk = mkey(CUR)
    compiled.sort(key=lambda r: (r["P"][mk]["leads"], r["P"]["hoje"]["leads"]), reverse=True)
    tot = sum(r["P"][mk]["leads"] for r in compiled)
    log_msg(f"Leads {mk}: {tot} | agendados {sum(r['P'][mk]['agendados'] for r in compiled)} | "
            f"comp {sum(r['P'][mk]['comp'] for r in compiled)} | vendas {sum(r['P'][mk]['vendas'] for r in compiled)}")

    meta = {"months": [month_label(ym) for ym in MONTHS], "today": TODAY_BRT.isoformat(),
            "updated": datetime.datetime.now().strftime("%d/%m/%Y às %H:%M")}
    index_path = os.path.join(REPO_DIR, "index.html")
    html = open(index_path, "r", encoding="utf-8").read()
    html = re.sub(r"/\*DATA\*/.*?/\*END\*/", lambda _: "/*DATA*/const DATA = " + json.dumps(compiled, ensure_ascii=False) + ";/*END*/", html, count=1, flags=re.S)
    html = re.sub(r"/\*META\*/.*?/\*END\*/", lambda _: "/*META*/const META = " + json.dumps(meta, ensure_ascii=False) + ";/*END*/", html, count=1, flags=re.S)
    if os.path.exists(ANALYSIS_PATH):
        html = re.sub(r"/\*ANALYSIS\*/.*?/\*END\*/", lambda _: "/*ANALYSIS*/const ANALYSIS = " + open(ANALYSIS_PATH, encoding="utf-8").read().strip() + ";/*END*/", html, count=1, flags=re.S)
    open(index_path, "w", encoding="utf-8").write(html)
    log_msg("index.html atualizado.")

    if "--no-push" in sys.argv:
        return
    try:
        subprocess.run(["git", "add", "index.html", "sync_daily.py", "metrics.py", "clients.py", "extract_cw.py", "verified.json", "analysis.json", "pdfs/"], cwd=REPO_DIR, check=False)
        msg = f"chore: sync painel ({datetime.datetime.now():%d/%m/%Y %H:%M})"
        subprocess.run(["git", "commit", "-m", msg], cwd=REPO_DIR, check=False)
        subprocess.run(["git", "-c", "credential.helper=manager", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        log_msg("Push executado; deploy no Vercel iniciado.")
    except Exception as e:
        log_msg(f"Aviso git push: {e}")


if __name__ == "__main__":
    sync()
