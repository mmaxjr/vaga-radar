# 📡 Vaga Radar

[![Testes](https://github.com/mmaxjr/vaga-radar/actions/workflows/tests.yml/badge.svg)](https://github.com/mmaxjr/vaga-radar/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

Agregador de vagas **remotas** de TI. Coleta de vários sites brasileiros e internacionais, filtra por área,
remove duplicadas, guarda em JSON, gera uma página com busca e manda um resumo das vagas novas no Telegram.

> *English:* a small, dependency-light Python tool that pulls remote tech jobs from Brazilian and international
> sources (LinkedIn, Gupy, GitHub job repos, Remote OK...), filters them with regexes you control, de-duplicates,
> and delivers a daily digest via Telegram plus a searchable static page. Sources are ~40-line plugins: easy to fork.

Por padrão busca **programação, infra, redes, DevOps e segurança**, mas a área é só configuração (veja abaixo).

## Fontes

| Fonte | Tipo | Como coleta |
|---|---|---|
| LinkedIn | Brasil | busca pública de visitante, filtro "remoto" |
| Gupy | Brasil | API pública do portal de vagas |
| GeekHunter | Brasil | listagem pública `/pt/vagas` pela busca oficial do site, só `workModality=remote` (fora "remoto em cidade"); nunca abre `/jobs/...`, que o robots.txt proíbe |
| Programathor | Brasil | HTML da listagem (ignora vagas "Vencida") |
| Vagas.com.br | Brasil | HTML da busca |
| GitHub: frontendbr, backend-br, androiddevbr, react-brasil, datascience-br, qa-brasil | Brasil | cada issue aberta é uma vaga |
| [Remote OK](https://remoteok.com), [We Work Remotely](https://weworkremotely.com), [Remotive](https://remotive.com) | Internacional | API/RSS pública; só entram vagas abertas ao Brasil ou "worldwide" |

## Começando

Precisa de Python 3.11+.

```bash
git clone https://github.com/mmaxjr/vaga-radar.git
cd vaga-radar
pip install -r requirements.txt

python -m vagas --dry-run              # mostra o que há de novo, sem salvar nem enviar
python -m vagas                        # coleta, salva em docs/jobs.json e gera docs/index.html
python -m vagas --sources gupy,github  # só algumas fontes
```

Abra `docs/index.html` no navegador para ver e filtrar as vagas. Os dados coletados ficam só na sua máquina
(`docs/jobs.json` e `docs/index.html` estão no `.gitignore`).

## Escolher a área

Tudo fica em [config.toml](config.toml):

| Campo | Para que serve |
|---|---|
| `terms` | o que é buscado nos sites que têm busca (Gupy, LinkedIn, Vagas.com.br) |
| `include` | o título precisa casar com ao menos um destes padrões (regex) |
| `exclude` | descarta se o título casar com algum destes |
| `max_age_days` | ignora vagas mais antigas que isso |
| `international_ok_regions` | regiões aceitas nas vagas internacionais |

Exemplo, só dados e IA: troque `terms` por `["engenheiro de dados", "machine learning", "analytics"]` e
`include` por `['dados', 'data', 'machine learning', '(?<![a-z])ia(?![a-z])']`.

Só entram vagas **remotas**: cada fonte já é consultada com o filtro de remoto.

Dica de regex: para casar só a palavra inteira use `(?<![a-z])go(?![a-z])` (evita casar "Goiás"). Se preferir
`\b`, use aspas simples no TOML (`'\bgo\b'`), que não interpretam a barra invertida.

## Resumo no Telegram

1. Crie um bot com o [@BotFather](https://t.me/BotFather) e copie o token.
2. Mande uma mensagem qualquer ao bot e abra `https://api.telegram.org/bot<TOKEN>/getUpdates` para achar o `chat.id`.
3. Defina as variáveis e rode:

```bash
export TELEGRAM_BOT_TOKEN=...   # PowerShell: $env:TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID=...
python -m vagas
```

Só vagas **novas** desde a última execução são enviadas (no máximo `notify.max_items` por resumo).

## Rodar sozinho todo dia (GitHub Actions)

Faça um fork e cadastre em *Settings → Secrets and variables → Actions* os secrets `TELEGRAM_BOT_TOKEN` e
`TELEGRAM_CHAT_ID`. O workflow [daily.yml](.github/workflows/daily.yml) roda às 08h (Brasília), guarda o histórico
em cache do Actions e manda o resumo. Ele **não** faz commit de dados coletados.

### Site público (opcional)

Em *Settings → Pages* escolha **Source: GitHub Actions** e crie a variável `ENABLE_PAGES` = `true`
(*Settings → Secrets and variables → Actions → Variables*). O workflow passa a publicar a página com busca.
A versão pública deixa o LinkedIn de fora (`--hide-sources linkedin`), porque os termos deles limitam a republicação.

## Adicionar uma fonte nova

Cada fonte é um módulo em [vagas/sources/](vagas/sources/) com uma função `fetch(cfg) -> list[Job]`:

```python
# vagas/sources/minhafonte.py
from .. import http
from ..models import Job

def fetch(cfg: dict) -> list[Job]:
    r = http.get("https://exemplo.com/api/vagas")
    if r is None:                  # http.get já trata erro/retry e devolve None se falhar
        return []
    return [Job(source="minhafonte", title=v["titulo"], url=v["link"],
                company=v["empresa"], location="Remoto", posted=v["data"])
            for v in r.json()]
```

Depois registre em [vagas/sources/\_\_init\_\_.py](vagas/sources/__init__.py) (`SOURCES["minhafonte"] = minhafonte.fetch`).
O filtro por área, a deduplicação, o Telegram e a página funcionam sem mais nada. Para fontes internacionais,
use `international=True` no `Job`. Para HTML, siga o padrão de `programathor.py` e teste o `parse()` com um trecho
de HTML em `tests/`.

## Estrutura

```
vagas/
  sources/     um módulo por site
  filters.py   filtro por área, região e idade
  store.py     histórico em JSON + deduplicação
  notify.py    resumo do Telegram
  site.py      gera a página HTML
  __main__.py  CLI
docs/template.html   modelo da página
config.toml          o que buscar
tests/
```

## Observações

- **LinkedIn**: usa o endpoint público de busca, sem login. Ele limita acessos: a coleta tem pausas e desiste sozinha
  se for bloqueada. Use com moderação (1 a 2 vezes por dia). O local exibido é o da empresa e o filtro de remoto
  às vezes falha, então confira a vaga.
- **Remote OK e Remotive** pedem link de volta à fonte e limitam consultas; a página já linka para elas.
- **GitHub**: sem token são 60 requisições/h. Defina `GITHUB_TOKEN` para mais.
- Sites mudam o HTML sem avisar. Se uma fonte parar de funcionar, o `parse()` dela é o primeiro lugar a olhar,
  e uma fonte que falha não derruba as outras.
- Confira sempre a vaga no site de origem antes de se candidatar.

## Testes

```bash
python -m pytest
```

## Licença

[MIT](LICENSE)
