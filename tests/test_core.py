import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vagas.filters import JobFilter
from vagas.models import Job, canonical_url
from vagas.notify import format_digest
from vagas.sources import linkedin, programathor
from vagas.store import Store

CFG = tomllib.loads((Path(__file__).parent.parent / "config.toml").read_text(encoding="utf-8"))
FLT = JobFilter(CFG)


def job(title, **kw):
    return Job(source="t", title=title, url=kw.pop("url", "https://x.com/" + title.replace(" ", "-")), **kw)


def test_aceita_areas_pedidas():
    for t in ["Analista de Infraestrutura Pleno", "Engenheiro DevOps", "Analista de Redes Sr",
              "Analista de Segurança da Informação", "Desenvolvedor Backend Python", "Analista de SOC III",
              "Cloud Security Engineer", "Pentester - Pentest"]:
        assert FLT.accepts(job(t)), t


def test_rejeita_outras_areas():
    for t in ["Engenheiro Civil", "Técnico de Segurança do Trabalho", "Vendedor Comercial",
              "Estagiário de TI", "Assistente Administrativo", "Vigilante Patrimonial"]:
        assert not FLT.accepts(job(t)), t


def test_palavra_curta_so_casa_inteira():
    assert not FLT.accepts(job("Gerente de Vendas Goiás Diversos"))  # "go" dentro de "Goiás"
    assert FLT.accepts(job("Desenvolvedor Go Sênior"))


def test_internacional_exige_regiao_compativel():
    assert FLT.accepts(job("Backend Engineer", international=True, location="Worldwide"))
    assert FLT.accepts(job("Backend Engineer", international=True, location=""))
    assert not FLT.accepts(job("Backend Engineer", international=True, location="USA Only"))


def test_vaga_antiga_e_descartada():
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    assert not FLT.accepts(job("Desenvolvedor Python", posted=old))
    assert FLT.accepts(job("Desenvolvedor Python", posted=datetime.now(timezone.utc).isoformat()))


def test_url_canonica_ignora_rastreamento():
    assert canonical_url("https://a.com/v/1?refId=x&trk=y#z") == "https://a.com/v/1"
    a = job("X", url="https://a.com/v/1?refId=1")
    b = job("X", url="https://a.com/v/1?refId=2")
    assert a.id == b.id


def test_store_deduplica_e_persiste(tmp_path):
    path = tmp_path / "jobs.json"
    store = Store(path)
    assert len(store.add_new([job("A dev"), job("A dev")])) == 1
    store.save()
    assert store.add_new([job("A dev")]) == []
    assert len(Store(path).jobs) == 1


def test_digest_respeita_limite_do_telegram_e_escapa_html():
    jobs = [job(f"Dev <b>{i}</b> & cia", company="X" * 80) for i in range(300)]
    msgs = format_digest(jobs, max_items=200)
    assert all(len(m) <= 4096 for m in msgs)
    assert "<b>0</b>" not in "".join(msgs).replace("<b>300 vagas", "")  # título escapado
    assert "+100 vagas" in msgs[-1]


def test_parse_linkedin():
    html = """<ul><li><div class="base-card base-search-card job-search-card">
      <a class="base-card__full-link" href="https://br.linkedin.com/jobs/view/dev-1?refId=z"></a>
      <h3 class="base-search-card__title"> Dev Python </h3>
      <h4 class="base-search-card__subtitle"><a>ACME</a></h4>
      <span class="job-search-card__location">Brasil</span>
      <time datetime="2026-09-28">ontem</time></div></li></ul>"""
    (j,) = linkedin.parse(html)
    assert (j.title, j.company, j.url, j.posted) == (
        "Dev Python", "ACME", "https://br.linkedin.com/jobs/view/dev-1", "2026-09-28")


def test_programathor_ignora_vaga_vencida():
    def cell(title):
        return f"""<div class="cell-list"><a href="/jobs/1-x"><h3>{title}</h3>
          <div class="cell-list-content-icon"><span>Empresa</span><span>Remoto</span></div></a></div>"""
    jobs = programathor.parse(cell("Vencida Dev Antigo") + cell("Dev Novo"))
    assert [j.title for j in jobs] == ["Dev Novo"]


