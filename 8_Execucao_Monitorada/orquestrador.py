# -*- coding: utf-8 -*-
"""
NOVO (Fase 7) - Execucao continua/agendada e monitorada do AgroSmart.

Cada CICLO executa o mesmo pipeline do executar_pipeline_integrado.py (os
scripts do Ryan, sem alteracao de logica) e acrescenta a camada de operacao:

  [coleta_simulada]*  5_Coleta_Dados_IoT/gerar_dados_simulados.py   (*so com --gerar-dados)
  visualizacao        5_Coleta_Dados_IoT/gerar_visualizacao_simulacao.py
  processamento       6_Processamento_Dados/processar_dados.py
  motor_decisao       7_Automacao_Inteligente/motor_decisao.py
  event_log           8_Execucao_Monitorada/event_log.py   (process mining - entrada)
  process_mining      9_Process_Mining/analisar_processo.py
  indicadores         contagens, status e tempos do ciclo

Monitoramento (pasta 8_Execucao_Monitorada/saida/):
  logs/agrosmart.jsonl           logs estruturados (timestamp, nivel, componente, mensagem, contexto)
  indicadores_ultimo_ciclo.json  indicadores do ultimo ciclo (lido pelo healthcheck do Docker)
  historico_execucoes.csv        uma linha por ciclo (serie historica dos indicadores)
  painel_operacao.html           painel de operacao (abre no navegador)
  event_log.csv                  event log por leitura (case = leitura de sensor)
  event_log_ciclos.csv           event log por ciclo (case = execucao, tempos reais)

Tratamento de erros: cada etapa tem timeout e retentativa; uma falha marca o
ciclo como FALHA, e registrada no log e NAO derruba o loop. O loop so para
apos N falhas consecutivas (--max-falhas), no fim dos ciclos pedidos ou com
Ctrl+C / SIGTERM (docker stop), sempre terminando o ciclo em andamento.

Uso:
  python 8_Execucao_Monitorada/orquestrador.py                       # 1 ciclo
  python 8_Execucao_Monitorada/orquestrador.py --ciclos 3 --intervalo 10
  python 8_Execucao_Monitorada/orquestrador.py --ciclos 0            # continuo
Variaveis de ambiente (ver .env.example) definem os mesmos parametros.
"""
import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime
from html import escape
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import event_log  # noqa: E402
from logger_json import LoggerJSON  # noqa: E402

PARAR = False


def _sinal_parar(signum, _frame):
    global PARAR
    PARAR = True


def _env_int(nome, padrao):
    try:
        return int(os.environ.get(nome, padrao))
    except ValueError:
        return padrao


def _env_bool(nome, padrao=False):
    return os.environ.get(nome, str(int(padrao))).strip().lower() in ("1", "true", "sim", "yes", "on")


def argumentos(argv=None):
    p = argparse.ArgumentParser(description="Execucao continua e monitorada do pipeline AgroSmart.")
    p.add_argument("--ciclos", type=int, default=_env_int("AGROSMART_CICLOS", 1),
                   help="quantidade de ciclos (0 = continuo ate Ctrl+C/SIGTERM)")
    p.add_argument("--intervalo", type=int, default=_env_int("AGROSMART_INTERVALO_S", 30),
                   help="segundos entre o fim de um ciclo e o inicio do proximo")
    p.add_argument("--gerar-dados", action="store_true", default=_env_bool("AGROSMART_GERAR_DADOS"),
                   help="recria a serie simulada de sensores (seed fixa) a cada ciclo")
    p.add_argument("--retentativas", type=int, default=_env_int("AGROSMART_RETENTATIVAS", 1))
    p.add_argument("--timeout-etapa", type=int, default=_env_int("AGROSMART_TIMEOUT_ETAPA_S", 120))
    p.add_argument("--max-falhas", type=int, default=_env_int("AGROSMART_MAX_FALHAS_CONSECUTIVAS", 5))
    p.add_argument("--intervalo-agendamento-min", type=int,
                   default=_env_int("AGROSMART_INTERVALO_AGENDAMENTO_MIN", 30),
                   help="janela do ciclo agendado usada no event_log (process mining)")
    p.add_argument("--defasagem-agendamento-s", type=int,
                   default=_env_int("AGROSMART_DEFASAGEM_AGENDAMENTO_S", 0),
                   help="atraso do ciclo agendado apos :00/:30 no event_log (melhoria simulada)")
    p.add_argument("--nivel-log", default=os.environ.get("AGROSMART_NIVEL_LOG", "INFO"))
    p.add_argument("--raiz", default=os.environ.get("AGROSMART_RAIZ", str(BASE_DIR.parent)),
                   help="raiz do projeto (usado nos testes)")
    return p.parse_args(argv)


