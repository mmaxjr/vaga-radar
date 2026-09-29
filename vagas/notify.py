from __future__ import annotations

import html
import logging
import os
from collections import defaultdict

import requests

from .models import Job

log = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4000  # o máximo da API é 4096 caracteres por mensagem


def format_digest(jobs: list[Job], max_items: int = 60) -> list[str]:
    """Monta o resumo em HTML do Telegram, já quebrado em mensagens de tamanho permitido."""
    if not jobs:
        return []
    total = len(jobs)
    jobs = sorted(jobs, key=lambda j: j.posted or j.first_seen, reverse=True)[:max_items]
    groups: dict[str, list[Job]] = defaultdict(list)
    for j in jobs:
        groups["Na sua cidade" if j.scope == "local" else "Remoto internacional" if j.international
               else "Remoto Brasil"].append(j)

    lines = [f"<b>{total} vagas novas</b>"]
    for name in ("Na sua cidade", "Remoto Brasil", "Remoto internacional"):
        if name not in groups:
            continue
        lines.append(f"\n<b>{name}</b>")
        for j in groups[name]:
            lines.append(_line(j))

    if total > len(jobs):
        lines.append(f"\n<i>+{total - len(jobs)} vagas no site/JSON</i>")

    messages, current = [], ""
    for line in lines:
        if len(current) + len(line) + 1 > TELEGRAM_LIMIT:
            messages.append(current)
            current = ""
        current += line + "\n"
    messages.append(current)
    return messages


def _line(j: Job) -> str:
    who = f" - {html.escape(j.company)}" if j.company else ""
    extra = f" ({html.escape(j.salary)})" if j.salary else ""
    if j.scope == "local" and j.location:  # regime importa: presencial, híbrido ou remoto
        extra += f" ({html.escape(j.location)})"
    return (f'• <a href="{html.escape(j.url, quote=True)}">{html.escape(j.title)}</a>{who}{extra} '
            f"<i>[{html.escape(j.source)}]</i>")


def send_telegram(messages: list[str]) -> bool:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        log.info("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não definidos: pulando envio")
        return False
    for text in messages:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=20, json={
            "chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True,
        })
        if not r.ok:
            log.error("Telegram respondeu %s: %s", r.status_code, r.text[:200])
            return False
    return True
