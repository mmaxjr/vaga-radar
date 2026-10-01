# Top do dia: ranking por encaixe + ficha automática da vaga

Data: 2026-10-01 · Status: aprovado pelo usuário ("pode fazer") · Escopo: Pacote 1 da lista de melhorias

## Problema
O sistema já acha vaga demais (665 remotas úteis no histórico, só 45 publicadas há até 1 dia, 75 duplicadas entre fontes,
uma empresa responde por 13%). O que falta é escolher as melhores do dia e ler os detalhes que hoje são lidos à mão:
exige cloud? inglês? PJ? residência? plantão? prazo?

## Objetivo
`python -m vagas.top --profile <perfil.toml>` imprime o **Top N do dia**, cada vaga com uma **ficha** (encaixe %, o que cobre,
o que falta, regime, contrato, idioma, prazo, alertas). Roda offline sobre o histórico + leitura de descrições das melhores.

## Fora de escopo (decidido com o usuário)
- Escolha automática do currículo: continua na conversa (a ficha só leva uma sugestão genérica "usar o currículo X" se o
  perfil mapear áreas para currículos).
- Aviso no celular e painel de candidaturas (Pacotes 2 e 3).
- Candidatura automática: nunca.

## Unidades (cada uma com uma responsabilidade e testável sozinha)
| Módulo | Faz | Depende de |
|---|---|---|
| `vagas/ficha.py` | Função pura: texto da vaga -> `Ficha` (cloud exigido, inglês, contrato, residência, plantão, prazo, senioridade, regime) | `verify` (prova de remoto) |
| `vagas/describe.py` | Busca a descrição por fonte (Gupy, Himalayas, Jobicy, LinkedIn, GitHub, InfoJobs, Empregare, Zoho, Greenhouse/Lever) com cache em disco; GeekHunter fica de fora (robots.txt) | `http`, fontes |
| `vagas/profile.py` | Lê o perfil local (TOML): habilidades com peso, lacunas, preferências; calcula encaixe de um texto | nada |
| `vagas/rank.py` | Pontua (encaixe + frescor + idioma + senioridade), remove duplicadas entre fontes, limita por empresa, agrupa empresas "inundadoras" | `profile`, `ficha` |
| `vagas/top.py` | CLI: junta tudo, respeita um orçamento de requisições, imprime texto ou Markdown | todos |

O perfil (habilidades, lacunas, currículos) vive em arquivo **local fora do Git**; o código público é genérico.

## Ficha: o que detecta e como
- **Cloud exigido**: tecnologias da lista de lacunas do perfil (ex.: aws, azure, gcp, kubernetes, terraform, docker) citadas na
  descrição; conta mais quando aparece em "requisitos/obrigatório/imprescindível" do que em "diferencial/desejável".
- **Inglês**: nenhum / básico-intermediário / avançado-fluente / obrigatório (por frases em PT e EN); idioma da vaga (PT ou EN).
- **Contrato**: CLT, PJ ou não informado. **Residência**: "residir em X". **Plantão**: plantão, sobreaviso, on-call, 12x36, turnos.
- **Prazo**: da fonte, quando existe. **Remoto**: "confirmado" (fonte filtra + descrição não contradiz) ou "a confirmar".
- Tudo por regras e regex, determinístico, sem IA e sem custo. Texto ambíguo vira "n/d", nunca um chute.

## Pontuação (0-100%)
`encaixe = habilidades do perfil presentes (pesos, com teto) - lacunas exigidas - penalidade de senioridade`
`ordem = encaixe + frescor (hoje > 2 dias > 7 dias; sem data usa a data em que foi vista) + idioma preferido + confiança no regime`.
Vaga que exige residência em cidade, ou lacuna "obrigatória" de tecnologia, cai para o fim com o motivo explícito.

## Duplicadas e empresas que inundam
- Chave = empresa normalizada + título normalizado (sem "Remote Work", "REF#123", pontuação). Fica a versão de fonte mais confiável.
- No máximo 2 vagas por empresa no Top; as demais viram uma linha: "Empresa: N vagas (as 3 melhores: ...)".

## Erros e limites
- Descrição indisponível (bloqueio, 404): a ficha sai só com o que o título permite e a marca "descrição não lida".
- Orçamento: lê no máximo K descrições por execução (padrão 40), com pausa; cache evita reler.
- Fonte sem descrição acessível (GeekHunter): entra no ranking pelo título, com aviso "abrir a vaga para ver requisitos".

## Testes
Textos reais anonimizados de descrições servem de fixture: ficha (cada detector, com acerto e com falso positivo conhecido, ex.:
"nuvem híbrida", "auxílio home office"), dedupe, teto por empresa, ordem do ranking, carga do perfil, orçamento de requisições
(com `http` simulado). Nada de rede nos testes.
