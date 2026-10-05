"""Texto da descrição de cada vaga, por fonte, com cache em disco e orçamento de requisições.

Jobicy, Vagas.com.br e Nerdin: lidos pelo JSON-LD `JobPosting` da página. Fontes sem leitura: GeekHunter (robots.txt proíbe
/jobs/...), Zoho (a API não busca por vaga), RemoteOK, Remotive e We Work Remotely (já vêm em inglês e curtas).
Nelas a vaga entra no ranking só pelo título.
"""
from __future__ import annotations

import html
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from bs4 import BeautifulSoup

from . import http, jsonld
from .models import Job
from .sources import gupy, himalayas, linkedin

log = logging.getLogger(__name__)
Resultado = tuple[str, str]  # (texto, prazo AAAA-MM-DD ou "")


def _texto(html_: str) -> str:
    return " ".join(BeautifulSoup(html_ or "", "lxml").get_text(" ").split())


def _gupy(job: Job) -> Resultado | None:
    params = {"jobName": job.title.strip()[:60], "limit": 20}
    if job.scope == "remoto":
        params["workplaceType"] = "remote"
    r = http.get(gupy.API, params=params)
    if r is None:
        return None
    alvo = job.url.split("?")[0]
    for it in r.json().get("data", []):
        if (it.get("jobUrl") or "").split("?")[0] == alvo:
            return _texto(it.get("description", "")), (it.get("applicationDeadline") or "")[:10]
    return None


def _himalayas(job: Job) -> Resultado | None:
    r = http.get(himalayas.API, params={"q": job.title[:40], "country": "Brazil"})
    if r is None:
        return None
    for it in r.json().get("jobs", []):
        if (it.get("guid") or "") == job.url:
            fim = it.get("expiryDate")
            prazo = datetime.fromtimestamp(fim, tz=timezone.utc).date().isoformat() if fim else ""
            return _texto(it.get("description", "")), prazo
    return None


def _linkedin(job: Job) -> Resultado | None:
    texto = linkedin.job_text(job)
    return (texto, "") if texto else None


def _github(job: Job) -> Resultado | None:
    repo, numero = "/".join(job.url.split("/")[3:5]), job.url.rstrip("/").split("/")[-1]
    r = http.get(f"https://api.github.com/repos/{repo}/issues/{numero}", headers={"Accept": "application/vnd.github+json"})
    return (r.json().get("body") or "", "") if r is not None else None


def _pagina(job: Job) -> Resultado | None:
    r = http.get(job.url)
    return (_texto(http.decode(r)), "") if r is not None else None


def _jsonld(job: Job) -> Resultado | None:
    """Páginas que publicam `JobPosting` (Jobicy, Vagas.com.br): lê a descrição e a validade desses dados."""
    r = http.get(job.url)
    vaga = jsonld.job_posting(http.decode(r)) if r is not None else None
    if not vaga or not vaga.get("description"):
        return None
    return _texto(html.unescape(vaga["description"])), (vaga.get("validThrough") or "")[:10]


def _empresa(job: Job) -> Resultado | None:
    slug, vaga = job.source.split(":", 1)[1], job.url.rstrip("/").split("/")[-1]
    r = http.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{vaga}")  # Lever não tem esta rota: None
    return (_texto(html.unescape(r.json().get("content", ""))), "") if r is not None else None


FETCHERS: dict[str, Callable[[Job], Resultado | None]] = {
    "gupy": _gupy, "himalayas": _himalayas, "linkedin": _linkedin, "github": _github,
    "infojobs": _pagina, "empregare": _pagina, "empresa": _empresa, "jobicy": _jsonld, "vagas.com.br": _jsonld, "nerdin": _jsonld,
}


class Descricoes:
    def __init__(self, cache: str | Path, delay: float = 1.0, orcamento: int = 40, max_chars: int = 6000):
        self.cache, self.delay, self.orcamento, self.max_chars = Path(cache), delay, orcamento, max_chars
        self.dados: dict[str, dict] = json.loads(self.cache.read_text(encoding="utf-8")) if self.cache.exists() else {}

    def obter(self, job: Job) -> Resultado | None:
        if job.id in self.dados:
            d = self.dados[job.id]
            return d["texto"], d["prazo"]
        buscar = FETCHERS.get(job.source.split(":")[0])
        if buscar is None or self.orcamento <= 0:
            return None
        self.orcamento -= 1
        try:
            achado = buscar(job)
        except Exception:  # uma vaga com página estranha não pode derrubar o ranking
            log.exception("descrição de %s falhou", job.url)
            achado = None
        time.sleep(self.delay)
        if achado is None:
            return None  # falha não vai para o cache: tenta de novo na próxima execução
        texto, prazo = achado[0][: self.max_chars], achado[1]
        self.dados[job.id] = {"texto": texto, "prazo": prazo}
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_text(json.dumps(self.dados, ensure_ascii=False), encoding="utf-8")
        return texto, prazo
