import os
import sys
import json
import re
import datetime
import subprocess
from concurrent.futures import ThreadPoolExecutor
import requests

sys.stdout.reconfigure(encoding='utf-8')

REPO_DIR = r"C:\Users\oluca\painel-executivo-comercial"
ENV_PATH = os.path.join(REPO_DIR, ".env")

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
    { "id": "C175-VivazOdontologia", "name": "Vivaz Odontologia", "seg": "Odonto", "inbox_id": 141, "sheet_id": None }
]

def fetch_chatwoot_metrics(client):
    ib_id = client.get("inbox_id")
    if not ib_id:
        return {
            "cw_leads": 0, "cw_resp": 0, "cw_unresp": 0, "cw_pct_resp": 0.0,
            "cw_alerts": 0, "cw_avg_resp_h": 0.0, "cw_status": "Desconectado" if client.get("disconnected") else "Sem Entrada"
        }

    now = datetime.datetime.now()
    sept_start = datetime.datetime(2026, 9, 1, 0, 0, 0)
    page = 1
    has_more = True
    sept_convs = []

    while has_more and page <= 6:
        url = f"{CHATWOOT_BASE}/api/v1/accounts/1/conversations?inbox_id={ib_id}&status=all&page={page}"
        try:
            r = requests.get(url, headers=HEADERS_CW, timeout=12)
            if r.status_code != 200:
                break
            payload = r.json().get("data", {}).get("payload", [])
            if not payload:
                break

            for cv in payload:
                c_at = cv.get("created_at")
                if not c_at:
                    continue
                dt = datetime.datetime.fromtimestamp(c_at)
                if dt >= sept_start:
                    sept_convs.append(cv)
                elif dt < sept_start:
                    has_more = False

            if len(payload) < 25:
                has_more = False
            page += 1
        except Exception:
            break

    total_leads = len(sept_convs)
    responded = 0
    unresponded = 0
    alerts_24h = 0
    total_resp_time_h = 0.0
    resp_count = 0

    for cv in sept_convs:
        c_at = cv.get("created_at")
        created_dt = datetime.datetime.fromtimestamp(c_at)
        first_reply = cv.get("first_reply_created_at")
        status = cv.get("status")

        is_resp = False
        if first_reply:
            is_resp = True
            resp_dt = datetime.datetime.fromtimestamp(first_reply)
            diff_h = (resp_dt - created_dt).total_seconds() / 3600.0
            if diff_h >= 0:
                total_resp_time_h += diff_h
                resp_count += 1
        else:
            msgs = cv.get("messages", [])
            outgoing = [m for m in msgs if m.get("message_type") in [1, "outgoing"]]
            if outgoing:
                is_resp = True
                first_out = outgoing[0].get("created_at")
                if first_out:
                    diff_h = (datetime.datetime.fromtimestamp(first_out) - created_dt).total_seconds() / 3600.0
                    if diff_h >= 0:
                        total_resp_time_h += diff_h
                        resp_count += 1

        if is_resp:
            responded += 1
        else:
            unresponded += 1
            hours_since = (now - created_dt).total_seconds() / 3600.0
            if hours_since > 24 and status != "resolved":
                alerts_24h += 1

    pct_resp = round((responded / total_leads * 100), 1) if total_leads > 0 else 0.0
    avg_resp_h = round((total_resp_time_h / resp_count), 1) if resp_count > 0 else 0.0

    if client.get("disconnected"):
        saude = "Desconectado"
    elif alerts_24h >= 3 or (total_leads > 5 and pct_resp < 70):
        saude = "Gargalo"
    elif alerts_24h > 0 or (total_leads > 5 and pct_resp < 90) or avg_resp_h > 24:
        saude = "Atenção"
    elif total_leads == 0:
        saude = "Sem Entrada"
    else:
        saude = "Saudável"

    return {
        "cw_leads": total_leads,
        "cw_resp": responded,
        "cw_unresp": unresponded,
        "cw_pct_resp": pct_resp,
        "cw_alerts": alerts_24h,
        "cw_avg_resp_h": avg_resp_h,
        "cw_status": saude
    }

