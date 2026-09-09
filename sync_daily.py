import os
import sys
import json
import re
import datetime
import subprocess
from concurrent.futures import ThreadPoolExecutor
import requests

if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

REPO_DIR = r"C:\Users\oluca\painel-executivo-comercial"
ENV_PATH = os.path.join(REPO_DIR, ".env")
LOG_FILE = os.path.join(REPO_DIR, "sync_daily.log")

def log_msg(msg):
    ts = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    if sys.stdout is not None:
        try:
            print(line, flush=True)
        except Exception:
            pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# 1. Load Environment Variables safely from local .env
env = {}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip().lstrip('\ufeff')] = v.strip()

CHATWOOT_BASE = env.get("CHATWOOT_BASE", "https://apps-chatwoot.r0ym2n.easypanel.host")
HEADERS_CW = {
    "access-token": env.get("CHATWOOT_ACCESS_TOKEN", ""),
    "client": env.get("CHATWOOT_CLIENT", ""),
    "uid": env.get("CHATWOOT_UID", ""),
    "token-type": env.get("CHATWOOT_TOKEN_TYPE", "Bearer")
}

# Master Clients Directory with Chatwoot Inboxes and CRM Sheet IDs
CLIENTS = [
    { "id": "C162-DrBrunoAraujo", "name": "Dr. Bruno Araújo", "seg": "Saúde", "inbox_id": 103, "sheet_id": "1Vc5IT497LN25AUD8ckoH7CkXJ-72O7ypn8ZxuoAUELg" },
    { "id": "C158-VictorianoFaces", "name": "Victoriano Faces", "seg": "Estética", "inbox_id": 124, "sheet_id": "12dTGJBLDOdxxPAX0WJJR7R6Zhu_NtZ9xX19VsUvdK8A" },
    { "id": "C172-DrCaioFigueira", "name": "Dr. Caio Figueira", "seg": "Saúde", "inbox_id": 134, "sheet_id": "1biD55AqQuFQZJlSnUyGvrg3DwKWD-8fLSl5bt2fJiEM" },
    { "id": "C169-DrKeeynerCorrea", "name": "Dr. Keeyner Correa", "seg": "Saúde", "inbox_id": 133, "sheet_id": "1SmdVcj_MQBpRJXNai8xM9yXW9coOquQEG8HxjDlLbeE" },
    { "id": "C123-OrgulhoSaoVicente", "name": "Orgulho São Vicente", "seg": "Odonto", "inbox_id": 116, "sheet_id": "1-Xp3qunysH4vw8jrU8wWW0g8eTzLK2pt4jmoSxMDId0" },
    { "id": "C174-EsteticFaceItapetininga", "name": "Estetic Face Itapetininga", "seg": "Estética", "inbox_id": 139, "sheet_id": "18V8FQD8Q5lVSoioIkDjnUKYFqminsQWgIWbuc8ImW9E" },
    { "id": "C123-DrRafaelRocha", "name": "Dr. Rafael Rocha", "seg": "Saúde", "inbox_id": 121, "sheet_id": "1iX55z4aFf7CIzLHD0OVGdZCeCWrMfgK-hE_3LLAkfko" },
    { "id": "C123-OrgulhodeSorrirPeruibe", "name": "Orgulho de Sorrir Peruíbe", "seg": "Odonto", "inbox_id": 115, "sheet_id": "17_CS-0I470XfX5sQMLAd0jdQJxng4gFCBkO1eaQx8qA" },
    { "id": "C150-Lumia", "name": "Lumia", "seg": "Estética", "inbox_id": 137, "sheet_id": "1fVoRc627ZhHEBKFIGuGvvtiMDBrO_2D3Wp2mWZlH3Go" },
    { "id": "C171-DraStefaniRezende", "name": "Dra. Stefani Rezende", "seg": "Saúde", "inbox_id": 135, "sheet_id": "16A--MHKp8IBoZKHGQD21LFN-7WUVL2m_BcZmu0UdEXg" },
    { "id": "C163-AcessoSaudeCIC", "name": "Acesso Saúde CIC", "seg": "Saúde", "inbox_id": 105, "sheet_id": "1SuyRNdYrGZXtBFmB0-Hv91ZICa7geeFHx6Ayiz7jU08" },
    { "id": "C149-ClinicaGGlow", "name": "Clínica Glow", "seg": "Estética", "inbox_id": 82, "sheet_id": "1zOwuPWh_g2fLHyfmBfHl1RIPYznzGdf7yGidGnq9qN0" },
    { "id": "C52-DrLucasPitao", "name": "Dr. Lucas Pitão", "seg": "Saúde", "inbox_id": 47, "sheet_id": "1ssM8yBQsSpby-y7FXqs8NmWAAjzsfigxhR4P4J7mfys" },
    { "id": "C135-DraMichelleSantos", "name": "Dra. Michelle Santos", "seg": "Saúde", "inbox_id": 25, "sheet_id": "1pQpLfdt9gCHoRekLRpqFk9pwW2V51ksCN_NTJd1G_zY" },
    { "id": "C170-DraMariaEduarda", "name": "Dra. Maria Eduarda", "seg": "Saúde", "inbox_id": 136, "sheet_id": "1eHv46erWBLB3w8zg5xP5oN_TWftJ6ELgJZzOlYVVbOY" },
    { "id": "C173-OdontoPrime", "name": "Odonto Prime", "seg": "Odonto", "inbox_id": 138, "sheet_id": "1wGjMuOTYoIwu9F2wI8atQQaMeLy3iMqaW4gOx2nqM-k" },
    { "id": "C63-DrRaphaelMoreira", "name": "Dr. Raphael Moreira", "seg": "Saúde", "inbox_id": 23, "sheet_id": "1hnJ7rl0Hcy2GcWdh3nMN7s9nhBCtahKsHYiQglAF_JE" },
    { "id": "C123-OrgulhodeSorrirSantos", "name": "Orgulho de Sorrir Santos", "seg": "Odonto", "inbox_id": 140, "sheet_id": "1bWYYqtG_2TZ3Zs0r5wkvadSI8gEMAug-9nZUp-jxYuc" },
    { "id": "C124-DraAnnaHOF", "name": "Dra. Anna HOF", "seg": "Saúde", "inbox_id": 77, "sheet_id": "1N2oAsy3PJud__z9MBSFrX9wr1AVfw_b-X-YpgDHIdkQ" },
    { "id": "C155-ClinicaElodonto", "name": "Clínica Elodonto", "seg": "Odonto", "inbox_id": 122, "sheet_id": "17eesV8xZKnisx9pJo11RndZOcKDwIT6zet8dBfHrPlM" },
    { "id": "C166-Lucasmallmann", "name": "Lucas Mallmann", "seg": "Saúde", "inbox_id": 126, "sheet_id": "1t4KLQdv9bjYcftwMw81rn-WvMs0NW92omQLWR_MkiF4" },
    { "id": "C136-IntegrareOdontologia", "name": "Integrar Odontologia", "seg": "Odonto", "inbox_id": 119, "sheet_id": "1TEuyWftgK9iM2rINKEeg-xTAZGVFxibmWZpokn6XCEc", "disconnected": True },
    { "id": "C157-DraCristianeTiburtino", "name": "Dra. Cristiane Tiburtino", "seg": "Saúde", "inbox_id": 114, "sheet_id": "1bM8T1h-gAZdbOgjWQqkFoJPU_vODLI-ObIt9OtTLGic", "disconnected": True },
    { "id": "EsteticaLosAngelesLeads", "name": "Estética Los Angeles", "seg": "Estética", "inbox_id": 108, "sheet_id": "1zBcRC0HaV4JXg1Cix-XBl6cZzQ6044oFMhM3NlTZn7E", "disconnected": True },
    { "id": "C86-DrWilliamHenrique", "name": "Dr. William Henrique", "seg": "Saúde", "inbox_id": 125, "sheet_id": "14Ss2564FyP_SJeXxTI8OI-5n0tRMlchsJJYFJrxRrxY", "disconnected": True },
    { "id": "C168-DraMichelleAlves", "name": "Dra. Michelle Alves", "seg": "Saúde", "inbox_id": 130, "sheet_id": "1VMbs_ElKqEs0l_OmEgf354Xo4nW5b7IexbpUki_Wtw0" },
    { "id": "C164-DraLea", "name": "Dra. Léa", "seg": "Saúde", "inbox_id": 111, "sheet_id": "1hQu7EiDa6hI0Wr7WVdcSBNg2eiaLucOw6P_mDgNkd0Y" },
    { "id": "C140-EspacoBottega", "name": "Espaço Bottega", "seg": "Estética", "inbox_id": 100, "sheet_id": "1AAcB8qjEf-NDM36lPTCOuUst7tsACIvfNe4QgsJf_yM" },
    { "id": "C167-AvanteOdontologiaBH", "name": "Avante Odontologia BH", "seg": "Odonto", "inbox_id": 128, "sheet_id": "17axePFMIWOUQ3kGJ308w4kptO6PZt_mY9XwjifqozrY" },
    { "id": "C167-AvanteOdontologiaSL", "name": "Avante Odontologia SL", "seg": "Odonto", "inbox_id": 129, "sheet_id": "1i5nQbdPOPLIQgUjibXCVZwd4JNuLo_AiKsqWEYNBx8k" },
    { "id": "C141-VictorRios", "name": "Victor Rios", "seg": "Saúde", "inbox_id": 112, "sheet_id": "1NQlACxzoHdcjBpH7B2_WDpiMc6uAnznEtiMWHMopHjo" },
    { "id": "C175-VivazOdontologia", "name": "Vivaz Odontologia", "seg": "Odonto", "inbox_id": 141, "sheet_id": "1LWOtVjWsaX_tkV1TG8ibN765WbRuNTablOxhwPSyKoc" }
]

