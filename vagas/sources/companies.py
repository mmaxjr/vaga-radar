"""Vagas direto das empresas, pelas APIs públicas de quadro de vagas (Greenhouse e Lever).

São as APIs oficiais que as próprias empresas usam nas páginas de carreira: estáveis e sem raspagem de HTML.
Só entra vaga que se declare remota (local com "remote", "home based", "worldwide"... ou, no Lever, o campo
workplaceType == "remote"); a região é checada pelo filtro geral (Brasil, LATAM, Americas, worldwide).

Sem data de publicação de propósito: as APIs só trazem a data de criação, que pode ser antiga para uma
vaga ainda aberta. A vaga está no quadro, então está aberta; "nova" = apareceu pela primeira vez no quadro.

Configuração ([companies] no config.toml): listas de "slugs", a parte do endereço do quadro de vagas.
  Greenhouse: boards.greenhouse.io/<slug>      Lever: jobs.lever.co/<slug>
"""
from __future__ import annotations

import re

from .. import http
from ..filters import REMOTE_WORDS
from ..models import Job

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
LEVER = "https://api.lever.co/v0/postings/{slug}"
BRAZIL = re.compile(r"brazil|brasil", re.I)


def fetch(cfg: dict) -> list[Job]:
    cc = cfg.get("companies", {})
    jobs: list[Job] = []
    for slug in cc.get("greenhouse", []):
        jobs += _greenhouse(slug)
    for slug in cc.get("lever", []):
        jobs += _lever(slug)
    return jobs


def _greenhouse(slug: str) -> list[Job]:
    r = http.get(GREENHOUSE.format(slug=slug))
    if r is None:
        return []
    jobs = []
    for it in r.json().get("jobs", []):
        place = (it.get("location") or {}).get("name", "")
        if not REMOTE_WORDS.search(f"{place} {it['title']}"):
            continue  # sem declarar remoto, não conta (ex.: "São Paulo, Brazil" é escritório)
        jobs.append(Job(
            source=f"empresa:{slug}",
            title=it["title"],
            url=it["absolute_url"],
            company=it.get("company_name") or slug,
            location=place,
            international=not BRAZIL.search(place),
        ))
    return jobs


def _lever(slug: str) -> list[Job]:
    r = http.get(LEVER.format(slug=slug), params={"mode": "json"})
    if r is None:
        return []
    jobs = []
    for it in r.json():
        if it.get("workplaceType") != "remote":
            continue
        cats = it.get("categories") or {}
        place = cats.get("location") or ", ".join(cats.get("allLocations") or [])
        jobs.append(Job(
            source=f"empresa:{slug}",
            title=it["text"],
            url=it["hostedUrl"],
            company=slug.replace("-", " ").title(),
            location=place,
            tags=[t for t in (cats.get("team"), cats.get("commitment")) if t][:2],
            international=not BRAZIL.search(place),
        ))
    return jobs

