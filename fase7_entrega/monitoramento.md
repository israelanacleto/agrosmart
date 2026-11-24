# Monitoramento e execução automatizada (Requisito 4)

O componente é o `8_Execucao_Monitorada/orquestrador.py` (NOVO na Fase 7). Ele roda os mesmos scripts do pipeline da Fase 6, sem alterar a lógica, e acrescenta agendamento, tratamento de erros, logs estruturados e indicadores.

## Modos de execução

| Modo | Comando | Uso |
|---|---|---|
| Ciclo único | `python 8_Execucao_Monitorada/orquestrador.py` | Execução em lote ou CI |
| Loop controlado | `python 8_Execucao_Monitorada/orquestrador.py --ciclos 3 --intervalo 10` | Demonstração |
| Contínuo | `python 8_Execucao_Monitorada/orquestrador.py --ciclos 0 --intervalo 30` ou `docker compose up` | Operação. Para com Ctrl+C ou `docker compose down` |
| Agendado pelo SO | Cron/Task Scheduler chamando o modo de ciclo único | Alternativa sem processo residente |

Todos os parâmetros também podem vir de variáveis de ambiente (veja `.env.example`): `AGROSMART_CICLOS`, `AGROSMART_INTERVALO_S`, `AGROSMART_GERAR_DADOS`, `AGROSMART_RETENTATIVAS`, `AGROSMART_TIMEOUT_ETAPA_S`, `AGROSMART_MAX_FALHAS_CONSECUTIVAS` e `AGROSMART_NIVEL_LOG`.

## Tratamento de erros

- **Por etapa:** cada script roda num subprocesso com **timeout** (padrão de 120 s) e **retentativa** (padrão de 1). Uma falha registra `WARNING` na tentativa e `ERROR` na desistência, junto com a última linha do erro.
- **Por ciclo:** se uma etapa falha, as etapas dependentes não rodam, o ciclo é marcado como `FALHA` e o histórico registra a `etapa_com_falha`. O **loop continua** no próximo ciclo.
- **Proteção do loop:** depois de N falhas seguidas (padrão de 5), o orquestrador encerra com código 2, para não ficar falhando em silêncio.
- **Parada limpa:** SIGINT e SIGTERM (`docker stop`) terminam o ciclo em andamento antes de sair.
- **Testado** em `tests/test_ponta_a_ponta.py::test_falha_de_etapa_nao_derruba_o_loop`, que apaga o arquivo raw e verifica 2 ciclos em `FALHA`, ambos registrados, com o loop vivo.

## Logs estruturados

O arquivo é `8_Execucao_Monitorada/saida/logs/agrosmart.jsonl`, em JSON Lines. Ele guarda sempre o nível DEBUG, com a saída de cada script, e faz rotação a 5 MB. O console (`docker logs`) mostra a partir do nível configurado.

Campos obrigatórios em toda linha: `timestamp` (ISO com fuso), `nivel`, `componente` e `mensagem`. O contexto inclui `execucao_id`, `ciclo`, `talhao`, `duracao_ms`, `tentativas`, `motivo` e `nivel_risco`.

Exemplos reais:
```json
{"timestamp": "2026-11-24T19:52:53.537-03:00", "nivel": "INFO", "componente": "indicadores", "mensagem": "Indicadores do ciclo", "execucao_id": "20261124-195253-bed7c3", "ciclo": 1, "raw": 144, "quarentena": 3, "duplicadas": 1, "validos": 140, "taxa_quarentena_pct": 2.08, "alertas": 8, "comandos": 2}
{"timestamp": "2026-11-24T19:52:53.537-03:00", "nivel": "WARNING", "componente": "processamento", "mensagem": "Leitura em quarentena", "execucao_id": "20261124-195253-bed7c3", "ciclo": 1, "talhao": "T2", "linha_arquivo": "66", "motivo": "temperatura_c=-50.0 fora da faixa [-10.0, 60.0]"}
{"timestamp": "2026-11-24T19:52:53.539-03:00", "nivel": "WARNING", "componente": "motor_decisao", "mensagem": "Status do talhao: CRITICO", "execucao_id": "20261124-195253-bed7c3", "ciclo": 1, "talhao": "T2", "nivel_risco": "CRITICO"}
{"timestamp": "2026-11-24T19:52:53.554-03:00", "nivel": "INFO", "componente": "orquestrador", "mensagem": "Ciclo concluido: SUCESSO", "execucao_id": "20261124-195253-bed7c3", "ciclo": 1, "status": "SUCESSO", "duracao_ms": 522.4}
```

Para filtrar no PowerShell, por exemplo só alertas de risco e erros:
```powershell
Get-Content 8_Execucao_Monitorada/saida/logs/agrosmart.jsonl | ConvertFrom-Json | Where-Object { $_.nivel -in 'WARNING','ERROR' } | Format-Table timestamp, componente, talhao, mensagem
```

## Indicadores de funcionamento

| Indicador | Significado | Onde |
|---|---|---|
| `status` do ciclo | SUCESSO / PARCIAL / FALHA | `indicadores_ultimo_ciclo.json`, histórico, painel |
| `duracao_ms` (ciclo e por etapa) | Desempenho; revela a etapa mais lenta | Idem, e `9_Process_Mining/saida/etapas_ciclo.csv` |
| `raw`, `validos` | Volume processado | Idem |
| `quarentena`, `taxa_quarentena_pct` | Qualidade do dado e saúde dos sensores (referência: 3 de 144 = 2,08%) | Idem, com o motivo por linha no log |
| `duplicadas` | Reenvios do gateway | Idem |
| `alertas`, `alertas_por_nivel`, `comandos_atuadores` | Saída de decisão (referência: 8 alertas, 2 comandos) | Idem |
| `nivel_por_talhao` | Risco atual de T1, T2 e T3 | Idem e log (`nivel_risco`) |
| `tentativas`, `etapa_com_falha` | Instabilidade | Histórico e painel |

## Como acompanhar em operação

1. **Painel de operação** (`8_Execucao_Monitorada/saida/painel_operacao.html`, abre direto no navegador). Mostra cartões com os indicadores do último ciclo, o risco por talhão, a tabela de etapas com status, duração, tentativas e erro, e o histórico dos últimos 50 ciclos.
2. **Painel agronômico** da Fase 6: `7_Automacao_Inteligente/saida/dashboard.html`.
3. **Docker:** `docker compose ps` mostra o estado `healthy` ou `unhealthy`. O HEALTHCHECK fica `unhealthy` se o último ciclo falhou ou se nenhum ciclo terminou em `max(3 × intervalo, 300 s)`. `docker compose logs -f` mostra o fluxo de logs JSON.
4. **Histórico:** `historico_execucoes.csv` tem uma linha por ciclo, pronta para Excel ou para um BI.
5. **Pontos de alerta sugeridos para a operação:**
   - `status = FALHA`;
   - `taxa_quarentena_pct` acima de 5%;
   - um talhão em `CRITICO`;
   - healthcheck `unhealthy`.

## Limite declarado
Cada ciclo reprocessa o arquivo raw disponível. Com `AGROSMART_GERAR_DADOS=1`, a série é recriada com a mesma seed, então os indicadores ficam estáveis entre ciclos. Isso é esperado numa demonstração com dados simulados. Em campo, o gateway acrescentaria leituras novas ao raw a cada ciclo.
