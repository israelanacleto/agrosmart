# -*- coding: utf-8 -*-
"""
NOVO (Fase 7) - Healthcheck do container (HEALTHCHECK do Dockerfile).

Saudavel (exit 0) quando o ultimo ciclo registrado:
  - existe em saida/indicadores_ultimo_ciclo.json;
  - nao terminou em FALHA;
  - terminou ha menos de max(3 x intervalo, 300) segundos (o loop esta vivo).
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent / "saida" / "indicadores_ultimo_ciclo.json"


def verificar():
    if not ARQUIVO.exists():
        return False, "nenhum ciclo concluido ainda"
    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    if dados.get("status") == "FALHA":
        return False, f"ultimo ciclo em FALHA ({dados.get('execucao_id')})"
    intervalo = int(os.environ.get("AGROSMART_INTERVALO_S", dados.get("intervalo_s", 30)))
    idade = (datetime.now() - datetime.fromisoformat(dados["fim"])).total_seconds()
    limite = max(3 * intervalo, 300)
    if idade > limite:
        return False, f"ultimo ciclo ha {int(idade)} s (limite {limite} s)"
    return True, f"ok: {dados['status']} ha {int(idade)} s"


if __name__ == "__main__":
    ok, motivo = verificar()
    print(motivo)
    sys.exit(0 if ok else 1)