def parse_sheet_date(d_str):
    if not d_str:
        return None
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', str(d_str))
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except Exception:
            pass
    return None

def process_client(client):
    cid = client["id"]
    name = client["name"]
    sid = client.get("sheet_id")
    ib_id = client.get("inbox_id")
    is_discon = client.get("disconnected", False)

    # 1. Fetch CRM Sheet (Single Source of Truth)
    sept_leads = []
    total_leads = 0
    today_leads = 0
    ago_leads = 0
    agendados = 0
    compareceram = 0
    vendas = 0
    latest_date = None

    if sid:
        url_sheet = f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:json&gid=1048674045"
        try:
            r = requests.get(url_sheet, timeout=12)
            raw = r.text.replace("/*O_o*/\n", "").replace("google.visualization.Query.setResponse(", "")
            if raw.endswith(");"):
                raw = raw[:-2]
            elif raw.endswith(")"):
                raw = raw[:-1]
            data = json.loads(raw)

            cols = [col.get("label") or "" for col in data.get("table", {}).get("cols", [])]
            idx_data = 0
            idx_hora = 1
            idx_nome = 2
            idx_num = 3
            idx_agend = None
            idx_comp = None
            idx_ganh = None

            for i, col in enumerate(cols):
                cl = col.lower().strip()
                if cl == "data":
                    idx_data = i
                elif cl == "hora":
                    idx_hora = i
                elif cl == "nome":
                    idx_nome = i
                elif cl in ["número", "numero", "telefone"]:
                    idx_num = i
                elif "agend" in cl and idx_agend is None:
                    idx_agend = i
                elif "comp" in cl and idx_comp is None:
                    idx_comp = i
                elif ("ganh" in cl or "vend" in cl or "data ganho" in cl) and idx_ganh is None:
                    idx_ganh = i

            rows = data.get("table", {}).get("rows", [])
            total_leads = len(rows)
            now = datetime.date.today()

            for row in rows:
                cells = row.get("c", [])
                def get_v(idx):
                    if idx is not None and idx < len(cells) and cells[idx]:
                        return str(cells[idx].get("f") or cells[idx].get("v") or "").strip()
                    return ""

                d_raw = get_v(idx_data)
                d = parse_sheet_date(d_raw)
                if not d:
                    continue

                if not latest_date or d > latest_date:
                    latest_date = d

                ag_val = get_v(idx_agend).lower()
                cp_val = get_v(idx_comp).lower()
                gh_val = get_v(idx_ganh).lower()

                if "agendad" in ag_val or (ag_val and ag_val not in ["não agendado", "nao agendado", "não", "nao", "0", "false", "em atendimento", "n/a"]):
                    agendados += 1
                if "compareceu" in cp_val or "sim" in cp_val:
                    compareceram += 1
                if "ganh" in gh_val or "sim" in gh_val or (idx_ganh and "data" in cols[idx_ganh].lower() and gh_val):
                    vendas += 1

                if d.year == now.year and d.month == now.month:
                    n_raw = get_v(idx_nome)
                    p_raw = get_v(idx_num)
                    h_raw = get_v(idx_hora)
                    sept_leads.append({
                        "data": d.strftime("%d/%m/%Y"),
                        "data_obj": d,
                        "hora": h_raw,
                        "nome": n_raw if n_raw else "Lead sem nome",
                        "clean_nome": re.sub(r'[^\w\s]', '', n_raw).strip().lower(),
                        "phone": p_raw,
                        "clean_phone": re.sub(r'\D', '', p_raw)
                    })
                    if d == now:
                        today_leads += 1
                elif d.year == now.year and d.month == (now.month - 1):
                    ago_leads += 1
        except Exception as e:
            log_msg(f"Aviso ao ler planilha {name}: {e}")

    # 2. Fetch Chatwoot Conversations for inbox (Index by phone suffix & name)
    cw_by_suffix = {}
    cw_by_name = {}

    if ib_id and not is_discon and sept_leads:
        page = 1
        has_more = True
        sept_start = datetime.datetime(2026, 9, 1, 0, 0, 0)
        while has_more and page <= 8:
            url_cw = f"{CHATWOOT_BASE}/api/v1/accounts/1/conversations?inbox_id={ib_id}&status=all&page={page}"
            try:
                r = requests.get(url_cw, headers=HEADERS_CW, timeout=12)
                if r.status_code != 200:
                    break
                payload = r.json().get("data", {}).get("payload", [])
                if not payload:
                    break
                for cv in payload:
                    c_at = cv.get("created_at")
                    if c_at and datetime.datetime.fromtimestamp(c_at) < sept_start:
                        pass
                    sender = cv.get("meta", {}).get("sender", {})
                    s_phone = re.sub(r'\D', '', sender.get("phone_number") or '')
                    s_name = re.sub(r'[^\w\s]', '', sender.get("name") or '').strip().lower()
                    if len(s_phone) >= 8:
                        suffix = s_phone[-8:]
                        if suffix not in cw_by_suffix:
                            cw_by_suffix[suffix] = cv
                    if s_name and len(s_name) > 3:
                        if s_name not in cw_by_name:
                            cw_by_name[s_name] = cv
                if len(payload) < 25:
                    break
                page += 1
            except Exception:
                break

    # 3. Match ONLY the leads from the client's spreadsheet
    responded = 0
    unresponded = 0
    alerts_24h = 0
    resp_times = []
    unresp_leads = []
    now_dt = datetime.datetime.now()

    for lead in sept_leads:
        clean_p = lead["clean_phone"]
        clean_n = lead["clean_nome"]

        cv = None
        if len(clean_p) >= 8 and clean_p[-8:] in cw_by_suffix:
            cv = cw_by_suffix[clean_p[-8:]]
        elif clean_n and len(clean_n) > 3 and clean_n in cw_by_name:
            cv = cw_by_name[clean_n]

        is_resp = False
        cv_id = cv.get("id") if cv else None

        if cv:
            first_reply = cv.get("first_reply_created_at")
            c_at = cv.get("created_at")
            created_dt = datetime.datetime.fromtimestamp(c_at) if c_at else datetime.datetime.combine(lead["data_obj"], datetime.time(12, 0))
            if first_reply:
                is_resp = True
                resp_dt = datetime.datetime.fromtimestamp(first_reply)
                diff_h = (resp_dt - created_dt).total_seconds() / 3600.0
                if diff_h >= 0:
                    resp_times.append(diff_h)
            else:
                msgs = cv.get("messages", [])
                outgoing = [m for m in msgs if m.get("message_type") in [1, "outgoing"]]
                if outgoing:
                    is_resp = True
                    first_out = outgoing[0].get("created_at")
                    if first_out:
                        diff_h = (datetime.datetime.fromtimestamp(first_out) - created_dt).total_seconds() / 3600.0
                        if diff_h >= 0:
                            resp_times.append(diff_h)
            hours_wait = round((now_dt - created_dt).total_seconds() / 3600.0, 1)
        else:
            created_dt = datetime.datetime.combine(lead["data_obj"], datetime.time(12, 0))
            hours_wait = round((now_dt - created_dt).total_seconds() / 3600.0, 1)

        if is_resp:
            responded += 1
        else:
            unresponded += 1
            is_alert = hours_wait > 24
            if is_alert:
                alerts_24h += 1
            unresp_leads.append({
                "id": cv_id,
                "name": lead["nome"],
                "phone": lead["phone"] if lead["phone"] else "—",
                "data": lead["data"] + (" " + lead["hora"] if lead["hora"] else ""),
                "espera_h": hours_wait,
                "is_alert": is_alert,
                "link": f"{CHATWOOT_BASE}/app/accounts/1/conversations/{cv_id}" if cv_id else (f"https://wa.me/{clean_p}" if clean_p else "")
            })

    cw_leads = len(sept_leads)
    pct_resp = round((responded / cw_leads * 100), 1) if cw_leads > 0 else 0.0
    avg_resp_h = round((sum(resp_times) / len(resp_times)), 1) if resp_times else 0.0

    if is_discon:
        cw_status = "Desconectado"
        status_code = "descon"
        status_text = "🔴 WhatsApp Off"
    elif alerts_24h >= 3 or (cw_leads > 5 and pct_resp < 70):
        cw_status = "Gargalo"
        status_code = "alta" if today_leads > 0 or cw_leads > 10 else "mod"
        status_text = "🟢 Alta Tração" if status_code == "alta" else "🟡 Moderado"
    elif alerts_24h > 0 or (cw_leads > 5 and pct_resp < 90) or avg_resp_h > 24:
        cw_status = "Atenção"
        status_code = "alta" if today_leads > 0 or cw_leads > 10 else "mod"
        status_text = "🟢 Alta Tração" if status_code == "alta" else "🟡 Moderado"
    elif cw_leads == 0:
        cw_status = "Sem Entrada"
        status_code = "pausado"
        status_text = "⚪ Sem Leads"
    else:
        cw_status = "Saudável"
        status_code = "alta" if today_leads > 0 or cw_leads > 10 else "mod"
        status_text = "🟢 Alta Tração" if status_code == "alta" else "🟡 Moderado"

    tx_ag = round((agendados / total_leads * 100), 1) if total_leads > 0 else 0.0
    tx_cp = round((compareceram / agendados * 100), 1) if agendados > 0 else 0.0
    tx_vd = round((vendas / compareceram * 100), 1) if compareceram > 0 else 0.0

    return {
        "id": cid,
        "name": name,
        "seg": client["seg"],
        "inbox_id": ib_id,
        "cw_leads": cw_leads,
        "cw_resp": responded,
        "cw_unresp": unresponded,
        "cw_pct_resp": pct_resp,
        "cw_alerts": alerts_24h,
        "cw_avg_resp_h": avg_resp_h,
        "cw_status": cw_status,
        "unresp_leads": unresp_leads,
        "total": total_leads,
        "set": cw_leads,
        "ago": ago_leads,
        "hoje": today_leads,
        "ult": latest_date.strftime("%d/%m/%Y") if latest_date else "—",
        "status": status_code,
        "statusText": status_text,
        "agendados": agendados,
        "tx_agend": tx_ag,
        "comp": compareceram,
        "tx_comp": tx_cp,
        "vendas": vendas,
        "tx_venda": tx_vd
    }

