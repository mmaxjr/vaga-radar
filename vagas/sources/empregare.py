"""Empregare (empregare.com). Listagens em HTML, sem bloqueio anti-robô e com robots.txt liberando as páginas de vagas
(só /api/ e rotas internas são proibidas, e nenhuma é usada aqui).

Cada cartão informa o regime ("Totalmente Remoto", "Híbrido" ou "Presencial"): a busca remota só guarda os
"Totalmente Remoto", então o regime vem provado pela própria fonte. `fetch_city` é usada pela fonte `local`.
"""
from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from .. import http
from ..models import Job

BASE = "https://www.empregare.com"
LIST = BASE + "/pt-br/{path}"
REGIME = re.compile(r"Totalmente Remoto|Presencial|H[ií]brido", re.I)
SALARY = re.compile(r"R\$\s?[\d.]+(?:,\d+)?")
BRT = timezone(timedelta(hours=-3))
MONTHS = {m: i for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split(), 1)}
DELAY = 0.7  # pausa entre páginas, para não sobrecarregar o site


def fetch(cfg: dict) -> list[Job]:
    """Vagas 100% remotas: a listagem de trabalho remoto e a busca por cada termo."""
    jobs: dict[str, Job] = {}
    for path, pages in [("vagas-de-trabalho-remoto", 4)] + [(f"vagas-de-{_slug(t)}", 2) for t in cfg["search"]["terms"]]:
        for job in _pages(path, pages):
            if job.location.lower().endswith("totalmente remoto"):
                jobs.setdefault(job.url, job)
    return list(jobs.values())


def fetch_city(city: str, uf: str, terms: list[str]) -> list[Job]:
    """Vagas da cidade em qualquer regime: a listagem completa da cidade e a busca por termo dentro dela."""
    where = f"{_slug(city)}-{uf.lower()}"
    jobs: dict[str, Job] = {}
    for path, pages in [(f"vagas-em-{where}", 8)] + [(f"vagas-de-{_slug(t)}-em-{where}", 2) for t in terms]:
        for job in _pages(path, pages):
            jobs.setdefault(job.url, job)
    return list(jobs.values())


def _pages(path: str, pages: int) -> list[Job]:
    found: list[Job] = []
    for page in range(1, pages + 1):
        r = http.get(LIST.format(path=path), params={"pagina": page} if page > 1 else None)
        time.sleep(DELAY)
        if r is None:
            break
        batch = parse(http.decode(r))
        new = [j for j in batch if j.url not in {f.url for f in found}]
        found += new
        if not new:  # fim da listagem (página repetida ou vazia)
            break
    return found


def parse(html: str, today: datetime | None = None) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    today = today or datetime.now(BRT)
    jobs = []
    for link in soup.select("a:has(article.card-vaga)"):
        title = link.select_one("p.titulo-vaga")
        if not (title and link.get("href")):
            continue
        text = " ".join(link.get_text(" ").split())
        regime = REGIME.search(" ".join(s.get_text(" ") for s in link.select("ul li small")))
        city = link.select_one("p.card-cidades")
        place = re.sub(r",\s*BR$", "", city.get_text(" ", strip=True)) if city else ""
        company = link.select_one("p.card-vaga-empresa")
        salary = SALARY.search(text)
        label = regime.group(0).lower() if regime else ""
        # nas listagens de remoto o "local" do cartão já é o próprio regime: não repetir
        where = place if not label or place.lower() == label else f"{place} · {label}"
        date = link.select_one(".texto-data-card")
        jobs.append(Job(
            source="empregare",
            title=title.get_text(strip=True),
            url=BASE + link["href"],
            company=company.get_text(strip=True) if company else "",
            location=where,
            posted=_posted(date.get_text(strip=True) if date else "", today),
            salary=salary.group(0) if salary else "",
        ))
    return jobs


def _posted(text: str, today: datetime) -> str:
    """'ter., 29/setembro' (sem ano) -> data ISO; se cair no futuro, é do ano passado."""
    m = re.search(r"(\d{1,2})/(\w+)", text)
    month = MONTHS.get(m.group(2).lower()) if m else None
    if not month:
        return ""
    when = datetime(today.year, month, int(m.group(1)), 12, tzinfo=BRT)
    if when > today + timedelta(days=1):
        when = when.replace(year=today.year - 1)
    return when.isoformat()


def _slug(text: str) -> str:
    ascii_ = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")
    return "-".join(ascii_.split())
