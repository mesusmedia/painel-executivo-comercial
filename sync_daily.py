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
    hoje_leads = []
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

                is_agend = "agendad" in ag_val or (ag_val and ag_val not in ["não agendado", "nao agendado", "não", "nao", "0", "false", "em atendimento", "n/a"])
                is_comp = "compareceu" in cp_val or "sim" in cp_val
                is_ganho = "ganh" in gh_val or "sim" in gh_val or (idx_ganh and "data" in cols[idx_ganh].lower() and gh_val)

                if is_agend:
                    agendados += 1
                if is_comp:
                    compareceram += 1
                if is_ganho:
                    vendas += 1

                if d.year == now.year and d.month == now.month:
                    n_raw = get_v(idx_nome)
                    p_raw = get_v(idx_num)
                    h_raw = get_v(idx_hora)
                    lead_obj = {
                        "data": d.strftime("%d/%m/%Y"),
                        "data_obj": d,
                        "hora": h_raw,
                        "nome": n_raw if n_raw else "Lead sem nome",
                        "clean_nome": re.sub(r'[^\w\s]', '', n_raw).strip().lower(),
                        "phone": p_raw,
                        "clean_phone": re.sub(r'\D', '', p_raw),
                        "is_agend": is_agend,
                        "is_comp": is_comp,
                        "is_ganho": is_ganho
                    }
                    sept_leads.append(lead_obj)
                    if d == now:
                        hoje_leads.append(lead_obj)
                elif d.year == now.year and d.month == (now.month - 1):
                    ago_leads += 1
        except Exception as e:
            log_msg(f"Aviso ao ler planilha {name}: {e}")

    # 2. Fetch Chatwoot Conversations for inbox (Index by phone suffix & name)
    cw_by_full_phone = {}
    cw_by_suffix = {}
    cw_by_name = {}

    if ib_id and not is_discon and sept_leads:
        page = 1
        sept_start = datetime.datetime(2026, 9, 1, 0, 0, 0)
        sept_start_ts = int(sept_start.timestamp())
        while page <= 30:
            url_cw = f"{CHATWOOT_BASE}/api/v1/accounts/1/conversations?inbox_id={ib_id}&status=all&page={page}"
            try:
                r = requests.get(url_cw, headers=HEADERS_CW, timeout=12)
                if r.status_code != 200:
                    break
                payload = r.json().get("data", {}).get("payload", [])
                if not payload:
                    break
                for cv in payload:
                    sender = cv.get("meta", {}).get("sender", {})
                    s_phone = re.sub(r'\D', '', sender.get("phone_number") or '')
                    s_name = re.sub(r'[^\w\s]', '', sender.get("name") or '').strip().lower()
                    if s_phone:
                        cw_by_full_phone[s_phone] = cv
                        if len(s_phone) >= 8:
                            cw_by_suffix[s_phone[-8:]] = cv
                    if s_name and len(s_name) > 3:
                        cw_by_name[s_name] = cv

                last_item = payload[-1]
                last_act = last_item.get("last_activity_at") or last_item.get("created_at")
                if last_act and last_act < sept_start_ts:
                    break
                if len(payload) < 25:
                    break
                page += 1
            except Exception:
                break

    # 3. Match Helper: Validação Contextual Profunda da Conversa
    CLOSING_WORDS = {
        "ok", "okay", "blz", "beleza", "combinado", "show", "certo", "perfeito", "tá bom", "ta bom", "tá bem", "ta bem",
        "pode deixar", "obrigado", "obrigada", "obg", "valeu", "vlw", "muito obrigado", "muito obrigada", "agradeço", "disponha",
        "tchau", "boa noite", "bom dia", "boa tarde", "ate mais", "até mais", "até logo", "ate logo", "abraço", "beijo", "bom descanso",
        "esta mensagem foi apagada", "mensagem apagada", "liguei por engano", "foi engano", "engano", "chamada de voz perdida",
        "não tenho interesse", "nao tenho interesse", "não quero", "nao quero", "já fiz", "ja fiz", "já fechei", "ja fechei",
        "não posso", "nao posso", "sem interesse", "agora não", "agora nao", "não tenho papada", "não preciso",
        "vou remarcar", "teremos que remarcar", "depois vejo", "aviso vocês", "aviso voces"
    }

    CLOSING_EMOJIS = ["👍", "❤️", "🙏", "😊", "🙌", "👏", "👋", "🤝", "🫱🏻‍🫲🏻", "😘", "🥰", "✨", "😉"]

    QUESTION_WORDS = ["?", "quanto", "qual", "preco", "preço", "valor", "onde", "quando", "horario", "horário", "como funciona", "tem vaga"]

    now_dt = datetime.datetime.now()
    def evaluate_subset(leads_list):
        if not leads_list:
            return {
                "leads": 0, "resp": 0, "unresp": 0, "pct_resp": 0.0,
                "alerts": 0, "avg_h": 0.0, "status": "Sem Entrada", "unresp_leads": []
            }
        resp = 0
        unresp = 0
        alerts = 0
        resp_times = []
        unresp_items = []

        for l in leads_list:
            cp = l["clean_phone"]
            cn = l["clean_nome"]
            cv = cw_by_full_phone.get(cp) or cw_by_suffix.get(cp[-8:] if len(cp) >= 8 else "") or cw_by_name.get(cn if len(cn) > 3 else "")
            cv_id = cv.get("id") if cv else None
            is_resp = False
            waiting_context = ""

            # 1. Validação no CRM (Planilha): Se o lead já agendou, compareceu ou comprou, já teve êxito
            is_crm_concluded = l.get("is_agend") or l.get("is_comp") or l.get("is_ganho")

            if cv:
                last_msg = cv.get("last_non_activity_message") or {}
                m_type = last_msg.get("message_type")
                status = cv.get("status")
                first_reply = cv.get("first_reply_created_at")
                c_at = cv.get("created_at")
                created_dt = datetime.datetime.fromtimestamp(c_at) if c_at else datetime.datetime.combine(l["data_obj"], datetime.time(12, 0))

                raw_content = re.sub(r'[\r\n\t\xa0]+', ' ', (last_msg.get("content") or "")).strip()
                content_lower = raw_content.lower()
                clean_txt = re.sub(r'[^\w\s]', '', content_lower).strip()

                # A) Conclusão comprovada no CRM da planilha (Agendado, Compareceu ou Venda)
                if is_crm_concluded:
                    is_resp = True
                # B) Conversa resolvida ou silenciada no Chatwoot
                elif status in ["resolved", "snoozed"]:
                    is_resp = True
                # C) A última mensagem partiu da nossa equipe ou bot
                elif m_type in [1, "outgoing"]:
                    is_resp = True
                # D) Validação profunda do contexto da conversa quando a última mensagem foi do lead:
                elif first_reply and first_reply > 0:
                    # D.1) Emojis de agradecimento/despedida
                    if any(e in raw_content for e in CLOSING_EMOJIS) and len(raw_content) <= 10:
                        is_resp = True
                    # D.2) Frases de encerramento, agradecimento ou desinteresse expresso
                    elif any(clean_txt == w or content_lower == w or clean_txt.startswith(w + " ") or clean_txt.endswith(" " + w) for w in CLOSING_WORDS):
                        is_resp = True
                    # D.3) Confirmação curta sem perguntas abertas
                    elif not any(qw in content_lower for qw in QUESTION_WORDS) and len(clean_txt) <= 15:
                        if clean_txt in ["ok", "ta", "sim", "isso", "obg", "vlw", "certo", "beleza", "show", "combinado"]:
                            is_resp = True
                        else:
                            is_resp = False
                            waiting_context = f"Aguardando resposta: '{raw_content[:50]}'"
                    else:
                        is_resp = False
                        waiting_context = f"Dúvida aberta do lead: '{raw_content[:50]}'"
                else:
                    # first_reply == 0 ou ausente: a equipe NUNCA respondeu o lead
                    is_resp = False
                    waiting_context = f"Nunca respondido pela equipe: '{raw_content[:50]}'" if raw_content else "Nunca respondido pela equipe"

                if is_resp and first_reply:
                    diff_h = (datetime.datetime.fromtimestamp(first_reply) - created_dt).total_seconds() / 3600.0
                    if diff_h >= 0:
                        resp_times.append(diff_h)

                hours_wait = round((now_dt - created_dt).total_seconds() / 3600.0, 1)
            else:
                created_dt = datetime.datetime.combine(l["data_obj"], datetime.time(12, 0))
                hours_wait = round((now_dt - created_dt).total_seconds() / 3600.0, 1)
                if is_crm_concluded:
                    is_resp = True
                else:
                    is_resp = False
                    waiting_context = "Sem conversa criada no Chatwoot"

            if is_resp:
                resp += 1
            else:
                unresp += 1
                is_alert = hours_wait > 24
                if is_alert:
                    alerts += 1
                unresp_items.append({
                    "id": cv_id,
                    "name": l["nome"],
                    "phone": l["phone"] if l["phone"] else "—",
                    "data": l["data"] + (" " + l["hora"] if l["hora"] else ""),
                    "espera_h": hours_wait,
                    "is_alert": is_alert,
                    "contexto": waiting_context or "Aguardando resposta da clínica",
                    "link": f"{CHATWOOT_BASE}/app/accounts/1/conversations/{cv_id}" if cv_id else (f"https://wa.me/{cp}" if cp else "")
                })

        pct = round((resp / len(leads_list) * 100), 1) if leads_list else 0.0
        avg_t = round((sum(resp_times) / len(resp_times)), 1) if resp_times else 0.0

        if is_discon:
            saude = "Desconectado"
        elif alerts >= 3 or (len(leads_list) > 5 and pct < 70):
            saude = "Gargalo"
        elif alerts > 0 or (len(leads_list) > 5 and pct < 90) or avg_t > 24:
            saude = "Atenção"
        elif len(leads_list) == 0:
            saude = "Sem Entrada"
        else:
            saude = "Saudável"

        return {
            "leads": len(leads_list), "resp": resp, "unresp": unresp,
            "pct_resp": pct, "alerts": alerts, "avg_h": avg_t,
            "status": saude, "unresp_leads": unresp_items
        }

    m_set = evaluate_subset(sept_leads)
    m_hoje = evaluate_subset(hoje_leads)

    tx_ag = round((agendados / total_leads * 100), 1) if total_leads > 0 else 0.0
    tx_cp = round((compareceram / agendados * 100), 1) if agendados > 0 else 0.0
    tx_vd = round((vendas / compareceram * 100), 1) if compareceram > 0 else 0.0

    return {
        "id": cid,
        "name": name,
        "seg": client["seg"],
        "inbox_id": ib_id,
        # Setembro Metrics (Default)
        "cw_leads": m_set["leads"],
        "cw_resp": m_set["resp"],
        "cw_unresp": m_set["unresp"],
        "cw_pct_resp": m_set["pct_resp"],
        "cw_alerts": m_set["alerts"],
        "cw_avg_resp_h": m_set["avg_h"],
        "cw_status": m_set["status"],
        "unresp_leads": m_set["unresp_leads"],
        # Hoje Metrics
        "hoje_cw_leads": m_hoje["leads"],
        "hoje_cw_resp": m_hoje["resp"],
        "hoje_cw_unresp": m_hoje["unresp"],
        "hoje_cw_pct_resp": m_hoje["pct_resp"],
        "hoje_cw_alerts": m_hoje["alerts"],
        "hoje_cw_avg_resp_h": m_hoje["avg_h"],
        "hoje_cw_status": m_hoje["status"],
        "hoje_unresp_leads": m_hoje["unresp_leads"],
        # Baseline Leads
        "total": total_leads,
        "set": m_set["leads"],
        "ago": ago_leads,
        "hoje": m_hoje["leads"],
        "ult": latest_date.strftime("%d/%m/%Y") if latest_date else "—",
        "status": "descon" if is_discon else ("alta" if m_hoje["leads"] > 0 or m_set["leads"] > 10 else ("mod" if m_set["leads"] > 0 else "pausado")),
        "statusText": "🔴 WhatsApp Off" if is_discon else ("🟢 Alta Tração" if m_hoje["leads"] > 0 or m_set["leads"] > 10 else ("🟡 Moderado" if m_set["leads"] > 0 else "⚪ Sem Leads")),
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
        lambda _: f'const DATA = {data_json};',
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
