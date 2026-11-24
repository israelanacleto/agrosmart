# Caso de teste ponta a ponta (Requisito 2)

Este é o caso padronizado e reproduzível: **seed 42, 3 talhões, 24 h em 17/05/2026**. Todos os trechos abaixo foram copiados de uma execução real do pipeline, sem edição. Os mesmos números são conferidos automaticamente:
- em `tests/test_ponta_a_ponta.py`;
- no smoke test do container no CI.

## Como executar

```powershell
# local (Python 3.10+, sem dependencias)
python 8_Execucao_Monitorada/orquestrador.py --ciclos 1 --gerar-dados

# via Docker
docker compose run --rm -e AGROSMART_CICLOS=1 -e AGROSMART_GERAR_DADOS=1 agrosmart
```

O executor original da Fase 6 também continua funcionando: `python executar_pipeline_integrado.py --gerar-dados`. Ele roda as mesmas etapas, mas sem logs, indicadores e event log.

## Resultado esperado (números de referência)

| Indicador | Valor | Onde conferir |
|---|---|---|
| Leituras raw | 144 | `5_Coleta_Dados_IoT/dados_sensores_brutos.csv` |
| Quarentena | 3 | `6_Processamento_Dados/saida/quarentena.csv` |
| Duplicadas removidas | 1 | log `processamento` / `indicadores` |
| Válidas (refined) | 140 | `6_Processamento_Dados/saida/dados_processados.csv` |
| Alertas na linha do tempo | 8 (1 CRITICO, 3 ALTO, 4 ATENCAO) | `7_Automacao_Inteligente/saida/alertas.json` |
| Comandos para atuadores | 2 (`'I'` para NODE-02) | `7_Automacao_Inteligente/saida/comandos_atuadores.txt` |
| Status final | T1 NORMAL, T2 CRITICO, T3 ALTO | `relatorio_alertas.txt`, `dashboard.html` |
| Event log | 144 casos, 722 eventos, 5 variantes | `8_Execucao_Monitorada/saida/event_log.csv` |

## Rastreio de uma leitura: T2, 22:00 (seca crítica → bomba ligada)

**1. Entrada RAW** (linha 134 do arquivo bruto):
```
2026-05-17 22:00:01,NODE-02,T2,193324000,27.4,47,19,0,0,0,0
```

**2. Trusted → Refined.** A linha passou na validação e foi enriquecida (`dados_processados.csv`):
```
data_hora,data,hora,periodo,talhao,no_sensor,temperatura_c,umidade_ar_pct,umidade_solo_pct,luminosidade_pct,movimento,chuva,bomba,ponto_orvalho_c,vpd_kpa,solo_media_movel_3,delta_solo,horas_ur_alta_consecutivas,intervalo_min,lacuna
2026-05-17 22:00:01,2026-05-17,22:00,noite,T2,NODE-02,27.4,47,19,0,0,0,0,15.1,1.93,20,-1,0.0,30,0
```
O solo saiu de 21% (21:00) para 20% (21:30) e chegou a **19%**, abaixo do limiar crítico de 20% da regra R02.

**3. Decisão** (`alertas.json`, `linha_do_tempo`):
```json
{
 "data_hora": "2026-05-17 22:00",
 "talhao": "T2",
 "acao": "A01",
 "nivel": "CRITICO",
 "mensagem": "Solo em nivel critico de umidade",
 "recomendacao": "Irrigar imediatamente (comando simulado gerado automaticamente).",
 "comando": "I",
 "evidencias": ["R02"]
}
```
A A01 exige que não haja chuva recente nem prevista. O JSON de clima traz `risco_chuva_pct` = 15%, abaixo do limiar de 60% da R08, então a irrigação não foi adiada.

**4. Atuação** (`comandos_atuadores.txt`):
```
2026-05-17 16:30  NODE-02  'I'  (Estresse hidrico: solo seco sob calor/ar seco)
2026-05-17 22:00  NODE-02  'I'  (Solo em nivel critico de umidade)
```

**5. Relatório para o produtor** (`relatorio_alertas.txt`):
```
Talhao T2 (NODE-02)  |  ultima leitura 2026-05-17 23:30
Classificacao de risco: CRITICO
Leitura: 24.9 C | UR 52% | solo 17% | VPD 1.51 kPa | 0.0 h de UR>=85% (24 h)
  - [CRITICO] Solo em nivel critico de umidade: Irrigar imediatamente (comando simulado gerado automaticamente).  [comando 'I' -> NODE-02]
      porque R02: Umidade do solo abaixo de 20%
```

**6. A mesma leitura no event log** (`event_log.csv`, caso `LEIT-0134`):
```
LEIT-0134,Leitura recebida,2026-05-17 22:00:01.000,T2,NODE-02,OK,0.0,,2026-05-17 22:30:00.000,134
LEIT-0134,Validacao (trusted),2026-05-17 22:30:00.001,T2,NODE-02,OK,0.789,,2026-05-17 22:30:00.000,134
LEIT-0134,Enriquecimento (refined),2026-05-17 22:30:00.002,T2,NODE-02,OK,0.789,,2026-05-17 22:30:00.000,134
LEIT-0134,Avaliacao no motor de regras,2026-05-17 22:30:00.003,T2,NODE-02,OK,1.001,,2026-05-17 22:30:00.000,134
LEIT-0134,Alerta emitido,2026-05-17 22:30:00.004,T2,NODE-02,CRITICO,0.0,A01: Solo em nivel critico de umidade,2026-05-17 22:30:00.000,134
LEIT-0134,Comando para atuador,2026-05-17 22:30:00.005,T2,NODE-02,'I',0.0,fila de comandos -> NODE-02,2026-05-17 22:30:00.000,134
LEIT-0134,Publicacao (painel e relatorios),2026-05-17 22:30:00.006,T2,NODE-02,OK,0.0,,2026-05-17 22:30:00.000,134
```

## Caminho de desvio: T2, 10:30 (sensor desconectado → quarentena)

```
RAW (linha 66):  2026-05-17 10:30:01,NODE-02,T2,151920000,-50.0,41,40,83,0,0,0
quarentena.csv:  66,T2,"temperatura_c=-50.0 fora da faixa [-10.0, 60.0]","2026-05-17 10:30:01,NODE-02,T2,..."
log JSON:        {"nivel": "WARNING", "componente": "processamento", "mensagem": "Leitura em quarentena",
                  "talhao": "T2", "linha_arquivo": "66", "motivo": "temperatura_c=-50.0 fora da faixa [-10.0, 60.0]", ...}
alerta:          2026-05-17 11:00  T2  ATENCAO  Falha de leitura no no de sensores   (A09, na leitura SEGUINTE)
```

O valor −50,0 °C corresponde a `analogRead = 0` no TMP36, ou seja, sensor desconectado, como documentado em `gerar_dados_simulados.py`.

## Caminho de desvio: T1, 06:00 (reenvio do gateway → duplicada)

As linhas 39 e 40 do raw são idênticas: `2026-05-17 06:00:03,NODE-01,T1,94321000,...`. A segunda é descartada pela chave `(no_sensor, millis)` e aparece no event log como `Descartada como duplicada`.

## Evidências versionadas

A execução de referência está copiada em `fase7_entrega/evidencias/`:
- logs JSON;
- indicadores e histórico;
- painel de operação;
- event log.

A pasta `8_Execucao_Monitorada/saida/` é regenerada a cada ciclo e por isso não é versionada.