def test_site_esconde_fontes_pedidas(tmp_path):
    import json
    import shutil

    from vagas.site import render_site

    docs = tmp_path / "docs"
    docs.mkdir()
    shutil.copy(Path(__file__).parent.parent / "docs" / "template.html", docs / "template.html")
    jobs = [job("Dev A", url="https://a.com/1").to_dict(), job("Dev B", url="https://b.com/2").to_dict()]
    jobs[1]["source"] = "linkedin"
    (docs / "jobs.json").write_text(json.dumps({"updated": "2026-01-01T00:00:00+00:00", "jobs": jobs}))
    html = render_site(docs / "jobs.json", frozenset({"linkedin"})).read_text(encoding="utf-8")
    assert "Dev A" in html and "Dev B" not in html


def test_linkedin_exige_prova_de_remoto():
    ok = Job(source="linkedin", title="Dev Python - Trabalho Remoto", url="https://l.com/1", location="Curitiba")
    presencial = Job(source="linkedin", title="Analista de Redes - BH", url="https://l.com/2", location="Belo Horizonte")
    gupy = Job(source="gupy", title="Analista de Redes", url="https://g.com/3", location="")
    assert FLT.accepts(ok)
    assert not FLT.accepts(presencial)
    assert FLT.accepts(gupy)  # fontes que já filtram por remoto seguem confiáveis


def test_parse_geekhunter():
    import json as _json
    from datetime import datetime, timezone

    from vagas.sources import geekhunter

    u1 = "https://www.geekhunter.com/pt/ntt-data/jobs/devops---sre-pleno--1"
    u2 = "https://www.geekhunter.com/pt/acme-2/jobs/analista-de-redes-1"
    ld = _json.dumps({"itemListElement": [
        {"@type": "ListItem", "url": u1, "name": "Devops - SRE Pleno"},
        {"@type": "ListItem", "url": u2, "name": "Analista de Redes"}]})
    filler = "Tarefas e Responsabilidades configurar e manter a infraestrutura de rede da empresa"
    html = f"""<script id="itemList" type="application/ld+json">{ld}</script>
      <div><a href="{u1}">x</a><p>Publicada há 3 dias Devops - SRE Pleno Pleno Remoto {filler}</p></div>
      <div><a href="{u2}">y</a><p>Publicada há 1 hora Analista de Redes Pleno São Paulo {filler}</p></div>"""
    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    # os <a> ficam no mesmo bloco do texto do cartão: coloca o texto dentro do <a>
    html = html.replace(f'<a href="{u1}">x</a><p>', f'<a href="{u1}"><p>').replace("</p></div>", "</p></a></div>")
    jobs = geekhunter.parse(html, now)
    assert [j.title for j in jobs] == ["Devops - SRE Pleno"]  # o cartão sem "Remoto" é descartado
    j = jobs[0]
    assert (j.company, j.location, j.tags) == ("Ntt Data", "Remoto", ["Pleno"])
    assert j.posted.startswith("2026-09-26T12:00")


def test_vaga_local_vale_em_qualquer_regime():
    presencial = Job(source="gupy", scope="local", title="Analista de Infraestrutura", url="https://g.com/9",
                     location="Maringá · presencial")
    remota_presencial = Job(source="gupy", scope="remoto", title="Analista de Infraestrutura", url="https://g.com/8",
                            location="", international=True)
    assert FLT.accepts(presencial)
    # vaga internacional sem região compatível continua barrada quando o escopo é remoto
    remota_presencial.location = "USA Only"
    assert not FLT.accepts(remota_presencial)
    linkedin_presencial = Job(source="linkedin", scope="local", title="Analista de Redes", url="https://l.com/5",
                              location="Maringá, PR")
    assert FLT.accepts(linkedin_presencial)  # sem "remoto" no título, mas é da sua cidade


