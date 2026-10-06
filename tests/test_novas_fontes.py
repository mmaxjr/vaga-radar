from datetime import date

from vagas.models import Job
from vagas.profile import Perfil
from vagas.sources import coodesh, trampos
from vagas.top import agrupar

ITENS = [
    {"id": 1, "name": "Analista de Infra", "category_slug": "ti", "home_office": True, "hybrid": False,
     "company": {"name": "ACME"}, "city": "Maringá", "published_at": "2026-10-05T10:03:29.000-03:00"},
    {"id": 2, "name": "Analista de Dados", "category_slug": "dados", "home_office": None, "hybrid": False, "company": None,
     "custom_company_name": "Beta", "published_at": "2026-10-05T09:00:00.000-03:00"},       # presencial: fora
    {"id": 3, "name": "Social Media", "category_slug": "social-media", "home_office": True, "hybrid": False,
     "company": {"name": "Gama"}, "published_at": "2026-10-05T08:00:00.000-03:00"},          # outra área: fora
]


def test_trampos_so_ti_e_dados_com_home_office():
    jobs = trampos.parse(ITENS)
    assert [(j.title, j.company, j.url) for j in jobs] == [("Analista de Infra", "ACME", "https://trampos.co/oportunidades/1")]
    assert jobs[0].source == "trampos" and jobs[0].scope == "remoto" and jobs[0].posted.startswith("2026-10-05")


PAGINA = """<html><head><meta property="og:title" content="Dev Python | FEATCODE LTDA"/></head><body>
<div>Full-Stack</div><div>Categoria</div><div>PJ</div><div>Tipo de Contratação</div>
<div>{local}</div><div>Localidade</div><div>Descrição:</div><div>Publicada: 25/07/2026</div><div>Python e AWS</div></body></html>"""


def test_coodesh_le_titulo_empresa_e_localidade_da_pagina():
    job = coodesh.parse(PAGINA.format(local="Remota"), "https://coodesh.com/jobs/dev-python-1")
    assert (job.title, job.company, job.posted) == ("Dev Python", "FEATCODE LTDA", "2026-07-25")
    assert job.source == "coodesh" and job.tags == ["PJ"]
    assert coodesh.parse(PAGINA.format(local="São Paulo, SP"), "https://coodesh.com/jobs/dev-python-2") is None


class SemTexto:
    def obter(self, job):
        return None


def test_grupos_separam_maringa_python_infra_e_outras():
    perfil = Perfil({"python": 3, "zabbix": 4}, [], {"padrao": "Completo"}, "intermediário", 10)

    def vaga(titulo, url, **kw):
        return Job(source="gupy", title=titulo, company=titulo, url=url, posted="2026-10-05", **kw)
    jobs = [vaga("Analista Zabbix Maringá", "1", scope="local"), vaga("Desenvolvedor Python", "2"),
            vaga("Analista de Redes", "3"), vaga("Analista de Marketing TI", "4")]
    grupos = agrupar(jobs, perfil, SemTexto(), n=5, pool=10, hoje=date(2026, 10, 6))
    assert {nome: [i.job.url for i in itens] for nome, itens in grupos.items()} == {
        "MARINGÁ": ["1"], "PYTHON / PROGRAMAÇÃO": ["2"], "REDES, INFRA E SEGURANÇA": ["3"], "OUTRAS": ["4"]}
