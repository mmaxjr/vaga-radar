from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Job


class Store:
    """Guarda as vagas em um JSON (que também alimenta a página em docs/)."""

    def __init__(self, path: str | Path, keep_days: int = 45):
        self.path = Path(path)
        self.keep_days = keep_days
        self.jobs: dict[str, Job] = {}
        if self.path.exists():
            for d in json.loads(self.path.read_text(encoding="utf-8")).get("jobs", []):
                job = Job.from_dict(d)
                self.jobs[job.id] = job

    def add_new(self, found: list[Job]) -> list[Job]:
        """Adiciona as vagas inéditas e devolve só essas."""
        new = []
        for job in found:
            if job.id not in self.jobs:
                self.jobs[job.id] = job
                new.append(job)
        return new

    def prune(self) -> None:
        limit = (datetime.now(timezone.utc) - timedelta(days=self.keep_days)).isoformat()
        self.jobs = {i: j for i, j in self.jobs.items() if j.first_seen >= limit}

    def save(self) -> None:
        self.prune()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self.jobs.values(), key=lambda j: j.posted or j.first_seen, reverse=True)
        payload = {
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "jobs": [j.to_dict() for j in ordered],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
