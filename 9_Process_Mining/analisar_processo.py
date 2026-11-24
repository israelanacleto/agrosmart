# -*- coding: utf-8 -*-
"""
NOVO (Fase 7) - Mineracao de processos sobre o event_log do AgroSmart.

Entrada:  8_Execucao_Monitorada/saida/event_log.csv          (case = leitura de sensor)
          8_Execucao_Monitorada/saida/event_log_ciclos.csv   (case = ciclo; opcional)
Saidas (pasta saida/):
  analise_processo.md   relatorio gerado: fluxo, variantes, gargalos, desvios, indicadores
  fluxo_processo.mmd    grafo directly-follows (DFG) em Mermaid, com frequencia e espera media
  variantes.csv         variantes (sequencia de atividades) com frequencia e % dos casos
  transicoes.csv        transicoes a -> b com frequencia e tempos de espera (s)
  etapas_ciclo.csv      duracao real medida por etapa do pipeline (se houver event_log_ciclos)

Tecnicas (equivalentes as de ferramentas como PM4Py/Disco, em Python puro):
  - descoberta do processo por Directly-Follows Graph (DFG);
  - analise de variantes (caminho completo de cada caso);
  - performance: tempo entre atividades consecutivas (espera) e tempo total do caso;
  - conformidade simples: casos que fogem do caminho feliz e o motivo do desvio.
Uso:  python 9_Process_Mining/analisar_processo.py [--event-log CAMINHO]
"""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median

BASE_DIR = Path(__file__).resolve().parent
RAIZ = BASE_DIR.parent
PADRAO_EVENT_LOG = RAIZ / "8_Execucao_Monitorada" / "saida" / "event_log.csv"
PADRAO_CICLOS = RAIZ / "8_Execucao_Monitorada" / "saida" / "event_log_ciclos.csv"
PASTA_SAIDA = BASE_DIR / "saida"

INICIO, FIM = "INICIO", "FIM"


def ler_tempo(texto):
    return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S.%f" if "." in texto else "%Y-%m-%d %H:%M:%S")


def carregar(caminho):
    with Path(caminho).open(encoding="utf-8", newline="") as arquivo:
        eventos = list(csv.DictReader(arquivo))
    casos = defaultdict(list)
    for ordem, e in enumerate(eventos):
        e["_t"] = ler_tempo(e["timestamp"])
        e["_ordem"] = ordem
        casos[e["case_id"]].append(e)
    for lista in casos.values():
        lista.sort(key=lambda e: (e["_t"], e["_ordem"]))
    return eventos, casos


def fmt_seg(segundos):
    if segundos >= 60:
        return f"{segundos / 60:.1f} min"
    if segundos >= 1:
        return f"{segundos:.1f} s"
    return f"{segundos * 1000:.1f} ms"


def analisar(casos):
    variantes = Counter()
    transicoes = defaultdict(list)
    atividades = Counter()
    casos_por_atividade = defaultdict(set)
    desvios = Counter()
    lead_time = []
    tempo_ate_alerta = []
    por_talhao = defaultdict(Counter)

    for case_id, evs in casos.items():
        seq = tuple(e["activity"] for e in evs)
        variantes[seq] += 1
        talhao = evs[0]["talhao"]
        por_talhao[talhao]["casos"] += 1
        anterior = None
        for e in evs:
            atividades[e["activity"]] += 1
            casos_por_atividade[e["activity"]].add(case_id)
            if anterior is not None:
                transicoes[(anterior["activity"], e["activity"])].append((e["_t"] - anterior["_t"]).total_seconds())
            if e["motivo_desvio"] and e["activity"] in ("Enviada para quarentena", "Descartada como duplicada",
                                                       "Enriquecimento (refined)"):
                desvios[(e["activity"], e["motivo_desvio"])] += 1
            if e["activity"] == "Alerta emitido":
                por_talhao[talhao]["alertas"] += 1
                tempo_ate_alerta.append(((e["_t"] - evs[0]["_t"]).total_seconds(), case_id, talhao, e["status"],
                                         e["motivo_desvio"]))
            if e["activity"] == "Comando para atuador":
                por_talhao[talhao]["comandos"] += 1
            if e["activity"] in ("Enviada para quarentena", "Descartada como duplicada"):
                por_talhao[talhao]["descartados"] += 1
            if e["status"] == "LACUNA":
                por_talhao[talhao]["lacunas"] += 1
            anterior = e
        transicoes[(INICIO, evs[0]["activity"])].append(0.0)
        transicoes[(evs[-1]["activity"], FIM)].append(0.0)
        lead_time.append((evs[-1]["_t"] - evs[0]["_t"]).total_seconds())

    return {
        "variantes": variantes, "transicoes": transicoes, "atividades": atividades,
        "casos_por_atividade": casos_por_atividade, "desvios": desvios, "lead_time": lead_time,
        "tempo_ate_alerta": sorted(tempo_ate_alerta), "por_talhao": por_talhao,
    }


