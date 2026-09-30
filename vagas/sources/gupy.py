"""Gupy: portal público de vagas de centenas de empresas brasileiras."""
from __future__ import annotations

from .. import http
from ..models import Job

API = "https://portal.gupy.io/api/job-search/jobs"  # o antigo employability-portal.gupy.io/api/v1/jobs saiu do ar (404)
PAGE = 50


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    for term in cfg["search"]["terms"]:
        offset = 0
        for _ in range(3):  # até 150 vagas por termo
            r = http.get(API, params={"jobName": term, "workplaceType": "remote",
                                      "limit": PAGE, "offset": offset})
            if r is None:
                break
            data = r.json()
            for it in data.get("data", []):
                jobs.append(Job(
                    source="gupy",
                    title=it["name"],
                    url=it["jobUrl"],
                    company=it.get("careerPageName", ""),
                    location="Remoto" if it.get("isRemoteWork") else _place(it),
                    posted=it.get("publishedDate", ""),
                ))
            offset += PAGE
            if offset >= data.get("pagination", {}).get("total", 0):
                break
    return jobs


def _place(it: dict) -> str:
    return ", ".join(p for p in (it.get("city"), it.get("state"), it.get("country")) if p)
