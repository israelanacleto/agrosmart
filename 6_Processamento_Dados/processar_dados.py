# -*- coding: utf-8 -*-
"""
Processamento e preparacao dos dados de sensores do AgroSmart.

Fluxo (camadas do Data Lake definidas na entrega 1):
  RAW      5_Coleta_Dados_IoT/dados_sensores_brutos.csv  (como chegou do gateway)
  TRUSTED  validacao de schema/tipos/faixas, quarentena e deduplicacao
  REFINED  padronizacao + variaveis derivadas + resumo por talhao

Saidas (pasta saida/):
  dados_processados.csv  leituras validas e enriquecidas (entrada do motor de decisao)
  quarentena.csv         leituras rejeitadas e o motivo
  resumo_por_talhao.csv  indicadores agregados por talhao

Usa apenas a biblioteca padrao do Python (mesma imagem Docker do projeto).
Uso:  python processar_dados.py
"""
import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_BRUTO = BASE_DIR.parent / "5_Coleta_Dados_IoT" / "dados_sensores_brutos.csv"
PASTA_SAIDA = BASE_DIR / "saida"

COLUNAS_BRUTAS = [
    "recebido_em", "no_sensor", "talhao", "millis", "temperatura_c", "umidade_ar_pct",
    "umidade_solo_pct", "luminosidade_pct", "movimento", "chuva", "bomba",
]
FAIXAS = {
    "temperatura_c": (-10.0, 60.0),     # fora disso = sensor com defeito/desconectado
    "umidade_ar_pct": (0, 100),
    "umidade_solo_pct": (0, 100),
    "luminosidade_pct": (0, 100),
}
EVENTOS = ("movimento", "chuva", "bomba")
UR_ALTA = 85            # % - limiar de molhamento foliar usado em modelos de doenca fungica
LUZ_DIA = 10            # % - acima disso consideramos periodo diurno
INTERVALO_ESPERADO_MIN = 30


# ---------------------------------------------------------------- leitura (RAW)
def ler_brutos():
    with ARQUIVO_BRUTO.open("r", encoding="utf-8", newline="") as arquivo:
        leitor = csv.reader(arquivo)
        cabecalho = next(leitor)
        if cabecalho != COLUNAS_BRUTAS:
            raise ValueError(f"Schema inesperado no arquivo bruto: {cabecalho}")
        for numero_linha, campos in enumerate(leitor, start=2):
            yield numero_linha, campos


# ------------------------------------------------------------- validacao (TRUSTED)
def validar(campos):
    """Converte tipos e checa faixas. Retorna (registro, None) ou (None, motivo)."""
    if len(campos) != len(COLUNAS_BRUTAS):
        return None, f"linha incompleta ({len(campos)} de {len(COLUNAS_BRUTAS)} campos)"

    bruto = dict(zip(COLUNAS_BRUTAS, (c.strip() for c in campos)))
    vazios = [nome for nome, valor in bruto.items() if valor == ""]
    if vazios:
        return None, f"campo vazio: {', '.join(vazios)}"

    try:
        registro = {
            "data_hora": datetime.strptime(bruto["recebido_em"], "%Y-%m-%d %H:%M:%S"),
            "no_sensor": bruto["no_sensor"],
            "talhao": bruto["talhao"],
            "millis": int(bruto["millis"]),
            "temperatura_c": float(bruto["temperatura_c"]),
            "umidade_ar_pct": int(bruto["umidade_ar_pct"]),
            "umidade_solo_pct": int(bruto["umidade_solo_pct"]),
            "luminosidade_pct": int(bruto["luminosidade_pct"]),
            **{evento: int(bruto[evento]) for evento in EVENTOS},
        }
    except ValueError as erro:
        return None, f"tipo invalido ({erro})"

    for coluna, (minimo, maximo) in FAIXAS.items():
        if not minimo <= registro[coluna] <= maximo:
            return None, f"{coluna}={registro[coluna]} fora da faixa [{minimo}, {maximo}]"
    for evento in EVENTOS:
        if registro[evento] not in (0, 1):
            return None, f"{evento}={registro[evento]} deveria ser 0 ou 1"

    return registro, None


# --------------------------------------------------------- enriquecimento (REFINED)
def ponto_de_orvalho(temp, ur):
    """Formula de Magnus-Tetens."""
    a, b = 17.27, 237.7
    gama = (a * temp) / (b + temp) + math.log(max(ur, 1) / 100)
    return b * gama / (a - gama)


def deficit_pressao_vapor(temp, ur):
    """VPD em kPa: quanto o ar 'puxa' agua da planta. > 1,6 kPa indica estresse."""
    pressao_saturacao = 0.6108 * math.exp(17.27 * temp / (temp + 237.3))
    return pressao_saturacao * (1 - ur / 100)


