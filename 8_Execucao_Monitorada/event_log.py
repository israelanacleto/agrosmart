# -*- coding: utf-8 -*-
"""
NOVO (Fase 7) - Gera o event_log de process mining a partir das SAIDAS do pipeline.

Nao altera a logica do Ryan: o log e reconstruido cruzando os arquivos que o
pipeline ja produz, com as mesmas regras de processar_dados.py:

  5_Coleta_Dados_IoT/dados_sensores_brutos.csv        (raw - uma linha = um caso)
  6_Processamento_Dados/saida/quarentena.csv          (linha_arquivo -> motivo)
  6_Processamento_Dados/saida/dados_processados.csv   (talhao + data_hora -> leitura refined)
  7_Automacao_Inteligente/saida/alertas.json          (linha_do_tempo: alertas e comandos)

Modelo de tempo (declarado na documentacao):
  - "Leitura recebida" usa o `recebido_em` REAL do arquivo bruto.
  - As demais atividades acontecem no CICLO AGENDADO que processa a leitura:
    o proximo multiplo de `intervalo_agendamento_min` (padrao 30 min, a mesma
    cadencia dos sensores) apos o recebimento. Isso e uma SIMULACAO de
    agendamento em lote, nao medicao de campo.
  - `duracao_ms` e o tempo MEDIDO da etapa no ciclo real, rateado por registro.

Colunas: case_id, activity, timestamp, talhao, no_sensor, status, duracao_ms,
         motivo_desvio, ciclo_agendado, linha_arquivo
"""
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

COLUNAS = [
    "case_id", "activity", "timestamp", "talhao", "no_sensor", "status",
    "duracao_ms", "motivo_desvio", "ciclo_agendado", "linha_arquivo",
]
COLUNAS_BRUTAS = 11  # mesmo schema de processar_dados.COLUNAS_BRUTAS

ATV_RECEBIDA = "Leitura recebida"
ATV_VALIDACAO = "Validacao (trusted)"
ATV_QUARENTENA = "Enviada para quarentena"
ATV_DUPLICADA = "Descartada como duplicada"
ATV_ENRIQUECIMENTO = "Enriquecimento (refined)"
ATV_MOTOR = "Avaliacao no motor de regras"
ATV_ALERTA = "Alerta emitido"
ATV_COMANDO = "Comando para atuador"
ATV_PUBLICACAO = "Publicacao (painel e relatorios)"

FMT = "%Y-%m-%d %H:%M:%S"