def sync():
    log_msg("Iniciando varredura no Google Sheets CRM e Chatwoot para todas as clínicas...")

    # Parallel CRM & Chatwoot Extraction
    with ThreadPoolExecutor(max_workers=8) as executor:
        compiled = list(executor.map(process_client, CLIENTS))

    # Sort primarily by september leads, then today
    compiled.sort(key=lambda x: (x['set'], x['hoje']), reverse=True)

    tot_leads = sum(c["total"] for c in compiled)
    tot_set = sum(c["set"] for c in compiled)
    tot_hoje = sum(c["hoje"] for c in compiled)
    tot_cw_resp = sum(c["cw_resp"] for c in compiled)
    tot_cw_unresp = sum(c["cw_unresp"] for c in compiled)
    tot_cw_alerts = sum(c["cw_alerts"] for c in compiled)

    resp_clinics = [c["cw_avg_resp_h"] for c in compiled if c["cw_avg_resp_h"] > 0]
    avg_resp_global = round((sum(resp_clinics) / len(resp_clinics)), 1) if resp_clinics else 0.0
    pct_resp_global = round((tot_cw_resp / tot_set * 100), 1) if tot_set > 0 else 0.0

    log_msg(f"CRM Planilhas: Total Base={tot_leads:,} | Set/26={tot_set:,} | Hoje={tot_hoje}")
    log_msg(f"Chatwoot Set/26: Leads Planilha={tot_set} | Respondidos={tot_cw_resp} ({pct_resp_global}%) | Sem Resposta={tot_cw_unresp} | Alertas >24h={tot_cw_alerts} | Tempo Médio={avg_resp_global}h")

    # 3. Read current index.html template and inject new DATA
    index_path = os.path.join(REPO_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Inject updated DATA
    data_json = json.dumps(compiled, indent=2, ensure_ascii=False)
    html = re.sub(
        r'const DATA = \[[\s\S]*?\];',
        f'const DATA = {data_json};',
        html
    )

    # Inject timestamp
    now_str = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M")
    html = re.sub(
        r'<div style="font-size:0.85rem;color:var\(--text-muted\);">.*?</div>',
        f'<div style="font-size:0.85rem;color:var(--text-muted);">{now_str}</div>',
        html,
        count=1
    )

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    log_msg("index.html atualizado com sucesso!")

    # 4. Commit and Push to GitHub (auto-deploys to Vercel)
    try:
        subprocess.run(["git", "add", "index.html", "sync_daily.py"], cwd=REPO_DIR, check=True)
        msg = f"chore: sync crm sheets & chatwoot ({datetime.datetime.now().strftime('%d/%m/%Y %H:%M')})"
        subprocess.run(["git", "commit", "-m", msg], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        log_msg("Git commit & push executados! Deploy no Vercel iniciado automaticamente.")
    except Exception as e:
        log_msg(f"Aviso ao rodar git push: {e}")

if __name__ == "__main__":
    sync()
