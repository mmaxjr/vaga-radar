from __future__ import annotations

import argparse
import logging
import sys
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import verify
from .filters import JobFilter
from .notify import format_digest, send_telegram
from .site import render_site
from .sources import SOURCES
from .store import Store

log = logging.getLogger("vagas")


def collect(cfg: dict, names: list[str]) -> list:
    """Roda as fontes em paralelo (cada uma fala com um site diferente)."""
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
        return [job for batch in pool.map(run, names) for job in batch]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vagas", description="Vaga Radar: agregador de vagas remotas de TI")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--sources", help=f"lista separada por vírgula. Padrão: todas ({', '.join(SOURCES)})")
    ap.add_argument("--dry-run", action="store_true", help="mostra as vagas novas sem salvar nem enviar")
    ap.add_argument("--no-notify", action="store_true", help="salva mas não envia para o Telegram")
    ap.add_argument("--hide-sources", default="",
                    help="fontes (separadas por vírgula) que ficam fora da página HTML, ex.: linkedin")
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
    found = list({j.id: j for j in collect(cfg, names)}.values())  # a mesma vaga pode vir por mais de um termo
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

    store.save()
    page = render_site(store.path, frozenset(filter(None, args.hide_sources.split(","))))
    log.info("página gerada: %s", page)
    if new and not args.no_notify:
        send_telegram(format_digest(new, max_items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
