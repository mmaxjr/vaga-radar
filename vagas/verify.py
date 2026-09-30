"""Confirma o regime remoto lendo a descrição da vaga, para fontes que não informam o regime (LinkedIn).

Antes, o LinkedIn só valia se o título dissesse "remoto" e muita vaga boa se perdia. Agora a vaga que passa em todos
os outros filtros mas não diz "remoto" no título tem a descrição lida: entra se a descrição afirma trabalho remoto e não
cita presencial, híbrido ou escritório. Em caso de dúvida, descarta (o objetivo é só vaga 100% remota).
"""
from __future__ import annotations

import logging
import re
import time
from typing import Callable

from .models import Job
from .sources import linkedin

log = logging.getLogger(__name__)

# Frases que afirmam o REGIME da vaga. Não contam: "acesso remoto"/"monitoramento remoto" (infra), "work from anywhere"
# e "auxílio home office" (benefícios que aparecem também em vagas presenciais ou híbridas).
REMOTE_TEXT = re.compile(
    r"100% ?remot|fully[- ]remote|totalmente remot|trabalho (100% )?remoto|remote (work|position|role|job|opportunity)"
    r"|modalidade remota|regime remoto|atua[cç][aã]o remota|vaga remota|posi[cç][aã]o remota|remote[- ]first"
    r"|(this|the) (role|position|job) is (fully |100% )?remote|remote in brazil"
    r"|(trabalho|regime|modelo|atua[cç][aã]o|vaga|posi[cç][aã]o|modalidade) (em |de )?home ?office",
    re.I)
# Regime presencial/híbrido. "Nuvem híbrida" ou "ambientes híbridos" (tecnologia) não contam como regime.
ONSITE_TEXT = re.compile(
    r"on-?site|presenci(al|ais|almente)|in[- ]office|office[- ]based|escrit[oó]rios?|\bdias? (na|por) semana no"
    r"|(modelo|regime|trabalho|modalidade|formato|atua[cç][aã]o|vaga|posi[cç][aã]o|jornada|contrato)[^.]{0,20}h[ií]brid"
    r"|h[ií]brid[oa]\s*\(?\d|h[ií]brid[oa]\s+(com|de)\s+\d|hybrid (work|model|role|position|schedule|setup|arrangement|mode)"
    r"|(work|working|model|schedule|setup|arrangement)\s*:?\s*hybrid|hybrid\b.{0,25}\b(days?|office|on-?site)",
    re.I)

TEXT_FETCHERS: dict[str, Callable[[Job], str | None]] = {"linkedin": linkedin.job_text}


def is_remote_text(text: str) -> bool:
    return bool(REMOTE_TEXT.search(text)) and not ONSITE_TEXT.search(text)


def check(jobs: list[Job], limit: int = 60, delay: float = 2.0) -> tuple[list[Job], list[Job]]:
    """Devolve (confirmadas como remotas, descartadas). Para ao primeiro bloqueio da fonte ou ao atingir o limite."""
    ok, no = [], []
    for job in jobs[:limit]:
        fetch_text = TEXT_FETCHERS.get(job.source)
        text = fetch_text(job) if fetch_text else None
        time.sleep(delay)
        if text is None:  # falha ou bloqueio: sem prova, sem decisão (tenta de novo na próxima vez)
            log.warning("verificação interrompida em %s (sem resposta)", job.source)
            break
        (ok if is_remote_text(text) else no).append(job)
    log.info("verificação de remoto: %d confirmadas, %d descartadas, %d ficaram para a próxima",
             len(ok), len(no), max(0, len(jobs) - len(ok) - len(no)))
    return ok, no
