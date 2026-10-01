"""Ficha da vaga: o que a descrição diz sobre cloud, inglês, contrato, residência, plantão e regime.

Tudo por regras sobre o texto, sem IA. Quando o texto não permite concluir, o valor é "n/d" ou vazio: nada de chute.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import verify

PT_WORDS = re.compile(r"\b(de|da|do|das|dos|para|com|uma|que|em|na|no|experi[eê]ncia|conhecimento|vaga|requisitos)\b", re.I)
EN_WORDS = re.compile(r"\b(the|and|with|for|you|your|will|experience|knowledge|team|work|we|are|have|of|to)\b", re.I)

DESEJAVEL = re.compile(r"diferencia(?:l|is)|desej[aá]ve(?:l|is)|nice to have|b[oô]nus|bonus|preferred|a plus|is a plus", re.I)
OBRIGATORIO = re.compile(
    r"requisitos|requirements|obrigat[oó]ri|imprescind[ií]ve|must[- ]have|qualifica[cç][oõ]es|what you(?:'ll)? (?:need|bring)"
    r"|you have|we are looking for", re.I)

ING_AVANCADO = re.compile(
    r"ingl[eê]s (?:avan[cç]ado|fluente)|fluente em ingl[eê]s|avan[cç]ado em ingl[eê]s|fluent (?:in )?english|advanced (?:level of )?english"
    r"|english (?:proficiency|fluency)|(?:advanced|fluent|professional) proficiency in english", re.I)
ING_INTERMEDIARIO = re.compile(r"ingl[eê]s (?:intermedi|t[eé]cnico|b[aá]sico)|intermediate english|english (?:intermediate|at an intermediate)", re.I)
ING_QUALQUER = re.compile(r"ingl[eê]s|english", re.I)

PJ = re.compile(r"(?<![a-z])pj(?![a-z])|pessoa jur[ií]dica|prestador de servi[cç]os|contractor|(?<![a-z])b2b(?![a-z])", re.I)
CLT = re.compile(r"(?<![a-z])clt(?![a-z])|carteira assinada", re.I)
RESIDENCIA = re.compile(r"(?:[Rr]esidir|[Mm]orar)\s+(?:em|na|no|nas|nos)\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ' ]{2,40}(?:/[A-Z]{2})?)")
PAIS = re.compile(r"^(?:o\s+)?(?:brasil|brazil)\b", re.I)
PROVA_DE_EXPERIENCIA = re.compile(r"experi[eê]ncia|demonstrad|comprov|registro|tempo de|per[ií]odo", re.I)
# Certificações que costumam ser eliminatórias (nome interno -> padrão)
CERTIFICACOES = {
    "itil": r"itil", "cissp": r"cissp", "cism": r"cism", "cisa": r"(?<![a-z])cisa(?![a-z])", "ceh": r"(?<![a-z])ceh(?![a-z])",
    "oscp": r"oscp", "security+": r"security\+", "cysa+": r"cysa\+", "ecsa": r"ecsa", "ecih": r"ecih", "csih": r"csih",
    "ccna": r"ccna", "ccnp": r"ccnp", "aws certified": r"aws certified|aws solutions architect|cloud practitioner",
    "az-900": r"az-?900|az-?104", "pmp": r"(?<![a-z])pmp(?![a-z])", "cobit": r"cobit",
}
PLANTAO = re.compile(
    r"(?<![a-z])(?:plant[aã]o|sobreaviso|on-?call|12x36|escala|turnos?|24/7|24x7)(?![a-z])|finais? de semana|fins de semana", re.I)


@dataclass
class Ficha:
    lida: bool = True
    remoto: str = "a confirmar"          # "confirmado" | "a confirmar"
    cita_presencial: bool = False        # o texto cita presencial/híbrido/escritório
    cloud: list[str] = field(default_factory=list)            # lacunas exigidas
    cloud_desejavel: list[str] = field(default_factory=list)  # lacunas só "diferencial"
    ingles: str = "n/d"                  # avançado | intermediário | desejável | mencionado | provável | nenhum | n/d
    idioma: str = "pt"                   # "pt" | "en"
    contrato: str = "n/d"                # CLT | PJ | CLT/PJ | n/d
    residencia: str = ""                 # cidade exigida, se houver
    plantao: bool = False
    prazo: str = ""                      # AAAA-MM-DD
    certificacoes: list[str] = field(default_factory=list)  # certificações EXIGIDAS (não as "diferencial")


def idioma_do_texto(texto: str) -> str:
    pt, en = len(PT_WORDS.findall(texto)), len(EN_WORDS.findall(texto))
    return "en" if en > pt * 1.2 else "pt"


def contexto(texto: str, pos: int) -> str:
    """'desejavel' ou 'obrigatorio', pelo marcador mais próximo antes de `pos` (ou "diferencial" na mesma frase)."""
    depois = texto[pos:pos + 80].split(".")[0]
    if DESEJAVEL.search(depois):
        return "desejavel"
    antes = texto[:pos]
    d = max((m.end() for m in DESEJAVEL.finditer(antes)), default=-1)
    o = max((m.end() for m in OBRIGATORIO.finditer(antes)), default=-1)
    return "desejavel" if d > o else "obrigatorio"


def _cloud(texto: str, lacunas: list[str]) -> tuple[list[str], list[str]]:
    obrigatorias, desejaveis = [], []
    for termo in lacunas:
        rx = re.compile(r"(?<![a-z0-9])" + re.escape(termo) + r"(?![a-z0-9])", re.I)
        contextos = {contexto(texto, m.start()) for m in rx.finditer(texto)}
        if not contextos:
            continue
        (obrigatorias if "obrigatorio" in contextos else desejaveis).append(termo)
    return obrigatorias, desejaveis


def _ingles(texto: str, idioma: str) -> str:
    for rx, nivel in ((ING_AVANCADO, "avançado"), (ING_INTERMEDIARIO, "intermediário"), (ING_QUALQUER, "mencionado")):
        m = rx.search(texto)
        if m:
            return "desejável" if contexto(texto, m.start()) == "desejavel" else nivel
    return "provável" if idioma == "en" else "nenhum"


def _contrato(texto: str) -> str:
    """CLT, PJ, CLT/PJ ou n/d. Ignora "experiência comprovada por contrato PJ ou carteira", que não é o regime da vaga."""
    def vale(rx: re.Pattern) -> bool:
        return any(not PROVA_DE_EXPERIENCIA.search(re.split(r"[.;\n]", texto[:m.start()])[-1]) for m in rx.finditer(texto))
    pj, clt = vale(PJ), vale(CLT)
    return "CLT/PJ" if pj and clt else "PJ" if pj else "CLT" if clt else "n/d"


def _certificacoes(texto: str) -> list[str]:
    achadas = []
    for nome, padrao in CERTIFICACOES.items():
        contextos = {contexto(texto, m.start()) for m in re.finditer(padrao, texto, re.I)}
        if "obrigatorio" in contextos:
            achadas.append(nome)
    return achadas


def _residencia(texto: str) -> str:
    m = RESIDENCIA.search(texto)
    if not m:
        return ""
    lugar = m.group(1).strip()
    return "" if PAIS.match(lugar) else lugar


def analisar(texto: str, lacunas: list[str], *, remote_proof: bool = False, prazo: str = "", lida: bool = True) -> Ficha:
    """Ficha a partir do texto da descrição. `remote_proof`: a própria fonte já garante o regime remoto."""
    if not lida:
        return Ficha(lida=False, remoto="confirmado" if remote_proof else "a confirmar", prazo=prazo)
    idioma = idioma_do_texto(texto)
    obrigatorias, desejaveis = _cloud(texto, lacunas)
    return Ficha(
        remoto="confirmado" if remote_proof or verify.is_remote_text(texto) else "a confirmar",
        cita_presencial=bool(verify.ONSITE_TEXT.search(texto)),
        cloud=obrigatorias,
        cloud_desejavel=desejaveis,
        ingles=_ingles(texto, idioma),
        idioma=idioma,
        contrato=_contrato(texto),
        certificacoes=_certificacoes(texto),
        residencia=_residencia(texto),
        plantao=bool(PLANTAO.search(texto)),
        prazo=prazo,
    )