def mermaid(resultado, total_casos):
    nomes = {INICIO: "n0", FIM: "nF"}
    for i, atv in enumerate(sorted(resultado["atividades"], key=lambda a: -resultado["atividades"][a]), start=1):
        nomes[atv] = f"n{i}"
    linhas = ["flowchart TD", f'    n0(["INICIO<br/>{total_casos} casos"])', '    nF(["FIM"])']
    for atv, n in resultado["atividades"].items():
        linhas.append(f'    {nomes[atv]}["{atv}<br/>{n} eventos"]')
    for (a, b), esperas in sorted(resultado["transicoes"].items(), key=lambda x: -len(x[1])):
        rotulo = f"{len(esperas)}x"
        if a != INICIO and b != FIM:
            rotulo += f" · media {fmt_seg(mean(esperas))}"
        linhas.append(f'    {nomes[a]} -->|"{rotulo}"| {nomes[b]}')
    linhas += [
        "    classDef desvio fill:#fdecea,stroke:#c62828;",
        "    classDef acao fill:#fff4e5,stroke:#b26a00;",
    ]
    for atv in ("Enviada para quarentena", "Descartada como duplicada"):
        if atv in nomes:
            linhas.append(f"    class {nomes[atv]} desvio;")
    for atv in ("Alerta emitido", "Comando para atuador"):
        if atv in nomes:
            linhas.append(f"    class {nomes[atv]} acao;")
    return "\n".join(linhas) + "\n"


def analisar_ciclos(caminho):
    if not Path(caminho).exists():
        return []
    with Path(caminho).open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    por_etapa = defaultdict(list)
    falhas = Counter()
    for linha in linhas:
        por_etapa[linha["activity"]].append(float(linha["duracao_ms"] or 0))
        if linha["status"] != "SUCESSO":
            falhas[linha["activity"]] += 1
    total = sum(mean(v) for v in por_etapa.values()) or 1.0
    return sorted(
        ({"etapa": etapa, "execucoes": len(v), "media_ms": round(mean(v), 1), "max_ms": round(max(v), 1),
          "pct_do_ciclo": round(100 * mean(v) / total, 1), "falhas": falhas[etapa]}
         for etapa, v in por_etapa.items()),
        key=lambda d: -d["media_ms"])


