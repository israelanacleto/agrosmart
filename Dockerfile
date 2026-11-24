# NOVO (Fase 7) - imagem da plataforma integrada AgroSmart (pipeline completo + operacao continua).
# A imagem antiga em "FIAP - Agrosmart Docker/" continua existindo para o fluxo de diagnostico.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    AGROSMART_CICLOS=1 \
    AGROSMART_INTERVALO_S=30

WORKDIR /app

# Runtime usa somente a biblioteca padrao: requirements.txt nao tem pacotes obrigatorios.
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && groupadd --system --gid 10001 agro \
    && useradd --system --uid 10001 --gid agro --no-create-home --shell /usr/sbin/nologin agro

# Codigo e dados de entrada pertencem ao root (somente leitura para o usuario da aplicacao).
COPY executar_pipeline_integrado.py ./
COPY 2_Ingestao_Administracao_Manutencao/exemplo_dados_api_clima.json 2_Ingestao_Administracao_Manutencao/
COPY ["FIAP - Agrosmart Docker/dados_agricolas.csv", "FIAP - Agrosmart Docker/"]
COPY 6_Processamento_Dados/processar_dados.py 6_Processamento_Dados/
COPY 7_Automacao_Inteligente/motor_decisao.py 7_Automacao_Inteligente/dashboard_template.html 7_Automacao_Inteligente/
COPY 8_Execucao_Monitorada/*.py 8_Execucao_Monitorada/
COPY 9_Process_Mining/analisar_processo.py 9_Process_Mining/
# A pasta 5 recebe escrita (dados_simulacao.js e, com --gerar-dados, o CSV raw).
COPY --chown=agro:agro 5_Coleta_Dados_IoT/ 5_Coleta_Dados_IoT/

# Somente as pastas de saida sao gravaveis pelo usuario nao-root.
RUN mkdir -p 6_Processamento_Dados/saida 7_Automacao_Inteligente/saida \
             8_Execucao_Monitorada/saida 9_Process_Mining/saida \
    && chown -R agro:agro 6_Processamento_Dados/saida 7_Automacao_Inteligente/saida \
                          8_Execucao_Monitorada/saida 9_Process_Mining/saida

USER agro

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "8_Execucao_Monitorada/healthcheck.py"]

CMD ["python", "8_Execucao_Monitorada/orquestrador.py"]
