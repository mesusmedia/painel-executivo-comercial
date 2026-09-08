import urllib.request, zipfile, io, xml.etree.ElementTree as ET, re, datetime, json, subprocess, os
from concurrent.futures import ThreadPoolExecutor

REPO_DIR = r"C:\Users\oluca\painel-executivo-comercial"

CLIENTS = [
  { "id": "C162-DrBrunoAraujo", "name": "Dr. Bruno Araújo", "seg": "Saúde", "sheet_id": "1Vc5IT497LN25AUD8ckoH7CkXJ-72O7ypn8ZxuoAUELg" },
  { "id": "C158-VictorianoFaces", "name": "Victoriano Faces", "seg": "Estética", "sheet_id": "12dTGJBLDOdxxPAX0WJJR7R6Zhu_NtZ9xX19VsUvdK8A" },
  { "id": "C172-DrCaioFigueira", "name": "Dr. Caio Figueira", "seg": "Saúde", "sheet_id": "1biD55AqQuFQZJlSnUyGvrg3DwKWD-8fLSl5bt2fJiEM" },
  { "id": "C169-DrKeeynerCorrea", "name": "Dr. Keeyner Correa", "seg": "Saúde", "sheet_id": "1SmdVcj_MQBpRJXNai8xM9yXW9coOquQEG8HxjDlLbeE" },
  { "id": "C123-OrgulhoSaoVicente", "name": "Orgulho São Vicente", "seg": "Odonto", "sheet_id": "1-Xp3qunysH4vw8jrU8wWW0g8eTzLK2pt4jmoSxMDId0" },
  { "id": "C174-EsteticFaceItapetininga", "name": "Estetic Face Itapetininga", "seg": "Estética", "sheet_id": "18V8FQD8Q5lVSoioIkDjnUKYFqminsQWgIWbuc8ImW9E" },
  { "id": "C123-DrRafaelRocha", "name": "Dr. Rafael Rocha", "seg": "Saúde", "sheet_id": "1iX55z4aFf7CIzLHD0OVGdZCeCWrMfgK-hE_3LLAkfko" },
  { "id": "C123-OrgulhodeSorrirPeruibe", "name": "Orgulho de Sorrir Peruíbe", "seg": "Odonto", "sheet_id": "17_CS-0I470XfX5sQMLAd0jdQJxng4gFCBkO1eaQx8qA" },
  { "id": "C150-Lumia", "name": "Lumia", "seg": "Estética", "sheet_id": "1fVoRc627ZhHEBKFIGuGvvtiMDBrO_2D3Wp2mWZlH3Go" },
  { "id": "C171-DraStefaniRezende", "name": "Dra. Stefani Rezende", "seg": "Saúde", "sheet_id": "16A--MHKp8IBoZKHGQD21LFN-7WUVL2m_BcZmu0UdEXg" },
  { "id": "C163-AcessoSaudeCIC", "name": "Acesso Saúde CIC", "seg": "Saúde", "sheet_id": "1SuyRNdYrGZXtBFmB0-Hv91ZICa7geeFHx6Ayiz7jU08" },
  { "id": "C149-ClinicaGGlow", "name": "Clínica Glow", "seg": "Estética", "sheet_id": "1zOwuPWh_g2fLHyfmBfHl1RIPYznzGdf7yGidGnq9qN0" },
  { "id": "C52-DrLucasPitao", "name": "Dr. Lucas Pitão", "seg": "Saúde", "sheet_id": "1ssM8yBQsSpby-y7FXqs8NmWAAjzsfigxhR4P4J7mfys" },
  { "id": "C135-DraMichelleSantos", "name": "Dra. Michelle Santos", "seg": "Saúde", "sheet_id": "1pQpLfdt9gCHoRekLRpqFk9pwW2V51ksCN_NTJd1G_zY" },
  { "id": "C170-DraMariaEduarda", "name": "Dra. Maria Eduarda", "seg": "Saúde", "sheet_id": "1eHv46erWBLB3w8zg5xP5oN_TWftJ6ELgJZzOlYVVbOY" },
  { "id": "C173-OdontoPrime", "name": "Odonto Prime", "seg": "Odonto", "sheet_id": "1wGjMuOTYoIwu9F2wI8atQQaMeLy3iMqaW4gOx2nqM-k" },
  { "id": "C63-DrRaphaelMoreira", "name": "Dr. Raphael Moreira", "seg": "Saúde", "sheet_id": "1hnJ7rl0Hcy2GcWdh3nMN7s9nhBCtahKsHYiQglAF_JE" },
  { "id": "C123-OrgulhodeSorrirSantos", "name": "Orgulho de Sorrir Santos", "seg": "Odonto", "sheet_id": "1bWYYqtG_2TZ3Zs0r5wkvadSI8gEMAug-9nZUp-jxYuc" },
  { "id": "C124-DraAnnaHOF", "name": "Dra. Anna HOF", "seg": "Saúde", "sheet_id": "1N2oAsy3PJud__z9MBSFrX9wr1AVfw_b-X-YpgDHIdkQ" },
  { "id": "C155-ClinicaElodonto", "name": "Clínica Elodonto", "seg": "Odonto", "sheet_id": "17eesV8xZKnisx9pJo11RndZOcKDwIT6zet8dBfHrPlM" },
  { "id": "C166-Lucasmallmann", "name": "Lucas Mallmann", "seg": "Saúde", "sheet_id": "1t4KLQdv9bjYcftwMw81rn-WvMs0NW92omQLWR_MkiF4" },
  { "id": "C136-IntegrareOdontologia", "name": "Integrar Odontologia", "seg": "Odonto", "sheet_id": "1TEuyWftgK9iM2rINKEeg-xTAZGVFxibmWZpokn6XCEc" },
  { "id": "C157-DraCristianeTiburtino", "name": "Dra. Cristiane Tiburtino", "seg": "Saúde", "sheet_id": "1bM8T1h-gAZdbOgjWQqkFoJPU_vODLI-ObIt9OtTLGic" },
  { "id": "EsteticaLosAngelesLeads", "name": "Estética Los Angeles", "seg": "Estética", "sheet_id": "1zBcRC0HaV4JXg1Cix-XBl6cZzQ6044oFMhM3NlTZn7E" },
  { "id": "C86-DrWilliamHenrique", "name": "Dr. William Henrique", "seg": "Saúde", "sheet_id": "14Ss2564FyP_SJeXxTI8OI-5n0tRMlchsJJYFJrxRrxY" },
  { "id": "C168-DraMichelleAlves", "name": "Dra. Michelle Alves", "seg": "Saúde", "sheet_id": "1VMbs_ElKqEs0l_OmEgf354Xo4nW5b7IexbpUki_Wtw0" },
  { "id": "C164-DraLea", "name": "Dra. Léa", "seg": "Saúde", "sheet_id": "1hQu7EiDa6hI0Wr7WVdcSBNg2eiaLucOw6P_mDgNkd0Y" },
  { "id": "C140-EspacoBottega", "name": "Espaço Bottega", "seg": "Estética", "sheet_id": "1AAcB8qjEf-NDM36lPTCOuUst7tsACIvfNe4QgsJf_yM" },
  { "id": "C167-AvanteOdontologiaBH", "name": "Avante Odontologia BH", "seg": "Odonto", "sheet_id": "17axePFMIWOUQ3kGJ308w4kptO6PZt_mY9XwjifqozrY" },
  { "id": "C167-AvanteOdontologiaSL", "name": "Avante Odontologia SL", "seg": "Odonto", "sheet_id": "1i5nQbdPOPLIQgUjibXCVZwd4JNuLo_AiKsqWEYNBx8k" },
  { "id": "C141-VictorRios", "name": "Victor Rios", "seg": "Saúde", "sheet_id": "1NQlACxzoHdcjBpH7B2_WDpiMc6uAnznEtiMWHMopHjo" }
]

