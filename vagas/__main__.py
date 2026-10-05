from __future__ import annotations

import argparse
import logging
import sys
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import http, verify
from .filters import JobFilter
from .notify import format_digest, send_telegram
from .site import render_site
from .sources import SOURCES
from .store import Store

log = logging.getLogger("vagas")


def collect(cfg: dict, names: list[str]) -> dict[str, list]:
    """Roda as fontes em paralelo (cada uma fala com um site diferente). Devolve fonte -> vagas."""
    def run(name: str):
        try:
            jobs = SOURCES[name](cfg)
            log.info("%-15s %4d vagas coletadas", name, len(jobs))
            if not jobs:
                log.warning("%s devolveu 0 vagas: a fonte pode ter quebrado (endereço ou layout mudou)", name)
            return jobs
        except Exception:  # uma fonte quebrada não pode derrubar as outras
            log.exception("fonte %s falhou", name)
            return []

    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        return dict(zip(names, pool.map(run, names)))


def _cedo(store: Store, cfg: dict, name: str) -> bool:
    """A fonte rodou há menos que o `min_hours` da sua seção do config (ex.: [linkedin] min_hours = 6)?"""
    horas, minimo = store.hours_since_source(name), cfg.get(name, {}).get("min_hours", 0)
    return bool(minimo) and horas is not None and horas < minimo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vagas", description="Vaga Radar: agregador de vagas remotas de TI")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--sources", help=f"lista separada por vírgula. Padrão: todas ({', '.join(SOURCES)})")
    ap.add_argument("--dry-run", action="store_true", help="mostra as vagas novas sem salvar nem enviar")
    ap.add_argument("--no-notify", action="store_true", help="salva mas não envia para o Telegram")
    ap.add_argument("--hide-sources", default="",
                    help="fontes (separadas por vírgula) que ficam fora da página HTML, ex.: linkedin")
    ap.add_argument("--min-hours", type=float, default=None,
                    help="não coleta se a última coleta foi há menos que isso (evita bloqueio por excesso de requisições). "
                         "Padrão: [storage] min_hours do config, ou 0")
    ap.add_argument("--force", action="store_true", help="ignora o intervalo mínimo entre coletas")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    cfg = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    names = args.sources.split(",") if args.sources else list(SOURCES)
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        ap.error(f"fonte desconhecida: {', '.join(unknown)}")

    flt = JobFilter(cfg)
    store = Store(cfg["storage"]["path"], cfg["storage"].get("keep_days", 45))
    min_hours = args.min_hours if args.min_hours is not None else cfg["storage"].get("min_hours", 0)
    since = store.hours_since_last_run()
    if not args.force and not args.dry_run and min_hours and since is not None and since < min_hours:
        log.info("última coleta há %.1f h (mínimo %.1f h): nada a fazer. Use --force para coletar mesmo assim.", since, min_hours)
        return 0
    due = [n for n in names if args.force or not _cedo(store, cfg, n)]
    puladas = [n for n in names if n not in due]
    if not due:
        log.info("todas as fontes pedidas rodaram há pouco (%s): nada a fazer. Use --force.", ", ".join(puladas))
        return 0
    batches = collect(cfg, due)
    log.info("fontes sem vagas: %s | puladas pelo intervalo: %s | bloqueadas (HTTP 429): %s",
             ", ".join(n for n, js in batches.items() if not js) or "nenhuma", ", ".join(puladas) or "nenhuma",
             ", ".join(sorted(http._blocked)) or "nenhuma")
    found = list({j.id: j for js in batches.values() for j in js}.values())  # a mesma vaga pode vir por mais de um termo
    kept = [j for j in found if flt.accepts(j)]

    # Vagas que passam em tudo, menos na prova de "remoto" (ex.: LinkedIn): lê a descrição das que ainda não vimos
    pending = [j for j in found if flt.needs_proof(j) and flt.accepts(j, assume_remote=True) and not store.is_known(j)]
    if pending:
        vcfg = cfg.get("verify", {})
        confirmed, denied = verify.check(pending, vcfg.get("max_per_run", 60), vcfg.get("delay", 2.0))
        kept += confirmed
        if not args.dry_run:
            store.reject(denied)

    per_source = Counter(j.source.split(":")[0] for j in kept)
    log.info("%d coletadas, %d passaram no filtro: %s", len(found), len(kept), dict(per_source))
    new = store.add_new(kept)
    log.info("%d vagas novas", len(new))

    max_items = cfg.get("notify", {}).get("max_items", 60)
    if args.dry_run:
        for msg in format_digest(new, max_items):
            print(msg)
        return 0

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store.source_runs.update({n: now for n in due})
    store.save()
    page = render_site(store.path, frozenset(filter(None, args.hide_sources.split(","))))
    log.info("página gerada: %s", page)
    if new and not args.no_notify:
        send_telegram(format_digest(new, max_items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
