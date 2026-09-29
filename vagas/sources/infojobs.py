"""InfoJobs Brasil. A listagem vem em HTML já com as vagas e o robots.txt não restringe a busca.

Cada cartão informa o regime ("Home Office", "Híbrido" ou "Presencial"): a busca remota só guarda os "Home Office",
então há prova do regime na própria fonte. Para a sua cidade (fonte `local`) o regime vira parte do local.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from .. import http
from ..models import Job

BASE = "https://www.infojobs.com.br"
REGIME = re.compile(r"\b(Presencial|H[ií]brido|Home Office)\b", re.I)
SALARY = re.compile(r"R\$\s?[\d.]+(?:,\d+)?(?:\s?a\s?R\$\s?[\d.]+(?:,\d+)?)?")
BRT = timezone(timedelta(hours=-3))


def fetch(cfg: dict) -> list[Job]:
    """Vagas 100% remotas ("Home Office") por termo de busca."""
    jobs: dict[str, Job] = {}
    for term in cfg["search"]["terms"]:
        slug = "+".join(_ascii(term).split())
        r = http.get(f"{BASE}/vagas-de-emprego-{slug}-trabalho-home-office.aspx")
        if r is None:
            continue
        for job in parse(http.decode(r)):
            if job.location.endswith("home office"):
                jobs.setdefault(job.url, job)
    return list(jobs.values())


def parse(html: str) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    jobs: dict[str, Job] = {}
    for card in soup.select("div.js_rowCard"):
        href, title = card.get("data-href"), card.select_one("h2")
        if not (href and title):
            continue  # o site repete cartões e mistura anúncios: só vale cartão de vaga
        text = " ".join(card.get_text(" ").split())
        regime = REGIME.search(text)
        company = card.find("a", href=re.compile(r"/empresa-"))
        where = card.select_one("div.mb-8")
        place = next(iter(where.stripped_strings), "") if where else ""
        salary = SALARY.search(text)
        url = BASE + href
        jobs.setdefault(url, Job(
            source="infojobs",
            title=title.get_text(strip=True),
            url=url,
            company=next(iter(company.stripped_strings), "") if company else "",
            location=f"{place} · {regime.group(1).lower()}" if regime else place,
            posted=_posted(card),
            salary=salary.group(0) if salary else "",
        ))
    return list(jobs.values())


def _posted(card) -> str:
    tag = card.select_one(".js_date")
    if tag is None or not tag.get("data-value"):
        return ""
    try:
        return datetime.strptime(tag["data-value"], "%Y/%m/%d %H:%M:%S").replace(tzinfo=BRT).isoformat()
    except ValueError:
        return ""


def _ascii(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")
