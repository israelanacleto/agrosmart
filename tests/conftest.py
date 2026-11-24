# -*- coding: utf-8 -*-
"""Utilitarios dos testes: importar os scripts das pastas numeradas e copiar o projeto."""
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PASTAS_PIPELINE = [
    "2_Ingestao_Administracao_Manutencao",
    "5_Coleta_Dados_IoT",
    "6_Processamento_Dados",
    "7_Automacao_Inteligente",
    "8_Execucao_Monitorada",
    "9_Process_Mining",
    "FIAP - Agrosmart Docker",
]
IGNORAR = shutil.ignore_patterns("saida", "__pycache__", "*.png", "*.jpg", "*.mp4")


def importar(caminho_relativo, nome):
    caminho = RAIZ / caminho_relativo
    sys.path.insert(0, str(caminho.parent))
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def projeto(tmp_path):
    """Copia isolada do projeto (sem saidas antigas) para rodar o pipeline sem sujar o repo."""
    destino = tmp_path / "agrosmart"
    for pasta in PASTAS_PIPELINE:
        shutil.copytree(RAIZ / pasta, destino / pasta, ignore=IGNORAR)
    return destino
