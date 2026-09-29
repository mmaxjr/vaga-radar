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
