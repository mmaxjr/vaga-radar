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
| InfoJobs | Brasil | HTML da busca "home office"; o cartão informa o regime, então só entra o que diz "Home Office" |
| Quadros de vagas de empresas (Canonical, Datadog, Elastic, GitLab e outras) | Global | APIs públicas Greenhouse/Lever/Ashby, lista de empresas em `[companies]`; só vagas que se declaram remotas |
| [Jobicy](https://jobicy.com) e [Himalayas](https://himalayas.app) | Internacional | API pública; só vagas abertas ao Brasil, LATAM ou "anywhere" |
| Empregare | Brasil | HTML das listagens (remoto, por termo e por cidade); o cartão informa o regime, então só entra o que diz "Totalmente Remoto" |
| Páginas de carreira do Zoho Recruit (ex.: Spassu) | Brasil | a listagem pública já traz todas as vagas com o campo "Trabalho remoto"; lista de empresas em `[zohorecruit]` |
| [Nerdin](https://www.nerdin.com.br) | Brasil | HTML da listagem (mais novas primeiro, `[nerdin] pages`); o cartão informa o regime, então só entra o que diz "Home Office"; a descrição vem do `JobPosting` da página |
| [Trampos.co](https://trampos.co) | Brasil | API JSON do próprio site (mais comunicação que TI); só categorias TI/dados com home office |
| [Coodesh](https://coodesh.com) | Brasil | sitemap oficial de vagas, uma página por vaga; só localidade "Remota" (as vagas costumam ser antigas e caem no filtro de idade) |
| [Torre](https://torre.ai) | América Latina | página pública da comunidade de vagas remotas de TI (`/sub/<nome>/jobs`, ~20 mais ativas); a API e a busca por parâmetros o robots.txt proíbe, então ficam de fora |
| [Hacker News "Who is hiring?"](https://news.ycombinator.com/submitted?id=whoishiring) | Global | API pública do Algolia, tópico mensal; só anúncios remotos abertos a Brasil/LATAM/mundo (pelo cabeçalho) |
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
python -m vagas --min-hours 6          # pula a coleta se a última foi há menos de 6 h
python -m vagas --min-hours 6 --force  # coleta mesmo assim
```

**Evite coletar toda hora.** Uma coleta completa faz centenas de requisições (só o LinkedIn passa de 100 por rodada) e as
fontes respondem HTTP 429 (limite de acessos) quando há excesso, às vezes por horas. Vagas novas surgem em poucos lotes por
dia, então 1 a 2 coletas já bastam. Para travar isso de vez, ponha `min_hours = 6` em `[storage]` no `config.toml`.

O que o projeto já faz para não ser bloqueado:
- **Intervalo por fonte:** `min_hours` na seção de cada fonte (o `config.toml` já traz `[linkedin] min_hours = 6`). As fontes
  de API seguem livres. Cada tentativa fica registrada no `jobs.json` (`source_runs`).
- **Disjuntor:** depois de um HTTP 429, o site não recebe mais pedidos até o fim da execução.
- **Resumo no fim:** quais fontes vieram vazias, quais foram puladas pelo intervalo e quais deram 429.
- **Dados estruturados:** Jobicy e Vagas.com.br têm a descrição lida pelo `JobPosting` (schema.org) da página, que muda menos que o HTML.

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

## Como o filtro decide

1. **Área** (`include`/`exclude`): o título precisa casar com um padrão de interesse. Por padrão inclui funções próximas de TI
   (suporte técnico, help desk, administração de sistemas, QA, dados, telecom), não só a área principal.
2. **Regime remoto**: fontes que já filtram por remoto (Gupy, InfoJobs, GeekHunter...) são confiáveis. O **LinkedIn** não é:
   o filtro "remoto" dele devolve muita vaga presencial. Por isso, a vaga do LinkedIn que passou nos outros filtros mas não diz
   "remoto" no título tem a **descrição lida** (`[verify]`): entra só se afirma trabalho remoto ("100% remoto", "fully remote"...) e
   não cita presencial, híbrido ou escritório. Na dúvida, descarta. O resultado fica no histórico para não reler a mesma vaga.
3. **Região** (vagas internacionais): só abertas ao Brasil, LATAM ou "anywhere".
4. **Idade** (`max_age_days`).

## Top do dia

`python -m vagas.top --jobs docs/jobs.json --profile perfil.toml --cache descricoes.json` (com `--grupos`: uma lista por grupo, Maringá, Python, redes/infra/segurança e outras) pega o histórico, tira as duplicadas entre
fontes, pontua cada vaga pelo seu perfil e pelo frescor, lê a descrição das melhores e imprime uma ficha por vaga: encaixe %,
o que você cobre, o que falta (ex.: cloud exigido x só diferencial), regime, contrato (CLT/PJ), inglês, residência, plantão e prazo.
No máximo 2 vagas por empresa; o resto vira uma linha ("Canonical: 84 outras..."). Por padrão mostra uma lista em português e
outra em inglês (`--idioma pt|en|todos`); `--desde <instante ISO>` limita às vagas vistas pela primeira vez depois dele e `--hoje`
só às de hoje. Veja o formato do `perfil.toml` no topo de
[vagas/profile.py](vagas/profile.py). O perfil é um arquivo local: não o publique.

## Vagas na sua cidade

Além das remotas, dá para incluir vagas da **sua cidade em qualquer regime** (presencial, híbrido ou remoto).
Ligue a seção `[local]` do [config.toml](config.toml):

```toml
[local]
enabled = true
city = "Maringá"
state = "Paraná"
cities = ["Maringá", "Sarandi", "Paiçandu", "Marialva"]   # cidades aceitas no resultado
terms = ["ti", "infraestrutura", "redes", "segurança da informação"]
```

As fontes usadas são Gupy (filtro de cidade), Vagas.com.br, InfoJobs, Empregare e LinkedIn. Essas vagas saem marcadas como
"na sua cidade", em um grupo separado no resumo e com filtro próprio na página, sem misturar com as remotas.
O Gupy informa o regime (presencial/híbrido/remoto); o LinkedIn e o Vagas.com.br nem sempre, então confira no anúncio.

Sites atrás de verificação anti-robô (ex.: Cloudflare "Just a moment...") não são coletados de propósito.

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
- **Remote OK, Remotive, Jobicy e Himalayas** pedem crédito à fonte e limitam consultas; a página já linka para elas.
- **Quadros de empresas**: as APIs não informam a data de publicação de forma confiável, então essas vagas entram sem data; "nova" significa que apareceu pela primeira vez no quadro.
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
