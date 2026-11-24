# -*- coding: utf-8 -*-
"""
Testes ponta a ponta: rodam o orquestrador numa copia isolada do projeto e
conferem os numeros "golden" da base do Ryan (seed 42), os logs estruturados,
o event_log e a resiliencia a falhas.
"""
import csv
import json
import subprocess
import sys

from conftest import importar

event_log = importar("8_Execucao_Monitorada/event_log.py", "event_log")

GOLDEN = {"raw": 144, "quarentena": 3, "duplicadas": 1, "validos": 140}


def rodar(projeto, *args):
    script = projeto / "8_Execucao_Monitorada" / "orquestrador.py"
    return subprocess.run([sys.executable, str(script), "--raiz", str(projeto), "--nivel-log", "ERROR", *args],
                          capture_output=True, text=True, encoding="utf-8", timeout=300)


def test_pipeline_completo_reproduz_numeros_da_base(projeto):
    r = rodar(projeto, "--ciclos", "1", "--gerar-dados")
    assert r.returncode == 0, r.stdout + r.stderr

    saida = projeto / "8_Execucao_Monitorada" / "saida"
    ind = json.loads((saida / "indicadores_ultimo_ciclo.json").read_text(encoding="utf-8"))
    assert ind["status"] == "SUCESSO"
    assert {k: ind["registros"][k] for k in GOLDEN} == GOLDEN
    assert ind["decisao"]["alertas"] == 8
    assert ind["decisao"]["comandos_atuadores"] == 2
    assert ind["decisao"]["nivel_por_talhao"] == {"T1": "NORMAL", "T2": "CRITICO", "T3": "ALTO"}

    # saidas do pipeline original continuam sendo geradas nos mesmos caminhos
    for arquivo in ["6_Processamento_Dados/saida/dados_processados.csv",
                    "6_Processamento_Dados/saida/quarentena.csv",
                    "6_Processamento_Dados/saida/resumo_por_talhao.csv",
                    "7_Automacao_Inteligente/saida/alertas.json",
                    "7_Automacao_Inteligente/saida/comandos_atuadores.txt",
                    "7_Automacao_Inteligente/saida/relatorio_alertas.txt",
                    "7_Automacao_Inteligente/saida/dashboard.html",
                    "8_Execucao_Monitorada/saida/painel_operacao.html",
                    "9_Process_Mining/saida/analise_processo.md",
                    "9_Process_Mining/saida/fluxo_processo.mmd"]:
        assert (projeto / arquivo).exists(), arquivo


def test_logs_estruturados_tem_campos_obrigatorios(projeto):
    assert rodar(projeto, "--ciclos", "1").returncode == 0
    logs = (projeto / "8_Execucao_Monitorada" / "saida" / "logs" / "agrosmart.jsonl").read_text(encoding="utf-8")
    registros = [json.loads(linha) for linha in logs.splitlines()]
    assert registros
    for reg in registros:
        assert {"timestamp", "nivel", "componente", "mensagem"} <= reg.keys()
    assert any(reg.get("talhao") == "T2" and reg.get("nivel_risco") == "CRITICO" for reg in registros)
    assert any(reg["componente"] == "processamento" and reg["nivel"] == "WARNING" for reg in registros)


def test_event_log_consistente(projeto):
    assert rodar(projeto, "--ciclos", "1").returncode == 0
    with (projeto / "8_Execucao_Monitorada" / "saida" / "event_log.csv").open(encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    assert list(linhas[0].keys()) == event_log.COLUNAS
    casos = {linha["case_id"] for linha in linhas}
    assert len(casos) == GOLDEN["raw"]
    contagem = {atv: sum(1 for linha in linhas if linha["activity"] == atv) for atv in
                (event_log.ATV_QUARENTENA, event_log.ATV_DUPLICADA, event_log.ATV_ALERTA, event_log.ATV_COMANDO)}
    assert contagem == {event_log.ATV_QUARENTENA: 3, event_log.ATV_DUPLICADA: 1,
                        event_log.ATV_ALERTA: 8, event_log.ATV_COMANDO: 2}
    # dentro de cada caso o tempo nunca volta
    por_caso = {}
    for linha in linhas:
        por_caso.setdefault(linha["case_id"], []).append(linha["timestamp"])
    assert all(ts == sorted(ts) for ts in por_caso.values())


def test_falha_de_etapa_nao_derruba_o_loop(projeto):
    (projeto / "5_Coleta_Dados_IoT" / "dados_sensores_brutos.csv").unlink()
    r = rodar(projeto, "--ciclos", "2", "--intervalo", "0", "--retentativas", "0")
    assert r.returncode == 1  # houve falha, mas os 2 ciclos rodaram
    saida = projeto / "8_Execucao_Monitorada" / "saida"
    with (saida / "historico_execucoes.csv").open(encoding="utf-8") as arquivo:
        historico = list(csv.DictReader(arquivo))
    assert [h["status"] for h in historico] == ["FALHA", "FALHA"]
    assert historico[0]["etapa_com_falha"] == "visualizacao"  # primeira etapa que le o raw
    logs = (saida / "logs" / "agrosmart.jsonl").read_text(encoding="utf-8")
    assert '"nivel": "ERROR"' in logs


def test_proximo_ciclo_agendado():
    from datetime import datetime
    assert event_log.proximo_ciclo(datetime(2026, 5, 17, 10, 0, 3), 30) == datetime(2026, 5, 17, 10, 30)
    assert event_log.proximo_ciclo(datetime(2026, 5, 17, 10, 30, 0), 30) == datetime(2026, 5, 17, 10, 30)
    assert event_log.proximo_ciclo(datetime(2026, 5, 17, 10, 0, 3), 30, 60) == datetime(2026, 5, 17, 10, 1)
