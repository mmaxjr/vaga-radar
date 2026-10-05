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
        self.rejected: dict[str, str] = {}  # id -> data em que foi descartada (para não reverificar todo dia)
        self.updated = ""  # instante (ISO, UTC) da última coleta salva
        self.source_runs: dict[str, str] = {}  # fonte -> instante da última tentativa (para o intervalo por fonte)
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.updated = data.get("updated", "")
            self.source_runs = data.get("source_runs", {})
            for d in data.get("jobs", []):
                job = Job.from_dict(d)
                self.jobs[job.id] = job
            self.rejected = data.get("rejected", {})

    @staticmethod
    def _hours_since(iso: str) -> float | None:
        if not iso:
            return None
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 3600

    def hours_since_last_run(self) -> float | None:
        """Horas desde a última coleta salva, ou None se nunca houve."""
        return self._hours_since(self.updated)

    def hours_since_source(self, name: str) -> float | None:
        """Horas desde a última tentativa desta fonte, ou None se nunca rodou."""
        return self._hours_since(self.source_runs.get(name, ""))

    def is_known(self, job: Job) -> bool:
        return job.id in self.jobs or job.id in self.rejected

    def reject(self, jobs: list[Job]) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        for job in jobs:
            self.rejected[job.id] = today

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
        self.rejected = {i: d for i, d in self.rejected.items() if d >= limit[:10]}

    def save(self) -> None:
        self.prune()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self.jobs.values(), key=lambda j: j.posted or j.first_seen, reverse=True)
        payload = {
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "jobs": [j.to_dict() for j in ordered],
            "rejected": self.rejected,
            "source_runs": self.source_runs,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