# Historical CRM Baseline (Sheet Totals & Funnel)
SHEET_CACHE = {
    "C162-DrBrunoAraujo": { "total": 1077, "set": 189, "ago": 193, "hoje": 21, "ult": "08/09/2026", "agendados": 15, "tx_agend": 1.4, "comp": 6, "tx_comp": 40.0, "vendas": 0, "tx_venda": 0.0 },
    "C158-VictorianoFaces": { "total": 2468, "set": 173, "ago": 615, "hoje": 15, "ult": "08/09/2026", "agendados": 69, "tx_agend": 2.8, "comp": 3, "tx_comp": 4.3, "vendas": 2, "tx_venda": 66.7 },
    "C172-DrCaioFigueira": { "total": 474, "set": 156, "ago": 316, "hoje": 11, "ult": "08/09/2026", "agendados": 8, "tx_agend": 1.7, "comp": 1, "tx_comp": 12.5, "vendas": 1, "tx_venda": 100.0 },
    "C169-DrKeeynerCorrea": { "total": 473, "set": 80, "ago": 224, "hoje": 8, "ult": "08/09/2026", "agendados": 39, "tx_agend": 8.2, "comp": 5, "tx_comp": 12.8, "vendas": 1, "tx_venda": 20.0 },
    "C123-OrgulhoSaoVicente": { "total": 2718, "set": 77, "ago": 356, "hoje": 7, "ult": "08/09/2026", "agendados": 708, "tx_agend": 26.0, "comp": 58, "tx_comp": 8.2, "vendas": 38, "tx_venda": 65.5 },
    "C174-EsteticFaceItapetininga": { "total": 225, "set": 74, "ago": 151, "hoje": 8, "ult": "08/09/2026", "agendados": 2, "tx_agend": 0.9, "comp": 0, "tx_comp": 0.0, "vendas": 0, "tx_venda": 0.0 },
    "C123-DrRafaelRocha": { "total": 4610, "set": 65, "ago": 401, "hoje": 6, "ult": "08/09/2026", "agendados": 1382, "tx_agend": 30.0, "comp": 166, "tx_comp": 12.0, "vendas": 126, "tx_venda": 75.9 },
    "C123-OrgulhodeSorrirPeruibe": { "total": 1692, "set": 61, "ago": 352, "hoje": 1, "ult": "08/09/2026", "agendados": 998, "tx_agend": 59.0, "comp": 121, "tx_comp": 12.1, "vendas": 31, "tx_venda": 25.6 },
    "C150-Lumia": { "total": 769, "set": 50, "ago": 97, "hoje": 5, "ult": "08/09/2026", "agendados": 220, "tx_agend": 28.6, "comp": 58, "tx_comp": 26.4, "vendas": 31, "tx_venda": 53.4 },
    "C171-DraStefaniRezende": { "total": 107, "set": 43, "ago": 60, "hoje": 3, "ult": "08/09/2026", "agendados": 14, "tx_agend": 13.1, "comp": 0, "tx_comp": 0.0, "vendas": 0, "tx_venda": 0.0 },
    "C163-AcessoSaudeCIC": { "total": 654, "set": 42, "ago": 167, "hoje": 5, "ult": "08/09/2026", "agendados": 18, "tx_agend": 2.8, "comp": 1, "tx_comp": 5.6, "vendas": 0, "tx_venda": 0.0 },
    "C149-ClinicaGGlow": { "total": 1213, "set": 34, "ago": 113, "hoje": 3, "ult": "08/09/2026", "agendados": 181, "tx_agend": 14.9, "comp": 25, "tx_comp": 13.8, "vendas": 22, "tx_venda": 88.0 },
    "C52-DrLucasPitao": { "total": 1401, "set": 23, "ago": 94, "hoje": 8, "ult": "08/09/2026", "agendados": 922, "tx_agend": 65.8, "comp": 128, "tx_comp": 13.9, "vendas": 51, "tx_venda": 39.8 },
    "C135-DraMichelleSantos": { "total": 1212, "set": 19, "ago": 48, "hoje": 2, "ult": "08/09/2026", "agendados": 471, "tx_agend": 38.9, "comp": 12, "tx_comp": 2.5, "vendas": 4, "tx_venda": 33.3 },
    "C170-DraMariaEduarda": { "total": 105, "set": 19, "ago": 75, "hoje": 1, "ult": "08/09/2026", "agendados": 4, "tx_agend": 3.8, "comp": 0, "tx_comp": 0.0, "vendas": 0, "tx_venda": 0.0 },
    "C173-OdontoPrime": { "total": 88, "set": 19, "ago": 69, "hoje": 0, "ult": "06/09/2026", "agendados": 16, "tx_agend": 18.2, "comp": 0, "tx_comp": 0.0, "vendas": 0, "tx_venda": 0.0 },
    "C63-DrRaphaelMoreira": { "total": 977, "set": 15, "ago": 71, "hoje": 4, "ult": "08/09/2026", "agendados": 508, "tx_agend": 52.0, "comp": 1, "tx_comp": 0.2, "vendas": 0, "tx_venda": 0.0 },
    "C123-OrgulhodeSorrirSantos": { "total": 1798, "set": 13, "ago": 0, "hoje": 0, "ult": "05/09/2026", "agendados": 579, "tx_agend": 32.2, "comp": 74, "tx_comp": 12.8, "vendas": 24, "tx_venda": 32.4 },
    "C124-DraAnnaHOF": { "total": 1285, "set": 11, "ago": 82, "hoje": 1, "ult": "08/09/2026", "agendados": 607, "tx_agend": 47.2, "comp": 98, "tx_comp": 16.1, "vendas": 26, "tx_venda": 26.5 },
    "C155-ClinicaElodonto": { "total": 117, "set": 5, "ago": 30, "hoje": 0, "ult": "07/09/2026", "agendados": 81, "tx_agend": 69.2, "comp": 12, "tx_comp": 14.8, "vendas": 8, "tx_venda": 66.7 },
    "C166-Lucasmallmann": { "total": 85, "set": 3, "ago": 15, "hoje": 0, "ult": "05/09/2026", "agendados": 24, "tx_agend": 28.2, "comp": 4, "tx_comp": 16.7, "vendas": 3, "tx_venda": 75.0 },
    "C136-IntegrareOdontologia": { "total": 1272, "set": 14, "ago": 64, "hoje": 0, "ult": "03/09/2026", "agendados": 789, "tx_agend": 62.0, "comp": 18, "tx_comp": 2.3, "vendas": 10, "tx_venda": 55.6 },
    "C157-DraCristianeTiburtino": { "total": 85, "set": 0, "ago": 30, "hoje": 0, "ult": "19/08/2026", "agendados": 1, "tx_agend": 1.2, "comp": 0, "tx_comp": 0.0, "vendas": 0, "tx_venda": 0.0 },
    "EsteticaLosAngelesLeads": { "total": 125, "set": 0, "ago": 30, "hoje": 0, "ult": "19/08/2026", "agendados": 0, "tx_agend": 0.0, "comp": 0, "tx_comp": 0.0, "vendas": 0, "tx_venda": 0.0 },
    "C86-DrWilliamHenrique": { "total": 126, "set": 0, "ago": 10, "hoje": 0, "ult": "03/08/2026", "agendados": 4, "tx_agend": 3.2, "comp": 0, "tx_comp": 0.0, "vendas": 0, "tx_venda": 0.0 },
    "C168-DraMichelleAlves": { "total": 212, "set": 2, "ago": 57, "hoje": 0, "ult": "01/09/2026", "agendados": 142, "tx_agend": 67.0, "comp": 2, "tx_comp": 1.4, "vendas": 0, "tx_venda": 0.0 },
    "C164-DraLea": { "total": 336, "set": 2, "ago": 48, "hoje": 0, "ult": "05/09/2026", "agendados": 13, "tx_agend": 3.9, "comp": 0, "tx_comp": 0.0, "vendas": 0, "tx_venda": 0.0 },
    "C140-EspacoBottega": { "total": 592, "set": 0, "ago": 44, "hoje": 0, "ult": "20/08/2026", "agendados": 163, "tx_agend": 27.5, "comp": 54, "tx_comp": 33.1, "vendas": 0, "tx_venda": 0.0 },
    "C167-AvanteOdontologiaBH": { "total": 120, "set": 10, "ago": 25, "hoje": 1, "ult": "08/09/2026", "agendados": 18, "tx_agend": 15.0, "comp": 3, "tx_comp": 16.7, "vendas": 2, "tx_venda": 66.7 },
    "C167-AvanteOdontologiaSL": { "total": 85, "set": 7, "ago": 18, "hoje": 1, "ult": "08/09/2026", "agendados": 12, "tx_agend": 14.1, "comp": 2, "tx_comp": 16.7, "vendas": 1, "tx_venda": 50.0 },
    "C141-VictorRios": { "total": 150, "set": 7, "ago": 22, "hoje": 1, "ult": "08/09/2026", "agendados": 28, "tx_agend": 18.7, "comp": 5, "tx_comp": 17.9, "vendas": 3, "tx_venda": 60.0 },
    "C175-VivazOdontologia": { "total": 350, "set": 125, "ago": 45, "hoje": 14, "ult": "08/09/2026", "agendados": 55, "tx_agend": 15.7, "comp": 12, "tx_comp": 21.8, "vendas": 8, "tx_venda": 66.7 }
}

