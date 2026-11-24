# -*- coding: utf-8 -*-
"""Testes unitarios da camada trusted/refined (6_Processamento_Dados/processar_dados.py)."""
import pytest
from conftest import importar

proc = importar("6_Processamento_Dados/processar_dados.py", "processar_dados")

VALIDA = ["2026-05-17 10:30:01", "NODE-02", "T2", "151920000", "30.1", "41", "40", "83", "0", "0", "0"]


def test_schema_bruto_mantido():
    assert proc.COLUNAS_BRUTAS == [
        "recebido_em", "no_sensor", "talhao", "millis", "temperatura_c", "umidade_ar_pct",
        "umidade_solo_pct", "luminosidade_pct", "movimento", "chuva", "bomba",
    ]


def test_linha_valida_converte_tipos():
    registro, motivo = proc.validar(VALIDA)
    assert motivo is None
    assert registro["temperatura_c"] == 30.1
    assert registro["umidade_solo_pct"] == 40
    assert registro["data_hora"].hour == 10


@pytest.mark.parametrize("alteracao, trecho_motivo", [
    (lambda c: c[:6], "linha incompleta"),
    (lambda c: c[:6] + [""] + c[7:], "campo vazio: umidade_solo_pct"),
    (lambda c: c[:4] + ["-50.0"] + c[5:], "fora da faixa"),
    (lambda c: c[:5] + ["101"] + c[6:], "umidade_ar_pct=101"),
    (lambda c: c[:8] + ["2"] + c[9:], "deveria ser 0 ou 1"),
    (lambda c: ["17/05/2026"] + c[1:], "tipo invalido"),
])
def test_linhas_invalidas_vao_para_quarentena(alteracao, trecho_motivo):
    registro, motivo = proc.validar(alteracao(list(VALIDA)))
    assert registro is None
    assert trecho_motivo in motivo


def test_ponto_de_orvalho_magnus_tetens():
    # 20 C e 50% UR -> ponto de orvalho ~9,3 C (valor de referencia da formula)
    assert proc.ponto_de_orvalho(20, 50) == pytest.approx(9.26, abs=0.05)
    # ar saturado: ponto de orvalho = temperatura
    assert proc.ponto_de_orvalho(25, 100) == pytest.approx(25, abs=0.01)


def test_vpd():
    assert proc.deficit_pressao_vapor(25, 100) == pytest.approx(0.0, abs=1e-9)
    assert proc.deficit_pressao_vapor(30, 40) == pytest.approx(2.55, abs=0.02)
