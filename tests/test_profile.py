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
