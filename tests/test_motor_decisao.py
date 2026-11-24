# -*- coding: utf-8 -*-
"""Testes das regras do motor de inferencia (7_Automacao_Inteligente/motor_decisao.py)."""
from conftest import importar

motor = importar("7_Automacao_Inteligente/motor_decisao.py", "motor_decisao")


def fatos(**sobrescrever):
    base = {
        "temperatura_c": 24.0, "umidade_ar_pct": 60, "umidade_solo_pct": 55, "vpd_kpa": 1.0,
        "movimento": 0, "periodo": "dia", "chuva_ultimas_2h": 0, "lacunas_2h": 0, "rejeitadas_2h": 0,
        "max_horas_ur_alta_24h": 0.0, "temp_media_24h": 30.0, "risco_chuva_previsto_pct": 15,
        "temp_max_prevista_c": 31, "focos_fungicos_ativos": 0, "maior_area_afetada_pct": 0.0,
    }
    base.update(sobrescrever)
    return base


def ids(acoes):
    return {a["acao"] for a in acoes}


def test_condicao_normal_sem_acoes():
    nivel, acoes, _ = motor.inferir(fatos())
    assert nivel == "NORMAL" and acoes == []


def test_solo_critico_sem_chuva_liga_bomba():
    nivel, acoes, _ = motor.inferir(fatos(umidade_solo_pct=15))
    assert nivel == "CRITICO"
    a01 = next(a for a in acoes if a["acao"] == "A01")
    assert a01["comando"] == "I" and "R02" in a01["evidencias"]


def test_chuva_prevista_adia_irrigacao():
    nivel, acoes, _ = motor.inferir(fatos(umidade_solo_pct=15, risco_chuva_previsto_pct=70))
    assert "A01" not in ids(acoes) and "A04" in ids(acoes)
    assert nivel == "ATENCAO"


def test_estresse_hidrico_por_encadeamento():
    nivel, acoes, disparadas = motor.inferir(fatos(umidade_solo_pct=25, temperatura_c=33))
    assert {"R01", "R04", "R06"} <= {d["regra"] for d in disparadas}
    assert "A02" in ids(acoes) and nivel == "ALTO"


def test_risco_fungico_exige_inoculo():
    clima_fungo = dict(max_horas_ur_alta_24h=9.5, temp_media_24h=20.0)
    _, sem_inoculo, _ = motor.inferir(fatos(**clima_fungo))
    _, com_inoculo, _ = motor.inferir(fatos(**clima_fungo, focos_fungicos_ativos=11))
    assert "A07" in ids(sem_inoculo) and "A06" not in ids(sem_inoculo)
    assert "A06" in ids(com_inoculo)


def test_movimento_noturno_e_falha_de_sensor():
    _, acoes, _ = motor.inferir(fatos(movimento=1, periodo="noite", rejeitadas_2h=1))
    assert {"A08", "A09"} <= ids(acoes)
