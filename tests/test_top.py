import json
from datetime import date

from vagas import top
from vagas.models import Job
from vagas.profile import Perfil
from vagas.top import formatar, main, montar

HOJE = date(2026, 10, 1)
PERFIL = Perfil({"bgp": 5, "zabbix": 4, "python": 3}, ["aws"], {"padrao": "Completo", "redes|bgp": "Redes"}, "intermediário", 10)


class FakeDescricoes:
    def __init__(self, textos):
        self.textos = textos

    def obter(self, job):
        return (self.textos[job.url], "") if job.url in self.textos else None


def j(titulo, empresa, url, fonte="gupy", posted="2026-10-01", **kw):
    return Job(source=fonte, title=titulo, company=empresa, url=url, posted=posted, **kw)


def test_monta_top_com_ficha_e_derruba_quem_exige_residencia():
    jobs = [j("Analista BGP", "A", "1"), j("Analista BGP Zabbix", "B", "2"), j("Analista Python", "C", "3")]
    textos = {"1": "Requisitos: BGP. Residir em Curitiba/PR.", "2": "BGP e Zabbix. Experiência com AWS.", "3": "Python."}
    itens, resto = montar(jobs, PERFIL, FakeDescricoes(textos), n=3, hoje=HOJE)
    assert [i.job.url for i in itens] == ["2", "3", "1"]  # residência derruba a 1; AWS derruba pouco a 2
    assert itens[0].ficha.cloud == ["aws"] and itens[2].ficha.residencia == "Curitiba/PR"
    assert resto == {}


def test_teto_por_empresa_e_vaga_sem_descricao():
    jobs = [j(f"Analista BGP {i}", "Canonical", f"c{i}") for i in range(5)] + [j("Analista BGP", "Outra", "o", fonte="geekhunter")]
    itens, resto = montar(jobs, PERFIL, FakeDescricoes({}), n=10, hoje=HOJE, por_empresa=2)
    assert [i.job.company for i in itens].count("Canonical") == 2 and len(resto["canonical"]) == 3
    assert all(i.ficha.lida is False for i in itens)


def test_formatar_mostra_ficha_cobertura_e_resumo_das_empresas_grandes():
    jobs = [j("Analista BGP", "ACME", "1")] + [j(f"Linux {i}", "Canonical", f"c{i}") for i in range(4)]
    itens, resto = montar(jobs, PERFIL, FakeDescricoes({"1": "BGP e Zabbix. Inglês avançado. Contrato PJ. Prazo."}), n=10, hoje=HOJE, por_empresa=1)
    texto = formatar(itens, resto, PERFIL, hoje=HOJE)
    assert "#1" in texto and "Analista BGP" in texto and "ACME" in texto
    assert "Cobre: bgp, zabbix" in texto and "PJ" in texto and "inglês avançado" in texto
    assert "Currículo sugerido: Redes" in texto
    assert "Canonical: 3 outras" in texto
    assert "descrição não lida" in texto  # as vagas da Canonical não têm texto no teste


def test_main_le_o_historico_e_imprime(tmp_path, monkeypatch, capsys):
    historico = tmp_path / "jobs.json"
    historico.write_text(json.dumps({"jobs": [j("Analista BGP", "ACME", "https://x/1", posted="2026-10-01").to_dict()]}), encoding="utf-8")
    perfil = tmp_path / "perfil.toml"
    perfil.write_text('[perfil]\nreferencia = 10\n[habilidades]\nbgp = 5\n[lacunas]\ntermos = ["aws"]\n', encoding="utf-8")
    monkeypatch.setattr(top, "Descricoes", lambda *a, **k: FakeDescricoes({}))
    code = main(["--jobs", str(historico), "--profile", str(perfil), "--cache", str(tmp_path / "c.json"), "--n", "5"])
    assert code == 0
    assert "Analista BGP" in capsys.readouterr().out


def test_linkedin_nao_garante_remoto_e_resumo_mostra_so_empresas_grandes():
    li = j("Analista BGP", "ACME", "li1", fonte="linkedin")
    gp = j("Analista BGP Zabbix", "Outra", "gp1")
    itens, _ = montar([li, gp], PERFIL, FakeDescricoes({"li1": "Atendimento remoto ou presencial. BGP.", "gp1": "BGP e Zabbix."}), n=5, hoje=HOJE)
    por_url = {i.job.url: i for i in itens}
    assert por_url["li1"].ficha.remoto == "a confirmar" and "regime remoto não confirmado" in por_url["li1"].pont.motivos
    assert por_url["gp1"].ficha.remoto == "confirmado"
    assert [i.job.url for i in itens][0] == "gp1"
    muitas = [j(f"BGP {k}", "Grande", f"g{k}") for k in range(5)] + [j("BGP z", "Pequena", "p1"), j("BGP y", "Pequena", "p2")]
    top_, resto_ = montar(muitas, PERFIL, FakeDescricoes({}), n=1, hoje=HOJE, por_empresa=1)
    texto = formatar(top_, resto_, PERFIL, hoje=HOJE)
    assert "Grande: 4 outras" in texto and "Pequena" not in texto.split("outras")[-1]
    assert "(+2 vagas de empresas menores" in texto


def test_nao_confirmadas_vao_depois_das_confirmadas_com_aviso():
    forte_mas_duvidosa = j("Analista BGP Zabbix Python", "A", "d1", fonte="linkedin")
    fraca_mas_confirmada = j("Analista Python", "B", "c1")
    textos = {"d1": "BGP, Zabbix e Python. Atendimento remoto ou presencial.", "c1": "Python."}
    itens, resto = montar([forte_mas_duvidosa, fraca_mas_confirmada], PERFIL, FakeDescricoes(textos), n=5, hoje=HOJE)
    assert [i.job.url for i in itens] == ["c1", "d1"]
    texto = formatar(itens, resto, PERFIL, hoje=HOJE)
    assert texto.index("#1") < texto.index("NÃO confirmado") < texto.index("#2")


def test_banco_de_talentos_perde_pontos():
    from vagas.rank import pontuar

    normal = j("Analista BGP", "A", "n1")
    talentos = j("Banco de Talentos | Analista BGP", "A", "n2")
    p = pontuar(talentos, PERFIL, hoje=HOJE)
    assert "banco de talentos (não é vaga aberta)" in p.motivos
    assert pontuar(normal, PERFIL, hoje=HOJE).pontos - p.pontos == 30
