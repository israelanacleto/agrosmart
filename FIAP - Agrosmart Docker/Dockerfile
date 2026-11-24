FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

# Fase 7: usuario nao-root (antes o container rodava como root)
RUN groupadd --system --gid 10001 agro \
    && useradd --system --uid 10001 --gid agro --no-create-home --shell /usr/sbin/nologin agro \
    && chown agro:agro /app

COPY --chown=agro:agro automacao_streaming.py dados_agricolas.csv pipeline_config.json ./

USER agro

CMD ["python", "automacao_streaming.py"]
