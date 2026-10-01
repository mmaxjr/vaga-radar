"""Top do dia: ranqueia o histórico pelo perfil, lê a descrição das melhores e imprime uma ficha por vaga.

    python -m vagas.top --jobs pessoal/jobs.json --profile pessoal/perfil.toml --cache pessoal/descricoes.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .describe import Descricoes
from .ficha import Ficha, analisar
from .models import Job
from .profile import Perfil
from .rank import BRT, Pontuacao, dedupe, empresa_chave, limitar_por_empresa, pontuar


@dataclass
class Item:
    job: Job
    ficha: Ficha
    pont: Pontuacao


def montar(jobs: list[Job], perfil: Perfil, descricoes: Descricoes, n: int = 10, pool: int = 40,
           hoje: date | None = None, por_empresa: int = 2) -> tuple[list[Item], dict[str, list[Item]]]:
    hoje = hoje or datetime.now(BRT).date()
    pre = sorted(dedupe(jobs), key=lambda j: pontuar(j, perfil, hoje=hoje).pontos, reverse=True)
    pre, cortadas = limitar_por_empresa(pre, empresa_chave, pool, por_empresa=4)  # a peneira não deixa uma empresa ocupar tudo

    def item(job: Job, achado: tuple[str, str] | None) -> Item:
        texto, prazo = achado if achado else ("", "")
        ficha = analisar(texto, perfil.lacunas, remote_proof=True, prazo=prazo, lida=achado is not None)
        return Item(job, ficha, pontuar(job, perfil, texto, ficha, hoje))

    itens = sorted((item(job, descricoes.obter(job)) for job in pre), key=lambda it: it.pont.pontos, reverse=True)
    top, resto = limitar_por_empresa(itens, lambda it: empresa_chave(it.job), n, por_empresa)
    for empresa, jobs_cortadas in cortadas.items():  # entram no resumo só pelo título (sem ler a descrição)
        resto.setdefault(empresa, []).extend(item(job, None) for job in jobs_cortadas)
    for lista in resto.values():
        lista.sort(key=lambda it: it.pont.pontos, reverse=True)
    return top, resto


def _prazo(prazo: str) -> str:
    try:
        return datetime.strptime(prazo, "%Y-%m-%d").strftime("%d/%m")
    except ValueError:
        return "n/d"


def _data(job: Job) -> str:
    return job.posted[:10] if job.posted else "sem data"


def formatar(top: list[Item], resto: dict[str, list[Item]], perfil: Perfil, hoje: date | None = None) -> str:
    linhas = []
    for i, it in enumerate(top, 1):
        j, f, p = it.job, it.ficha, it.pont
        linhas.append(f"#{i:<2} {j.title.strip()[:78]} | {j.company[:26] or 'empresa n/d'} | {j.source.split(':')[0]} | {_data(j)}")
        linhas.append(f"    {j.url}")
        if not f.lida:
            linhas.append(f"    Encaixe {p.encaixe}% | descrição não lida (abra a vaga para ver os requisitos)")
        else:
            linhas.append(f"    Encaixe {p.encaixe}% | Remoto: {f.remoto} | Contrato: {f.contrato} | Inglês: {f.ingles} | Prazo: {_prazo(f.prazo)}")
        if p.cobre:
            linhas.append(f"    Cobre: {', '.join(p.cobre)}")
        falta = [f"{t} (exigido)" for t in f.cloud] + [f"{t} (diferencial)" for t in f.cloud_desejavel]
        if falta:
            linhas.append(f"    Falta: {', '.join(falta)}")
        alertas = list(p.motivos)
        if f.cita_presencial:
            alertas.append("o texto cita presencial/híbrido")
        if alertas:
            linhas.append(f"    Atenção: {' | '.join(alertas)}")
        sugestao = perfil.curriculo(f"{j.title} {' '.join(p.cobre)}")
        if sugestao:
            linhas.append(f"    Currículo sugerido: {sugestao} (confirme comigo)")
        linhas.append("")
    for empresa, itens in resto.items():
        melhores = "; ".join(it.job.title.strip()[:40] for it in itens[:3])
        linhas.append(f"{itens[0].job.company or empresa}: {len(itens)} outras (as melhores: {melhores})")
    return "\n".join(linhas).rstrip() + "\n"


def _filtrar(jobs: list[Job], escopo: str, so_hoje: bool, hoje: date) -> list[Job]:
    if escopo != "todos":
        jobs = [j for j in jobs if j.scope == escopo]
    if so_hoje:
        from .rank import idade_dias
        jobs = [j for j in jobs if idade_dias(j, hoje)[0] <= 0]
    return jobs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vagas.top", description="Top do dia: vagas ranqueadas pelo seu perfil, com ficha")
    ap.add_argument("--jobs", default="pessoal/jobs.json")
    ap.add_argument("--profile", default="pessoal/perfil.toml")
    ap.add_argument("--cache", default="pessoal/descricoes.json")
    ap.add_argument("--n", type=int, default=10, help="quantas vagas mostrar")
    ap.add_argument("--pool", type=int, default=40, help="quantas candidatas têm a descrição lida")
    ap.add_argument("--orcamento", type=int, default=40, help="máximo de requisições de descrição por execução")
    ap.add_argument("--escopo", choices=["remoto", "local", "todos"], default="remoto")
    ap.add_argument("--hoje", action="store_true", help="só vagas publicadas (ou vistas pela 1ª vez) hoje")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    hoje = datetime.now(BRT).date()
    jobs = [Job.from_dict(d) for d in json.loads(Path(args.jobs).read_text(encoding="utf-8"))["jobs"]]
    jobs = _filtrar(jobs, args.escopo, args.hoje, hoje)
    perfil = Perfil.carregar(args.profile)
    descricoes = Descricoes(args.cache, orcamento=args.orcamento)
    itens, resto = montar(jobs, perfil, descricoes, n=args.n, pool=args.pool, hoje=hoje)
    print(f"Top {len(itens)} de {len(jobs)} vagas ({hoje:%d/%m/%Y})\n")
    print(formatar(itens, resto, perfil, hoje))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