def test_fonte_local_filtra_cidade_e_marca_regime(monkeypatch):
    from vagas.sources import local

    class R:
        def __init__(self, data): self._d = data
        def json(self): return self._d

    gupy_data = {"data": [
        {"name": "Analista de Redes", "jobUrl": "https://g.com/1", "careerPageName": "ACME", "city": "Maringá",
         "workplaceType": "hybrid", "publishedDate": "2026-09-28"},
        {"name": "Analista de Redes", "jobUrl": "https://g.com/2", "careerPageName": "BETA", "city": "Londrina",
         "workplaceType": "on-site", "publishedDate": "2026-09-28"}], "pagination": {"total": 2}}
    monkeypatch.setattr(local.http, "get", lambda url, **kw: R(gupy_data) if "gupy" in url else None)
    cfg = {"local": {"enabled": True, "city": "Maringá", "state": "Paraná", "cities": ["Maringá"], "terms": ["redes"]}}
    jobs = local.fetch(cfg)
    assert [(j.company, j.location, j.scope) for j in jobs] == [("ACME", "Maringá · híbrido", "local")]
    assert local.fetch({"local": {"enabled": False}}) == []


class _Resp:
    def __init__(self, data): self._d = data
    def json(self): return self._d


def test_companies_greenhouse_e_lever_so_aceitam_remoto(monkeypatch):
    from vagas.sources import companies

    gh = {"jobs": [
        {"title": "Linux Support Engineer", "absolute_url": "https://g.io/c/1", "company_name": "Canonical",
         "location": {"name": "Home based - Worldwide"}, "first_published": "2026-09-01T10:00:00-04:00"},
        {"title": "Analista de Infraestrutura", "absolute_url": "https://g.io/c/2", "company_name": "Canonical",
         "location": {"name": "São Paulo, Brazil"}, "first_published": "2026-09-01T10:00:00-04:00"}]}
    lever = [{"text": "SRE", "hostedUrl": "https://l.co/x/1", "workplaceType": "remote", "createdAt": 1790000000000,
              "categories": {"location": "Brazil", "team": "Infra"}},
             {"text": "SRE Presencial", "hostedUrl": "https://l.co/x/2", "workplaceType": "onsite", "categories": {}}]
    monkeypatch.setattr(companies.http, "get", lambda url, **kw: _Resp(gh if "greenhouse" in url else lever))
    jobs = companies.fetch({"companies": {"greenhouse": ["canonical"], "lever": ["acme"]}})
    assert [(j.title, j.international) for j in jobs] == [("Linux Support Engineer", True), ("SRE", False)]
    assert jobs[0].company == "Canonical" and jobs[1].tags == ["Infra"]
    # a região é decidida pelo filtro geral: worldwide passa, "Home based - EMEA" não
    assert FLT.accepts(jobs[0])
    assert not FLT.accepts(Job(source="x", title="Linux Engineer", url="https://x/9",
                               location="Home based - EMEA", international=True))


def test_parse_infojobs():
    from vagas.sources import infojobs

    card = """<div class="js_rowCard" data-href="/vaga-de-analista-x__1.aspx"><div class="js_date" data-value="2026/09/29 02:57:00"></div>
      <h2> Analista de Segurança da Informação </h2><a href="/empresa-acme__-1.aspx"><span>ACME</span></a>
      <div class="mb-8">Curitiba - PR<span hidden>, 5 Km</span></div>R$ 5.000,00 Home Office Ensino Superior</div>"""
    presencial = card.replace("__1", "__2").replace("Home Office", "Presencial")
    jobs = infojobs.parse(card + card + presencial + '<div class="js_rowCard"><h2>anúncio</h2></div>')
    assert len(jobs) == 2  # duplicado e anúncio sem link descartados
    j = jobs[0]
    assert (j.company, j.location, j.salary) == ("ACME", "Curitiba - PR · home office", "R$ 5.000,00")
    assert j.posted.startswith("2026-09-29T02:57") and j.url.endswith("/vaga-de-analista-x__1.aspx")
    assert jobs[1].location.endswith("presencial")


