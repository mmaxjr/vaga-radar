"""Sólides Vagas (vagas.solides.com.br).

A própria página do site busca as vagas em /api/vacancies, no mesmo endereço do portal (o robots.txt libera tudo). O
parâmetro `jobsType=remoto` já filtra o regime, então o regime vem provado pela fonte. Sem navegador e sem login. O site
só aceita 14 vagas por página (take maior dá erro 500) e devolve da mais nova para a mais antiga."""
from __future__ import annotations

import time
from datetime import date

from .. import http
from ..models import Job

API = "https://vagas.solides.com.br/api/vacancies"
DELAY = 0.8  # pausa entre pedidos, para não sobrecarregar o site


def fetch(cfg: dict) -> list[Job]:
    sc = cfg.get("solides", {})
    jobs: dict[str, Job] = {}
    for term in sc.get("terms", cfg["search"]["terms"]):
        for page in range(1, sc.get("pages", 1) + 1):
            r = http.get(API, params={"page": page, "take": 14, "jobsType": "remoto", "title": term, "locations": ""})
            if r is None:
                break
            dados = r.json()
            for job in parse(dados.get("data", [])):
                jobs.setdefault(job.url, job)
            time.sleep(DELAY)
            if page >= dados.get("totalPages", 1):
                break
    return list(jobs.values())


def parse(itens: list[dict]) -> list[Job]:
    """Só vagas remotas, abertas a todos (sem as exclusivas PcD ou afirmativas), ainda no prazo e com página pública
    (as "externas" têm código alfanumérico e a página delas não abre)."""
    jobs = []
    hoje = date.today().isoformat()
    for it in itens:
        if it.get("jobType") != "remoto" or it.get("pcdOnly") or it.get("affirmative") or not str(it["id"]).isdigit():
            continue
        if ((it.get("date") or {}).get("due") or "9999") < hoje:
            continue
        nomes = lambda campo: [x["name"] for x in it.get(campo) or []]  # noqa: E731
        cidade = (it.get("city") or {}).get("name", "")
        uf = (it.get("state") or {}).get("code", "")
        jobs.append(Job(
            source="solides",
            title=it["title"].strip(),
            url=f"https://vagas.solides.com.br/vaga/{it['id']}",
            company=it.get("companyName", ""),
            location=f"{cidade} - {uf}".strip(" -"),
            posted=it.get("createdAt", ""),
            tags=nomes("recruitmentContractType") + nomes("seniority"),
        ))
    return jobs