def relatorio(eventos, casos, r, etapas_ciclo, caminho_log):
    total = len(casos)
    feliz = max(r["variantes"].items(), key=lambda kv: kv[1])
    linhas = [
        "# Analise de processo (process mining) - AgroSmart",
        "",
        f"Gerado automaticamente em {datetime.now():%d/%m/%Y %H:%M} por `9_Process_Mining/analisar_processo.py`",
        f"a partir de `{caminho_log}`. **Nao edite a mao.** A interpretacao fica em",
        "`fase7_entrega/process_mining.md`.",
        "",
        "## Visao geral",
        "",
        "| Indicador | Valor |",
        "|---|---|",
        f"| Casos (leituras de sensor) | {total} |",
        f"| Eventos | {len(eventos)} |",
        f"| Atividades distintas | {len(r['atividades'])} |",
        f"| Variantes | {len(r['variantes'])} |",
        f"| Casos no caminho principal | {feliz[1]} ({100 * feliz[1] / total:.1f}%) |",
        f"| Lead time medio (recebida -> fim) | {fmt_seg(mean(r['lead_time']))} |",
        f"| Lead time mediano | {fmt_seg(median(r['lead_time']))} |",
        f"| Lead time maximo | {fmt_seg(max(r['lead_time']))} |",
        "",
        "## Atividades",
        "",
        "| Atividade | Eventos | Casos | % dos casos |",
        "|---|---|---|---|",
    ]
    for atv, n in r["atividades"].most_common():
        c = len(r["casos_por_atividade"][atv])
        linhas.append(f"| {atv} | {n} | {c} | {100 * c / total:.1f}% |")

    linhas += ["", "## Variantes (caminhos do processo)", "", "| # | Casos | % | Sequencia |", "|---|---|---|---|"]
    for i, (seq, n) in enumerate(r["variantes"].most_common(), start=1):
        linhas.append(f"| V{i} | {n} | {100 * n / total:.1f}% | {' → '.join(seq)} |")

    linhas += ["", "## Gargalos: espera entre atividades consecutivas", "",
               "| De | Para | Freq. | Espera media | Mediana | Maxima |", "|---|---|---|---|---|---|"]
    reais = [(k, v) for k, v in r["transicoes"].items() if INICIO not in k and FIM not in k]
    for (a, b), v in sorted(reais, key=lambda kv: -mean(kv[1])):
        linhas.append(f"| {a} | {b} | {len(v)} | {fmt_seg(mean(v))} | {fmt_seg(median(v))} | {fmt_seg(max(v))} |")
    soma = sum(sum(v) for _, v in reais) or 1.0
    maior = max(reais, key=lambda kv: sum(kv[1]))
    linhas += ["", f"A transicao **{maior[0][0]} → {maior[0][1]}** responde por "
               f"**{100 * sum(maior[1]) / soma:.1f}%** de todo o tempo de espera do processo."]

    linhas += ["", "## Desvios do caminho principal", "", "| Atividade | Motivo | Casos |", "|---|---|---|"]
    for (atv, motivo), n in r["desvios"].most_common():
        linhas.append(f"| {atv} | {motivo} | {n} |")

    linhas += ["", "## Tempo da leitura ate o alerta", "",
               "| Caso | Talhao | Nivel | Alerta | Tempo desde a leitura |", "|---|---|---|---|---|"]
    for seg, case_id, talhao, nivel, motivo in r["tempo_ate_alerta"]:
        linhas.append(f"| {case_id} | {talhao} | {nivel} | {motivo} | {fmt_seg(seg)} |")

    linhas += ["", "## Por talhao", "", "| Talhao | Casos | Descartados | Lacunas | Alertas | Comandos |",
               "|---|---|---|---|---|---|"]
    for talhao, c in sorted(r["por_talhao"].items()):
        linhas.append(f"| {talhao} | {c['casos']} | {c['descartados']} | {c['lacunas']} | {c['alertas']} | "
                      f"{c['comandos']} |")

    if etapas_ciclo:
        linhas += ["", "## Etapas do pipeline (tempo real medido, event_log_ciclos.csv)", "",
                   "| Etapa | Execucoes | Media (ms) | Max (ms) | % do ciclo | Falhas |", "|---|---|---|---|---|---|"]
        for d in etapas_ciclo:
            linhas.append(f"| {d['etapa']} | {d['execucoes']} | {d['media_ms']} | {d['max_ms']} | "
                          f"{d['pct_do_ciclo']}% | {d['falhas']} |")

    linhas += ["", "## Fluxo descoberto (DFG)", "", "```mermaid", mermaid(r, total).rstrip(), "```", ""]
    return "\n".join(linhas)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--event-log", default=str(PADRAO_EVENT_LOG))
    parser.add_argument("--event-log-ciclos", default=str(PADRAO_CICLOS))
    args = parser.parse_args()

    eventos, casos = carregar(args.event_log)
    if not casos:
        raise SystemExit("[ERRO] event_log vazio")
    r = analisar(casos)
    etapas_ciclo = analisar_ciclos(args.event_log_ciclos)

    PASTA_SAIDA.mkdir(exist_ok=True)
    nome_log = Path(args.event_log).relative_to(RAIZ).as_posix() if Path(args.event_log).is_relative_to(RAIZ) \
        else Path(args.event_log).name
    (PASTA_SAIDA / "analise_processo.md").write_text(relatorio(eventos, casos, r, etapas_ciclo, nome_log),
                                                     encoding="utf-8")
    (PASTA_SAIDA / "fluxo_processo.mmd").write_text(mermaid(r, len(casos)), encoding="utf-8")
    with (PASTA_SAIDA / "variantes.csv").open("w", encoding="utf-8", newline="") as arquivo:
        w = csv.writer(arquivo)
        w.writerow(["variante", "casos", "pct_casos", "sequencia"])
        for i, (seq, n) in enumerate(r["variantes"].most_common(), start=1):
            w.writerow([f"V{i}", n, round(100 * n / len(casos), 2), " > ".join(seq)])
    with (PASTA_SAIDA / "transicoes.csv").open("w", encoding="utf-8", newline="") as arquivo:
        w = csv.writer(arquivo)
        w.writerow(["de", "para", "frequencia", "espera_media_s", "espera_mediana_s", "espera_max_s"])
        for (a, b), v in sorted(r["transicoes"].items(), key=lambda kv: -len(kv[1])):
            w.writerow([a, b, len(v), round(mean(v), 3), round(median(v), 3), round(max(v), 3)])
    if etapas_ciclo:
        with (PASTA_SAIDA / "etapas_ciclo.csv").open("w", encoding="utf-8", newline="") as arquivo:
            w = csv.DictWriter(arquivo, fieldnames=list(etapas_ciclo[0]))
            w.writeheader()
            w.writerows(etapas_ciclo)

    print(f"Casos: {len(casos)} | eventos: {len(eventos)} | variantes: {len(r['variantes'])}")
    for i, (seq, n) in enumerate(r["variantes"].most_common(), start=1):
        print(f"   V{i}: {n} casos - {' > '.join(seq)}")
    print(f"[SUCESSO] Analise gravada em {PASTA_SAIDA.name}/analise_processo.md")


if __name__ == "__main__":
    main()