def test_jobicy_e_himalayas(monkeypatch):
    from vagas.sources import himalayas, jobicy

    monkeypatch.setattr(jobicy.time, "sleep", lambda s: None)
    monkeypatch.setattr(himalayas.time, "sleep", lambda s: None)
    jb = {"jobs": [{"url": "https://jobicy.com/jobs/1", "jobTitle": "DevOps Engineer", "companyName": "Acme",
                    "jobGeo": "LATAM", "pubDate": "2026-09-21 09:35:21", "salaryMin": "1000", "salaryMax": "2000",
                    "salaryCurrency": "USD", "salaryPeriod": "monthly"}]}
    monkeypatch.setattr(jobicy.http, "get", lambda url, **kw: _Resp(jb))
    (j,) = jobicy.fetch({"jobicy": {"geos": ["brazil"], "tags": ["devops", "sre"]}})  # mesma vaga em 2 buscas
    assert (j.location, j.posted, j.international) == ("LATAM", "2026-09-21T09:35:21", True)
    assert j.salary == "USD 1,000-2,000/mon"

    hm = {"jobs": [
        {"title": "SRE", "companyName": "A", "guid": "https://h.app/1", "locationRestrictions": ["Brazil", "Chile"],
         "pubDate": 1790000000, "seniority": ["Senior"]},
        {"title": "SRE US", "companyName": "B", "guid": "https://h.app/2", "locationRestrictions": ["United States"]},
        {"title": "SRE global", "companyName": "C", "guid": "https://h.app/3", "locationRestrictions": []}]}
    monkeypatch.setattr(himalayas.http, "get", lambda url, **kw: _Resp(hm))
    jobs = himalayas.fetch({"himalayas": {"queries": ["sre"]}})
    assert [j.title for j in jobs] == ["SRE", "SRE global"]  # a que exclui o Brasil fica de fora
    assert jobs[0].tags == ["Senior"] and jobs[1].location == "Global"


def test_parse_empregare():
    from datetime import datetime, timedelta, timezone

    from vagas.sources import empregare

    def card(slug, title, regime, date="ter., 29/setembro"):
        return f"""<a href="/pt-br/vaga-{slug}"><article class="card card-vaga">
          <p class="card-vaga-empresa">ACME</p><small class="texto-data-card">{date}</small>
          <p class="titulo-vaga">{title}</p><p class="card-cidades"><span></span> Maringá, PR, BR</p>
          <ul><li><small>{regime}</small></li></ul>R$ 8.000,00</article></a>"""

    today = datetime(2026, 9, 29, 15, 0, tzinfo=timezone(timedelta(hours=-3)))
    html = (card("a_1", "Analista de Redes", "Totalmente Remoto") + card("b_2", "Analista de TI", "Presencial", "dom., 30/dezembro")
            + '<a href="/pt-br/x"><p>sem cartão</p></a>')
    remoto, presencial = empregare.parse(html, today)
    assert (remoto.company, remoto.location, remoto.salary) == ("ACME", "Maringá, PR · totalmente remoto", "R$ 8.000,00")
    assert remoto.posted.startswith("2026-09-29") and remoto.url == "https://www.empregare.com/pt-br/vaga-a_1"
    assert presencial.location == "Maringá, PR · presencial"
    so_remoto = empregare.parse(card("c_3", "Dev", "Totalmente Remoto").replace("Maringá, PR, BR", "Totalmente Remoto"), today)
    assert so_remoto[0].location == "Totalmente Remoto"  # não repete o regime
    assert presencial.posted.startswith("2025-12-30")  # 30/dezembro no futuro = ano passado


def test_funcoes_proximas_agora_passam():
    for t in ["IT Support Engineer", "Analista de Suporte Técnico Pleno", "Systems Administrator", "Help Desk N2",
              "Analista de Sistemas", "Engenheiro de Dados", "Analista de QA", "Técnico em Telecom"]:
        assert FLT.accepts(job(t)), t
    for t in ["Engenheiro de Produção", "Contest Manager", "Analista de Vendas TI"]:
        assert not FLT.accepts(job(t)), t


def test_needs_proof_e_assume_remote():
    sem_prova = Job(source="linkedin", title="Analista de Redes Pleno", url="https://l.com/7", location="Curitiba")
    assert FLT.needs_proof(sem_prova) and not FLT.accepts(sem_prova)
    assert FLT.accepts(sem_prova, assume_remote=True)  # descrição confirmou o remoto
    com_prova = Job(source="linkedin", title="Analista de Redes - Remoto", url="https://l.com/8", location="Brasil")
    assert not FLT.needs_proof(com_prova) and FLT.accepts(com_prova)
    assert not FLT.needs_proof(Job(source="gupy", title="Analista de Redes", url="https://g.com/4"))


