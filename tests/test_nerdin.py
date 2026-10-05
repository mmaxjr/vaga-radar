from vagas.sources import nerdin

CARD = """
<div class="vaga-card" data-href="vaga_emprego/vaga-{slug}-{n}.php">
  <h3 class="vaga-titulo"> {titulo} <span class="vaga-nova-badge">Nova</span></h3>
  <p class="vaga-resumo-linha"> {resumo} </p>
  <span class="vaga-empresa-nome">{empresa}</span>
  <div class="vaga-local-linha"><span>Brasília • DF</span></div>
  <p class="vaga-meta-extra">Sistemas • <time datetime="2026-10-05T11:21:14-04:00">Há 1 hora</time></p>
</div>"""

HTML = (CARD.format(slug="analista-redes", n=1, titulo="Analista de Redes", resumo="CLT • Pleno • Home Office", empresa="ACME")
        + CARD.format(slug="dev-java", n=2, titulo="Dev Java", resumo="CLT • Senior • Híbrido", empresa="Beta")
        + CARD.format(slug="suporte", n=3, titulo="Suporte N2", resumo="Pleno", empresa="Gama"))


def test_parse_fica_so_com_as_vagas_home_office():
    jobs = nerdin.parse(HTML)
    assert [j.title for j in jobs] == ["Analista de Redes"]  # o badge "Nova" não entra no título
    j = jobs[0]
    assert j.url == "https://www.nerdin.com.br/vaga_emprego/vaga-analista-redes-1.php"
    assert (j.source, j.company, j.scope) == ("nerdin", "ACME", "remoto")
    assert j.posted.startswith("2026-10-05")


def test_fetch_para_na_pagina_vazia(monkeypatch):
    class R:
        content = HTML.encode()
    paginas = []
    monkeypatch.setattr(nerdin.http, "get", lambda url, params=None, **kw: paginas.append(params["pagina"]) or (R() if params["pagina"] < 3 else None))
    assert len(nerdin.fetch({"nerdin": {"pages": 5}})) == 2  # páginas 1 e 2 vieram; a 3 falhou e encerrou
    assert paginas == [1, 2, 3]
