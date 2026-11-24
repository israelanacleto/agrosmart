# -*- coding: utf-8 -*-
import csv
import time
import unicodedata
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_DADOS = BASE_DIR / "dados_agricolas.csv"
ARQUIVO_RELATORIO = BASE_DIR / "relatorio_intervencao.txt"


def normalizar_texto(valor):
    texto = unicodedata.normalize("NFKD", valor or "")
    texto_sem_acentos = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return texto_sem_acentos.strip().lower()


def definir_acao(diagnostico, tipo, area_afetada):
    diagnostico_normalizado = normalizar_texto(diagnostico)

    if diagnostico_normalizado == "saudavel" or tipo == "Nenhuma":
        return "Acao Normal: manter rotina de monitoramento e registrar status normal."
    elif area_afetada > 25:
        return "Alerta Critico: intervencao quimica imediata recomendada."
    elif tipo == "Ferrugem" or tipo == "Antracnose":
        return "Alerta Moderado: agendar inspecao preventiva no campo."
    else:
        return "Aviso de Monitoramento: aplicar controle biologico e manejo preventivo integrado."


def gerar_relatorio(resultados):
    cabecalho = (
        "RELATORIO DE ACAO AUTOMATICA AGRICOLA (STREAM)\n\n"
        f"Data de processamento: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"Total de amostras processadas: {len(resultados)}\n"
    )
    corpo = ""

    for item in resultados:
        corpo += (
            "\n----------------------------------------\n"
            f"Amostra: {item['id_amostra']}  |  Leitura: {item['data_leitura']}\n"
            f"Diagnostico: {item['diagnostico']}\n"
            f"Tipo de anomalia: {item['tipo']}\n"
            f"Area afetada: {item['area_afetada']}%\n"
            "Acao executada pelo sistema:\n"
            f"{item['acao']}\n"
        )

    with ARQUIVO_RELATORIO.open("w", encoding="utf-8") as arquivo:
        arquivo.write(cabecalho + corpo)


def main():
    print("======= INICIANDO INGESTAO DE DADOS CONTINUOS (AGROSMART) =======")
    print("Aguardando novas leituras dos sensores em tempo real...\n")
    time.sleep(2)

    resultados = []

    try:
        with ARQUIVO_DADOS.open("r", encoding="utf-8", newline="") as arquivo:
            dados = csv.DictReader(arquivo)

            for linha in dados:
                id_amostra = linha.get("id_amostra", "-")
                data_leitura = linha.get("data_leitura", "-")
                diagnostico = linha["diagnostico"]
                tipo = linha["tipo"]
                area_afetada = float(linha["area_afetada"])

                timestamp_atual = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp_atual}] Nova amostra RECEBIDA via Stream: {id_amostra}")

                acao = definir_acao(diagnostico, tipo, area_afetada)

                print(f"   -> Diagnostico: {diagnostico} ({tipo}) - Area Afetada: {area_afetada}%")
                print(f"   -> [ACAO EXECUTADA]: {acao}")
                print("------------------------------------------------------------")

                resultados.append(
                    {
                        "id_amostra": id_amostra,
                        "data_leitura": data_leitura,
                        "diagnostico": diagnostico,
                        "tipo": tipo,
                        "area_afetada": area_afetada,
                        "acao": acao,
                    }
                )
                time.sleep(3)

        gerar_relatorio(resultados)
        print("\n[SUCESSO] Stream finalizado. Arquivo 'relatorio_intervencao.txt' gerado.")
    except FileNotFoundError:
        print("Erro: O arquivo 'dados_agricolas.csv' nao foi encontrado nesta pasta!")


if __name__ == "__main__":
    main()
