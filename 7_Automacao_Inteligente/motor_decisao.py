# -*- coding: utf-8 -*-
"""
Motor de decisao automatizada do AgroSmart (motor inferencial baseado em regras).

Entradas (todas produzidas pelas etapas anteriores):
  6_Processamento_Dados/saida/dados_processados.csv      leituras de sensores (refined)
  6_Processamento_Dados/saida/quarentena.csv             leituras rejeitadas
  2_Ingestao_.../exemplo_dados_api_clima.json            previsao do tempo (API externa)
  FIAP - Agrosmart Docker/dados_agricolas.csv            diagnosticos de doenca por amostra

Como funciona:
  1. Para cada talhao, as leituras sao "reproduzidas" em ordem cronologica,
     como se chegassem em tempo real.
  2. A cada leitura monta-se uma base de FATOS (leitura atual + janelas de
     2 h e 24 h + clima + diagnosticos).
  3. As REGRAS sao aplicadas por encadeamento progressivo (forward chaining):
     regras de 1o nivel derivam fatos intermediarios (ex.: solo_seco), que
     disparam regras de 2o nivel (ex.: estresse_hidrico) ate nao surgir
     nenhum fato novo.
  4. Regras de ACAO transformam fatos em alertas com nivel de risco,
     recomendacao e, quando cabe, um comando para o atuador do no de campo
     ('I' liga / 'D' desliga a bomba - ver agrosmart_no_sensor.ino).
  5. Cada alerta guarda as regras que o justificaram (explicabilidade).

Saidas (pasta saida/):
  alertas.json            status final por talhao + linha do tempo de alertas
  relatorio_alertas.txt   relatorio legivel para o produtor
  comandos_atuadores.txt  fila de comandos para os nos de campo
  dashboard.html          painel de visualizacao (abre direto no navegador)

Uso:  python motor_decisao.py
"""
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean

BASE_DIR = Path(__file__).resolve().parent
RAIZ = BASE_DIR.parent
ARQ_PROCESSADOS = RAIZ / "6_Processamento_Dados" / "saida" / "dados_processados.csv"
ARQ_QUARENTENA = RAIZ / "6_Processamento_Dados" / "saida" / "quarentena.csv"
ARQ_CLIMA = RAIZ / "2_Ingestao_Administracao_Manutencao" / "exemplo_dados_api_clima.json"
ARQ_DIAGNOSTICOS = RAIZ / "FIAP - Agrosmart Docker" / "dados_agricolas.csv"
ARQ_TEMPLATE = BASE_DIR / "dashboard_template.html"
PASTA_SAIDA = BASE_DIR / "saida"

NIVEIS = ["NORMAL", "ATENCAO", "ALTO", "CRITICO"]
ANOMALIAS_FUNGICAS = {"Ferrugem", "Antracnose", "Míldio", "Mancha Foliar"}
NO_POR_TALHAO = {"T1": "NODE-01", "T2": "NODE-02", "T3": "NODE-03"}


