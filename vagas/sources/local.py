"""Vagas na sua cidade (config [local]): presencial, híbrido ou remoto.

Diferente das outras fontes, aqui o regime não importa. Cada vaga sai com scope="local" e o regime
no campo `location` (ex.: "Maringá · presencial"), para a página e o resumo não misturarem com as remotas.

Usa Gupy (filtro de cidade da API), Vagas.com.br, InfoJobs e Empregare (busca por cidade) e a busca pública do LinkedIn.
O LinkedIn roda por último: se bloquear, as outras já foram coletadas.
"""
from __future__ import annotations

import time
import unicodedata
from urllib.parse import quote

from .. import http
from ..models import Job
from . import empregare, gupy, infojobs, linkedin, vagascombr

REGIME = {"remote": "remoto", "hybrid": "híbrido", "on-site": "presencial"}


def fetch(cfg: dict) -> list[Job]:
    loc = cfg.get("local", {})
    if not loc.get("enabled", False):
        return []
    jobs = _gupy(loc) + _vagascombr(loc) + _infojobs(loc) + _empregare(loc) + _linkedin(loc)
    cities = {_norm(c) for c in loc.get("cities", [loc.get("city", "")])}
    return [j for j in jobs if any(c in _norm(j.location) for c in cities)]


def _terms(loc: dict) -> list[str]:
    return loc.get("terms", ["ti", "infraestrutura", "redes", "desenvolvedor"])


def _gupy(loc: dict) -> list[Job]:
    jobs = []
    for term in _terms(loc):
        offset = 0
        for _ in range(2):
            r = http.get(gupy.API, params={"jobName": term, "city": loc["city"], "state": loc.get("state", ""),
                                            "limit": gupy.PAGE, "offset": offset})
            if r is None:
                break
            data = r.json()
            for it in data.get("data", []):
                regime = REGIME.get(it.get("workplaceType"), "")
                jobs.append(Job(
                    source="gupy", scope="local", title=it["name"], url=it["jobUrl"],
                    company=it.get("careerPageName", ""),
                    location=f"{it.get('city') or loc['city']} · {regime}".strip(" ·"),
                    posted=it.get("publishedDate", ""),
                ))
            offset += gupy.PAGE
            if offset >= data.get("pagination", {}).get("total", 0):
                break
    return jobs


def _vagascombr(loc: dict) -> list[Job]:
    jobs = []
    slug_city = _norm(loc["city"]).replace(" ", "-")
    for term in _terms(loc):
        slug = quote(_norm(term).replace(" ", "-"))
        r = http.get(f"{vagascombr.BASE}/vagas-de-{slug}-em-{slug_city}", params={"ordenar_por": "mais_recentes"})
        if r is None:
            continue
        for job in vagascombr.parse(http.decode(r)):
            job.scope = "local"
            jobs.append(job)
    return jobs


def _empregare(loc: dict) -> list[Job]:
    jobs = empregare.fetch_city(loc["city"], loc.get("uf", ""), _terms(loc))
    for job in jobs:
        job.scope = "local"
    return jobs


def _infojobs(loc: dict) -> list[Job]:
    jobs = []
    city, uf = _norm(loc["city"]).replace(" ", "-"), loc.get("uf", "").lower()
    for term in _terms(loc):
        slug = "-".join(_norm(term).split())
        r = http.get(f"{infojobs.BASE}/vagas-de-emprego-{slug}-em-{city},-{uf}.aspx")
        if r is None:
            continue
        for job in infojobs.parse(http.decode(r)):
            job.scope = "local"
            jobs.append(job)
    return jobs


def _linkedin(loc: dict) -> list[Job]:
    jobs = []
    place = f"{loc['city']}, {loc.get('state', '')}, Brasil".replace(", ,", ",")
    for term in _terms(loc):
        r = http.get(linkedin.API, params={
            "keywords": term, "location": place,
            "f_TPR": f"r{loc.get('days', 14) * 86400}", "sortBy": "DD", "start": 0,
        }, retries=0)
        time.sleep(loc.get("delay", 2.5))
        if r is None:
            break  # provável bloqueio: devolve o que já temos
        for job in linkedin.parse(http.decode(r)):
            job.scope = "local"
            jobs.append(job)
    return jobs


def _norm(text: str) -> str:
    """Minúsculas e sem acento, para comparar 'Maringá' com 'maringa'."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")
