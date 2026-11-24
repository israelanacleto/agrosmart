"""Prepara a reprodução visual do CSV bruto da simulação Python, sem dependências."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent


def main():
    linhas = (BASE / "dados_sensores_brutos.csv").read_text(encoding="utf-8").splitlines()
    dados = {"cabecalho": linhas[0], "linhas": linhas[1:]}
    destino = BASE / "dados_simulacao.js"
    destino.write_text("const SIMULACAO = " + json.dumps(dados, ensure_ascii=True) + ";\n", encoding="utf-8")
    print(f"[OK] Reprodução visual preparada: {len(linhas) - 1} pacotes. Abra simulacao_sensores.html")


if __name__ == "__main__":
    main()
