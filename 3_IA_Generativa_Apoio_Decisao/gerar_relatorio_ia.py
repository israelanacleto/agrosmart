# -*- coding: utf-8 -*-
"""
Gera um relatorio de apoio a decisao usando IA generativa a partir dos
dados ja processados pelo pipeline (relatorio_intervencao.txt).

Se a variavel de ambiente ANTHROPIC_API_KEY estiver definida e o pacote
"anthropic" estiver instalado, o script chama a API real. Caso
contrario, retorna o relatorio simulado (exemplo_saida_ia.txt), que
serve como exemplo da saida esperada.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJETO_DIR = BASE_DIR.parent / "FIAP - Agrosmart Docker"
RELATORIO_DADOS = PROJETO_DIR / "relatorio_intervencao.txt"
SAIDA_SIMULADA = BASE_DIR / "exemplo_saida_ia.txt"

PROMPT_SISTEMA = (
    "Voce e um agronomo assistente virtual do AgroSmart. Receba os dados "
    "processados de amostras de lavoura e gere um relatorio executivo em "
    "linguagem natural com: 1) resumo geral da saude da lavoura, 2) pontos "
    "de atencao prioritaria, 3) recomendacoes praticas de manejo e 4) a "
    "tendencia observada ao longo das leituras."
)


def carregar_contexto():
    if not RELATORIO_DADOS.exists():
        raise FileNotFoundError(
            "Rode automacao_streaming.py antes para gerar o "
            "relatorio_intervencao.txt usado como contexto."
        )
    return RELATORIO_DADOS.read_text(encoding="utf-8")


def gerar_com_ia_real(contexto):
    from anthropic import Anthropic

    cliente = Anthropic()
    resposta = cliente.messages.create(
        model="claude-sonnet-5-5",  # Fase 7: ID de modelo corrigido
        max_tokens=1024,
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": contexto}],
    )
    return resposta.content[0].text


def gerar_simulado():
    return SAIDA_SIMULADA.read_text(encoding="utf-8")


def main():
    contexto = carregar_contexto()

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            relatorio = gerar_com_ia_real(contexto)
            origem = "IA generativa (chamada real)"
        except Exception as erro:
            print(f"[AVISO] Falha ao chamar IA real ({erro}). Usando modo simulado.")
            relatorio = gerar_simulado()
            origem = "IA generativa (modo simulado)"
    else:
        relatorio = gerar_simulado()
        origem = "IA generativa (modo simulado)"

    print(f"===== RELATORIO GERADO - {origem} =====\n")
    print(relatorio)


if __name__ == "__main__":
    main()
