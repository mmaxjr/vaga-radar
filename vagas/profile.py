"""Perfil de quem procura vaga: habilidades (com peso), lacunas e currículos. Vive em um TOML local, fora do Git.

Exemplo de perfil.toml:
    [perfil]
    ingles = "intermediário"   # nível de inglês de quem procura
    referencia = 30            # soma de pesos que vale 100% de encaixe

    [habilidades]              # termo = peso de 1 a 5
    bgp = 5
    "github actions" = 2

    [lacunas]
    termos = ["aws", "kubernetes"]   # o que você ainda NÃO tem; vaga que exige isso perde pontos

    [curriculos]               # regex = nome do currículo; vale o primeiro que casar
    padrao = "Curriculo-Completo"
    "redes|network" = "Analista-de-Redes"
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _tem(texto: str, termo: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(termo) + r"(?![a-z0-9])", texto, re.I))


@dataclass(frozen=True)
class Perfil:
    habilidades: dict[str, int]
    lacunas: list[str]
    curriculos: dict[str, str] = field(default_factory=dict)
    ingles: str = "?"
    referencia: int = 30

    @classmethod
    def carregar(cls, caminho: str | Path) -> "Perfil":
        dados = tomllib.loads(Path(caminho).read_text(encoding="utf-8"))
        meta = dados.get("perfil", {})
        return cls(
            habilidades={k: int(v) for k, v in dados.get("habilidades", {}).items()},
            lacunas=list(dados.get("lacunas", {}).get("termos", [])),
            curriculos=dict(dados.get("curriculos", {})),
            ingles=meta.get("ingles", "?"),
            referencia=int(meta.get("referencia", 30)),
        )

    def encaixe(self, texto: str) -> tuple[int, list[str]]:
        """(percentual de 0 a 100, habilidades cobertas por peso decrescente)."""
        cobertas = {h: p for h, p in self.habilidades.items() if _tem(texto, h)}
        pontos = sum(cobertas.values())
        return min(100, round(100 * pontos / self.referencia)), sorted(cobertas, key=lambda h: -cobertas[h])

    def curriculo(self, texto: str) -> str:
        for padrao, nome in self.curriculos.items():
            if padrao != "padrao" and re.search(padrao, texto, re.I):
                return nome
        return self.curriculos.get("padrao", "")
