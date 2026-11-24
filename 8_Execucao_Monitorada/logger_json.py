# -*- coding: utf-8 -*-
"""
NOVO (Fase 7) - Logger estruturado em JSON Lines (um objeto JSON por linha).

Campos fixos de cada registro:
  timestamp   ISO 8601 com fuso e milissegundos
  nivel       DEBUG | INFO | WARNING | ERROR
  componente  etapa/modulo que gerou o log (orquestrador, processamento, ...)
  mensagem    texto legivel
  + contexto  qualquer campo extra (execucao_id, ciclo, talhao, duracao_ms, ...)

O mesmo registro vai para o console (stdout, lido por `docker logs`) e para
um arquivo .jsonl, com rotacao simples por tamanho. Usa apenas a stdlib.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

NIVEIS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


class LoggerJSON:
    def __init__(self, arquivo, nivel_console="INFO", nivel_arquivo="DEBUG", tamanho_max_bytes=5_000_000):
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.nivel_console = NIVEIS.get(str(nivel_console).upper(), 20)
        self.nivel_arquivo = NIVEIS.get(str(nivel_arquivo).upper(), 10)
        self.tamanho_max_bytes = tamanho_max_bytes
        self.contexto_fixo = {}

    def vincular(self, **contexto):
        """Define campos que entram em todos os registros seguintes (ex.: execucao_id)."""
        self.contexto_fixo.update(contexto)

    def _rotacionar(self):
        if self.arquivo.exists() and self.arquivo.stat().st_size > self.tamanho_max_bytes:
            antigo = self.arquivo.with_suffix(self.arquivo.suffix + ".1")
            antigo.unlink(missing_ok=True)
            self.arquivo.rename(antigo)

    def log(self, nivel, componente, mensagem, **contexto):
        nivel = nivel.upper()
        valor = NIVEIS.get(nivel, 20)
        registro = {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
            "nivel": nivel,
            "componente": componente,
            "mensagem": mensagem,
            **self.contexto_fixo,
            **contexto,
        }
        linha = json.dumps(registro, ensure_ascii=False, default=str)
        if valor >= self.nivel_arquivo:
            self._rotacionar()
            with self.arquivo.open("a", encoding="utf-8") as saida:
                saida.write(linha + "\n")
        if valor >= self.nivel_console:
            print(linha, file=sys.stdout, flush=True)
        return registro

    def debug(self, componente, mensagem, **contexto):
        return self.log("DEBUG", componente, mensagem, **contexto)

    def info(self, componente, mensagem, **contexto):
        return self.log("INFO", componente, mensagem, **contexto)

    def warning(self, componente, mensagem, **contexto):
        return self.log("WARNING", componente, mensagem, **contexto)

    def error(self, componente, mensagem, **contexto):
        return self.log("ERROR", componente, mensagem, **contexto)