# =================================================================== REGRAS
# Cada regra: (id, descricao, condicao sobre os fatos, fato que conclui)
REGRAS_INFERENCIA = [
    ("R01", "Umidade do solo abaixo de 30%",
     lambda f: f["umidade_solo_pct"] < 30, "solo_seco"),
    ("R02", "Umidade do solo abaixo de 20%",
     lambda f: f["umidade_solo_pct"] < 20, "solo_critico"),
    ("R03", "Umidade do solo acima de 85%",
     lambda f: f["umidade_solo_pct"] > 85, "solo_encharcado"),
    ("R04", "Temperatura do ar >= 32 C",
     lambda f: f["temperatura_c"] >= 32, "calor_intenso"),
    ("R05", "Deficit de pressao de vapor >= 2,0 kPa",
     lambda f: f["vpd_kpa"] >= 2.0, "ar_seco"),
    ("R06", "Solo seco combinado com calor intenso ou ar seco",
     lambda f: f.get("solo_seco") and (f.get("calor_intenso") or f.get("ar_seco")), "estresse_hidrico"),
    ("R07", "Pluviometro registrou chuva nas ultimas 2 h",
     lambda f: f["chuva_ultimas_2h"] > 0, "chuva_recente"),
    ("R08", "API de clima preve chuva com probabilidade >= 60%",
     lambda f: f["risco_chuva_previsto_pct"] >= 60, "chuva_prevista"),
    ("R09", "Ar com UR >= 85% por 6 h seguidas ou mais nas ultimas 24 h",
     lambda f: f["max_horas_ur_alta_24h"] >= 6, "molhamento_prolongado"),
    ("R10", "Temperatura media das ultimas 24 h entre 15 e 28 C",
     lambda f: 15 <= f["temp_media_24h"] <= 28, "temperatura_favoravel_fungo"),
    ("R11", "Molhamento prolongado com temperatura favoravel",
     lambda f: f.get("molhamento_prolongado") and f.get("temperatura_favoravel_fungo"), "ambiente_favoravel_fungo"),
    ("R12", "Ha focos fungicos ativos nos diagnosticos da propriedade",
     lambda f: f["focos_fungicos_ativos"] > 0, "inoculo_presente"),
    ("R13", "Ambiente favoravel a fungo com inoculo presente",
     lambda f: f.get("ambiente_favoravel_fungo") and f.get("inoculo_presente"), "risco_fungico_alto"),
    ("R14", "Movimento detectado pelo PIR durante a noite",
     lambda f: f["movimento"] == 1 and f["periodo"] == "noite", "intrusao"),
    ("R15", "Leitura perdida ou rejeitada nas ultimas 2 h",
     lambda f: f["lacunas_2h"] + f["rejeitadas_2h"] > 0, "falha_sensor"),
]

# Cada acao: (id, nivel, condicao, mensagem, recomendacao, comando_atuador)
REGRAS_ACAO = [
    ("A01", "CRITICO",
     lambda f: f.get("solo_critico") and not (f.get("chuva_recente") or f.get("chuva_prevista")),
     "Solo em nivel critico de umidade",
     "Irrigar imediatamente (comando simulado gerado automaticamente).", "I"),
    ("A02", "ALTO",
     lambda f: f.get("estresse_hidrico") and not f.get("solo_critico")
     and not (f.get("chuva_recente") or f.get("chuva_prevista")),
     "Estresse hidrico: solo seco sob calor/ar seco",
     "Irrigar no proximo turno e priorizar o horario mais fresco.", "I"),
    ("A03", "ATENCAO",
     lambda f: f.get("solo_seco") and not f.get("estresse_hidrico") and not f.get("solo_critico")
     and not (f.get("chuva_recente") or f.get("chuva_prevista")),
     "Solo abaixo da faixa ideal",
     "Programar irrigacao para o proximo ciclo.", None),
    ("A04", "ATENCAO",
     lambda f: f.get("solo_seco") and (f.get("chuva_recente") or f.get("chuva_prevista")),
     "Solo seco, mas ha chuva recente/prevista",
     "Adiar irrigacao e reavaliar apos a chuva (economia de agua).", None),
    ("A05", "ATENCAO",
     lambda f: f.get("solo_encharcado"),
     "Solo encharcado",
     "Suspender irrigacao e verificar drenagem.", "D"),
    ("A06", "ALTO",
     lambda f: f.get("risco_fungico_alto"),
     "Alto risco de doenca fungica",
     "Inspecionar folhas em 24 h e aplicar fungicida preventivo se houver sintomas.", None),
    ("A07", "ATENCAO",
     lambda f: f.get("ambiente_favoravel_fungo") and not f.get("inoculo_presente"),
     "Clima favoravel a fungos",
     "Intensificar monitoramento visual do talhao.", None),
    ("A08", "ALTO",
     lambda f: f.get("intrusao"),
     "Movimento noturno no talhao (possivel animal/invasao)",
     "Verificar cameras/cerca e enviar equipe ao local.", None),
    ("A09", "ATENCAO",
     lambda f: f.get("falha_sensor"),
     "Falha de leitura no no de sensores",
     "Verificar conexao, alimentacao e sensor do no de campo.", None),
]