def proximo_ciclo(instante, intervalo_min, defasagem_s=0):
    """Inicio do proximo ciclo agendado: 00:00 + defasagem + k * intervalo_min."""
    base = instante.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(seconds=defasagem_s)
    passo = timedelta(minutes=intervalo_min)
    ciclos = -(-(instante - base) // passo)  # teto da divisao
    return base + ciclos * passo


def _ts(instante):
    return instante.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def carregar_entradas(raiz):
    raiz = Path(raiz)
    bruto = raiz / "5_Coleta_Dados_IoT" / "dados_sensores_brutos.csv"
    with bruto.open(encoding="utf-8", newline="") as arquivo:
        leitor = csv.reader(arquivo)
        next(leitor)
        linhas = list(enumerate(leitor, start=2))

    saida6 = raiz / "6_Processamento_Dados" / "saida"
    with (saida6 / "quarentena.csv").open(encoding="utf-8", newline="") as arquivo:
        quarentena = {int(q["linha_arquivo"]): q["motivo"] for q in csv.DictReader(arquivo)}
    with (saida6 / "dados_processados.csv").open(encoding="utf-8", newline="") as arquivo:
        processados = {(p["talhao"], p["data_hora"]): p for p in csv.DictReader(arquivo)}

    alertas_json = json.loads(
        (raiz / "7_Automacao_Inteligente" / "saida" / "alertas.json").read_text(encoding="utf-8"))
    alertas = {}
    for evento in alertas_json["linha_do_tempo"]:
        alertas.setdefault((evento["talhao"], evento["data_hora"]), []).append(evento)
    return linhas, quarentena, processados, alertas


def gerar(raiz, destino, intervalo_agendamento_min=30, duracoes_ms=None, defasagem_s=0):
    """Grava o event_log em `destino` e devolve um resumo com contagens."""
    duracoes_ms = duracoes_ms or {}
    linhas, quarentena, processados, alertas = carregar_entradas(raiz)
    n_raw = max(len(linhas), 1)
    n_validos = max(len(processados), 1)
    dur_proc = round(duracoes_ms.get("processamento", 0.0) / n_raw, 3)
    dur_motor = round(duracoes_ms.get("motor_decisao", 0.0) / n_validos, 3)

    eventos, vistos = [], set()
    resumo = {"casos": 0, "quarentena": 0, "duplicadas": 0, "validos": 0, "alertas": 0,
              "comandos": 0, "sem_timestamp": 0}

    for numero, campos in linhas:
        try:
            recebido = datetime.strptime(campos[0].strip(), FMT)
        except (ValueError, IndexError):
            resumo["sem_timestamp"] += 1
            continue
        no_sensor = campos[1].strip() if len(campos) > 1 else "?"
        talhao = campos[2].strip() if len(campos) > 2 else "?"
        case_id = f"LEIT-{numero:04d}"
        ciclo = proximo_ciclo(recebido, intervalo_agendamento_min, defasagem_s)
        relogio = [ciclo]

        def emitir(atividade, status="OK", duracao=0.0, motivo="", instante=None,
                   _case=case_id, _talhao=talhao, _no=no_sensor, _ciclo=ciclo, _linha=numero, _rel=relogio):
            if instante is None:
                # avanca o relogio do ciclo pela duracao medida (minimo 1 ms para manter a ordem)
                _rel[0] = _rel[0] + timedelta(milliseconds=max(duracao, 1.0))
                instante = _rel[0]
            eventos.append({
                "case_id": _case, "activity": atividade, "timestamp": _ts(instante),
                "talhao": _talhao, "no_sensor": _no, "status": status, "duracao_ms": duracao,
                "motivo_desvio": motivo, "ciclo_agendado": _ts(_ciclo), "linha_arquivo": _linha,
            })

        resumo["casos"] += 1
        emitir(ATV_RECEBIDA, instante=recebido)

        if numero in quarentena:
            emitir(ATV_VALIDACAO, "REJEITADA", dur_proc, quarentena[numero])
            emitir(ATV_QUARENTENA, "REJEITADA", 0.0, quarentena[numero])
            resumo["quarentena"] += 1
            continue

        chave = (no_sensor, campos[3].strip() if len(campos) > 3 else "")
        if chave in vistos:
            emitir(ATV_VALIDACAO, "OK", dur_proc)
            emitir(ATV_DUPLICADA, "DESCARTADA", 0.0, "mesmo no_sensor + millis ja recebido (reenvio do gateway)")
            resumo["duplicadas"] += 1
            continue
        vistos.add(chave)

        refinada = processados.get((talhao, recebido.strftime(FMT)))
        emitir(ATV_VALIDACAO, "OK", dur_proc)
        if refinada is None:
            emitir(ATV_ENRIQUECIMENTO, "AUSENTE", dur_proc, "leitura valida nao encontrada no refined")
            continue
        resumo["validos"] += 1
        if refinada["lacuna"] == "1":
            emitir(ATV_ENRIQUECIMENTO, "LACUNA", dur_proc,
                   f"{refinada['intervalo_min']} min sem leitura anterior (pacote perdido/rejeitado)")
        else:
            emitir(ATV_ENRIQUECIMENTO, "OK", dur_proc)

        emitir(ATV_MOTOR, "OK", dur_motor)
        for alerta in alertas.get((talhao, recebido.strftime("%Y-%m-%d %H:%M")), []):
            emitir(ATV_ALERTA, alerta["nivel"], 0.0, f"{alerta['acao']}: {alerta['mensagem']}")
            resumo["alertas"] += 1
            if alerta.get("comando"):
                emitir(ATV_COMANDO, f"'{alerta['comando']}'", 0.0, f"fila de comandos -> {no_sensor}")
                resumo["comandos"] += 1
        emitir(ATV_PUBLICACAO, "OK", 0.0)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(eventos)
    resumo["eventos"] = len(eventos)
    return resumo


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gera o event_log a partir das saidas do pipeline.")
    parser.add_argument("--intervalo-agendamento-min", type=int, default=30)
    parser.add_argument("--defasagem-s", type=int, default=0, help="atraso do ciclo apos :00/:30 (what-if)")
    parser.add_argument("--destino", default=str(Path(__file__).resolve().parent / "saida" / "event_log.csv"))
    args = parser.parse_args()
    raiz_projeto = Path(__file__).resolve().parent.parent
    print(gerar(raiz_projeto, args.destino, args.intervalo_agendamento_min, defasagem_s=args.defasagem_s))
