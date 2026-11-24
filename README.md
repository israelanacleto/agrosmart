# AgroSmart: monitoramento agrícola inteligente (FIAP, Fase 7)

![DevSecOps](../../actions/workflows/devsecops.yml/badge.svg)

Plataforma ponta a ponta. Sensores de campo, simulados, alimentam um data lake em camadas (raw → trusted → refined, com quarentena). Um motor de regras explicável gera alertas, recomendações e comandos de irrigação.

A Fase 7 acrescentou:
- execução contínua e monitorada;
- logs estruturados;
- process mining;
- pipeline DevSecOps no GitHub Actions.

Turma 4ESOA, Grupo 102. A base das Fases 4 a 6 foi consolidada a partir da entrega do integrante Ryan Aquino. A lista de integrantes fica fora do repositório público.

## Início rápido

```powershell
# local: Python 3.10+, sem dependencias de runtime
python 8_Execucao_Monitorada/orquestrador.py --ciclos 1 --gerar-dados

# via Docker: execucao continua (Ctrl+C para parar); evidencias em ./evidencias_docker/
docker compose up --build

# testes e qualidade
python -m pip install -r requirements-dev.txt
ruff check .
python -m pytest -v
```

Para ver os resultados no navegador, abra:
- `7_Automacao_Inteligente/saida/dashboard.html` (painel agronômico);
- `8_Execucao_Monitorada/saida/painel_operacao.html` (operação).

## Entrega da Fase 7

| Requisito | Artefatos |
|---|---|
| 1. Arquitetura final | [`fase7_entrega/descricao_arquitetura_final.md`](fase7_entrega/descricao_arquitetura_final.md), [`arquitetura_final.mmd`](fase7_entrega/arquitetura_final.mmd) |
| 2. Execução da plataforma | [`fase7_entrega/caso_de_teste_e2e.md`](fase7_entrega/caso_de_teste_e2e.md), `8_Execucao_Monitorada/orquestrador.py`, [`fase7_entrega/evidencias/`](fase7_entrega/evidencias/) |
| 3. Pipeline DevSecOps | [`.github/workflows/devsecops.yml`](.github/workflows/devsecops.yml), `Dockerfile`, `docker-compose.yml`, `.env.example`, [`fase7_entrega/devsecops.md`](fase7_entrega/devsecops.md) |
| 4. Monitoramento | `8_Execucao_Monitorada/`, [`fase7_entrega/monitoramento.md`](fase7_entrega/monitoramento.md) |
| 5. Process mining | `8_Execucao_Monitorada/event_log.py`, `9_Process_Mining/`, [`fase7_entrega/process_mining.md`](fase7_entrega/process_mining.md) |
| 6. Pitch | [`fase7_entrega/pitch_e_demo.md`](fase7_entrega/pitch_e_demo.md), `Business_Model_Canvas_AgroSmart.pdf` |
| Resumo executivo | [`fase7_entrega/RESUMO_EXECUTIVO.md`](fase7_entrega/RESUMO_EXECUTIVO.md) |

## Estrutura

```
1_Arquitetura_Data_Lake/            camadas do data lake (Fase 6)
2_Ingestao_Administracao_Manutencao/ clima JSON e fluxo de ingestao
3_IA_Generativa_Apoio_Decisao/      relatorio por IA generativa (execucao separada)
4_Arquitetura_Solucao/              diagrama da Fase 6
5_Coleta_Dados_IoT/                 nos IoT simulados, firmware Arduino (proposto)
6_Processamento_Dados/              raw -> trusted -> refined + quarentena
7_Automacao_Inteligente/            motor de regras, alertas, comandos, dashboard
8_Execucao_Monitorada/   NOVO       orquestrador, logs JSON, indicadores, healthcheck, event log
9_Process_Mining/        NOVO       DFG, variantes, gargalos
FIAP - Agrosmart Docker/            streaming de diagnosticos (container legado, agora nao-root)
fase7_entrega/           NOVO       documentacao e evidencias da Fase 7
tests/                   NOVO       21 testes (unitarios + ponta a ponta)
executar_pipeline_integrado.py      executor original da Fase 6 (continua funcionando)
```

Os dados de ambiente são **simulados** (17/05/2026, seed 42) e não são medições reais. O `README.txt` traz a documentação original da Fase 6.
