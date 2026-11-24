# Resumo executivo: AgroSmart Fase 7

**Entregue.** O AgroSmart roda ponta a ponta por um único orquestrador, local ou via Docker. A execução é contínua e monitorada, com logs JSON, indicadores, painel de operação e healthcheck.
- O event log alimenta a análise de processo.
- O pipeline DevSecOps no GitHub Actions faz qualidade, segurança e smoke test em container.
- A base do Ryan (Fases 4 a 6) foi preservada, sem mudar regras, colunas nem caminhos. Os números de referência (144 raw, 3 em quarentena, 1 duplicada, 140 válidas, 8 alertas e 2 comandos) são reproduzidos e travados por teste.

## Rastreabilidade dos 6 requisitos

| # | Requisito | Evidência principal | Verificação |
|---|---|---|---|
| 1 | Arquitetura final | `descricao_arquitetura_final.md` + `arquitetura_final.mmd` | Revisão |
| 2 | Execução ponta a ponta | `caso_de_teste_e2e.md` (entrada → saída de uma leitura real), `evidencias/` | `test_pipeline_completo_reproduz_numeros_da_base` |
| 3 | DevSecOps | `.github/workflows/devsecops.yml`, `Dockerfile`, `.env.example`, `devsecops.md` | ruff ✅, pytest 21/21 ✅, pip-audit runtime ✅; job de container ⏳ (ver abaixo) |
| 4 | Monitoramento | `8_Execucao_Monitorada/`, `monitoramento.md` | `test_logs_estruturados…`, `test_falha_de_etapa_nao_derruba_o_loop` |
| 5 | Process mining | `event_log.csv`, `9_Process_Mining/saida/analise_processo.md`, `process_mining.md` | `test_event_log_consistente` |
| 6 | Pitch | `pitch_e_demo.md` (pitch ≤ 5 min + demo 5 a 8 min) | Revisão |

## Arquivos criados (NOVO na Fase 7)

| Arquivo | Para quê |
|---|---|
| `8_Execucao_Monitorada/orquestrador.py` | Ciclos agendados ou contínuos, timeout, retentativa, falha isolada, SIGTERM, indicadores, histórico e painel |
| `8_Execucao_Monitorada/logger_json.py` | Logs estruturados em JSON Lines, com rotação |
| `8_Execucao_Monitorada/event_log.py` | Event log por leitura, reconstruído das saídas, com modelo de agendamento declarado |
| `8_Execucao_Monitorada/healthcheck.py` | HEALTHCHECK do container |
| `9_Process_Mining/analisar_processo.py` (+ `saida/`) | DFG, variantes, gargalos, desvios e tempo até o alerta |
| `tests/` (4 arquivos, 21 testes) | Unitários (validação, Magnus-Tetens, VPD e regras) e ponta a ponta |
| `Dockerfile`, `docker-compose.yml`, `.dockerignore` (raiz) | Imagem da plataforma integrada: não-root, código só leitura, HEALTHCHECK, `cap_drop` |
| `.env.example`, `.gitignore` | Configuração por ambiente; `.env` e `integrantes.txt` fora do Git |
| `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` | Runtime só com stdlib; ferramentas fixadas; regras do ruff (incluindo segurança) |
| `.github/workflows/devsecops.yml` | CI: qualidade, segurança e container |
| `README.md` | Porta de entrada do repositório |
| `fase7_entrega/*` | Arquitetura, caso ponta a ponta, DevSecOps, monitoramento, process mining, pitch/demo, este resumo e `evidencias/` |

## Arquivos do Ryan alterados (mudanças pontuais, sem mudar comportamento)

