"""Dados estruturados `JobPosting` (schema.org) que muitas páginas de vaga publicam para máquinas: mudam menos que o HTML."""
from __future__ import annotations

import json
import re

BLOCO = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def job_posting(html: str) -> dict | None:
    for m in BLOCO.finditer(html):
        try:
            dados = json.loads(m.group(1), strict=False)  # strict=False: aceita quebra de linha dentro do texto
        except ValueError:
            continue
        for d in dados if isinstance(dados, list) else [dados]:
            if isinstance(d, dict) and d.get("@type") == "JobPosting":
                return d
    return None
