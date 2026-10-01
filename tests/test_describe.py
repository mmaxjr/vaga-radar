from vagas import describe
from vagas.describe import Descricoes
from vagas.models import Job


class R:
    def __init__(self, dados):
        self._d = dados

    def json(self):
        return self._d


GUPY = {"data": [
    {"jobUrl": "https://g.gupy.io/job/1?x=1", "description": "<p>Requisitos: AWS</p>", "applicationDeadline": "2026-10-23T00:00:00.000Z"},
    {"jobUrl": "https://g.gupy.io/job/2", "description": "<p>outra</p>", "applicationDeadline": None}]}


def _preparar(monkeypatch, respostas):
    chamadas = []

    def fake_get(url, **kw):
        chamadas.append((url, kw.get("params")))
        return respostas(url)

    monkeypatch.setattr(describe.http, "get", fake_get)
    monkeypatch.setattr(describe.time, "sleep", lambda s: None)
    return chamadas


def test_gupy_busca_casa_pela_url_e_usa_cache_em_disco(tmp_path, monkeypatch):
    chamadas = _preparar(monkeypatch, lambda url: R(GUPY))
    job = Job(source="gupy", title="Analista", url="https://g.gupy.io/job/1?jobBoardSource=x")
    d = Descricoes(tmp_path / "c.json", delay=0, orcamento=5)
    assert d.obter(job) == ("Requisitos: AWS", "2026-10-23")
    assert chamadas[0][1]["workplaceType"] == "remote"
    outra = Descricoes(tmp_path / "c.json", delay=0, orcamento=5)  # nova instância: lê o cache do disco
    assert outra.obter(job) == ("Requisitos: AWS", "2026-10-23")
    assert len(chamadas) == 1


def test_vaga_local_nao_filtra_por_remoto(tmp_path, monkeypatch):
    chamadas = _preparar(monkeypatch, lambda url: R(GUPY))
    job = Job(source="gupy", scope="local", title="Analista", url="https://g.gupy.io/job/2")
    Descricoes(tmp_path / "c.json", delay=0).obter(job)
    assert "workplaceType" not in chamadas[0][1]


def test_orcamento_esgotado_fonte_sem_descricao_e_falha_nao_cacheada(tmp_path, monkeypatch):
    chamadas = _preparar(monkeypatch, lambda url: None)
    gupy = Job(source="gupy", title="A", url="https://g.gupy.io/job/1")
    assert Descricoes(tmp_path / "a.json", delay=0, orcamento=0).obter(gupy) is None  # sem orçamento
    assert not chamadas
    geek = Job(source="geekhunter", title="B", url="https://www.geekhunter.com/pt/x/jobs/b")
    assert Descricoes(tmp_path / "b.json", delay=0, orcamento=3).obter(geek) is None  # robots.txt proíbe
    d = Descricoes(tmp_path / "c.json", delay=0, orcamento=3)
    assert d.obter(gupy) is None and len(chamadas) == 1  # falhou: não grava no cache
    assert d.obter(gupy) is None and len(chamadas) == 2  # tenta de novo (gasta orçamento)
    assert d.orcamento == 1


def test_github_e_greenhouse(tmp_path, monkeypatch):
    def resp(url):
        if "api.github.com" in url:
            return R({"body": "Vaga **remota**. Requisitos: Python"})
        return R({"content": "&lt;p&gt;Linux support &lt;b&gt;engineer&lt;/b&gt;&lt;/p&gt;"})
    chamadas = _preparar(monkeypatch, resp)
    d = Descricoes(tmp_path / "c.json", delay=0)
    gh = Job(source="github:frontendbr", title="Dev", url="https://github.com/frontendbr/vagas/issues/8564")
    assert d.obter(gh) == ("Vaga **remota**. Requisitos: Python", "")
    assert chamadas[0][0].endswith("/repos/frontendbr/vagas/issues/8564")
    emp = Job(source="empresa:canonical", title="Linux", url="https://job-boards.greenhouse.io/canonical/jobs/6448444")
    assert d.obter(emp) == ("Linux support engineer", "")
    assert chamadas[1][0].endswith("/boards/canonical/jobs/6448444")
