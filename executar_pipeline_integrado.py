# -*- coding: utf-8 -*-
"""
Executa a solucao integrada do AgroSmart de ponta a ponta:

  1. Coleta ........ 5_Coleta_Dados_IoT/gerar_dados_simulados.py   (opcional: --gerar-dados)
  2. Processamento . 6_Processamento_Dados/processar_dados.py
  3. Automacao ..... 7_Automacao_Inteligente/motor_decisao.py
  4. Visualizacao .. 7_Automacao_Inteligente/saida/dashboard.html

Por padrao usa o dados_sensores_brutos.csv que ja esta na pasta 5 (que
pode ser substituido por um log real exportado do gateway). Passe
--gerar-dados para recriar a serie simulada de 24 h antes de processar.

Uso:  python executar_pipeline_integrado.py [--gerar-dados]
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ETAPAS = [
    RAIZ / "5_Coleta_Dados_IoT" / "gerar_visualizacao_simulacao.py",
    RAIZ / "6_Processamento_Dados" / "processar_dados.py",
    RAIZ / "7_Automacao_Inteligente" / "motor_decisao.py",
]

if "--gerar-dados" in sys.argv:
    ETAPAS.insert(0, RAIZ / "5_Coleta_Dados_IoT" / "gerar_dados_simulados.py")

for script in ETAPAS:
    print(f"\n>>> {script.parent.name}/{script.name}\n", flush=True)
    resultado = subprocess.run([sys.executable, str(script)], cwd=script.parent)
    if resultado.returncode != 0:
        sys.exit(f"[ERRO] A etapa {script.name} falhou (codigo {resultado.returncode}).")

painel = RAIZ / "7_Automacao_Inteligente" / "saida" / "dashboard.html"
print(f"\n[SUCESSO] Pipeline completo. Abra no navegador: {painel}")