# Fatos que cada acao usa e de quais fatos cada conclusao intermediaria depende.
# Servem para montar a justificativa de cada alerta (so a cadeia de regras relevante).
FATOS_DA_ACAO = {
    "A01": ["solo_critico"], "A02": ["estresse_hidrico"], "A03": ["solo_seco"],
    "A04": ["solo_seco", "chuva_recente", "chuva_prevista"], "A05": ["solo_encharcado"],
    "A06": ["risco_fungico_alto"], "A07": ["ambiente_favoravel_fungo"],
    "A08": ["intrusao"], "A09": ["falha_sensor"],
}
DEPENDENCIAS = {
    "estresse_hidrico": ["solo_seco", "calor_intenso", "ar_seco"],
    "ambiente_favoravel_fungo": ["molhamento_prolongado", "temperatura_favoravel_fungo"],
    "risco_fungico_alto": ["ambiente_favoravel_fungo", "inoculo_presente"],
}


def justificar(id_acao, disparadas):
    pendentes, cadeia = list(FATOS_DA_ACAO[id_acao]), set()
    while pendentes:
        fato = pendentes.pop()
        if fato not in cadeia:
            cadeia.add(fato)
            pendentes += DEPENDENCIAS.get(fato, [])
    return [d["regra"] for d in disparadas if d["conclusao"] in cadeia]


def inferir(fatos):
    """Encadeamento progressivo: aplica regras ate nao haver fato novo."""
    disparadas = []
    houve_novo = True
    while houve_novo:
        houve_novo = False
        for id_regra, descricao, condicao, conclusao in REGRAS_INFERENCIA:
            if not fatos.get(conclusao) and condicao(fatos):
                fatos[conclusao] = True
                disparadas.append({"regra": id_regra, "conclusao": conclusao, "descricao": descricao})
                houve_novo = True

    acoes = []
    for id_acao, nivel, condicao, mensagem, recomendacao, comando in REGRAS_ACAO:
        if condicao(fatos):
            acoes.append({"acao": id_acao, "nivel": nivel, "mensagem": mensagem,
                          "recomendacao": recomendacao, "comando": comando,
                          "evidencias": justificar(id_acao, disparadas)})

    nivel = max((a["nivel"] for a in acoes), key=NIVEIS.index, default="NORMAL")
    return nivel, acoes, disparadas


# ============================================================ BASE DE FATOS
def carregar_leituras():
    with ARQ_PROCESSADOS.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    for l in linhas:
        l["data_hora"] = datetime.strptime(l["data_hora"], "%Y-%m-%d %H:%M:%S")
        for campo in ("temperatura_c", "vpd_kpa", "horas_ur_alta_consecutivas", "ponto_orvalho_c"):
            l[campo] = float(l[campo])
        for campo in ("umidade_ar_pct", "umidade_solo_pct", "luminosidade_pct", "movimento",
                      "chuva", "bomba", "lacuna"):
            l[campo] = int(l[campo])
    return linhas


def carregar_rejeitadas():
    rejeitadas = defaultdict(list)
    if ARQ_QUARENTENA.exists():
        with ARQ_QUARENTENA.open(encoding="utf-8", newline="") as arquivo:
            for q in csv.DictReader(arquivo):
                instante = datetime.strptime(q["conteudo_original"].split(",")[0], "%Y-%m-%d %H:%M:%S")
                rejeitadas[q["talhao"]].append(instante)
    return rejeitadas


def carregar_contexto_externo():
    clima = json.loads(ARQ_CLIMA.read_text(encoding="utf-8"))
    with ARQ_DIAGNOSTICOS.open(encoding="utf-8", newline="") as arquivo:
        diagnosticos = list(csv.DictReader(arquivo))
    focos = [d for d in diagnosticos if d["diagnostico"] == "Doente" and d["tipo"] in ANOMALIAS_FUNGICAS]
    return {
        "risco_chuva_previsto_pct": clima["previsao_proximas_24h"]["risco_chuva_pct"],
        "temp_max_prevista_c": clima["previsao_proximas_24h"]["temperatura_maxima_celsius"],
        "focos_fungicos_ativos": len(focos),
        "maior_area_afetada_pct": max((float(d["area_afetada"]) for d in focos), default=0.0),
    }


