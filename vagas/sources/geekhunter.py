"""GeekHunter (vagas de tecnologia no Brasil).

Usa só a listagem pública /pt/vagas, pela interface de busca que o próprio site publica (schema.org
SearchAction: searchTerm + workModality). O robots.txt libera essa página para bots e proíbe /jobs/...,
por isso as páginas de cada vaga nunca são abertas: título, empresa e data vêm dos cartões da listagem.

workModality=remote NÃO inclui "remote-in-city" (remoto amarrado a uma cidade), então só vem 100% remoto.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from .. import http
from ..models import Job

URL = "https://www.geekhunter.com/pt/vagas"
PAGE_SIZE = 25
LEVELS = ("Estagiário", "Júnior", "Pleno", "Sênior", "Especialista", "Coordenador", "Gerente", "Diretor")
UNITS = {"minuto": 1 / 60, "hora": 1, "dia": 24, "semana": 168, "mes": 720, "mês": 720, "ano": 8760}


def fetch(cfg: dict) -> list[Job]:
    gh = cfg.get("geekhunter", {})
    delay = gh.get("delay", 1.5)
    jobs: dict[str, Job] = {}
    for term in cfg["search"]["terms"]:
        for page in range(1, gh.get("pages_per_term", 2) + 1):
            params = {"searchTerm": term, "workModality": "remote"}
            if page > 1:
                params["page"] = page
            r = http.get(URL, params=params)
            time.sleep(delay)
            if r is None:
                return list(jobs.values())  # possível bloqueio: devolve o que já temos
            found = parse(http.decode(r))
            for job in found:
                jobs.setdefault(job.url, job)
            if len(found) < PAGE_SIZE:
                break
    return list(jobs.values())


def parse(html: str, now: datetime | None = None) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    tag = soup.select_one("script#itemList")
    if tag is None or not tag.string:
        return []
    now = now or datetime.now(timezone.utc)
    jobs = []
    for item in json.loads(tag.string).get("itemListElement", []):
        url, title = item.get("url", ""), item.get("name", "")
        anchor = soup.find("a", href=url)
        text = _card_text(anchor)
        if "Remoto" not in text:  # segunda checagem, além do filtro da busca
            continue
        jobs.append(Job(
            source="geekhunter",
            title=title,
            url=url,
            company=_company(url),
            location="Remoto",
            posted=_posted(text, now),
            tags=[lv for lv in LEVELS if lv in text][:1],
        ))
    return jobs


def _card_text(anchor) -> str:
    """Sobe do link até o contêiner do cartão (o primeiro com texto suficiente)."""
    node = anchor
    for _ in range(6):
        if node is None:
            return ""
        text = " ".join(node.get_text(" ").split())
        if len(text) > 120:
            return text
        node = node.parent
    return ""


def _company(url: str) -> str:
    # https://www.geekhunter.com/pt/ntt-data/jobs/... -> "Ntt Data"
    m = re.search(r"/pt/([^/]+)/jobs/", url)
    if not m:
        return ""
    return re.sub(r"-\d+$", "", m.group(1)).replace("-", " ").title()


def _posted(text: str, now: datetime) -> str:
    """'Publicada há 3 dias' / 'Atualizada há 2 meses' -> data aproximada em ISO."""
    m = re.search(r"há (\d+) (minuto|hora|dia|semana|mes|mês|ano)", text)
    if not m:
        return ""
    hours = int(m.group(1)) * UNITS[m.group(2)]
    return (now - timedelta(hours=hours)).isoformat(timespec="seconds")
