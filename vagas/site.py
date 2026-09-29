from __future__ import annotations

import json
from pathlib import Path

# O modelo fica no repositório; o JSON de dados e a página gerada podem ficar em qualquer pasta
TEMPLATE = Path(__file__).resolve().parent.parent / "docs" / "template.html"


def render_site(jobs_json: Path, hide_sources: frozenset[str] = frozenset()) -> Path:
    """Gera docs/index.html com os dados embutidos (funciona abrindo o arquivo direto no navegador).

    `hide_sources` tira fontes só da página (ex.: para um site público), sem apagá-las do JSON.
    """
    template = TEMPLATE.read_text(encoding="utf-8")
    data = json.loads(jobs_json.read_text(encoding="utf-8"))
    data["jobs"] = [j for j in data["jobs"] if j["source"].split(":")[0] not in hide_sources]
    # "</" dentro de <script> poderia fechar a tag antes da hora
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = jobs_json.parent / "index.html"
    out.write_text(template.replace("/*JOBS_JSON*/", payload), encoding="utf-8")
    return out
