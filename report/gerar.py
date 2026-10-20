"""Monta os relatorios no padrao Jordana (16/10) a partir de raw/ (leads x conversas) e cache/julgamentos.json.
Sem IA: numeros da planilha + agendamentos firmes/possiveis ja julgados; textos por regra.
Uso: python report/gerar.py <pasta_trabalho> [id ...]
Gera: report/out/<id>.json, pdfs/*.pdf + manifest.json, analysis.json, verified.json."""
import glob, hashlib, json, os, re, subprocess, sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO); sys.path.insert(0, HERE)
from clients import CLIENTS  # noqa: E402
from sem_analise import SEM_ANALISE  # noqa: E402

WORK = sys.argv[1]; ONLY = set(sys.argv[2:])
MES = "2026-10"
NOMES = {c[0]: c[1] for c in CLIENTS}
PREV_DIR = os.path.expanduser("~/Documents/Relatorios-Clientes-Out-2026-16-10-final/dados")
PREV_ROT = "o relatório de 16/10"
pt = lambda x, d=1: f"{x:.{d}f}".replace(".", ",")
pc = lambda a, b: pt(a / b * 100) + "%" if b else None
norm = lambda s: re.sub(r"[^a-z]", "", s.lower())
semorig = lambda l: not l["campanha"] or l["campanha"].lower() == "direto_whatsapp"
JUL = {}
# Motivo de perda (CRM/conversa) -> ação concreta no plano, em vez de texto genérico igual para todo cliente
MOTIVO_ACOES = {
    "convênio": "Avaliar tabela ou parceria para convênio: foi o motivo de perda mais citado",
    "convenio": "Avaliar tabela ou parceria para convênio: foi o motivo de perda mais citado",
    "preço": "Rever a oferta ou condição de parcelamento: preço foi o motivo de perda mais citado",
    "preco": "Rever a oferta ou condição de parcelamento: preço foi o motivo de perda mais citado",
    "distância": "Reforçar divulgação de unidades próximas ou atendimento remoto: distância foi o motivo mais citado",
    "distancia": "Reforçar divulgação de unidades próximas ou atendimento remoto: distância foi o motivo mais citado",
    "tentativas de contato esgotadas": "Ajustar a cadência de follow-up: muitos leads pararam de responder antes de decidir",
    "ficou de retornar": "Programar um novo contato em poucos dias para quem disse que ia retornar",
}


def anterior(cid):
    k2 = norm(re.sub(r"^C\d+-", "", cid))
    for g in glob.glob(PREV_DIR + "/*.json"):
        b = norm(os.path.basename(g)[:-5])
        if b == k2 or k2.endswith(b) or b.endswith(k2):
            return json.load(open(g, encoding="utf-8"))
    return None


