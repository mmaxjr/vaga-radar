from vagas.profile import Perfil

TOML = '''
[perfil]
ingles = "intermediário"
referencia = 20

[habilidades]
bgp = 5
zabbix = 4
"github actions" = 2
python = 3

[lacunas]
termos = ["aws", "docker"]

[curriculos]
padrao = "Curriculo-Completo"
"red team|pentest|seguran" = "Cybersecurity"
"redes|network|bgp" = "Analista-de-Redes"
'''


def _perfil(tmp_path):
    p = tmp_path / "perfil.toml"
    p.write_text(TOML, encoding="utf-8")
    return Perfil.carregar(p)


def test_carrega_e_calcula_encaixe(tmp_path):
    perfil = _perfil(tmp_path)
    pct, cobre = perfil.encaixe("Analista de redes com BGP e Zabbix, automação em Python e GitHub Actions")
    assert cobre == ["bgp", "zabbix", "python", "github actions"]
    assert pct == 70  # (5+4+3+2) / 20
    assert perfil.lacunas == ["aws", "docker"] and perfil.ingles == "intermediário"
    assert perfil.encaixe("bgpx e pythonic")[0] == 0  # só palavra inteira


def test_encaixe_tem_teto_de_100(tmp_path):
    assert _perfil(tmp_path).encaixe("bgp zabbix python github actions bgp")[0] == 70  # (5+4+3+2)/20; a repetição não soma
    assert Perfil({"a": 50}, [], {}, "?", 20).encaixe("a")[0] == 100


def test_sugere_curriculo_pelo_primeiro_padrao_que_casar(tmp_path):
    perfil = _perfil(tmp_path)
    assert perfil.curriculo("Analista de Segurança Purple Team") == "Cybersecurity"
    assert perfil.curriculo("Analista de Redes BGP") == "Analista-de-Redes"
    assert perfil.curriculo("Designer de produto") == "Curriculo-Completo"


def test_evitar_e_carregado_do_toml(tmp_path):
    p = tmp_path / "p.toml"
    p.write_text('[habilidades]\nlinux = 5\n[evitar]\ntermos = ["kernel"]\n', encoding="utf-8")
    perfil = Perfil.carregar(p)
    assert perfil.fora_do_perfil("Ubuntu Kernel Engineer") == ["kernel"]
    assert perfil.fora_do_perfil("Analista Linux") == []


def test_interesses_somam_os_pesos_das_palavras_do_titulo(tmp_path):
    p = tmp_path / "p.toml"
    p.write_text('[habilidades]\nlinux = 5\n[interesses]\nredes = 5\nsuporte = 3\n"segurança" = 4\n', encoding="utf-8")
    perfil = Perfil.carregar(p)
    assert perfil.interesse("Analista de Suporte de Redes") == 8
    assert perfil.interesse("Analista de Segurança") == 4
    assert perfil.interesse("Designer") == 0


def test_curriculo_em_ingles_para_vaga_em_ingles(tmp_path):
    p = tmp_path / "p.toml"
    p.write_text('[habilidades]\nlinux = 5\n[curriculos]\npadrao = "PT"\npadrao_en = "EN"\n"redes" = "Redes"\n', encoding="utf-8")
    perfil = Perfil.carregar(p)
    assert perfil.curriculo("Analista de Redes", "pt") == "Redes"
    assert perfil.curriculo("Network Engineer", "en") == "EN"
    assert perfil.curriculo("Designer", "pt") == "PT"
    sem_en = tmp_path / "q.toml"
    sem_en.write_text('[habilidades]\nlinux = 5\n[curriculos]\npadrao = "PT"\n', encoding="utf-8")
    assert Perfil.carregar(sem_en).curriculo("Engineer", "en") == "PT"  # sem padrao_en, cai no padrão


def test_certificacoes_que_voce_tem(tmp_path):
    p = tmp_path / "p.toml"
    p.write_text('[habilidades]\nlinux = 5\n[certificacoes]\npossui = ["CCNA", "MTCNA"]\n', encoding="utf-8")
    assert Perfil.carregar(p).certificacoes == ["ccna", "mtcna"]