| Arquivo | Mudança | Motivo |
|---|---|---|
| `4_Arquitetura_Solucao/gerar_diagrama.py` | Fallback de fonte quando `C:/Windows/Fonts` não existe | Quebrava em Linux/CI com Pillow instalado |
| `3_IA_Generativa_Apoio_Decisao/gerar_relatorio_ia.py` | ID do modelo `claude-sonnet-5` → `claude-sonnet-5-5` | O ID antigo não é válido e caía sempre no modo simulado |
| `FIAP - Agrosmart Docker/Dockerfile`, `docker-compose.yml` | Usuário não-root, `no-new-privileges`, `cap_drop` | Hardening do container legado |
| `README.txt` | Título "Fase 6" e lista de integrantes trocada por uma referência a `integrantes.txt` | RMs fora do repositório público |
| Removidos do pacote | `Video Streaming.mp4` (77 MB) e `.vscode/extensions.json` | Peso no Git; recomendação de extensão de terceiro |

As saídas em `6_Processamento_Dados/saida/` e `7_Automacao_Inteligente/saida/` foram regeneradas pelo pipeline. O conteúdo é idêntico ao do zip, exceto a data de geração (`gerado_em`).

## Como executar

```powershell
# Local (Python 3.10+, sem instalar nada)
python 8_Execucao_Monitorada/orquestrador.py --ciclos 1 --gerar-dados
python 8_Execucao_Monitorada/orquestrador.py --ciclos 3 --intervalo 10     # loop controlado

# Docker (continuo; Ctrl+C ou "docker compose down" para parar)
docker compose up --build
docker compose ps                                   # estado healthy

# Qualidade e seguranca
python -m pip install -r requirements-dev.txt
ruff check .
python -m pytest -v
pip-audit -r requirements.txt
```

Saídas para mostrar:
- `7_Automacao_Inteligente/saida/dashboard.html`
- `8_Execucao_Monitorada/saida/painel_operacao.html`
- `9_Process_Mining/saida/analise_processo.md`

## Principais achados da análise de processo
- **Gargalo:** 100% do tempo de espera está entre a recepção e a validação, 30 min. As leituras chegam de 1 a 5 s depois do horário do ciclo e perdem o ciclo. Defasar o ciclo em 60 s reduz o lead time para cerca de 57 s (`evidencias/whatif_defasagem_60s.md`).
- **Variações:** há 5 variantes. 91,7% das leituras seguem o caminho feliz, 2,1% vão para a quarentena, 0,7% são duplicadas, 4,2% geram alerta e 1,4% geram alerta com comando.
- **Alertas:** 4 dos 8 são de infraestrutura (falha de leitura) e só aparecem cerca de 60 min depois da falha. Recomendações: alerta no próprio evento de quarentena e fila separada para manutenção.

## O que exige ação humana

| # | Ação | Quem |
|---|---|---|
| 1 | **Criar o repositório no GitHub e dar push** (sugestão: público, `israelanacleto/agrosmart`). Não fiz commit nem push. Antes do push, conferir que o upstream não aponta para uma branch protegida | Israel |
| 2 | **Conferir a primeira execução do Actions.** Os jobs `qualidade` e `seguranca` foram reproduzidos localmente. O job `container` (build, smoke e Trivy) **não pôde ser verificado localmente** porque o Docker Desktop não subiu nesta sessão. Se o Trivy apontar CVE HIGH/CRITICAL corrigível na base `python:3.12-slim`, basta rebuildar com a base atualizada | Israel |
| 3 | **Prints para o PDF:** Actions verde, `docker compose ps` healthy, `painel_operacao.html`, `dashboard.html` e o trecho do `analise_processo.md` | Israel |
| 4 | **Vídeo:** o grupo decidiu não gravar. Se o enunciado da FIAP exigir link de vídeo para o pitch ou a demo, os roteiros prontos estão em `pitch_e_demo.md` | Grupo |
| 5 | **`[A PREENCHER]` no pitch:** mercado endereçável e preço, só se houver fonte. Caso contrário, remover | Grupo |
| 6 | **Secrets:** nenhum é necessário para o CI. `ANTHROPIC_API_KEY` só é usada se quiserem a IA real fora do pipeline; nesse caso, ela vai no `.env` local ou em GitHub Secrets, nunca no código | Opcional |
| 7 | **Integrantes e RMs:** ficam em `integrantes.txt` local (gitignored). Colocá-los no PDF ou no formulário de entrega, não no repositório | Israel |
