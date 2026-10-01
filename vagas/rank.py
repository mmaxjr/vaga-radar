"""Pontuação e seleção das melhores vagas: encaixe com o perfil, frescor, penalidades e teto por empresa."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable, TypeVar

from .ficha import Ficha
from .models import Job
from .profile import Perfil

T = TypeVar("T")
BRT = timezone(timedelta(hours=-3))
# Fontes da mais para a menos confiável: na duplicada, fica a primeira da lista
PRIORIDADE = ["gupy", "zoho", "empresa", "infojobs", "empregare", "himalayas", "jobicy", "linkedin", "geekhunter",
              "github", "programathor", "vagas.com.br", "remotive", "remoteok", "weworkremotely"]


def _ascii(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _fonte(job: Job) -> str:
    return job.source.split(":")[0]


def empresa_chave(job: Job) -> str:
    nome = job.company.strip().lower()
    return nome or f"__sem_empresa_{job.id}"


def _titulo_chave(job: Job) -> str:
    t = _ascii(job.title)
    t = re.sub(r"remote work|trabalho remoto|ref ?#? ?\d+", " ", t)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


def dedupe(jobs: list[Job]) -> list[Job]:
    """Mesma empresa + mesmo título (sem "Remote Work", "REF#123"): fica a fonte mais confiável; a ordem original se mantém."""
    def peso(j: Job) -> int:
        return PRIORIDADE.index(_fonte(j)) if _fonte(j) in PRIORIDADE else len(PRIORIDADE)

    melhor: dict[tuple, Job] = {}
    for j in jobs:
        chave = (_ascii(j.company.strip()), _titulo_chave(j)) if j.company.strip() else ("", j.id)
        if chave not in melhor or peso(j) < peso(melhor[chave]):
            melhor[chave] = j
    escolhidas = {id(j) for j in melhor.values()}
    return [j for j in jobs if id(j) in escolhidas]


def idade_dias(job: Job, hoje: date) -> tuple[int, bool]:
    """(dias desde a publicação, True) ou, sem data de publicação, (dias desde que foi vista, False)."""
    if job.posted:
        try:
            dt = datetime.fromisoformat(job.posted.replace("Z", "+00:00"))
            dia = (dt if dt.tzinfo else dt.replace(tzinfo=BRT)).astimezone(BRT).date() if len(job.posted) > 10 else dt.date()
            return (hoje - dia).days, True
        except ValueError:
            pass
    vista = datetime.fromisoformat(job.first_seen).astimezone(BRT).date()
    return (hoje - vista).days, False


@dataclass
class Pontuacao:
    pontos: float
    encaixe: int
    cobre: list[str] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)


def _frescor(dias: int) -> float:
    return 20 if dias <= 0 else 16 if dias <= 1 else 10 if dias <= 3 else 5 if dias <= 7 else 0


def pontuar(job: Job, perfil: Perfil, texto: str = "", ficha: Ficha | None = None, hoje: date | None = None) -> Pontuacao:
    hoje = hoje or datetime.now(BRT).date()
    encaixe, cobre = perfil.encaixe(f"{job.title} {texto}")
    pontos, motivos = encaixe * 0.6 + min(20, 2 * perfil.interesse(job.title)), []  # área de interesse vale até 20
    dias, datada = idade_dias(job, hoje)
    pontos += _frescor(dias) * (1 if datada else 0.5)
    titulo = _ascii(job.title)
    if re.search(r"estagi|trainee", titulo):
        pontos -= 40
        motivos.append("estágio")
    elif re.search(r"junior|(?<![a-z])jr(?![a-z])", titulo):
        pontos -= 25
        motivos.append("nível júnior")
    elif re.search(r"principal|staff|head of|diretor|director|(?<![a-z])lead(?![a-z])|(?<![a-z])vp(?![a-z])", titulo):
        pontos -= 8
        motivos.append("nível muito sênior")
    if re.search(r"banco de talentos|cadastro reserva|talent pool", titulo):
        pontos -= 30
        motivos.append("banco de talentos (não é vaga aberta)")
    if re.search(r"pleno|senior|(?<![a-z])(pl|sr|ii|iii)(?![a-z])", titulo):
        pontos += 4  # nível compatível com o de quem procura
    if job.scope == "remoto" and re.search(r"presencial|hibrid|hybrid|on-?site", titulo):
        pontos -= 40
        motivos.append("o título diz presencial/híbrido")
    for termo in perfil.fora_do_perfil(titulo):
        pontos -= 12
        motivos.append(f"fora do seu perfil ({termo})")
    if ficha is not None:
        if job.scope == "remoto" and ficha.remoto != "confirmado":
            pontos -= 45
            motivos.append("regime remoto não confirmado")
        if job.scope == "remoto" and ficha.cita_presencial:
            pontos -= 10
            motivos.append("o texto cita presencial/híbrido")
        if ficha.idioma == "pt":
            pontos += 5
        for termo in ficha.cloud[:3]:
            pontos -= 8
            motivos.append(f"exige {termo}")
        if ficha.residencia:
            pontos -= 50
            motivos.append(f"residir em {ficha.residencia}")
        if ficha.plantao:
            pontos -= 6
            motivos.append("plantão")
        if ficha.ingles in ("avançado", "provável") and perfil.ingles != "avançado":
            pontos -= 6
            motivos.append("inglês avançado" if ficha.ingles == "avançado" else "inglês provável")
    return Pontuacao(pontos, encaixe, cobre, motivos)


def limitar_por_empresa(itens: list[T], chave: Callable[[T], str], n: int, por_empresa: int) -> tuple[list[T], dict[str, list[T]]]:
    """Mantém a ordem; no máximo `por_empresa` por empresa e `n` no total. O excedente por empresa vai para o resto."""
    mantidos: list[T] = []
    resto: dict[str, list[T]] = {}
    contagem: dict[str, int] = {}
    for item in itens:
        c = chave(item)
        if len(mantidos) < n and contagem.get(c, 0) < por_empresa:
            mantidos.append(item)
            contagem[c] = contagem.get(c, 0) + 1
        else:
            resto.setdefault(c, []).append(item)
    return mantidos, resto
