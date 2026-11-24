"""Gera SVG da arquitetura atual e PNG quando Pillow estiver instalado.

Uso: python 4_Arquitetura_Solucao/gerar_diagrama.py
Pillow e opcional e usado somente para regenerar o PNG, nao pelo pipeline.
"""
from html import escape
from pathlib import Path

BASE = Path(__file__).resolve().parent
W, H = 1360, 1000
parts = []
try:
    from PIL import Image, ImageDraw, ImageFont
    canvas = Image.new("RGB", (W * 2, H * 2), "white")
    draw = ImageDraw.Draw(canvas)
except ImportError:
    canvas = draw = None


def text(x, y, value, size=18, bold=False, color="#244337"):
    parts.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(value)}</text>')
    if draw:
        name = "arialbd.ttf" if bold else "arial.ttf"
        # Fase 7: fonte do Windows quando existir; fallback para rodar em Linux/CI
        try:
            font = ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size * 2)
        except OSError:
            font = ImageFont.load_default()
        draw.text((x * 2, y * 2), value, fill=color, font=font, anchor="ls")


def line(points, dashed=False):
    coords = " ".join(f"{x},{y}" for x, y in points)
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    parts.append(f'<polyline points="{coords}" fill="none" stroke="#668576" stroke-width="2"{dash} marker-end="url(#arrow)"/>')
    if draw:
        draw.line([(x * 2, y * 2) for x, y in points], fill="#668576", width=4)
        x, y = points[-1]
        px, py = points[-2]
        if x == px:
            sign = 1 if y > py else -1
            arrow = [(x, y), (x - 5, y - sign * 9), (x + 5, y - sign * 9)]
        else:
            sign = 1 if x > px else -1
            arrow = [(x, y), (x - sign * 9, y - 5), (x - sign * 9, y + 5)]
        draw.polygon([(a * 2, b * 2) for a, b in arrow], fill="#668576")


def box(x, y, w, h, title, rows, fill="#eef6f0", planned=False):
    dash = ' stroke-dasharray="7 5"' if planned else ""
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="#9eb7a7"{dash}/>')
    if draw:
        draw.rounded_rectangle((x * 2, y * 2, (x + w) * 2, (y + h) * 2), radius=24, fill=fill, outline="#9eb7a7", width=2)
    text(x + 16, y + 29, title, 19, True)
    for i, row in enumerate(rows):
        text(x + 16, y + 54 + i * 24, row, 16)


text(40, 45, "AgroSmart | Arquitetura da demonstracao entregue", 28, True)
text(40, 76, "Fluxo executado: simulacao Python, arquivos locais, processamento, regras e visualizacao.", 18)
text(1040, 128, "COMPONENTES PROPOSTOS", 18, True)
box(1040, 150, 280, 260, "Integracao futura", ["Arduino / TinkerCad", "Sensores e atuadores fisicos", "Gateway de campo via Serial", "Consulta de clima ao vivo", "Envio de comandos a bomba", "Cameras e drones"], "#f8f5ef", True)
text(1056, 390, "Sem execucao no pipeline atual.", 15)

box(60, 110, 360, 90, "1. Dispositivos virtuais", ["gerar_dados_simulados.py", "24 h, tres talhoes, falhas e eventos"])
box(60, 245, 360, 90, "2. Coleta / camada raw", ["dados_sensores_brutos.csv", "CSV com data/hora simulada"])
box(550, 245, 410, 90, "Clima: exemplo local de API", ["exemplo_dados_api_clima.json", "Previsao lida do JSON, sem requisicao"])
box(60, 380, 360, 110, "3. Processamento / trusted", ["processar_dados.py", "Validacao, limpeza e deduplicacao", "Linhas invalidas -> quarentena.csv"])
box(550, 380, 410, 90, "Diagnosticos da fase anterior", ["dados_agricolas.csv", "CSV lido diretamente pelo motor"])
box(60, 535, 360, 90, "Dados preparados / refined", ["dados_processados.csv", "Variaveis derivadas e resumo por talhao"])
box(550, 530, 410, 110, "4. Motor de decisao", ["motor_decisao.py", "15 regras de inferencia e 9 de acao", "Cruza sensores + clima + diagnosticos"], "#f0eef9")
box(60, 720, 360, 110, "Evidencia da coleta", ["gerar_visualizacao_simulacao.py", "simulacao_sensores.html", "Reproducao do CSV bruto e captura"], "#edf3fb")
box(550, 720, 410, 130, "5. Dashboard e saidas", ["dashboard.html | indicadores e graficos", "alertas.json e relatorio_alertas.txt", "comandos_atuadores.txt: comandos I/D", "Registro simulado, sem atuacao fisica"], "#edf3fb")

line([(240, 200), (240, 245)])
line([(240, 335), (240, 380)])
line([(240, 490), (240, 535)])
line([(420, 580), (550, 580)])
line([(755, 470), (755, 530)])
line([(960, 290), (995, 290), (995, 550), (960, 550)])
line([(755, 640), (755, 720)])
line([(60, 290), (35, 290), (35, 775), (60, 775)])

text(1040, 500, "FASES ANTERIORES", 18, True)
box(1040, 520, 280, 280, "Execucao separada", ["automacao_streaming.py", "CSV de diagnosticos ->", "relatorio_intervencao.txt", "Docker: opcional no streaming", "gerar_relatorio_ia.py ->", "relatorio executivo", "IA simulada ou API com chave"], "#f8f5ef")
text(1056, 780, "Fora do executor integrado.", 15)
text(40, 905, "Linhas com setas: fluxo executado na demonstracao. O reprodutor visual le a camada bruta.", 18)
text(40, 935, "Os modulos anteriores usam seus proprios arquivos; imagens, Serial e atuacao fisica sao propostas.", 18)
text(40, 965, "Camadas raw / trusted / refined sao organizadas em arquivos locais, sem servico de Data Lake em nuvem.", 17)

svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1360" height="1000" viewBox="0 0 1360 1000" role="img">'
       '<title>Arquitetura atual da demonstracao AgroSmart</title>'
       '<desc>Simulacao Python gera CSV bruto, processado e consumido por regras com clima JSON e diagnosticos CSV. O motor gera dashboard, alertas e comandos em arquivo. Componentes futuros e modulos anteriores sao indicados separadamente.</desc>'
       '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#668576"/></marker></defs>'
       '<rect width="1360" height="1000" fill="white"/>' + "\n".join(parts) + '</svg>')
(BASE / "diagrama_arquitetura.svg").write_text(svg, encoding="utf-8")
if canvas:
    canvas.save(BASE / "diagrama_arquitetura.png")
print("[OK] SVG gerado; " + ("PNG gerado." if canvas else "instale Pillow para regenerar o PNG."))