def montar_fatos(leitura, historico, rejeitadas, externo):
    agora = leitura["data_hora"]
    janela_2h = [h for h in historico if h["data_hora"] > agora - timedelta(hours=2)]
    janela_24h = [h for h in historico if h["data_hora"] > agora - timedelta(hours=24)]
    return {
        "temperatura_c": leitura["temperatura_c"],
        "umidade_ar_pct": leitura["umidade_ar_pct"],
        "umidade_solo_pct": leitura["umidade_solo_pct"],
        "vpd_kpa": leitura["vpd_kpa"],
        "movimento": leitura["movimento"],
        "periodo": leitura["periodo"],
        "chuva_ultimas_2h": sum(h["chuva"] for h in janela_2h),
        "lacunas_2h": sum(h["lacuna"] for h in janela_2h),
        "rejeitadas_2h": sum(1 for r in rejeitadas if agora - timedelta(hours=2) < r <= agora),
        "max_horas_ur_alta_24h": max(h["horas_ur_alta_consecutivas"] for h in janela_24h),
        "temp_media_24h": round(mean(h["temperatura_c"] for h in janela_24h), 1),
        **externo,
    }


# ================================================================ EXECUCAO
def executar():
    leituras = carregar_leituras()
    rejeitadas = carregar_rejeitadas()
    externo = carregar_contexto_externo()

    por_talhao = defaultdict(list)
    for l in leituras:
        por_talhao[l["talhao"]].append(l)

    linha_do_tempo, status_final, comandos = [], {}, []
    for talhao in sorted(por_talhao):
        historico, ativas = [], {}
        for leitura in sorted(por_talhao[talhao], key=lambda x: x["data_hora"]):
            historico.append(leitura)
            fatos = montar_fatos(leitura, historico, rejeitadas[talhao], externo)
            nivel, acoes, disparadas = inferir(fatos)

            # Gera alerta somente quando a acao comeca (evita repetir a cada leitura)
            ids_agora = {a["acao"] for a in acoes}
            for a in acoes:
                if a["acao"] not in ativas:
                    evento = {
                        "data_hora": leitura["data_hora"].strftime("%Y-%m-%d %H:%M"),
                        "talhao": talhao, **a,
                    }
                    linha_do_tempo.append(evento)
                    if a["comando"]:
                        comandos.append(
                            f"{evento['data_hora']}  {NO_POR_TALHAO[talhao]}  '{a['comando']}'  ({a['mensagem']})"
                        )
            for id_encerrada in set(ativas) - ids_agora:
                ativas.pop(id_encerrada)
            for a in acoes:
                ativas[a["acao"]] = a

        ultima = historico[-1]
        status_final[talhao] = {
            "no_sensor": NO_POR_TALHAO[talhao],
            "ultima_leitura": ultima["data_hora"].strftime("%Y-%m-%d %H:%M"),
            "nivel": nivel,
            "acoes": acoes,
            "regras_disparadas": disparadas,
            "fatos": {k: v for k, v in fatos.items() if not isinstance(v, bool)},
        }

    linha_do_tempo.sort(key=lambda e: (e["data_hora"], e["talhao"]))
    return leituras, externo, status_final, linha_do_tempo, comandos


