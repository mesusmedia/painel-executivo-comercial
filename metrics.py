"""Métricas comerciais por cliente a partir da aba CRM da planilha Gerencial.

Fonte única de verdade do painel e dos PDFs. Regras:
- lead = telefone único (últimos 8 dígitos) cuja data de entrada cai no período;
- funil monotônico: venda => compareceu => agendou (evita taxa > 100%);
- taxas: agendamento = ag/leads, comparecimento = comp/ag, fechamento = vendas/comp.
"""
import csv
import datetime
import io
import re
import urllib.request

GID = "1048674045"


def norm(s):
    return (s or "").strip().lower()


def fetch_csv(sheet_id, gid=GID, timeout=60):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    return urllib.request.urlopen(url, timeout=timeout).read().decode("utf-8")


def parse_date(s):
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _neg(v):
    return any(w in v for w in ("não", "nao", "desmarc", "faltou", "cancel", "descart", "remarc", "reagend"))


def parse_leads(csv_text):
    """Lê o CSV e devolve leads únicos por telefone (primeira entrada), flags OR-ados."""
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        return []
    hdr = [h.strip() for h in rows[0]]
    low = [h.lower() for h in hdr]

    def col(*names, contains=None):
        for n in names:
            if n in low:
                return low.index(n)
        if contains:
            for i, h in enumerate(low):
                if contains in h:
                    return i
        return None

    i_data = col("data")
    i_hora = col("hora")
    i_nome = col("nome")
    i_num = col("número", "numero", "telefone")
    if i_num is not None:
        amostra = [re.sub(r"\D", "", r[i_num]) for r in rows[1:21] if i_num < len(r)]
        if sum(1 for s in amostra if len(s) >= 8) < len(amostra) * 0.3:
            i_num = None  # coluna "número" existe mas não guarda telefone (ex.: nome da conta de anúncio)
    if i_num is None:
        i_num = 3  # Peruíbe: cabeçalho da coluna de telefone corrompido
    i_ag = col("agendou?")
    i_comp = col("compareceu?")
    i_ganh = col("ganhou?", "fechou?")
    i_orig = col("origem")
    i_sub = col("suborigem")
    i_camp = col("campanha")
    i_conj = col("conjunto")
    i_anu = col("anúncio", "anuncio")
    i_plat = col("plataforma")
    i_motivo = col("motivo de perda")
    i_obs = col("observações", "observacoes")
    i_cont = col("contato?")
    i_dag = col("data agendamento", "data agendado", "data avaliação", "data da consulta")

    def g(r, i):
        return r[i].strip() if i is not None and i < len(r) else ""

    seen = {}
    out = []
    for r in rows[1:]:
        d = parse_date(g(r, i_data))
        if not d:
            continue
        phone = re.sub(r"\D", "", g(r, i_num))
        key = phone[-8:] if len(phone) >= 8 else ""
        ag_v, cp_v, gh_v = norm(g(r, i_ag)), norm(g(r, i_comp)), norm(g(r, i_ganh))
        is_ag = "agendad" in ag_v and not _neg(ag_v)
        is_cp = cp_v.startswith("compareceu")
        is_gh = (gh_v in ("ganha", "ganho", "convênio", "convenio", "particular", "fechou", "fechou consulta", "sim")
                 or gh_v.startswith("ganh"))
        is_open = gh_v in ("em aberto", "negociação", "negociacao")
        lead = {
            "data": d,
            "hora": g(r, i_hora),
            "nome": g(r, i_nome) or "Lead sem nome",
            "phone": phone,
            "key": key,
            "origem": g(r, i_orig),
            "suborigem": g(r, i_sub),
            "campanha": g(r, i_camp),
            "conjunto": g(r, i_conj),
            "anuncio": g(r, i_anu),
            "plataforma": g(r, i_plat),
            "contato": g(r, i_cont),
            "agendou_raw": g(r, i_ag),
            "comp_raw": g(r, i_comp),
            "ganhou_raw": g(r, i_ganh),
            "motivo_perda": g(r, i_motivo),
            "obs": g(r, i_obs),
            "data_agendamento": g(r, i_dag),
            "ag": is_ag,
            "comp": is_cp,
            "venda": is_gh,
            "aberto": is_open,
        }
        if key and key in seen:
            p = seen[key]
            for f in ("ag", "comp", "venda", "aberto"):
                p[f] = p[f] or lead[f]
            continue
        if key:
            seen[key] = lead
        out.append(lead)
    for l in out:  # funil monotônico
        if l["venda"]:
            l["comp"] = True
        if l["comp"]:
            l["ag"] = True
        if not l["ag"]:  # orçamento em aberto só existe pra quem passou por agendado
            l["aberto"] = False
        if l["venda"]:  # orcamento em aberto = compareceu e ainda nao fechou
            l["aberto"] = False
    return out


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def summarize(leads, start, end):
    sel = [l for l in leads if start <= l["data"] <= end]
    n = len(sel)
    ag = sum(l["ag"] for l in sel)
    cp = sum(l["comp"] for l in sel)
    vd = sum(l["venda"] for l in sel)
    return {
        "leads": n, "ag": ag, "comp": cp, "vendas": vd,
        "aberto": sum(l["aberto"] for l in sel),
        "tx_ag": pct(ag, n), "tx_comp": pct(cp, ag), "tx_venda": pct(vd, cp),
    }


def month_range(y, m, until=None):
    start = datetime.date(y, m, 1)
    nxt = datetime.date(y + (m == 12), m % 12 + 1, 1)
    end = nxt - datetime.timedelta(days=1)
    if until and until < end:
        end = until
    return start, end


def prev_month(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)
