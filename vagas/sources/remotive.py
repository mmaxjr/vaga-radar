"""Remotive (internacional). Pede link de volta e limita as consultas por dia."""
from __future__ import annotations

from .. import http
from ..models import Job


def fetch(cfg: dict) -> list[Job]:
    r = http.get("https://remotive.com/api/remote-jobs", params={"category": "software-dev", "limit": 200})
    if r is None:
        return []
    return [Job(
        source="remotive",
        title=it["title"],
        url=it["url"],
        company=it.get("company_name", ""),
        location=it.get("candidate_required_location", ""),
        posted=it.get("publication_date", ""),
        tags=it.get("tags", [])[:6],
        salary=it.get("salary", ""),
        international=True,
    ) for it in r.json().get("jobs", [])]
