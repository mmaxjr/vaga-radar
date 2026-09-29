"""Programathor: vagas de tecnologia no Brasil."""
from __future__ import annotations

from bs4 import BeautifulSoup

from .. import http
from ..models import Job

BASE = "https://programathor.com.br"


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    for page in range(1, 6):
        r = http.get(f"{BASE}/jobs/page/{page}")
        if r is None:
            break
        found = parse(http.decode(r))
        if not found:
            break
        jobs.extend(found)
    return [j for j in jobs if "remot" in j.location.lower()]


def parse(html: str) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    for cell in soup.select("div.cell-list"):
        a = cell.find("a", href=True)
        h3 = cell.find("h3")
        if not (a and h3):
            continue
        if h3.get_text(strip=True).startswith("Vencida"):
            continue  # vaga encerrada
        spans = [s.get_text(strip=True) for s in cell.select(".cell-list-content-icon span")]
        # ordem observada: empresa, local, porte, nível, contrato
        jobs.append(Job(
            source="programathor",
            title=h3.get_text(strip=True),
            url=BASE + a["href"],
            company=spans[0] if spans else "",
            location=spans[1] if len(spans) > 1 else "",
            tags=[t.get_text(strip=True) for t in cell.select("span.tag-list")],
        ))
    return jobs
