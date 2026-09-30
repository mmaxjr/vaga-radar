"""Himalayas (internacional), API pública de busca. O campo locationRestrictions diz em quais países a
empresa contrata: só entram vagas abertas ao Brasil ou sem restrição. A página cita a fonte com link."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from .. import http
from ..models import Job

API = "https://himalayas.app/jobs/api/search"


def fetch(cfg: dict) -> list[Job]:
    hc = cfg.get("himalayas", {})
    jobs: dict[str, Job] = {}
    failures = 0
    for query in hc.get("queries", ["devops", "sre", "infrastructure", "security", "network engineer", "linux"]):
        r = http.get(API, params={"q": query, "country": "Brazil"})
        time.sleep(hc.get("delay", 1.0))
        if r is None:
            failures += 1
            if failures >= 3:
                return list(jobs.values())
            continue
        failures = 0
        for it in r.json().get("jobs", []):
            places = it.get("locationRestrictions") or []
            if places and "Brazil" not in places:
                continue
            url = it.get("guid") or it.get("applicationLink", "")
            lo, hi = it.get("minSalary"), it.get("maxSalary")
            jobs.setdefault(url, Job(
                source="himalayas",
                title=it["title"],
                url=url,
                company=it.get("companyName", ""),
                location="Brasil ou global" if places else "Global",
                posted=_from_epoch(it.get("pubDate")),
                tags=_as_list(it.get("seniority")),
                salary=f"{it.get('currency', '')} {int(lo):,}-{int(hi):,}" if lo and hi else "",
                international=True,
            ))
    return list(jobs.values())


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    return [v for v in (value or []) if isinstance(v, str)][:2]


def _from_epoch(value) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds") if value else ""
