"""Trampos.co (mais comunicação que TI). Usa a API JSON que o próprio site consome: 12 vagas por página, das mais novas
para as mais antigas. O parâmetro de busca da API é ignorado, então o filtro é local: só TI/dados com home office."""
from __future__ import annotations

import time

from .. import http
from ..models import Job

API = "https://trampos.co/api/v2/opportunities"


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    for page in range(1, cfg.get("trampos", {}).get("pages", 5) + 1):
        r = http.get(API, params={"page": page})
        if r is None:
            break
        itens = r.json().get("opportunities", [])
        jobs.extend(parse(itens))
        if not itens:
            break
        time.sleep(1)
    return jobs


def parse(itens: list[dict]) -> list[Job]:
    return [Job(
        source="trampos",
        title=o["name"].strip(),
        url=f"https://trampos.co/oportunidades/{o['id']}",
        company=(o.get("company") or {}).get("name") or o.get("custom_company_name") or "",
        location=(o.get("city") or "").strip(),
        posted=o.get("published_at", ""),
    ) for o in itens if o.get("category_slug") in ("ti", "dados") and o.get("home_office") and not o.get("hybrid")]