def build(cid):
    raw = json.load(open(os.path.join(WORK, "raw", cid + ".json"), encoding="utf-8"))
    L = raw["leads"]; dfim = int(raw["periodo"][1][8:10])
    ver = lambda l: JUL.get(f'{cid}:{l["key"]}', {}).get("v")
    firme = {i for i, l in enumerate(L) if not l["ag"] and ver(l) == "firme"}
    possivel = {i for i, l in enumerate(L) if not l["ag"] and i not in firme and ver(l) == "possivel"}
    ag = {i for i, l in enumerate(L) if l["ag"] or i in firme}
    comp = {i for i, l in enumerate(L) if l["comp"]}; venda = {i for i, l in enumerate(L) if l["venda"]}
    aberto = {i for i, l in enumerate(L) if l["aberto"] or l["ganhou_raw"].strip().lower() in ("em aberto", "negociação", "negociacao")} - venda  # raw antigo zerava aberto de quem compareceu
    assert venda <= comp <= ag, "funil nao monotonico"
    n, A, C, V = len(L), len(ag), len(comp), len(venda)
    falt = sum(1 for l in L if "falt" in (l["comp_raw"] or "").lower())
    sem_orig = sum(1 for l in L if semorig(l))
    og, sem = {}, dict(ag=0, pos_ag=0, venda=0, pos_venda=0)
    for i, l in enumerate(L):
        fl = dict(ag=i in ag, pos_ag=i in possivel, venda=i in venda, pos_venda=i in aberto)
        if not any(fl.values()):
            continue
        tgt = sem if semorig(l) else og.setdefault((l["campanha"], l["conjunto"], l["anuncio"]), dict(ag=0, pos_ag=0, venda=0, pos_venda=0))
        for k, v in fl.items():
            tgt[k] += v
    obs, plano = [], []
    camp = Counter(l["campanha"] for l in L if not semorig(l))
    if camp and sum(camp.values()) >= 0.5 * n:
        obs.append(f"Entraram {n} leads novos de 01/10 a {dfim:02d}/10, a maior parte vinda da campanha {camp.most_common(1)[0][0]}.")
    else:
        obs.append(f"Entraram {n} leads novos de 01/10 a {dfim:02d}/10, uma média de {pt(n / dfim)} por dia.")
    if A:
        t = f"{A} pacientes agendaram ({pc(A, n)} dos leads)"
        if C:
            t += f" e {C} compareceram, o que dá {pc(C, A)} de comparecimento entre os agendados"
        t += "."
        if falt:
            t += f" {falt} {'paciente faltou' if falt == 1 else 'pacientes faltaram'}."
        obs.append(t)
    else:
        obs.append("Ainda não há agendamentos registrados no período.")
    if A and og:
        ranked = sorted(((k, v) for k, v in og.items() if v["ag"] > 0), key=lambda kv: -kv[1]["ag"])
        if ranked:
            partes = []
            for (campn, conj, anu), v in ranked[:4]:
                rotulo = " / ".join(x for x in (anu, conj) if x) or campn or "sem identificação"
                extra = f", {v['venda']} venda{'s' if v['venda'] != 1 else ''}" if v["venda"] else ""
                partes.append(f"{rotulo} ({v['ag']} agendamento{'s' if v['ag'] != 1 else ''}{extra})")
            obs.append("Os agendamentos vieram de: " + "; ".join(partes) + ".")
    if V or aberto:
        t = []
        if V:
            t.append(f"{V} {'paciente fechou' if V == 1 else 'pacientes fecharam'} tratamento" + (f" ({pc(V, C)} de quem compareceu)" if C else ""))
        if aberto:
            t.append(f"{len(aberto)} {'segue' if len(aberto) == 1 else 'seguem'} com orçamento em aberto")
        obs.append(" e ".join(t).capitalize() + ".")
    elif C:
        obs.append("Nenhuma venda foi registrada entre os pacientes que compareceram até agora.")
    cj = {}
    for i, l in enumerate(L):
        if l["conjunto"]:
            e = cj.setdefault(l["conjunto"], [0, 0]); e[0] += 1; e[1] += i in ag
    gr = {k: v for k, v in cj.items() if v[0] >= 10}
    if len(gr) >= 2 and sum(v[1] for v in gr.values()) >= 2:
        best = max(gr.items(), key=lambda kv: kv[1][1] / kv[1][0]); worst = min(gr.items(), key=lambda kv: kv[1][1] / kv[1][0])
        if best[0] != worst[0] and best[1][1] / best[1][0] > worst[1][1] / worst[1][0]:
            obs.append(f"O público {best[0]} foi o mais eficiente: {best[1][1]} agendamentos em {best[1][0]} leads ({pc(best[1][1], best[1][0])}), contra {worst[1][1]} em {worst[1][0]} ({pc(worst[1][1], worst[1][0])}) no público {worst[0]}.")
    if n >= 10 and sem_orig / n >= 0.25:
        obs.append(f"{sem_orig} dos {n} leads ({pc(sem_orig, n)}) estão sem campanha, conjunto e anúncio informados, o que limita a leitura de quais anúncios geram mais pacientes.")
    if possivel:
        obs.append(f"Há ainda {len(possivel)} pacientes com horário oferecido ou combinado, aguardando confirmação.")
    mot = Counter(l["motivo_perda"].strip().lower() for l in L if l["motivo_perda"].strip())
    if sum(mot.values()) >= 2:
        obs.append("Entre os leads que não seguiram, os motivos registrados foram: " + ", ".join(f"{k} ({v})" if v > 1 else k for k, v in mot.most_common(3)) + ".")
    if A:
        plano.append("Confirmar o comparecimento dos agendados no dia anterior e reagendar rapidamente quem faltar.")
    if C and (not V or aberto):
        plano.append("Registrar o desfecho de cada paciente que compareceu (fechou, em decisão ou não fechou) e o valor do tratamento, para medirmos o retorno por campanha.")
    if aberto:
        plano.append(f"Entrar em contato com os {len(aberto)} orçamentos em aberto, oferecendo dois horários para uma conversa de decisão.")
    if n >= 30 and A / n < 0.15:
        plano.append("Reforçar o acompanhamento dos leads em atendimento, oferecendo dois horários para a próxima semana.")
    if n >= 10 and sem_orig / n >= 0.25:
        plano.append("Completar campanha, conjunto e anúncio dos leads sem identificação, para saber quais anúncios geram mais agendamentos.")
    if mot:
        motivo_top, n_top = mot.most_common(1)[0]
        acao = MOTIVO_ACOES.get(motivo_top)
        if acao and n_top >= 2:
            plano.append(f"{acao} ({n_top} leads).")
    if possivel:
        plano.insert(1 if plano else 0, f"Confirmar com os {len(possivel)} pacientes que estão com horário oferecido, travando data e hora na agenda.")
    if not A or len(plano) < 3:
        plano.append("Registrar o desfecho de cada lead no mesmo dia (agendou, compareceu, fechou), para medirmos o retorno por campanha com precisão.")
    plano = plano[:5]
    origem = [dict(campanha=k[0], conjunto=k[1], anuncio=k[2], **v) for k, v in og.items()]
    origem.sort(key=lambda r: -(r["venda"] * 4 + r["ag"] * 3 + r["pos_venda"] * 2 + r["pos_ag"]))
    ag_list = []
    for i in sorted(ag, key=lambda i: (L[i]["data"], L[i]["hora"])):
        l = L[i]; cp = (l["comp_raw"] or "").strip().lower()
        ag_list.append({"nome": l["nome"] or "-", "telefone": l["phone"] or "-", "campanha": "" if semorig(l) else l["campanha"],
                        "conjunto": l["conjunto"], "anuncio": l["anuncio"],
                        "comparecimento": "Compareceu" if i in comp else ("Faltou" if "falt" in cp else ""),
                        "resultado": "Venda" if i in venda else "Orçamento em aberto" if i in aberto else ""})
    dias = Counter(int(l["data"][8:10]) for l in L)
    prev = anterior(cid); itens = []
    if prev:
        for nome, antes, agora in (("Leads", prev.get("leads_total"), n), ("Agendamentos", prev.get("agendamentos"), A),
                                   ("Comparecimentos", prev.get("comparecimentos"), C), ("Vendas registradas", prev.get("vendas"), V)):
            if antes is not None and (antes or agora):
                itens.append({"nome": nome, "antes": antes, "agora": agora})
    if any(i["agora"] < i["antes"] for i in itens):  # base de contagem diferente do relatorio anterior: nao comparar
        print("BASE DIFERENTE de 16/10 (sem comparativo):", cid, [(i["nome"], i["antes"], i["agora"]) for i in itens]); itens = []
    pdf = {"cliente": NOMES[cid], "periodo": f"01/10/2026 até {dfim:02d}/10/2026", "leads_total": n, "agendamentos": A or None,
           "comparecimentos": C or None, "vendas": V or None, "orcamento_aberto": len(aberto) or None,
           "comparativo": {"rotulo": PREV_ROT, "itens": itens} if itens else None,
           "leads_por_dia": [{"dia": f"{d:02d}", "v": dias.get(d, 0)} for d in range(1, dfim + 1)] if n >= 10 else None,
           "observacoes": obs, "plano_acao": plano, "origem": origem or None, "origem_sem_identificacao": sem, "agendados": ag_list or None}
    pdf = {k: v for k, v in pdf.items() if v is not None}
    return pdf, sorted(L[i]["key"] for i in firme if L[i]["key"]), {"leads": n, "ag": A, "comp": C, "vendas": V}, dfim


