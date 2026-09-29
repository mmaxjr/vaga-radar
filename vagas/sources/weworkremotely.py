"""We Work Remotely (internacional) via RSS."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from .. import http
from ..models import Job

FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]


def fetch(cfg: dict) -> list[Job]:
    jobs = []
    for feed in FEEDS:
        r = http.get(feed)
        if r is None:
            continue
        for item in ET.fromstring(r.content).iter("item"):
            raw = (item.findtext("title") or "").strip()
            company, _, title = raw.partition(": ")  # "Empresa: Cargo"
            try:
                posted = parsedate_to_datetime(item.findtext("pubDate")).isoformat()
            except (TypeError, ValueError):
                posted = ""
            jobs.append(Job(
                source="weworkremotely",
                title=title or raw,
                url=(item.findtext("link") or "").strip(),
                company=company if title else "",
                location=item.findtext("region") or "",
                posted=posted,
                international=True,
            ))
    return jobs