def parse_excel_date(v):
    if not v: return None
    try:
        f = float(v)
        if 40000 <= f <= 50000:
            return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(f))
    except: pass
    s = str(v).strip()
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        try: return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except: pass
    return None

def fetch_client(c):
    url = f"https://docs.google.com/spreadsheets/d/{c['sheet_id']}/export?format=xlsx"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read()
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            wb_xml = z.read('xl/workbook.xml').decode('utf-8')
            root = ET.fromstring(wb_xml)
            crm_target = None
            for s in root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet'):
                sname = s.attrib.get('name', '')
                if 'Db_CRM' in sname or 'CRM' in sname:
                    crm_target = s.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                    break
            wb_rels = z.read('xl/_rels/workbook.xml.rels').decode('utf-8')
            r_root = ET.fromstring(wb_rels)
            target_path = None
            for r in r_root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                if r.attrib.get('Id') == crm_target:
                    target_path = 'xl/' + r.attrib.get('Target').lstrip('/')
                    break
            if not target_path or target_path not in z.namelist():
                target_path = 'xl/worksheets/sheet1.xml'

            strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                sst_xml = z.read('xl/sharedStrings.xml').decode('utf-8')
                sst_root = ET.fromstring(sst_xml)
                ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                strings = ["".join([t.text or "" for t in si.findall('.//ns:t', ns)]) for si in sst_root.findall('.//ns:si', ns)]

            xml_data = z.read(target_path).decode('utf-8')
            s_root = ET.fromstring(xml_data)
            ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            
            rows = []
            for r in s_root.findall('.//ns:row', ns):
                r_dict = {}
                for cell in r.findall('ns:c', ns):
                    ref = cell.attrib.get('r')
                    col = re.match(r'([A-Z]+)', ref).group(1)
                    t = cell.attrib.get('t')
                    v = cell.find('ns:v', ns)
                    val = v.text if v is not None else None
                    if t == 's' and val is not None and int(val) < len(strings):
                        val = strings[int(val)]
                    r_dict[col] = val
                if any(r_dict.values()):
                    rows.append(r_dict)

            header = rows[0]
            col_agendou = None
            col_compareceu = None
            col_ganhou = None
            for k, v in header.items():
                if not v: continue
                vl = v.lower()
                if 'agendou' in vl or 'agendado' in vl:
                    if not col_agendou: col_agendou = k
                if 'compareceu' in vl:
                    if not col_compareceu: col_compareceu = k
                if 'ganhou' in vl or 'ganha' in vl or 'venda' in vl:
                    if not col_ganhou: col_ganhou = k

            now = datetime.date.today()
            total_leads = len(rows) - 1
            sept_leads = 0
            aug_leads = 0
            today_leads = 0
            agendados = 0
            compareceram = 0
            vendas = 0
            latest_d = None

            for r in rows[1:]:
                # date
                d = None
                for k in ['A', 'G', 'M', 'N', 'AH']:
                    d = parse_excel_date(r.get(k))
                    if d: break
                if not d and r.get('S') and r.get('T'):
                    try: d = datetime.date(int(float(r.get('S'))), int(float(r.get('T'))), int(float(r.get('U', 1))))
                    except: pass

                if d:
                    if not latest_d or d > latest_d: latest_d = d
                    if d.year == now.year and d.month == now.month:
                        sept_leads += 1
                        if d.day == now.day: today_leads += 1
                    elif d.year == now.year and d.month == (now.month - 1):
                        aug_leads += 1

                # Funnel
                ag = str(r.get(col_agendou) or '').strip().lower()
                cp = str(r.get(col_compareceu) or '').strip().lower()
                gh = str(r.get(col_ganhou) or '').strip().lower()
                st = str(r.get('F') or '').strip().lower()

                if 'agendad' in ag or (ag and ag not in ['não agendado', 'nao agendado', 'não', 'nao', '0', '0.0', 'false', 'n/a', 'em atendimento']) or 'agendad' in st:
                    agendados += 1
                if 'compareceu' in cp or 'sim' in cp:
                    compareceram += 1
                if 'ganh' in gh or 'vend' in gh or 'sim' in gh:
                    vendas += 1

            # Status logic
            if c['id'] in ['C86-DrWilliamHenrique', 'C157-DraCristianeTiburtino', 'EsteticaLosAngelesLeads', 'C136-IntegrareOdontologia']:
                status = "descon"
                statusText = "🔴 WhatsApp Off"
            elif sept_leads > 10 or today_leads > 0:
                status = "alta"
                statusText = "🟢 Alta Tração"
            elif sept_leads > 0:
                status = "mod"
                statusText = "🟡 Moderado"
            else:
                status = "pausado"
                statusText = "⚪ Sem Leads"

            tx_ag = round((agendados / total_leads * 100), 1) if total_leads > 0 else 0
            tx_cp = round((compareceram / agendados * 100), 1) if agendados > 0 else 0
            tx_vd = round((vendas / compareceram * 100), 1) if compareceram > 0 else 0

            return {
                "id": c['id'],
                "name": c['name'],
                "seg": c['seg'],
                "total": total_leads,
                "set": sept_leads,
                "ago": aug_leads,
                "hoje": today_leads,
                "ult": latest_d.strftime("%d/%m/%Y") if latest_d else "—",
                "status": status,
                "statusText": statusText,
                "agendados": agendados,
                "tx_agend": tx_ag,
                "comp": compareceram,
                "tx_comp": tx_cp,
                "vendas": vendas,
                "tx_venda": tx_vd
            }
    except Exception as e:
        return {
            "id": c['id'],
            "name": c['name'],
            "seg": c['seg'],
            "total": 0, "set": 0, "ago": 0, "hoje": 0, "ult": "—",
            "status": "erro", "statusText": "🔒 Erro/Permissão",
            "agendados": 0, "tx_agend": 0, "comp": 0, "tx_comp": 0, "vendas": 0, "tx_venda": 0
        }

