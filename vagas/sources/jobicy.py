"""Jobicy (internacional). Pede crédito com link direto à fonte (a página cita) e a URL de cada vaga é a da
própria Jobicy, que leva ao anúncio original. O feed é atualizado a cada hora: poucas chamadas por execução."""
from __future__ import annotations

import time

from .. import http
from ..models import Job

API = "https://jobicy.com/api/v2/remote-jobs"


def fetch(cfg: dict) -> list[Job]:
    jc = cfg.get("jobicy", {})
    jobs: dict[str, Job] = {}
    failures = 0  # a API rejeita algumas combinações (HTTP 400): pula só essa; desiste após 3 falhas seguidas
    for geo in jc.get("geos", ["brazil", "anywhere"]):
        for tag in jc.get("tags", ["devops", "sre", "infrastructure", "security", "network", "linux"]):
            r = http.get(API, params={"count": 50, "geo": geo, "tag": tag})
            time.sleep(jc.get("delay", 1.0))
            if r is None:
                failures += 1
                if failures >= 3:
                    return list(jobs.values())  # provável limite de uso: devolve o que já temos
                continue
            failures = 0
            for it in r.json().get("jobs", []):
                jobs.setdefault(it["url"], Job(
                    source="jobicy",
                    title=it["jobTitle"],
                    url=it["url"],
                    company=it.get("companyName", ""),
                    location=it.get("jobGeo", ""),
                    posted=_iso(it.get("pubDate", "")),
                    salary=_salary(it),
                    international=True,
                ))
    return list(jobs.values())


def _iso(value: str) -> str:
    return value.replace(" ", "T") if value else ""


def _salary(it: dict) -> str:
    lo, hi, cur = it.get("salaryMin"), it.get("salaryMax"), it.get("salaryCurrency", "")
    return f"{cur} {int(lo):,}-{int(hi):,}/{(it.get('salaryPeriod') or '')[:3]}" if lo and hi else ""
