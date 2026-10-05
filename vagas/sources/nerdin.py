"""Nerdin, vagas de TI (nerdin.com.br). O cartão da listagem já traz o regime ("CLT • Pleno • Home Office"),
então só as vagas home office entram. A listagem vem da mais nova para a mais antiga."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import http
from ..models import Job

BASE = "https://www.nerdin.com.br"
REMOTE = re.compile(r"home ?office|remot", re.I)


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    for page in range(1, cfg.get("nerdin", {}).get("pages", 5) + 1):  # ~20 vagas por página
        r = http.get(f"{BASE}/vagas.php", params={"pagina": page})
        found = parse(http.decode(r)) if r is not None else []
        jobs.extend(found)
        if r is None:
            break
    return jobs


def parse(html: str) -> list[Job]:
    jobs = []
    for card in BeautifulSoup(html, "lxml").select("div.vaga-card"):
        resumo = card.select_one(".vaga-resumo-linha")
        title = card.select_one("h3.vaga-titulo")
        if not (title and card.get("data-href") and resumo and REMOTE.search(resumo.get_text())):
            continue
        company, place, when = (card.select_one(s) for s in (".vaga-empresa-nome", ".vaga-local-linha span", "time"))
        jobs.append(Job(
            source="nerdin",
            title=next(title.stripped_strings),  # o selo "Nova" fica fora
            url=f"{BASE}/{card['data-href']}",
            company=company.get_text(strip=True) if company else "",
            location=place.get_text(strip=True) if place else "",
            posted=when.get("datetime", "") if when else "",
            tags=[" ".join(resumo.get_text().split())],
        ))
    return jobs
