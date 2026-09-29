from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Job:
    source: str
    title: str
    url: str
    company: str = ""
    location: str = ""
    posted: str = ""  # ISO 8601; vazio se a fonte não informa
    tags: list[str] = field(default_factory=list)
    salary: str = ""
    international: bool = False
    scope: str = "remoto"  # "remoto" (100% remota) ou "local" (vaga na sua cidade, qualquer regime)
    first_seen: str = field(default_factory=now_iso)

    @property
    def id(self) -> str:
        return hashlib.sha1(canonical_url(self.url).encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        d = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**d)


def canonical_url(url: str) -> str:
    """Remove query string e fragmento, que mudam a cada requisição (tracking)."""
    return url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