# ================================================================== SAIDAS
def gravar_relatorio(status_final, linha_do_tempo, externo, gerado_em):
    linhas = [
        "RELATORIO DE DECISAO AUTOMATIZADA - AGROSMART",
        "",
        f"Gerado em: {gerado_em}",
        f"Contexto externo: chuva prevista {externo['risco_chuva_previsto_pct']}% | "
        f"max prevista {externo['temp_max_prevista_c']} C | "
        f"focos fungicos ativos {externo['focos_fungicos_ativos']} "
        f"(maior area afetada {externo['maior_area_afetada_pct']}%)",
        "",
        "========================================",
        "SITUACAO ATUAL POR TALHAO",
        "========================================",
    ]
    for talhao, s in status_final.items():
        f = s["fatos"]
        linhas += [
            "",
            f"Talhao {talhao} ({s['no_sensor']})  |  ultima leitura {s['ultima_leitura']}",
            f"Classificacao de risco: {s['nivel']}",
            f"Leitura: {f['temperatura_c']} C | UR {f['umidade_ar_pct']}% | solo {f['umidade_solo_pct']}% | "
            f"VPD {f['vpd_kpa']} kPa | {f['max_horas_ur_alta_24h']} h de UR>=85% (24 h)",
        ]
        if s["acoes"]:
            for a in s["acoes"]:
                cmd = f"  [comando '{a['comando']}' -> {s['no_sensor']}]" if a["comando"] else ""
                linhas.append(f"  - [{a['nivel']}] {a['mensagem']}: {a['recomendacao']}{cmd}")
                descricoes = {r["regra"]: r["descricao"] for r in s["regras_disparadas"]}
                for regra in a["evidencias"]:
                    linhas.append(f"      porque {regra}: {descricoes[regra]}")
        else:
            linhas.append("  - Nenhuma acao necessaria: manter monitoramento.")
        if s["regras_disparadas"]:
            linhas.append("  Fatos inferidos: " + ", ".join(
                f"{r['conclusao']} ({r['regra']})" for r in s["regras_disparadas"]))

    linhas += ["", "========================================",
               "LINHA DO TEMPO DE ALERTAS (24 h)",
               "========================================"]
    for e in linha_do_tempo:
        linhas.append(f"{e['data_hora']}  {e['talhao']}  {e['nivel']:<8} {e['mensagem']}")

    (PASTA_SAIDA / "relatorio_alertas.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def gravar_dashboard(leituras, status_final, linha_do_tempo, externo, gerado_em):
    series = defaultdict(list)
    for l in sorted(leituras, key=lambda x: x["data_hora"]):
        series[l["talhao"]].append({
            "t": l["data_hora"].strftime("%H:%M"),
            "m": l["data_hora"].hour * 60 + l["data_hora"].minute,
            "temp": l["temperatura_c"], "ur": l["umidade_ar_pct"], "solo": l["umidade_solo_pct"],
        })
    dados = {
        "gerado_em": gerado_em,
        "externo": externo,
        "series": series,
        "status": {t: {"nivel": s["nivel"], "no": s["no_sensor"], "ultima": s["ultima_leitura"],
                       "fatos": s["fatos"], "acoes": s["acoes"]} for t, s in status_final.items()},
        "alertas": linha_do_tempo,
    }
    html = ARQ_TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"))
    (PASTA_SAIDA / "dashboard.html").write_text(html, encoding="utf-8")


def main():
    print("======= MOTOR DE DECISAO AUTOMATIZADA (AGROSMART) =======")
    leituras, externo, status_final, linha_do_tempo, comandos = executar()
    gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")

    PASTA_SAIDA.mkdir(exist_ok=True)
    (PASTA_SAIDA / "alertas.json").write_text(json.dumps(
        {"gerado_em": gerado_em, "contexto_externo": externo,
         "status_por_talhao": status_final, "linha_do_tempo": linha_do_tempo},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (PASTA_SAIDA / "comandos_atuadores.txt").write_text(
        "FILA DE COMANDOS SIMULADOS PARA OS NOS DE CAMPO (sem envio Serial)\n"
        "'I' = liga bomba | 'D' = desliga bomba\n\n" + "\n".join(comandos) + "\n", encoding="utf-8")
    gravar_relatorio(status_final, linha_do_tempo, externo, gerado_em)
    gravar_dashboard(leituras, status_final, linha_do_tempo, externo, gerado_em)

    print(f"Leituras avaliadas: {len(leituras)} | alertas gerados: {len(linha_do_tempo)}\n")
    for e in linha_do_tempo:
        print(f"[{e['data_hora']}] {e['talhao']} {e['nivel']:<8} {e['mensagem']}")
    print("\nSituacao atual:")
    for talhao, s in status_final.items():
        print(f"   {talhao}: {s['nivel']:<8} " + (" | ".join(a["mensagem"] for a in s["acoes"]) or "sem alertas"))
    print(f"\n[SUCESSO] Saidas gravadas em {PASTA_SAIDA.name}/ (abra dashboard.html no navegador)")


if __name__ == "__main__":
    main()
