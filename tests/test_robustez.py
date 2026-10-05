import json
from datetime import datetime, timedelta, timezone

from vagas import __main__ as cli
from vagas import describe, http, jsonld
from vagas.describe import Descricoes
from vagas.models import Job
from vagas.store import Store


class Resp:
    def __init__(self, status=200, text=""):
        self.status_code, self.content = status, text.encode()


def test_disjuntor_para_de_pedir_ao_site_que_deu_429(monkeypatch):
    http._blocked.clear()
    chamadas = []

    def fake(url, **kw):
        chamadas.append(url)
        return Resp(429)

    monkeypatch.setattr(http._session, "get", fake)
    assert http.get("https://x.com/a") is None
    assert http.get("https://x.com/b") is None  # mesmo site: nem tenta
    assert chamadas == ["https://x.com/a"]
    monkeypatch.setattr(http._session, "get", lambda url, **kw: Resp(200, "ok"))
    assert http.get("https://outro.com/").content == b"ok"  # outro site segue normal
    http._blocked.clear()


def test_store_guarda_quando_cada_fonte_rodou(tmp_path):
    path = tmp_path / "jobs.json"
    s = Store(path)
    assert s.hours_since_source("linkedin") is None
    s.source_runs["linkedin"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec="seconds")
    s.save()
    assert 2.9 < Store(path).hours_since_source("linkedin") < 3.1


def _cfg(tmp_path, extra=""):
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'[search]\ninclude = ["dev"]\n[storage]\npath = "{(tmp_path / "jobs.json").as_posix()}"\n{extra}',
                   encoding="utf-8")
    return cfg


def test_fonte_com_intervalo_e_pulada_mas_as_outras_rodam(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, '[linkedin]\nmin_hours = 6\n')
    s = Store(tmp_path / "jobs.json")
    s.source_runs["linkedin"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    s.save()
    rodou = []
    monkeypatch.setattr(cli, "collect", lambda c, nomes: rodou.append(nomes) or {n: [] for n in nomes})
    assert cli.main(["--config", str(cfg), "--no-notify", "--sources", "linkedin,gupy"]) == 0
    assert rodou == [["gupy"]]  # linkedin rodou há instantes: fica de fora
    assert cli.main(["--config", str(cfg), "--no-notify", "--sources", "linkedin,gupy", "--force"]) == 0
    assert rodou[1] == ["linkedin", "gupy"]
    assert Store(tmp_path / "jobs.json").hours_since_source("gupy") < 0.1  # a execução ficou registrada


def test_jsonld_le_jobposting_mesmo_com_quebra_de_linha_no_texto():
    pagina = ('<script type="application/ld+json">{"@type":"Organization"}</script>'
              '<script type="application/ld+json">{"@type":"JobPosting","title":"Dev",'
              '"description":"linha 1\nlinha 2","validThrough":"2026-11-01T00:00:00Z"}</script>')
    vaga = jsonld.job_posting(pagina)
    assert vaga["title"] == "Dev" and "linha 2" in vaga["description"]
    assert jsonld.job_posting("<html>sem dados</html>") is None


def test_descricao_via_jsonld_para_jobicy(tmp_path, monkeypatch):
    pagina = ('<script type="application/ld+json">{"@type":"JobPosting","description":"&lt;p&gt;Requisitos: Python&lt;/p&gt;",'
              '"validThrough":"2026-11-01T00:00:00Z"}</script>')
    monkeypatch.setattr(describe.http, "get", lambda url, **kw: Resp(200, pagina))
    monkeypatch.setattr(describe.time, "sleep", lambda s: None)
    job = Job(source="jobicy", title="Dev", url="https://jobicy.com/jobs/1")
    assert Descricoes(tmp_path / "c.json", delay=0).obter(job) == ("Requisitos: Python", "2026-11-01")


def test_json_do_arquivo_nao_muda_de_formato(tmp_path):
    path = tmp_path / "jobs.json"
    Store(path).save()
    assert set(json.loads(path.read_text(encoding="utf-8"))) >= {"updated", "jobs", "rejected"}
