"""Torre (torre.ai), comunidades públicas de vagas remotas para a América Latina.

Só lê a página pública da comunidade (`/sub/<comunidade>/jobs`), que o robots.txt permite; a API e a busca com
parâmetros ficam de fora porque o robots.txt as proíbe. A página traz só as vagas mais ativas (umas 20), sem data."""
from __future__ import annotations

from bs4 import BeautifulSoup

from .. import http
from ..models import Job

BASE = "https://torre.ai"


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    for comunidade in cfg.get("torre", {}).get("communities", ["remote-latam-information-technology"]):
        r = http.get(f"{BASE}/sub/{comunidade}/jobs")
        if r is not None:
            jobs.extend(parse(http.decode(r)))
    return jobs


def parse(html: str) -> list[Job]:
    jobs = []
    for card in BeautifulSoup(html, "lxml").select('a[href*="/post/"]'):
        # o avatar da empresa também tem .text-h2, mas não tem .text-accent
        titulo, empresa = card.select_one("div.text-accent.text-h2"), card.select_one("span.text-accent.text-regular")
        if not (titulo and "remote" in card.get_text(" ").lower()):
            continue
        jobs.append(Job(
            source="torre",
            title=titulo.get_text(strip=True),
            url=card["href"].split("?")[0],
            company=empresa.get_text(strip=True) if empresa else "",
            location="LATAM (remoto)",  # a comunidade é aberta a quem mora na América Latina
            international=True,
        ))
    return jobs
