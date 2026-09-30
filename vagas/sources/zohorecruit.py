"""Páginas de carreira do Zoho Recruit (<empresa>.zohorecruit.com), usadas por várias empresas (ex.: Spassu).

A listagem pública (/jobs/Careers) já traz todas as vagas num bloco de dados da própria página, com o campo
"Trabalho remoto" (Remote_Job) e a cidade de cada uma: uma única requisição, sem abrir vaga por vaga. O robots.txt
libera /jobs/*. Vaga com Remote_Job = verdadeiro entra como remota (escopo "remoto"); vaga com cidade só entra se a
cidade for uma das configuradas em [local] (escopo "local", regime presencial/híbrido não informado).

A data de abertura vai nas tags e não em `posted`: nessas páginas a vaga listada está aberta mesmo que tenha meses, e
o filtro de idade a descartaria por engano.

Configuração: [zohorecruit] sites = ["spassu"]   (a parte antes de .zohorecruit.com)
"""
from __future__ import annotations

import html
import json
import re
import unicodedata

from .. import http
from ..models import Job

LISTING = "https://{site}.zohorecruit.com/jobs/Careers"
BLOCK = re.compile(r'value="(\[\{&#34;Remote_Job&#34;.*?)"', re.S)


def fetch(cfg: dict) -> list[Job]:
    cities = _cities(cfg)
    jobs: list[Job] = []
    for site in cfg.get("zohorecruit", {}).get("sites", []):
        r = http.get(LISTING.format(site=site))
        if r is not None:
            jobs += parse(http.decode(r), site, cities)
    return jobs


def parse(page: str, site: str, cities: set[str] = frozenset()) -> list[Job]:
    m = BLOCK.search(page)
    if not m:
        return []
    jobs = []
    for it in json.loads(html.unescape(m.group(1)), strict=False):
        if not it.get("Publish", True):
            continue
        remote = bool(it.get("Remote_Job"))
        city = it.get("City") or ""
        if not remote and _norm(city) not in cities:
            continue  # presencial fora da sua cidade
        title = it["Posting_Title"].strip()
        opened = (it.get("Date_Opened") or "")[:10]
        jobs.append(Job(
            source=f"zoho:{site}",
            scope="remoto" if remote else "local",
            title=title,
            url=f"https://{site}.zohorecruit.com/jobs/Careers/{it['id']}/{_slug(title)}",
            company=site.replace("-", " ").title(),
            location="Remoto" if remote else city,
            tags=[f"aberta em {opened}"] if opened else [],
        ))
    return jobs


def _cities(cfg: dict) -> set[str]:
    loc = cfg.get("local", {})
    if not loc.get("enabled"):
        return set()
    return {_norm(c) for c in loc.get("cities", [loc.get("city", "")]) if c}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", _ascii(text)).strip("-") or "vaga"


def _norm(text: str) -> str:
    return _ascii(text).lower().strip()


def _ascii(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
