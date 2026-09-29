"""Repositórios de vagas da comunidade (frontendbr/vagas etc.): cada issue aberta é uma vaga.

Sem token a API do GitHub permite 60 requisições/h. Com GITHUB_TOKEN sobe para 5000/h.
"""
from __future__ import annotations

import os
import re

from .. import http
from ..models import Job

REMOTE = re.compile(r"remot|home ?office|anywhere", re.I)


def fetch(cfg: dict) -> list[Job]:
    gh = cfg["github"]
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"

    jobs: list[Job] = []
    for repo in gh["repos"]:
        for page in range(1, gh.get("max_pages", 2) + 1):
            r = http.get(f"https://api.github.com/repos/{repo}/issues",
                         params={"state": "open", "per_page": 100, "page": page,
                                 "sort": "created", "direction": "desc"},
                         headers=headers)
            if r is None:
                break
            items = r.json()
            for it in items:
                if "pull_request" in it:
                    continue
                labels = [lb["name"] for lb in it.get("labels", [])]
                if not REMOTE.search(" ".join([it["title"], *labels])):
                    continue
                jobs.append(Job(
                    source=f"github:{repo.split('/')[0]}",
                    title=_clean_title(it["title"]),
                    url=it["html_url"],
                    location="Remoto",
                    posted=it["created_at"],
                    tags=[lb for lb in labels if not REMOTE.search(lb)],
                ))
            if len(items) < 100:
                break
    return jobs


def _clean_title(title: str) -> str:
    # "[Remoto] Desenvolvedor Back-end na Empresa" -> "Desenvolvedor Back-end na Empresa"
    return re.sub(r"^\s*(\[[^\]]*\]\s*)+", "", title).strip() or title
