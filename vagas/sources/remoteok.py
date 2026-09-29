"""RemoteOK (internacional). A API exige link de volta para remoteok.com (ver README)."""
from __future__ import annotations

from .. import http
from ..models import Job


def fetch(cfg: dict) -> list[Job]:
    r = http.get("https://remoteok.com/api")
    if r is None:
        return []
    jobs = []
    for it in r.json():
        if not isinstance(it, dict) or "position" not in it:
            continue
        lo, hi = it.get("salary_min"), it.get("salary_max")
        jobs.append(Job(
            source="remoteok",
            title=it["position"],
            url=it.get("url") or f"https://remoteok.com/remote-jobs/{it.get('slug', '')}",
            company=it.get("company", ""),
            location=it.get("location", ""),
            posted=it.get("date", ""),
            tags=it.get("tags", [])[:6],
            salary=f"US$ {lo:,}-{hi:,}" if lo and hi else "",
            international=True,
        ))
    return jobs
