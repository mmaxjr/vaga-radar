"""Top do dia: ranqueia o histórico pelo perfil, lê a descrição das melhores e imprime uma ficha por vaga.

    python -m vagas.top --jobs pessoal/jobs.json --profile pessoal/perfil.toml --cache pessoal/descricoes.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .describe import Descricoes
from .ficha import Ficha, analisar, idioma_do_texto
from .models import Job
from .profile import Perfil
from .rank import BRT, Pontuacao, dedupe, empresa_chave, limitar_por_empresa, pontuar


PRE_POR_EMPRESA = 8  # na 1ª peneira (só pelo título) vale um teto largo: o título engana, a descrição decide


@dataclass
class Item:
    job: Job
    ficha: Ficha
    pont: Pontuacao


def _nao_confirmada(it: "Item") -> bool:
    """Vaga remota cujo regime nem a fonte nem a descrição provam: vai para depois das confirmadas."""
    return it.job.scope == "remoto" and it.ficha.remoto != "confirmado"


def idioma_do_item(it: "Item") -> str:
    """Idioma da vaga: o da descrição, quando lida; senão o do título."""
    return it.ficha.idioma if it.ficha.lida else idioma_do_texto(it.job.title)


def montar(jobs: list[Job], perfil: Perfil, descricoes: Descricoes, n: int = 10, pool: int = 40,
           hoje: date | None = None, por_empresa: int = 2, idioma: str = "todos") -> tuple[list[Item], dict[str, list[Item]]]:
    hoje = hoje or datetime.now(BRT).date()
    pre = sorted(dedupe(jobs), key=lambda j: pontuar(j, perfil, hoje=hoje).pontos, reverse=True)
    pre, cortadas = limitar_por_empresa(pre, empresa_chave, pool, por_empresa=PRE_POR_EMPRESA)  # a peneira não deixa uma empresa ocupar tudo

    def item(job: Job, achado: tuple[str, str] | None) -> Item:
        texto, prazo = achado if achado else ("", "")
        garantido = job.scope == "local" or job.source.split(":")[0] != "linkedin"  # o LinkedIn erra no filtro "remoto"
        ficha = analisar(texto, perfil.lacunas, remote_proof=garantido, prazo=prazo, lida=achado is not None)
        return Item(job, ficha, pontuar(job, perfil, texto, ficha, hoje))

    def do_idioma(it: Item) -> bool:
        return idioma == "todos" or idioma_do_item(it) == idioma

    itens = sorted((item(job, descricoes.obter(job)) for job in pre), key=lambda it: (_nao_confirmada(it), -it.pont.pontos))
    top, resto = limitar_por_empresa([it for it in itens if do_idioma(it)], lambda it: empresa_chave(it.job), n, por_empresa)
    for empresa, jobs_cortadas in cortadas.items():  # entram no resumo só pelo título (sem ler a descrição)
        resto.setdefault(empresa, []).extend(it for it in (item(job, None) for job in jobs_cortadas) if do_idioma(it))
    for lista in resto.values():
        lista.sort(key=lambda it: it.pont.pontos, reverse=True)
    return top, resto


GRUPOS = ["MARINGÁ", "PYTHON / PROGRAMAÇÃO", "REDES, INFRA E SEGURANÇA", "OUTRAS"]
PROG = re.compile(r"python|back-?end|full-?stack|desenvolv|developer|software|programador|(?<![a-z])dev(?![a-z])", re.I)
INFRA = re.compile(r"rede|network|infra|segur|secur|cyber|(?<![a-z])(?:noc|sre)(?![a-z])|devops|sysadmin|administrador|suporte|support"
                   r"|linux|monitor|observab|telecom|sistemas", re.I)


def agrupar(jobs: list[Job], perfil: Perfil, descricoes: Descricoes, n: int = 8, pool: int = 40,
            hoje: date | None = None) -> dict[str, list[Item]]:
    """Maringá, Python, redes/infra/segurança e o resto, cada grupo ranqueado à parte: nenhum some atrás dos outros."""
    partes: dict[str, list[Job]] = {nome: [] for nome in GRUPOS}
    for job in jobs:
        if job.scope == "local":
            partes[GRUPOS[0]].append(job)
        else:
            partes[next((nome for nome, rx in ((GRUPOS[1], PROG), (GRUPOS[2], INFRA)) if rx.search(job.title)), GRUPOS[3])].append(job)
    return {nome: montar(js, perfil, descricoes, n=n, pool=pool, hoje=hoje)[0] for nome, js in partes.items()}


def _prazo(prazo: str) -> str:
    try:
        return datetime.strptime(prazo, "%Y-%m-%d").strftime("%d/%m")
    except ValueError:
        return "n/d"


def _data(job: Job) -> str:
    return job.posted[:10] if job.posted else "sem data"


def formatar(top: list[Item], resto: dict[str, list[Item]], perfil: Perfil, hoje: date | None = None) -> str:
    linhas = []
    aviso = False
    for i, it in enumerate(top, 1):
        j, f, p = it.job, it.ficha, it.pont
        if _nao_confirmada(it) and not aviso:
            aviso = True
            linhas.append("--- regime remoto NÃO confirmado: confira o anúncio antes de se candidatar ---\n")
        linhas.append(f"#{i:<2} [{idioma_do_item(it).upper()}] {j.title.strip()[:74]} | {j.company[:26] or 'empresa n/d'} | {j.source.split(':')[0]} | {_data(j)}")
        linhas.append(f"    {j.url}")
        if not f.lida:
            linhas.append(f"    Encaixe {p.encaixe}% | descrição não lida (abra a vaga para ver os requisitos)")
        else:
            linhas.append(f"    Encaixe {p.encaixe}% | Remoto: {f.remoto} | Contrato: {f.contrato} | Inglês: {f.ingles} | Prazo: {_prazo(f.prazo)}")
        if p.cobre:
            linhas.append(f"    Cobre: {', '.join(p.cobre)}")
        falta = ([f"{t} (exigido)" for t in f.cloud] + [f"{t} (diferencial)" for t in f.cloud_desejavel]
                 + [f"certificação {c.upper()}" for c in f.certificacoes if c not in perfil.certificacoes])
        if falta:
            linhas.append(f"    Falta: {', '.join(falta)}")
        if p.motivos:
            linhas.append(f"    Atenção: {' | '.join(p.motivos)}")
        sugestao = perfil.curriculo(f"{j.title} {' '.join(p.cobre)}", f.idioma)
        if sugestao:
            linhas.append(f"    Currículo sugerido: {sugestao} (confirme comigo)")
        linhas.append("")
    grandes = sorted(((e, its) for e, its in resto.items() if not e.startswith("__") and len(its) >= 3),
                     key=lambda par: -len(par[1]))
    for empresa, itens in grandes[:8]:
        melhores = "; ".join(it.job.title.strip()[:40] for it in itens[:3])
        linhas.append(f"{itens[0].job.company or empresa}: {len(itens)} outras (as melhores: {melhores})")
    menores = sum(len(its) for e, its in resto.items()) - sum(len(its) for _, its in grandes[:8])
    if menores > 0:
        linhas.append(f"(+{menores} vagas de empresas menores, fora do Top)")
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
    ap.add_argument("--pool", type=int, default=60, help="quantas candidatas têm a descrição lida")
    ap.add_argument("--orcamento", type=int, default=60, help="máximo de requisições de descrição por execução")
    ap.add_argument("--escopo", choices=["remoto", "local", "todos"], default="remoto")
    ap.add_argument("--idioma", choices=["pt", "en", "todos"], default="todos",
                    help="idioma da vaga; 'todos' mostra uma lista em português e outra em inglês")
    ap.add_argument("--grupos", action="store_true",
                    help="uma lista por grupo (Maringá, Python, redes/infra/segurança, outras); ignora --escopo e --idioma")
    ap.add_argument("--desde", default="", help="só vagas vistas pela 1ª vez depois deste instante (ISO 8601, UTC)")
    ap.add_argument("--hoje", action="store_true", help="só vagas publicadas (ou vistas pela 1ª vez) hoje")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    hoje = datetime.now(BRT).date()
    jobs = [Job.from_dict(d) for d in json.loads(Path(args.jobs).read_text(encoding="utf-8"))["jobs"]]
    jobs = _filtrar(jobs, "todos" if args.grupos else args.escopo, args.hoje, hoje)
    if args.desde:
        jobs = [j for j in jobs if j.first_seen > args.desde]
    perfil = Perfil.carregar(args.profile)
    descricoes = Descricoes(args.cache, orcamento=args.orcamento)
    idiomas = [("pt", "EM PORTUGUÊS"), ("en", "EM INGLÊS")] if args.idioma == "todos" else [(args.idioma, "")]
    print(f"{len(jobs)} vagas consideradas ({hoje:%d/%m/%Y})\n")
    if args.grupos:
        for nome, itens in agrupar(jobs, perfil, descricoes, n=args.n, pool=args.pool, hoje=hoje).items():
            print(f"========== {nome}: {len(itens)} vagas ==========\n")
            print(formatar(itens, {}, perfil, hoje))
        return 0
    for codigo, titulo in idiomas:
        itens, resto = montar(jobs, perfil, descricoes, n=args.n, pool=args.pool, hoje=hoje, idioma=codigo)
        if titulo:
            print(f"========== {titulo}: Top {len(itens)} ==========\n")
        print(formatar(itens, resto, perfil, hoje))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