def enriquecer(registros):
    """Calcula variaveis derivadas por talhao, em ordem cronologica."""
    por_talhao = defaultdict(list)
    for r in registros:
        por_talhao[r["talhao"]].append(r)

    saida = []
    for talhao in sorted(por_talhao):
        anterior = None
        horas_ur_alta = 0.0
        historico_solo = []
        for r in sorted(por_talhao[talhao], key=lambda x: x["data_hora"]):
            intervalo = (
                (r["data_hora"] - anterior["data_hora"]).total_seconds() / 60 if anterior else 0.0
            )
            if r["umidade_ar_pct"] >= UR_ALTA:
                horas_ur_alta += intervalo / 60 if anterior and anterior["umidade_ar_pct"] >= UR_ALTA else 0.0
            else:
                horas_ur_alta = 0.0

            historico_solo.append(r["umidade_solo_pct"])
            r.update(
                {
                    "data": r["data_hora"].strftime("%Y-%m-%d"),
                    "hora": r["data_hora"].strftime("%H:%M"),
                    "periodo": "dia" if r["luminosidade_pct"] >= LUZ_DIA else "noite",
                    "ponto_orvalho_c": round(ponto_de_orvalho(r["temperatura_c"], r["umidade_ar_pct"]), 1),
                    "vpd_kpa": round(deficit_pressao_vapor(r["temperatura_c"], r["umidade_ar_pct"]), 2),
                    "solo_media_movel_3": round(mean(historico_solo[-3:]), 1),
                    "delta_solo": r["umidade_solo_pct"] - anterior["umidade_solo_pct"] if anterior else 0,
                    "horas_ur_alta_consecutivas": round(horas_ur_alta, 1),
                    "intervalo_min": round(intervalo),
                    "lacuna": int(intervalo > INTERVALO_ESPERADO_MIN * 1.5),
                }
            )
            saida.append(r)
            anterior = r
    return saida


def resumir(registros, quarentena):
    rejeitadas = defaultdict(int)
    for q in quarentena:
        rejeitadas[q["talhao"]] += 1

    por_talhao = defaultdict(list)
    for r in registros:
        por_talhao[r["talhao"]].append(r)

    resumo = []
    for talhao in sorted(por_talhao):
        linhas = por_talhao[talhao]
        temps = [r["temperatura_c"] for r in linhas]
        resumo.append(
            {
                "talhao": talhao,
                "no_sensor": linhas[0]["no_sensor"],
                "leituras_validas": len(linhas),
                "leituras_quarentena": rejeitadas[talhao],
                "lacunas": sum(r["lacuna"] for r in linhas),
                "temp_min_c": min(temps),
                "temp_media_c": round(mean(temps), 1),
                "temp_max_c": max(temps),
                "ur_media_pct": round(mean(r["umidade_ar_pct"] for r in linhas), 1),
                "max_horas_ur_alta": max(r["horas_ur_alta_consecutivas"] for r in linhas),
                "vpd_max_kpa": max(r["vpd_kpa"] for r in linhas),
                "solo_inicial_pct": linhas[0]["umidade_solo_pct"],
                "solo_final_pct": linhas[-1]["umidade_solo_pct"],
                "solo_min_pct": min(r["umidade_solo_pct"] for r in linhas),
                "eventos_chuva": sum(r["chuva"] for r in linhas),
                "movimentos_noite": sum(r["movimento"] for r in linhas if r["periodo"] == "noite"),
                "movimentos_dia": sum(r["movimento"] for r in linhas if r["periodo"] == "dia"),
            }
        )
    return resumo


# ------------------------------------------------------------------- gravacao
def gravar_csv(caminho, linhas, colunas):
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow(
                {k: (v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, datetime) else v) for k, v in linha.items()}
            )


def main():
    print("======= PROCESSAMENTO DE DADOS DE SENSORES (AGROSMART) =======")
    validos, quarentena, vistos = [], [], set()
    total = duplicadas = 0

    for numero_linha, campos in ler_brutos():
        total += 1
        registro, motivo = validar(campos)
        if motivo:
            quarentena.append(
                {
                    "linha_arquivo": numero_linha,
                    "talhao": campos[2] if len(campos) > 2 else "?",
                    "motivo": motivo,
                    "conteudo_original": ",".join(campos),
                }
            )
            continue

        chave = (registro["no_sensor"], registro["millis"])
        if chave in vistos:
            duplicadas += 1
            continue
        vistos.add(chave)
        validos.append(registro)

    processados = enriquecer(validos)
    resumo = resumir(processados, quarentena)

    PASTA_SAIDA.mkdir(exist_ok=True)
    gravar_csv(
        PASTA_SAIDA / "dados_processados.csv",
        processados,
        ["data_hora", "data", "hora", "periodo", "talhao", "no_sensor", "temperatura_c",
         "umidade_ar_pct", "umidade_solo_pct", "luminosidade_pct", "movimento", "chuva", "bomba",
         "ponto_orvalho_c", "vpd_kpa", "solo_media_movel_3", "delta_solo",
         "horas_ur_alta_consecutivas", "intervalo_min", "lacuna"],
    )
    gravar_csv(PASTA_SAIDA / "quarentena.csv", quarentena,
               ["linha_arquivo", "talhao", "motivo", "conteudo_original"])
    gravar_csv(PASTA_SAIDA / "resumo_por_talhao.csv", resumo, list(resumo[0].keys()))

    print(f"Linhas lidas (raw) .............. {total}")
    print(f"Enviadas para quarentena ........ {len(quarentena)}")
    for q in quarentena:
        print(f"   - linha {q['linha_arquivo']} ({q['talhao']}): {q['motivo']}")
    print(f"Duplicadas removidas ............ {duplicadas}")
    print(f"Leituras validas (refined) ...... {len(processados)}")
    lacunas = [r for r in processados if r["lacuna"]]
    for r in lacunas:
        print(f"   - lacuna em {r['talhao']}: {r['intervalo_min']} min sem leitura antes de {r['hora']}")
    print("\nResumo por talhao:")
    for r in resumo:
        print(
            f"   {r['talhao']}: temp {r['temp_min_c']}-{r['temp_max_c']} C | "
            f"solo {r['solo_inicial_pct']}% -> {r['solo_final_pct']}% | "
            f"max {r['max_horas_ur_alta']} h com UR>={UR_ALTA}% | "
            f"chuva {r['eventos_chuva']} | movimento noite {r['movimentos_noite']}"
        )
    print(f"\n[SUCESSO] Arquivos gerados em {PASTA_SAIDA.name}/")


if __name__ == "__main__":
    main()
