from datetime import date

from vagas.ficha import Ficha
from vagas.models import Job
from vagas.profile import Perfil
from vagas.rank import dedupe, empresa_chave, idade_dias, limitar_por_empresa, pontuar

HOJE = date(2026, 10, 1)
PERFIL = Perfil({"bgp": 5, "python": 3}, ["aws"], {}, "intermediário", 10)
NEUTRA = Ficha(remoto="confirmado")  # regime provado e nada mais: serve de linha de base


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
    base = pontuar(job(), PERFIL, ficha=NEUTRA, hoje=HOJE)  # ficha neutra: já inclui o bônus de vaga em português
    f = Ficha(remoto="confirmado", cloud=["aws"], residencia="Curitiba/PR", plantao=True, ingles="avançado")
    p = pontuar(job(), PERFIL, ficha=f, hoje=HOJE)
    assert base.pontos - p.pontos == 12 + 50 + 6 + 6
    assert {"exige aws", "residir em Curitiba/PR", "plantão", "inglês avançado"} <= set(p.motivos)
    assert pontuar(job(), PERFIL, ficha=Ficha(remoto="confirmado", ingles="avançado"), hoje=HOJE).pontos == base.pontos - 6
    sabe_ingles = Perfil({"bgp": 5}, [], {}, "avançado", 10)
    assert pontuar(job(), sabe_ingles, ficha=Ficha(remoto="confirmado", ingles="avançado"), hoje=HOJE).motivos == []


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


def test_titulo_presencial_regime_nao_confirmado_lead_e_fora_do_perfil():
    base = pontuar(job(), PERFIL, ficha=NEUTRA, hoje=HOJE)
    assert pontuar(job("Analista de Redes BGP - Presencial SP"), PERFIL, hoje=HOJE).pontos <= pontuar(job(), PERFIL, hoje=HOJE).pontos - 40
    nao_confirmada = pontuar(job(), PERFIL, ficha=Ficha(remoto="a confirmar", cita_presencial=True), hoje=HOJE)
    assert base.pontos - nao_confirmada.pontos == 45 + 10
    assert {"regime remoto não confirmado", "o texto cita presencial/híbrido"} <= set(nao_confirmada.motivos)
    local = job(scope="local")  # vaga da sua cidade: regime não é cobrado
    assert pontuar(local, PERFIL, ficha=Ficha(remoto="a confirmar", cita_presencial=True), hoje=HOJE).motivos == []
    assert "nível muito sênior" in pontuar(job("Lead Linux Engineer"), PERFIL, hoje=HOJE).motivos
    evita = Perfil({"linux": 5}, [], {}, "?", 10, evitar=["kernel"])
    p = pontuar(job("Linux Kernel Engineer"), evita, hoje=HOJE)
    assert "fora do seu perfil (kernel)" in p.motivos


def test_area_de_interesse_no_titulo_pesa_mesmo_sem_habilidade_no_titulo():
    com = Perfil({"bgp": 5}, [], {}, "?", 10, interesses={"suporte": 3, "seguranca": 4})
    sem = Perfil({"bgp": 5}, [], {}, "?", 10)
    vaga = job("Analista de Suporte Técnico Sênior", url="s1")
    assert pontuar(vaga, com, hoje=HOJE).pontos - pontuar(vaga, sem, hoje=HOJE).pontos == 6  # 2 x peso 3
    muito = Perfil({}, [], {}, "?", 10, interesses={"redes": 5, "noc": 5, "monitoramento": 5})
    assert pontuar(job("Redes NOC Monitoramento"), muito, hoje=HOJE).pontos - pontuar(job("Redes NOC Monitoramento"), sem, hoje=HOJE).pontos == 20  # teto


def test_nivel_pleno_ou_senior_ganha_pequeno_bonus():
    sem, com = job("Analista de Redes BGP", url="n1"), job("Analista de Redes BGP Sênior", url="n2")
    assert pontuar(com, PERFIL, hoje=HOJE).pontos - pontuar(sem, PERFIL, hoje=HOJE).pontos == 4


def test_certificacao_exigida_que_falta_perde_pontos_e_a_que_tem_nao():
    tem = Perfil({"bgp": 5}, [], {}, "?", 10, certificacoes=["itil"])
    f = Ficha(remoto="confirmado", certificacoes=["itil", "cysa+", "ecsa", "cissp"])
    p = pontuar(job(), tem, ficha=f, hoje=HOJE)
    assert p.motivos == ["exige certificação cysa+", "exige certificação ecsa"]  # a que tem não conta; teto de 2
    assert pontuar(job(), tem, ficha=NEUTRA, hoje=HOJE).pontos - p.pontos == 16
