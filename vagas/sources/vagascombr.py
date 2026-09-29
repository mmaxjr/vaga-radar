"""Vagas.com.br"""
from __future__ import annotations

import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .. import http
from ..models import Job

BASE = "https://www.vagas.com.br"
REMOTE = re.compile(r"remot|home ?office", re.I)


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    for term in cfg["search"]["terms"]:
        slug = quote(term.lower().replace(" ", "-"))
        for page in (1, 2):
            r = http.get(f"{BASE}/vagas-de-{slug}", params={"ordenar_por": "mais_recentes", "pagina": page})
            if r is None:
                break
            found = parse(http.decode(r))
            jobs.extend(found)
            if not found:
                break
    return [j for j in jobs if REMOTE.search(j.title + " " + j.location + " " + " ".join(j.tags))]


def parse(html: str) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    for li in soup.select("li.vaga"):
        a = li.select_one("a.link-detalhes-vaga")
        if not a:
            continue
        company = li.select_one(".emprVaga")
        place = li.select_one(".vaga-local")
        detail = li.select_one(".detalhes")
        jobs.append(Job(
            source="vagas.com.br",
            title=a.get("title") or a.get_text(strip=True),
            url=BASE + a["href"],
            company=company.get_text(strip=True) if company else "",
            location=" ".join(place.get_text().split()) if place else "",
            tags=[detail.get_text(" ", strip=True)[:300]] if detail else [],
        ))
    return jobs