def sync():
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando sincronização diária de {len(CLIENTS)} clientes...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch_client, CLIENTS))

    # sort by september leads
    results.sort(key=lambda x: (x['set'], x['hoje']), reverse=True)

    html_path = os.path.join(REPO_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # replace DATA = [...];
    data_json = json.dumps(results, ensure_ascii=False)
    html = re.sub(r'const DATA = \[.*?\];', f'const DATA = {data_json};', html, flags=re.DOTALL)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Git commit & push
    try:
        subprocess.run(["git", "add", "index.html"], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "commit", "-m", f"chore: Atualização automática diária - {datetime.date.today().strftime('%d/%m/%Y')}"], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        print("✓ Git commit e push concluídos com sucesso. Vercel atualizada!")
    except Exception as e:
        print(f"Aviso git: {e}")

    tot_leads = sum(r['total'] for r in results)
    tot_set = sum(r['set'] for r in results)
    tot_hoje = sum(r['hoje'] for r in results)
    tot_ag = sum(r['agendados'] for r in results)
    tot_cp = sum(r['comp'] for r in results)
    tot_vd = sum(r['vendas'] for r in results)

    print("\n--- RESUMO DO DIA ---")
    print(f"Total Leads Base: {tot_leads:,}")
    print(f"Leads Mês: {tot_set:,} | Leads Hoje: {tot_hoje}")
    print(f"Agendados: {tot_ag:,} | Compareceram: {tot_cp:,} | Vendas Fechadas: {tot_vd:,}")

if __name__ == "__main__":
    sync()
