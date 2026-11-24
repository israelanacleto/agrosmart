# -*- coding: utf-8 -*-
"""
Simula 24 horas de leituras de tres nos de sensores AgroSmart (um por
talhao), no mesmo formato que o sketch agrosmart_no_sensor.ino envia pela
Serial, acrescido do carimbo de data/hora colocado pelo gateway de campo.

Por que simular: no TinkerCad a simulacao roda poucos minutos e o
Arduino nao tem relogio; para ter um dia inteiro de dados (ciclo de
temperatura, luz e umidade) o comportamento fisico de cada talhao e
reproduzido aqui com as mesmas faixas e conversoes do circuito.

Cenarios:
  T1 (NODE-01) - talhao irrigado, condicoes normais
  T2 (NODE-02) - talhao de sequeiro em dia quente: solo secando
  T3 (NODE-03) - baixada umida: ar saturado por muitas horas (risco de fungo)

Tambem sao injetadas falhas tipicas de campo (linha duplicada, linha
truncada, sensor desconectado, campo vazio e pacote perdido) para que a
etapa de processamento tenha o que validar.

Uso:  python gerar_dados_simulados.py
Saida: dados_sensores_brutos.csv (camada raw)
"""
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_SAIDA = BASE_DIR / "dados_sensores_brutos.csv"

INICIO = datetime(2026, 5, 17, 0, 0)
PASSO = timedelta(minutes=30)
LEITURAS = 48  # 24 h

CABECALHO = (
    "recebido_em,no_sensor,talhao,millis,temperatura_c,umidade_ar_pct,"
    "umidade_solo_pct,luminosidade_pct,movimento,chuva,bomba"
)

NOS = [
    {"no": "NODE-01", "talhao": "T1", "t_min": 16.0, "t_max": 30.0, "ur_min": 45, "ur_max": 82,
     "solo": 64.0, "perda_base": 0.06, "perda_calor": 0.03, "luz_max": 95, "boot_h": 20.2},
    {"no": "NODE-02", "talhao": "T2", "t_min": 21.0, "t_max": 36.0, "ur_min": 30, "ur_max": 62,
     "solo": 44.0, "perda_base": 0.2, "perda_calor": 0.055, "luz_max": 98, "boot_h": 31.7},
    {"no": "NODE-03", "talhao": "T3", "t_min": 15.0, "t_max": 25.0, "ur_min": 68, "ur_max": 97,
     "solo": 76.0, "perda_base": 0.05, "perda_calor": 0.02, "luz_max": 80, "boot_h": 9.4},
]

# Eventos de campo
CHUVA = {"03:00", "03:30"}                                 # pancada de chuva na madrugada
MOVIMENTO = {("NODE-03", "02:30"), ("NODE-03", "03:00"),   # animal na baixada a noite
             ("NODE-01", "10:00")}                         # equipe de campo (dia)


def temperatura(hora, t_min, t_max):
    """Ciclo diario: minima as 05h, maxima as 14h."""
    if 5 <= hora <= 14:
        return t_min + (t_max - t_min) * (1 - math.cos(math.pi * (hora - 5) / 9)) / 2
    h = hora - 14 if hora > 14 else hora + 10
    return t_max - (t_max - t_min) * (1 - math.cos(math.pi * h / 15)) / 2


def luminosidade(hora, luz_max):
    if hora < 6 or hora > 18:
        return 0.0
    return luz_max * math.sin(math.pi * (hora - 6) / 12)


def simular():
    random.seed(42)
    linhas = []

    for no in NOS:
        solo = no["solo"]
        for i in range(LEITURAS):
            instante = INICIO + i * PASSO
            hora = instante.hour + instante.minute / 60
            hhmm = instante.strftime("%H:%M")

            t_real = temperatura(hora, no["t_min"], no["t_max"])
            frac = (t_real - no["t_min"]) / (no["t_max"] - no["t_min"])
            ur_real = no["ur_max"] - (no["ur_max"] - no["ur_min"]) * frac

            choveu = hhmm in CHUVA
            if choveu:
                solo += 2.5
                ur_real = min(99, ur_real + 6)
            else:
                solo -= no["perda_base"] + no["perda_calor"] * max(0.0, t_real - 20)

            temp = round(t_real + random.gauss(0, 0.3), 1)
            ur = int(round(min(100, max(0, ur_real + random.gauss(0, 1.5)))))
            umid_solo = int(round(min(100, max(0, solo + random.gauss(0, 0.5)))))
            luz_base = luminosidade(hora, no["luz_max"])
            luz = int(round(min(100, max(0, luz_base + random.gauss(0, 3))))) if luz_base else 0
            mov = 1 if (no["no"], hhmm) in MOVIMENTO else 0

            millis = int((no["boot_h"] * 3600 + i * 1800 + random.randint(0, 4)) * 1000)
            recebido = instante + timedelta(seconds=random.randint(1, 5))
            linhas.append([
                recebido.strftime("%Y-%m-%d %H:%M:%S"), no["no"], no["talhao"], millis,
                f"{temp:.1f}", ur, umid_solo, luz, mov, int(choveu), 0,
            ])

    linhas.sort(key=lambda l: (l[0], l[1]))
    texto = [",".join(str(c) for c in l) for l in linhas]
    return injetar_falhas(texto)


def injetar_falhas(texto):
    def indice(no, hhmm):
        return next(i for i, l in enumerate(texto) if f" {hhmm}:" in l and f",{no}," in l)

    # TMP36 desconectado: analogRead = 0 -> (0 - 0,5) * 100 = -50,0 C
    i = indice("NODE-02", "10:30")
    c = texto[i].split(",")
    c[4] = "-50.0"
    texto[i] = ",".join(c)

    # Campo de umidade do solo perdido na transmissao
    i = indice("NODE-03", "12:00")
    c = texto[i].split(",")
    c[6] = ""
    texto[i] = ",".join(c)

    # Linha truncada (queda de comunicacao no meio do envio)
    i = indice("NODE-01", "15:00")
    texto[i] = ",".join(texto[i].split(",")[:6])

    # Reenvio do gateway: mesma leitura gravada duas vezes
    i = indice("NODE-01", "06:00")
    texto.insert(i + 1, texto[i])

    # Pacote perdido: leitura das 20:00 do NODE-02 nunca chegou
    del texto[indice("NODE-02", "20:00")]

    return texto


def main():
    linhas = simular()
    ARQUIVO_SAIDA.write_text(CABECALHO + "\n" + "\n".join(linhas) + "\n", encoding="utf-8")
    print(f"[OK] {len(linhas)} linhas gravadas em {ARQUIVO_SAIDA.name}")


if __name__ == "__main__":
    main()