def test_verificacao_le_a_descricao():
    from vagas import verify

    assert verify.is_remote_text("Esta vaga é 100% remota. Atuação em home office.") is True
    assert verify.is_remote_text("Trabalho remoto, com encontros presenciais mensais.") is False  # cita presencial
    assert verify.is_remote_text("Monitoramento remoto de servidores e acesso remoto via VPN.") is False  # não é regime
    assert verify.is_remote_text("Fully remote role. Hybrid model with 2 days in office.") is False  # regime híbrido: descarta
    assert verify.is_remote_text("Vaga 100% remota. Experiência em nuvem híbrida e ambientes híbridos.") is True  # híbrido = tecnologia
    assert verify.is_remote_text("Auxílio home office. Vaga em Porto Alegre. Work from Anywhere policy.") is False  # só benefícios


def test_verify_check_para_no_bloqueio(monkeypatch):
    from vagas import verify

    textos = {"a": "Trabalho remoto 100% remoto.", "b": "Vaga presencial em Maringá.", "c": None, "d": "home office"}
    monkeypatch.setitem(verify.TEXT_FETCHERS, "linkedin", lambda j: textos[j.title])
    monkeypatch.setattr(verify.time, "sleep", lambda s: None)
    jobs = [Job(source="linkedin", title=t, url=f"https://l.com/{t}") for t in "abcd"]
    ok, no = verify.check(jobs, limit=10, delay=0)
    assert [j.title for j in ok] == ["a"] and [j.title for j in no] == ["b"]  # parou em "c" (bloqueio); "d" fica para depois


def test_store_lembra_descartadas(tmp_path):
    path = tmp_path / "jobs.json"
    store = Store(path)
    velha, nova = job("Dev A", url="https://a.com/1"), job("Dev B", url="https://b.com/2")
    store.reject([velha])
    store.add_new([nova])
    store.save()
    again = Store(path)
    assert again.is_known(velha) and again.is_known(nova) and not again.is_known(job("Dev C", url="https://c.com/3"))


def test_jobicy_uma_falha_nao_derruba_as_demais(monkeypatch):
    from vagas.sources import jobicy

    monkeypatch.setattr(jobicy.time, "sleep", lambda s: None)
    respostas = iter([None, _Resp({"jobs": [{"url": "https://jobicy.com/jobs/9", "jobTitle": "SRE", "jobGeo": "LATAM"}]}), None])
    monkeypatch.setattr(jobicy.http, "get", lambda url, **kw: next(respostas))
    jobs = jobicy.fetch({"jobicy": {"geos": ["brazil"], "tags": ["a", "b", "c"]}})
    assert [j.title for j in jobs] == ["SRE"]  # o 400 do primeiro tag não impediu o segundo


def test_parse_zohorecruit():
    import html as _html
    import json as _json

    from vagas.sources import zohorecruit

    data = [
        {"Remote_Job": True, "Posting_Title": "Profissional Red Team ", "City": None, "id": "111", "Date_Opened": "2026-06-21", "Publish": True},
        {"Remote_Job": False, "Posting_Title": "Analista de Redes", "City": "Maringá", "id": "222", "Date_Opened": "2026-09-01", "Publish": True},
        {"Remote_Job": False, "Posting_Title": "Analista de Redes", "City": "Vitória", "id": "333", "Date_Opened": "2026-09-01", "Publish": True},
        {"Remote_Job": True, "Posting_Title": "Rascunho", "City": None, "id": "444", "Publish": False},
    ]
    page = '<input type="hidden" value="' + _html.escape(_json.dumps(data), quote=True).replace("&quot;", "&#34;") + '">'
    remoto, aqui = zohorecruit.parse(page, "spassu", {"maringa"})
    assert (remoto.scope, remoto.location, remoto.title) == ("remoto", "Remoto", "Profissional Red Team")
    assert remoto.url == "https://spassu.zohorecruit.com/jobs/Careers/111/Profissional-Red-Team"
    assert remoto.posted == "" and remoto.tags == ["aberta em 2026-06-21"]  # sem data de publicação: não é cortada por idade
    assert FLT.accepts(remoto)  # vaga aberta há meses ainda passa (Red Team)
    assert (aqui.scope, aqui.location) == ("local", "Maringá")
    assert zohorecruit.parse(page, "spassu", set()) == [remoto]  # sem cidade configurada: só as remotas
    assert zohorecruit.parse("<html></html>", "spassu") == []
