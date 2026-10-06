"""Coodesh. A listagem é montada por JavaScript, então o ponto de partida é o sitemap oficial de vagas (as mais novas);
cada página traz título, empresa, "Localidade" e data. Só entram as de localidade remota."""
from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup

from .. import http
from ..models import Job

SITEMAP = "https://coodesh.com/sitemaps/jobs.xml"
REMOTE = re.compile(r"remot|home ?office", re.I)


def fetch(cfg: dict) -> list[Job]:
    r = http.get(SITEMAP)
    urls = re.findall(r"<loc>(.*?)</loc>", http.decode(r)) if r is not None else []
    jobs: list[Job] = []
    for url in urls[:cfg.get("coodesh", {}).get("max_jobs", 40)]:
        page = http.get(url)
        job = parse(http.decode(page), url) if page is not None else None
        if job:
            jobs.append(job)
        time.sleep(1)
    return jobs


def parse(html: str, url: str) -> Job | None:
    soup = BeautifulSoup(html, "lxml")
    og = soup.find("meta", property="og:title")
    linhas = [" ".join(t.split()) for t in soup.get_text("\n").split("\n") if t.strip()]

    def antes(rotulo: str) -> str:  # na página o valor vem na linha anterior ao rótulo
        return linhas[linhas.index(rotulo) - 1] if rotulo in linhas[1:] else ""

    if not (og and REMOTE.search(antes("Localidade"))):
        return None
    titulo, _, empresa = og["content"].partition(" | ")
    data = re.search(r"Publicada: (\d\d)/(\d\d)/(\d{4})", html)
    return Job(
        source="coodesh", title=titulo.strip(), url=url, company=empresa.strip(),
        posted=f"{data[3]}-{data[2]}-{data[1]}" if data else "",
        tags=[t for t in (antes("Tipo de Contratação"),) if t],
    )
