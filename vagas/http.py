from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)
_blocked: set[str] = set()  # sites que responderam 429 nesta execução

UA = "Mozilla/5.0 (compatible; vagas-remotas/0.1; +https://github.com/)"

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})


def get(url: str, *, params: dict | None = None, headers: dict | None = None,
        retries: int = 2, timeout: int = 25) -> requests.Response | None:
    """GET com retry simples. Devolve None se falhar (as fontes seguem sem a página).

    Depois de um HTTP 429 o site fica bloqueado até o fim da execução: insistir só piora o bloqueio."""
    host = urlsplit(url).hostname
    if host in _blocked:
        return None
    for attempt in range(retries + 1):
        try:
            r = _session.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            log.warning("erro em %s: %s", url, e)
        else:
            if r.status_code == 200:
                return r
            if r.status_code in (403, 404, 429):
                log.warning("%s -> HTTP %s (desistindo)", url, r.status_code)
                if r.status_code == 429:
                    _blocked.add(host)
                return None
            log.warning("%s -> HTTP %s", url, r.status_code)
        time.sleep(1.5 * (attempt + 1))
    return None


def decode(r: requests.Response) -> str:
    """Alguns sites brasileiros ainda servem latin-1/cp1252."""
    try:
        return r.content.decode("utf-8")
    except UnicodeDecodeError:
        return r.content.decode("cp1252", errors="replace")