class Orquestrador:
    def __init__(self, args):
        self.args = args
        self.raiz = Path(args.raiz).resolve()
        self.saida = self.raiz / "8_Execucao_Monitorada" / "saida"
        self.saida.mkdir(parents=True, exist_ok=True)
        self.log = LoggerJSON(self.saida / "logs" / "agrosmart.jsonl", nivel_console=args.nivel_log)

    # ---------------------------------------------------------------- etapas
    def etapas(self):
        lista = []
        if self.args.gerar_dados:
            lista.append(("coleta_simulada", self.raiz / "5_Coleta_Dados_IoT" / "gerar_dados_simulados.py"))
        lista += [
            ("visualizacao", self.raiz / "5_Coleta_Dados_IoT" / "gerar_visualizacao_simulacao.py"),
            ("processamento", self.raiz / "6_Processamento_Dados" / "processar_dados.py"),
            ("motor_decisao", self.raiz / "7_Automacao_Inteligente" / "motor_decisao.py"),
        ]
        return lista

    def executar_script(self, nome, script):
        """Roda um script do pipeline com timeout e retentativa. Devolve dict da etapa."""
        ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        tentativas = self.args.retentativas + 1
        erro = ""
        inicio_etapa = datetime.now()
        t0 = time.perf_counter()
        for tentativa in range(1, tentativas + 1):
            try:
                if not script.exists():
                    raise FileNotFoundError(f"script nao encontrado: {script}")
                r = subprocess.run([sys.executable, str(script)], cwd=script.parent, env=ambiente,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=self.args.timeout_etapa)
                for linha in r.stdout.splitlines():
                    if linha.strip():
                        self.log.debug(nome, linha.strip())
                if r.returncode == 0:
                    return {"etapa": nome, "status": "SUCESSO", "tentativas": tentativa, "inicio": inicio_etapa,
                            "duracao_ms": round((time.perf_counter() - t0) * 1000, 1), "erro": ""}
                erro = (r.stderr.strip().splitlines() or [f"codigo {r.returncode}"])[-1]
            except (subprocess.TimeoutExpired, OSError) as exc:
                erro = f"{type(exc).__name__}: {exc}"
            nivel = "warning" if tentativa < tentativas else "error"
            getattr(self.log, nivel)(nome, f"Etapa falhou (tentativa {tentativa}/{tentativas})", erro=erro)
        return {"etapa": nome, "status": "FALHA", "tentativas": tentativas, "inicio": inicio_etapa,
                "duracao_ms": round((time.perf_counter() - t0) * 1000, 1), "erro": erro}

    def executar_funcao(self, nome, funcao):
        inicio_etapa = datetime.now()
        t0 = time.perf_counter()
        try:
            resultado = funcao()
            status, erro = "SUCESSO", ""
        except Exception as exc:  # erro de uma etapa nao pode derrubar o loop
            resultado, status, erro = None, "FALHA", f"{type(exc).__name__}: {exc}"
            self.log.error(nome, "Etapa falhou", erro=erro)
        return {"etapa": nome, "status": status, "tentativas": 1, "inicio": inicio_etapa,
                "duracao_ms": round((time.perf_counter() - t0) * 1000, 1), "erro": erro}, resultado

    # ----------------------------------------------------------- indicadores
    def coletar_indicadores(self):
        bruto = self.raiz / "5_Coleta_Dados_IoT" / "dados_sensores_brutos.csv"
        with bruto.open(encoding="utf-8", newline="") as arquivo:
            total_raw = sum(1 for _ in arquivo) - 1
        saida6 = self.raiz / "6_Processamento_Dados" / "saida"
        with (saida6 / "quarentena.csv").open(encoding="utf-8", newline="") as arquivo:
            quarentena = list(csv.DictReader(arquivo))
        with (saida6 / "dados_processados.csv").open(encoding="utf-8", newline="") as arquivo:
            validos = sum(1 for _ in csv.DictReader(arquivo))
        alertas = json.loads((self.raiz / "7_Automacao_Inteligente" / "saida" / "alertas.json")
                             .read_text(encoding="utf-8"))
        linha_tempo = alertas["linha_do_tempo"]
        por_nivel = {}
        for a in linha_tempo:
            por_nivel[a["nivel"]] = por_nivel.get(a["nivel"], 0) + 1
        return {
            "registros": {
                "raw": total_raw,
                "quarentena": len(quarentena),
                # mesma conta de processar_dados.py: raw = quarentena + duplicadas + validos
                "duplicadas": total_raw - len(quarentena) - validos,
                "validos": validos,
                "taxa_quarentena_pct": round(100 * len(quarentena) / total_raw, 2) if total_raw else 0.0,
            },
            "decisao": {
                "alertas": len(linha_tempo),
                "comandos_atuadores": sum(1 for a in linha_tempo if a.get("comando")),
                "alertas_por_nivel": por_nivel,
                "nivel_por_talhao": {t: s["nivel"] for t, s in alertas["status_por_talhao"].items()},
            },
            "quarentena_motivos": [{"talhao": q["talhao"], "linha": q["linha_arquivo"], "motivo": q["motivo"]}
                                   for q in quarentena],
        }

    # ----------------------------------------------------------------- ciclo
    def ciclo(self, numero):
        execucao_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.log.vincular(execucao_id=execucao_id, ciclo=numero)
        inicio = datetime.now()
        t0 = time.perf_counter()
        self.log.info("orquestrador", "Ciclo iniciado", gerar_dados=self.args.gerar_dados)

        etapas, falhou = [], False
        for nome, script in self.etapas():
            resultado = self.executar_script(nome, script)
            etapas.append(resultado)
            self.log.info(nome, f"Etapa {resultado['status'].lower()}", duracao_ms=resultado["duracao_ms"],
                          tentativas=resultado["tentativas"])
            if resultado["status"] != "SUCESSO":
                falhou = True
                break  # etapas seguintes dependem desta

        indicadores = {}
        if not falhou:
            duracoes = {e["etapa"]: e["duracao_ms"] for e in etapas}
            res, resumo_el = self.executar_funcao("event_log", lambda: event_log.gerar(
                self.raiz, self.saida / "event_log.csv", self.args.intervalo_agendamento_min, duracoes,
                self.args.defasagem_agendamento_s))
            etapas.append(res)
            if resumo_el:
                self.log.info("event_log", "Event log gerado", duracao_ms=res["duracao_ms"], **resumo_el)
            analise = self.raiz / "9_Process_Mining" / "analisar_processo.py"
            res = self.executar_script("process_mining", analise)
            etapas.append(res)
            self.log.info("process_mining", f"Etapa {res['status'].lower()}", duracao_ms=res["duracao_ms"])

            res, indicadores = self.executar_funcao("indicadores", self.coletar_indicadores)
            etapas.append(res)
            indicadores = indicadores or {}
            if indicadores:
                r = indicadores["registros"]
                self.log.info("indicadores", "Indicadores do ciclo", **r,
                              alertas=indicadores["decisao"]["alertas"],
                              comandos=indicadores["decisao"]["comandos_atuadores"])
                for q in indicadores["quarentena_motivos"]:
                    self.log.warning("processamento", "Leitura em quarentena", talhao=q["talhao"],
                                     linha_arquivo=q["linha"], motivo=q["motivo"])
                for talhao, nivel in indicadores["decisao"]["nivel_por_talhao"].items():
                    log_nivel = "warning" if nivel in ("ALTO", "CRITICO") else "info"
                    getattr(self.log, log_nivel)("motor_decisao", f"Status do talhao: {nivel}",
                                                 talhao=talhao, nivel_risco=nivel)

        status = "FALHA" if falhou else ("PARCIAL" if any(e["status"] != "SUCESSO" for e in etapas) else "SUCESSO")
        fim = datetime.now()
        resultado = {
            "execucao_id": execucao_id, "ciclo": numero, "status": status,
            "inicio": inicio.isoformat(timespec="seconds"), "fim": fim.isoformat(timespec="seconds"),
            "duracao_ms": round((time.perf_counter() - t0) * 1000, 1),
            "intervalo_s": self.args.intervalo,
            "etapas": [{k: (v.isoformat(timespec="milliseconds") if isinstance(v, datetime) else v)
                        for k, v in e.items()} for e in etapas],
            **indicadores,
        }
        self.gravar_monitoramento(resultado)
        nivel = "info" if status == "SUCESSO" else "error"
        getattr(self.log, nivel)("orquestrador", f"Ciclo concluido: {status}", status=status,
                                 duracao_ms=resultado["duracao_ms"])
        return resultado

    # -------------------------------------------------------- monitoramento
    def gravar_monitoramento(self, r):
        (self.saida / "indicadores_ultimo_ciclo.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

        reg, dec = r.get("registros", {}), r.get("decisao", {})
        linha = {
            "execucao_id": r["execucao_id"], "ciclo": r["ciclo"], "inicio": r["inicio"], "fim": r["fim"],
            "status": r["status"], "duracao_ms": r["duracao_ms"],
            "raw": reg.get("raw", ""), "quarentena": reg.get("quarentena", ""),
            "duplicadas": reg.get("duplicadas", ""), "validos": reg.get("validos", ""),
            "taxa_quarentena_pct": reg.get("taxa_quarentena_pct", ""),
            "alertas": dec.get("alertas", ""), "comandos_atuadores": dec.get("comandos_atuadores", ""),
            "etapa_com_falha": next((e["etapa"] for e in r["etapas"] if e["status"] != "SUCESSO"), ""),
        }
        historico = self.saida / "historico_execucoes.csv"
        novo = not historico.exists()
        with historico.open("a", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(linha))
            if novo:
                escritor.writeheader()
            escritor.writerow(linha)

        ciclos_log = self.saida / "event_log_ciclos.csv"
        novo = not ciclos_log.exists()
        with ciclos_log.open("a", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=event_log.COLUNAS)
            if novo:
                escritor.writeheader()
            for e in r["etapas"]:
                escritor.writerow({"case_id": r["execucao_id"], "activity": e["etapa"],
                                   "timestamp": e["inicio"].replace("T", " "), "talhao": "-", "no_sensor": "-",
                                   "status": e["status"], "duracao_ms": e["duracao_ms"],
                                   "motivo_desvio": e["erro"], "ciclo_agendado": r["inicio"].replace("T", " "),
                                   "linha_arquivo": ""})
        self.gravar_painel()

    def gravar_painel(self):
        historico = self.saida / "historico_execucoes.csv"
        with historico.open(encoding="utf-8", newline="") as arquivo:
            linhas = list(csv.DictReader(arquivo))[-50:]
        ultimo = json.loads((self.saida / "indicadores_ultimo_ciclo.json").read_text(encoding="utf-8"))
        cor = {"SUCESSO": "#2e7d32", "PARCIAL": "#b26a00", "FALHA": "#c62828"}
        reg, dec = ultimo.get("registros", {}), ultimo.get("decisao", {})
        cartoes = [
            ("Status do ultimo ciclo", ultimo["status"]), ("Duracao do ciclo", f"{ultimo['duracao_ms']} ms"),
            ("Leituras raw", reg.get("raw", "-")), ("Validas (refined)", reg.get("validos", "-")),
            ("Quarentena", reg.get("quarentena", "-")), ("Duplicadas", reg.get("duplicadas", "-")),
            ("Alertas", dec.get("alertas", "-")), ("Comandos p/ atuadores", dec.get("comandos_atuadores", "-")),
        ]
        talhoes = "".join(f"<li><b>{escape(t)}</b>: {escape(n)}</li>"
                          for t, n in dec.get("nivel_por_talhao", {}).items())
        etapas = "".join(
            f"<tr><td>{escape(e['etapa'])}</td><td style='color:{cor.get(e['status'], '#000')}'>{e['status']}</td>"
            f"<td>{e['duracao_ms']}</td><td>{e['tentativas']}</td><td>{escape(e['erro'])}</td></tr>"
            for e in ultimo["etapas"])
        hist = "".join(
            f"<tr><td>{escape(h['inicio'])}</td><td style='color:{cor.get(h['status'], '#000')}'>{h['status']}</td>"
            f"<td>{h['duracao_ms']}</td><td>{h['raw']}</td><td>{h['quarentena']}</td><td>{h['duplicadas']}</td>"
            f"<td>{h['validos']}</td><td>{h['alertas']}</td><td>{h['comandos_atuadores']}</td>"
            f"<td>{escape(h['etapa_com_falha'])}</td></tr>" for h in reversed(linhas))
        html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>AgroSmart - Painel de operacao</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:Arial,sans-serif;margin:24px;color:#244337;background:#f6faf7}}
h1{{margin:0 0 4px}} .sub{{color:#668576;margin-bottom:20px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:20px}}
.card{{background:#fff;border:1px solid #cfe0d5;border-radius:10px;padding:12px}}
.card span{{display:block;font-size:13px;color:#668576}} .card b{{font-size:22px}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-bottom:20px;font-size:14px}}
th,td{{border:1px solid #cfe0d5;padding:6px 8px;text-align:left}} th{{background:#eef6f0}}
</style></head><body>
<h1>AgroSmart | Painel de operacao do pipeline</h1>
<div class="sub">Execucao {escape(ultimo['execucao_id'])} | ciclo {ultimo['ciclo']} | {escape(ultimo['fim'])}
 | gerado pelo orquestrador (8_Execucao_Monitorada)</div>
<div class="cards">{''.join(f'<div class="card"><span>{escape(str(k))}</span><b>{escape(str(v))}</b></div>'
                            for k, v in cartoes)}</div>
<h2>Risco atual por talhao (motor de decisao)</h2><ul>{talhoes or '<li>sem dados</li>'}</ul>
<h2>Etapas do ultimo ciclo</h2>
<table><tr><th>Etapa</th><th>Status</th><th>Duracao (ms)</th><th>Tentativas</th><th>Erro</th></tr>{etapas}</table>
<h2>Historico de ciclos (ultimos 50)</h2>
<table><tr><th>Inicio</th><th>Status</th><th>Duracao (ms)</th><th>Raw</th><th>Quarentena</th><th>Duplicadas</th>
<th>Validos</th><th>Alertas</th><th>Comandos</th><th>Etapa com falha</th></tr>{hist}</table>
<p>Logs estruturados: <code>saida/logs/agrosmart.jsonl</code> | Painel agronomico:
<code>7_Automacao_Inteligente/saida/dashboard.html</code> | Process mining:
<code>9_Process_Mining/saida/analise_processo.md</code></p>
</body></html>
"""
        (self.saida / "painel_operacao.html").write_text(html, encoding="utf-8")

    # ------------------------------------------------------------------ loop
    def rodar(self):
        signal.signal(signal.SIGINT, _sinal_parar)
        signal.signal(signal.SIGTERM, _sinal_parar)
        a = self.args
        self.log.info("orquestrador", "Orquestrador iniciado", ciclos=a.ciclos, intervalo_s=a.intervalo,
                      gerar_dados=a.gerar_dados, raiz=str(self.raiz))
        numero, falhas_seguidas, alguma_falha = 0, 0, False
        while not PARAR and (a.ciclos == 0 or numero < a.ciclos):
            numero += 1
            resultado = self.ciclo(numero)
            if resultado["status"] == "SUCESSO":
                falhas_seguidas = 0
            else:
                falhas_seguidas += 1
                alguma_falha = True
                if falhas_seguidas >= a.max_falhas:
                    self.log.error("orquestrador", "Limite de falhas consecutivas atingido; encerrando",
                                   falhas_consecutivas=falhas_seguidas)
                    return 2
            if a.ciclos == 0 or numero < a.ciclos:
                fim_espera = time.monotonic() + a.intervalo
                while not PARAR and time.monotonic() < fim_espera:
                    time.sleep(min(0.5, max(0.0, fim_espera - time.monotonic())))
        self.log.vincular(execucao_id=None, ciclo=None)
        self.log.info("orquestrador", "Orquestrador encerrado", ciclos_executados=numero,
                      interrompido=PARAR, houve_falha=alguma_falha)
        return 1 if alguma_falha else 0


def main(argv=None):
    return Orquestrador(argumentos(argv)).rodar()


if __name__ == "__main__":
    sys.exit(main())
