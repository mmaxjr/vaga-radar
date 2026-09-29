"""LinkedIn via endpoint público de busca (o mesmo usado por visitantes sem login).

Não usa login nem contorna proteção. Mesmo assim o LinkedIn limita esse acesso: por isso há
pausa entre requisições e a coleta desiste sozinha ao receber bloqueio (HTTP 429). Use com moderação.
"""
from __future__ import annotations

import time

from bs4 import BeautifulSoup

from .. import http
from ..models import Job, canonical_url

API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


def fetch(cfg: dict) -> list[Job]:
    li = cfg["linkedin"]
    jobs: list[Job] = []
    for term in cfg["search"]["terms"]:
        for page in range(li.get("pages_per_term", 2)):
            r = http.get(API, params={
                "keywords": term,
                "location": li.get("location", "Brazil"),
                "f_WT": 2,  # 2 = remoto
                "f_TPR": f"r{li.get('days', 7) * 86400}",
                "sortBy": "DD",  # mais recentes primeiro
                "start": page * 25,
            }, retries=0)
            time.sleep(li.get("delay", 2.5))
            if r is None:
                return jobs  # provável bloqueio: para tudo e devolve o que já temos
            cards = parse(http.decode(r))
            jobs.extend(cards)
            if len(cards) < 25:
                break
    return jobs


def parse(html: str) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    for card in soup.select("div.base-search-card"):
        link = card.select_one("a.base-card__full-link")
        title = card.select_one(".base-search-card__title")
        if not (link and title):
            continue
        company = card.select_one(".base-search-card__subtitle")
        place = card.select_one(".job-search-card__location")
        when = card.select_one("time")
        jobs.append(Job(
            source="linkedin",
            title=title.get_text(strip=True),
            url=canonical_url(link["href"]),
            company=company.get_text(strip=True) if company else "",
            location=place.get_text(strip=True) if place else "",
            posted=when.get("datetime", "") if when else "",
        ))
    return jobs
