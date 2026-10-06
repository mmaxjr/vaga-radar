"""Hacker News, tópico mensal "Ask HN: Who is hiring?", pela API pública do Algolia.

Cada anúncio começa por um cabeçalho "Empresa | Cargo | Local | Remoto". Só entram os que dizem remoto no cabeçalho
e são abertos ao mundo, à América Latina ou ao Brasil (o texto do corpo não conta, para não pegar "remote friendly")."""
from __future__ import annotations

import html
import re

from .. import http
from ..models import Job

API = "https://hn.algolia.com/api/v1"
REMOTE = re.compile(r"remote", re.I)
REGION = re.compile(r"brazil|brasil|latam|latin america|south america|americas|worldwide|anywhere|global", re.I)


def fetch(cfg: dict) -> list[Job]:
    r = http.get(f"{API}/search_by_date", params={"tags": "story,author_whoishiring", "hitsPerPage": 4})
    if r is None:
        return []
    topico = next((h for h in r.json().get("hits", []) if h["title"].startswith("Ask HN: Who is hiring?")), None)
    r = http.get(f"{API}/items/{topico['objectID']}") if topico else None
    return parse(r.json().get("children", [])) if r is not None else []


def parse(comentarios: list[dict]) -> list[Job]:
    jobs = []
    for c in comentarios:
        texto = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<p>", "\n", c.get("text") or "")))
        cabecalho = " ".join(texto.strip().split("\n")[0].split())[:200]
        if not (REMOTE.search(cabecalho) and REGION.search(cabecalho)):
            continue
        jobs.append(Job(
            source="hn",
            title=cabecalho,
            url=f"https://news.ycombinator.com/item?id={c['id']}",
            company=cabecalho.split("|")[0].strip(),
            location=cabecalho,
            posted=c.get("created_at", ""),
            international=True,
        ))
    return jobs
