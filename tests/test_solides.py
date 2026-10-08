from vagas.sources import solides


def vaga(id, titulo, **kw):
    base = {"id": str(id), "title": titulo, "companyName": "ACME", "jobType": "remoto", "createdAt": "2026-10-07",
            "city": {"name": "Maringá"}, "state": {"code": "PR"}, "pcdOnly": False, "affirmative": [],
            "recruitmentContractType": [{"name": "CLT"}], "seniority": [{"name": "Pleno"}], "date": {"due": "2099-01-01"}}
    base.update(kw)
    return base


def test_parse_so_remotas_abertas_a_todos():
    itens = [
        vaga(1, "Analista de Redes "),
        vaga(2, "Analista Presencial", jobType="presencial"),
        vaga(3, "Vaga PcD", pcdOnly=True),
        vaga(4, "Vaga Afirmativa", affirmative=[{"name": "Mulheres"}]),
        vaga("x4wH2E9ESa", "Vaga externa sem página"),
        vaga(5, "Vaga vencida", date={"due": "2020-01-01"}),
    ]
    jobs = solides.parse(itens)
    assert [j.title for j in jobs] == ["Analista de Redes"]
    j = jobs[0]
    assert j.url == "https://vagas.solides.com.br/vaga/1" and j.source == "solides" and j.company == "ACME"
    assert j.posted == "2026-10-07" and j.tags == ["CLT", "Pleno"] and j.scope == "remoto"


def test_fetch_pagina_so_ate_totalPages_e_junta_termos_sem_repetir(monkeypatch):
    chamadas = []

    class R:
        def __init__(self, d):
            self.d = d

        def json(self):
            return self.d

    def fake_get(url, params=None, **kw):
        chamadas.append((params["title"], params["page"]))
        return R({"totalPages": 2, "data": [vaga(7, "Analista de Redes")] if params["page"] == 1 else [vaga(8, params["title"])]})

    monkeypatch.setattr(solides.http, "get", fake_get)
    monkeypatch.setattr(solides.time, "sleep", lambda s: None)
    jobs = solides.fetch({"search": {"terms": ["redes", "noc"]}, "solides": {"pages": 3}})
    assert chamadas == [("redes", 1), ("redes", 2), ("noc", 1), ("noc", 2)]  # nunca passa de totalPages
    assert sorted(j.url.rsplit("/", 1)[-1] for j in jobs) == ["7", "8"]  # a mesma vaga achada por dois termos conta uma vez


def test_descricao_vem_da_lista_da_api(tmp_path, monkeypatch):
    from vagas import describe
    from vagas.describe import Descricoes
    from vagas.models import Job

    class R:
        def json(self):
            return {"data": [{"id": "9", "description": "<p>outra</p>"},
                             {"id": "7", "description": "<p>Requisitos: BGP</p>", "date": {"due": "2026-11-01"}}]}

    monkeypatch.setattr(describe.http, "get", lambda url, **kw: R())
    monkeypatch.setattr(describe.time, "sleep", lambda s: None)
    job = Job(source="solides", title="Analista de Redes", url="https://vagas.solides.com.br/vaga/7")
    assert Descricoes(tmp_path / "c.json", delay=0).obter(job) == ("Requisitos: BGP", "2026-11-01")