def main():
    global JUL
    JUL = json.load(open(os.path.join(REPO, "cache", "julgamentos.json"), encoding="utf-8"))
    rd = lambda p: json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    mp, ap, vp = (os.path.join(REPO, x) for x in ("pdfs/manifest.json", "analysis.json", "verified.json"))
    manifest, analysis, verified = rd(mp), rd(ap), rd(vp)
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True); os.makedirs(os.path.join(REPO, "pdfs"), exist_ok=True)
    for cid in (c[0] for c in CLIENTS):
        if ONLY and cid not in ONLY:
            continue
        if cid in SEM_ANALISE:
            analysis[cid] = {"disponivel": False, "motivo": SEM_ANALISE[cid]}; manifest.pop(cid, None); continue
        if not os.path.exists(os.path.join(WORK, "raw", cid + ".json")):
            print("SEM RAW:", cid); continue
        pdf, ver, snap, dfim = build(cid)
        jp = os.path.join(HERE, "out", cid + ".json")
        json.dump(pdf, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        fn = f"relatorio_{cid}-{hashlib.sha256(('mesus-painel:' + cid).encode()).hexdigest()[:8]}.pdf"
        subprocess.run([sys.executable, os.path.join(HERE, "make_pdf.py"), jp, os.path.join(REPO, "pdfs", fn)], check=True, stdout=subprocess.DEVNULL)
        manifest[cid] = "/pdfs/" + fn; verified[cid] = {"ag": ver}
        analysis[cid] = {"disponivel": True, "mes": MES, "periodo": f"01/10 a {dfim:02d}/10/2026", "obs": pdf["observacoes"], "plano": pdf["plano_acao"], "snap": snap}
        print("OK", cid, snap)
    json.dump(manifest, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(analysis, open(ap, "w", encoding="utf-8"), ensure_ascii=False); json.dump(verified, open(vp, "w", encoding="utf-8"), ensure_ascii=False)


main()
