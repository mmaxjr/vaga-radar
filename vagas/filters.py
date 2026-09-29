from __future__ import annotations

import re

from datetime import datetime, timedelta, timezone

from .models import Job


REMOTE_WORDS = re.compile(r"remot|home ?office|anywhere|worldwide|work from home", re.I)


class JobFilter:
    def __init__(self, cfg: dict):
        s = cfg["search"]
        self.include = re.compile("|".join(s["include"]), re.I)
        self.exclude = re.compile("|".join(s["exclude"]), re.I) if s.get("exclude") else None
        self.max_age = timedelta(days=s.get("max_age_days", 30))
        # Fontes que não garantem o regime: a vaga só entra se o título/local disser que é remota
        self.strict_sources = set(s.get("strict_remote_sources", []))
        regions = s.get("international_ok_regions", [])
        self.regions = re.compile("|".join(map(re.escape, regions)), re.I) if regions else None

    def accepts(self, job: Job) -> bool:
        if not job.title or not job.url:
            return False
        if not self.include.search(job.title):
            return False
        if self.exclude and self.exclude.search(job.title):
            return False
        # Vagas "local" (sua cidade) valem em qualquer regime; as demais precisam ser 100% remotas
        if job.scope == "remoto":
            if job.source in self.strict_sources and not REMOTE_WORDS.search(f"{job.title} {job.location}"):
                return False
            if job.international and not self.region_ok(job.location):
                return False
        return not self.too_old(job)

    def region_ok(self, location: str) -> bool:
        # Sem informação de região = normalmente "qualquer lugar"
        if not location.strip():
            return True
        return bool(self.regions and self.regions.search(location))

    def too_old(self, job: Job) -> bool:
        posted = parse_date(job.posted)
        return posted is not None and datetime.now(timezone.utc) - posted > self.max_age


def parse_date(value: str) -> datetime | None:
    """Aceita ISO 8601 (com ou sem fuso) e devolve datetime com fuso UTC, ou None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
