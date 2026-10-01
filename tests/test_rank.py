from datetime import date

from vagas.ficha import Ficha
from vagas.models import Job
from vagas.profile import Perfil
from vagas.rank import dedupe, empresa_chave, idade_dias, limitar_por_empresa, pontuar

HOJE = date(2026, 10, 1)
PERFIL = Perfil({"bgp": 5, "python": 3}, ["aws"], {}, "intermediário", 10)


def job(titulo="Analista de Redes BGP", fonte="gupy", empresa="ACME", url="u", posted="2026-10-01", **kw):
    return Job(source=fonte, title=titulo, company=empresa, url=url, posted=posted, **kw)


def test_dedupe_prefere_a_fonte_mais_confiavel():
    a = job("Senior Network Engineer - Remote Work | REF#303277", "linkedin", "BairesDev", "l/1")
    b = job("Senior Network Engineer", "gupy", "BairesDev", "g/1")
    outra = job("Senior Network Engineer", "gupy", "Outra", "g/2")
    assert dedupe([a, b, outra]) == [b, outra]


def test_idade_usa_publicacao_ou_a_data_em_que_foi_vista():
    assert idade_dias(job(posted="2026-09-28"), HOJE) == (3, True)
    vista = job(posted="", first_seen="2026-09-30T12:00:00+00:00")
    assert idade_dias(vista, HOJE) == (1, False)


def test_vaga_nova_pontua_mais_que_a_velha_e_junior_perde():
    nova, velha = job(url="1"), job(url="2", posted="2026-09-01")
    assert pontuar(nova, PERFIL, hoje=HOJE).pontos > pontuar(velha, PERFIL, hoje=HOJE).pontos
    junior = job("Analista de Redes BGP Júnior", url="3")
    p = pontuar(junior, PERFIL, hoje=HOJE)
    assert "nível júnior" in p.motivos and p.pontos < pontuar(nova, PERFIL, hoje=HOJE).pontos


def test_ficha_aplica_penalidades_com_motivo():
    base = pontuar(job(), PERFIL, ficha=Ficha(), hoje=HOJE)  # ficha neutra: já inclui o bônus de vaga em português
    f = Ficha(cloud=["aws"], residencia="Curitiba/PR", plantao=True, ingles="avançado")
    p = pontuar(job(), PERFIL, ficha=f, hoje=HOJE)
    assert base.pontos - p.pontos == 8 + 50 + 6 + 6
    assert {"exige aws", "residir em Curitiba/PR", "plantão", "inglês avançado"} <= set(p.motivos)
    assert pontuar(job(), PERFIL, ficha=Ficha(ingles="avançado"), hoje=HOJE).pontos == base.pontos - 6
    sabe_ingles = Perfil({"bgp": 5}, [], {}, "avançado", 10)
    assert pontuar(job(), sabe_ingles, ficha=Ficha(ingles="avançado"), hoje=HOJE).motivos == []


def test_encaixe_e_cobertura_vem_do_titulo_e_do_texto():
    p = pontuar(job("Analista de Redes"), PERFIL, texto="Experiência com BGP e Python", hoje=HOJE)
    assert p.cobre == ["bgp", "python"] and p.encaixe == 80


def test_limitar_por_empresa():
    itens = [("Canonical", i) for i in range(6)] + [("Outra", 99)]
    top, resto = limitar_por_empresa(itens, chave=lambda x: x[0], n=4, por_empresa=2)
    assert top == [("Canonical", 0), ("Canonical", 1), ("Outra", 99)]
    assert resto == {"Canonical": [("Canonical", 2), ("Canonical", 3), ("Canonical", 4), ("Canonical", 5)]}


def test_empresa_sem_nome_nao_entra_no_mesmo_balde():
    assert empresa_chave(job(empresa="  Ntt Data ")) == "ntt data"
    assert empresa_chave(job(empresa="", url="x")) != empresa_chave(job(empresa="", url="y"))