def sync():
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando varredura no Chatwoot para todas as clínicas...")
    
    # 2. Parallel Chatwoot Extraction
    with ThreadPoolExecutor(max_workers=8) as executor:
        cw_results = list(executor.map(fetch_chatwoot_metrics, CLIENTS))

    compiled = []
    tot_cw_leads = 0
    tot_cw_resp = 0
    tot_cw_unresp = 0
    tot_cw_alerts = 0
    total_resp_time_acc = 0.0
    total_resp_clinics = 0

    for c, cw in zip(CLIENTS, cw_results):
        cid = c["id"]
        base = SHEET_CACHE.get(cid, {
            "total": cw["cw_leads"], "set": cw["cw_leads"], "ago": 0, "hoje": 0, "ult": "—",
            "agendados": 0, "tx_agend": 0.0, "comp": 0, "tx_comp": 0.0, "vendas": 0, "tx_venda": 0.0
        })

        # Lead status text
        if c.get("disconnected"):
            status_text = "🔴 WhatsApp Off"
            status_code = "descon"
        elif base["hoje"] > 0 or cw["cw_leads"] > 10:
            status_text = "🟢 Alta Tração"
            status_code = "alta"
        elif cw["cw_leads"] > 0:
            status_text = "🟡 Moderado"
            status_code = "mod"
        else:
            status_text = "⚪ Sem Leads"
            status_code = "pausado"

        compiled.append({
            "id": cid,
            "name": c["name"],
            "seg": c["seg"],
            "inbox_id": c.get("inbox_id"),
            # Chatwoot metrics (Real response tracking)
            "cw_leads": cw["cw_leads"],
            "cw_resp": cw["cw_resp"],
            "cw_unresp": cw["cw_unresp"],
            "cw_pct_resp": cw["cw_pct_resp"],
            "cw_alerts": cw["cw_alerts"],
            "cw_avg_resp_h": cw["cw_avg_resp_h"],
            "cw_status": cw["cw_status"],
            # Leads baseline
            "total": base["total"],
            "set": base["set"],
            "ago": base["ago"],
            "hoje": base["hoje"],
            "ult": base["ult"],
            "status": status_code,
            "statusText": status_text,
            # Funnel metrics
            "agendados": base["agendados"],
            "tx_agend": base["tx_agend"],
            "comp": base["comp"],
            "tx_comp": base["tx_comp"],
            "vendas": base["vendas"],
            "tx_venda": base["tx_venda"]
        })

        tot_cw_leads += cw["cw_leads"]
        tot_cw_resp += cw["cw_resp"]
        tot_cw_unresp += cw["cw_unresp"]
        tot_cw_alerts += cw["cw_alerts"]
        if cw["cw_avg_resp_h"] > 0:
            total_resp_time_acc += cw["cw_avg_resp_h"]
            total_resp_clinics += 1

    avg_resp_global = round((total_resp_time_acc / total_resp_clinics), 1) if total_resp_clinics > 0 else 0.0
    pct_resp_global = round((tot_cw_resp / tot_cw_leads * 100), 1) if tot_cw_leads > 0 else 0.0

    print(f"Chatwoot Set/26: Leads={tot_cw_leads} | Respondidos={tot_cw_resp} ({pct_resp_global}%) | Sem Resposta={tot_cw_unresp} | Alertas >24h={tot_cw_alerts} | Tempo Médio={avg_resp_global}h")

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

    print("index.html atualizado com sucesso!")

    # 4. Commit and Push to GitHub (auto-deploys to Vercel)
    try:
        subprocess.run(["git", "add", "index.html"], cwd=REPO_DIR, check=True)
        msg = f"chore: sync diario comercial & chatwoot ({datetime.datetime.now().strftime('%d/%m/%Y %H:%M')})"
        subprocess.run(["git", "commit", "-m", msg], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        print("Git commit & push executados! Deploy no Vercel iniciado automaticamente.")
    except Exception as e:
        print("Aviso ao rodar git push:", e)

if __name__ == "__main__":
    sync()
