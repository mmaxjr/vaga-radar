from vagas.ficha import Ficha, analisar, idioma_do_texto

GAPS = ["aws", "azure", "gcp", "kubernetes", "docker", "terraform"]


def test_cloud_obrigatorio_x_desejavel():
    t = "Requisitos: Linux e redes. Experiência com AWS e Docker. Diferenciais: Kubernetes, Terraform."
    f = analisar(t, GAPS)
    assert f.cloud == ["aws", "docker"]
    assert f.cloud_desejavel == ["kubernetes", "terraform"]


def test_cloud_desejavel_na_mesma_frase_e_mencao_solta_conta_como_obrigatorio():
    assert analisar("Linux. Docker é um diferencial.", GAPS).cloud_desejavel == ["docker"]
    assert analisar("Atuação com Terraform e Azure no dia a dia.", GAPS).cloud == ["azure", "terraform"]
    assert analisar("Conhecimento em GCPX e awsome.", GAPS).cloud == []  # palavra inteira


def test_ingles():
    assert analisar("Inglês avançado obrigatório.", GAPS).ingles == "avançado"
    assert analisar("Requisitos: Linux. Diferenciais: inglês avançado.", GAPS).ingles == "desejável"
    assert analisar("Inglês intermediário para leitura técnica.", GAPS).ingles == "intermediário"
    assert analisar("Experiência com Linux e redes.", GAPS).ingles == "nenhum"
    f = analisar("We are looking for an engineer. You will work with the team and the customers.", GAPS)
    assert f.idioma == "en" and f.ingles == "provável"


def test_idioma_do_texto():
    assert idioma_do_texto("Experiência com Python para atuar em projetos de infraestrutura e DevOps.") == "pt"
    assert idioma_do_texto("You will work with the team and we are hiring for the role.") == "en"
    assert idioma_do_texto("") == "pt"


def test_contrato_residencia_plantao():
    f = analisar("Contrato PJ. Residir em João Pessoa/PB; Graduado em TI. Atuação em plantão e sobreaviso.", GAPS)
    assert (f.contrato, f.residencia, f.plantao) == ("PJ", "João Pessoa/PB", True)
    g = analisar("Residir em qualquer lugar do Brasil (CLT). Escalabilidade e escalar demandas.", GAPS)
    assert (g.contrato, g.residencia, g.plantao) == ("CLT", "", False)
    assert analisar("Contrato CLT ou PJ", GAPS).contrato == "CLT/PJ"
    assert analisar("Sem informação.", GAPS).contrato == "n/d"
    assert analisar("Must reside in Brazil.", GAPS).residencia == ""  # o país não é restrição


def test_remoto_prazo_e_presencial():
    assert analisar("Vaga 100% remota.", GAPS).remoto == "confirmado"
    f = analisar("Atendimento telefônico, remoto ou presencial.", GAPS)
    assert f.remoto == "a confirmar" and f.cita_presencial is True
    assert analisar("Atendimento telefônico, remoto ou presencial.", GAPS, remote_proof=True).remoto == "confirmado"
    assert analisar("x", GAPS, prazo="2026-10-23").prazo == "2026-10-23"


def test_descricao_nao_lida():
    f = analisar("", GAPS, lida=False)
    assert f.lida is False and f.cloud == [] and f.ingles == "n/d"
    assert isinstance(f, Ficha)
