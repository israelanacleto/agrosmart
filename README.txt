====================================================================
AGROSMART - FASE 6 (base da Fase 7; ver README.md)
Automacao e Robotica Inteligente
====================================================================

Turma: 4ESOA - Grupo 102

INTEGRANTES
- Ver integrantes.txt (arquivo local, nao versionado: contem RMs).

--------------------------------------------------------------------
1. O QUE E ESTE PROJETO
--------------------------------------------------------------------
Solucao do AgroSmart para a Fase 6, com seis entregas:

  1) Integração da Arquitetura da Solução
  2) Coleta de Dados do Ambiente (IoT ou Simulação)
  3) Processamento e Preparação dos Dados
  4) Automação Inteligente Baseada em Dados
  5) Dashboard Analítico da Solução
  6) Demonstração da Plataforma

A integração da Arquitetura de Solução detalha categoricamente como as APIs. diagnósticos, imagens e IoT (TinkerCad) com a integração contínua alimenta o Raw, trusted e o refined.
O Refined como o refinamento de dados, alimenta e gera relatórios, comandos, painéis e alertas com o auxílio de IA generativa. 

Coleta de Dados do Ambiente: Os sensores capitam, usam do Arduino Uno R3 para ter como saída luzes de indicação.

FLUXO DOS DADOS

(
  Nos IoT (Arduino/TinkerCad)
      | Serial: uma linha CSV por leitura
      v
  Gateway de campo -> acrescenta data/hora (recebido_em)
      |
      v
  [RAW]  5_Coleta_Dados_IoT/dados_sensores_brutos.csv
      |  1. Leitura do arquivo e conferencia do cabecalho (schema)
      v
  [TRUSTED]
      |  2. Validacao de cada linha:
      |     - numero de campos correto (pega linha truncada)
      |     - nenhum campo vazio
      |     - conversao de tipos (data/hora, numeros, eventos 0/1)
      |     - faixas fisicas: temperatura -10..60 C; UR, solo e luz 0..100%
      |     -> linha invalida vai para quarentena.csv com o motivo
      |  3. Remocao de duplicadas (mesmo no_sensor + mesmo millis)
      v
  [REFINED]
      |  4. Organizacao: ordena por talhao e horario; separa data e hora
      |  5. Transformacao / variaveis derivadas (por talhao):
      |     - periodo ............ dia ou noite (luminosidade >= 10%)
      |     - ponto_orvalho_c .... formula de Magnus-Tetens
      |     - vpd_kpa ............ deficit de pressao de vapor (estresse da planta)
      |     - solo_media_movel_3 . suaviza o ruido do sensor de solo
      |     - delta_solo ......... variacao em relacao a leitura anterior
      |     - horas_ur_alta_consecutivas  horas seguidas com UR >= 85%
      |                                   (molhamento foliar: risco de fungo)
      |     - intervalo_min / lacuna ...  detecta leituras perdidas
      |  6. Agregacao por talhao (resumo_por_talhao.csv)
      v
  saida/dados_processados.csv  -> entrada do motor de decisao (7_Automacao_Inteligente)
)

TIPO DE AUTOMACAO
(
Motor inferencial baseado em regras, com encadeamento progressivo
(forward chaining). Optamos por regras em vez de Machine Learning porque:
  - ainda nao ha historico rotulado suficiente para treinar um modelo;
  - as regras seguem conhecimento agronomico conhecido (limites de
    umidade do solo, molhamento foliar para fungos, VPD);
  - cada decisao e explicavel: o alerta mostra quais regras o geraram.
Quando a camada refined acumular historico com o resultado real das
acoes, o mesmo dataset pode ser usado para treinar um classificador
que substitua ou calibre os limiares das regras.
)

O Dashboard está na pasta 7_Automacao_Inteligente

--------------------------------------------------------------------
2. ESTRUTURA DOS ARQUIVOS
--------------------------------------------------------------------
/ (raiz)
  Arquitetura_Data_Lake .................. Diagrama do Data Lake
  Ingestao_Administracao_Manutencao ...... Fluxo da ingestão
  IA_Generativa_Apoio_Decisao ............ Descrição funcionamento da IA
  Arquitetura_Solucao .................... Diagrama da Arquitetura
  Coleta_Dados_IoT ....................... Descrição dos sensores
  Processamento_Dados .................... Fluxo de dados
  Automacao_Inteligente .................. Descrição da automação e na subpasta (saida): há o dashboard
  Business_Model_Canvas_AgroSmart ........ Modelo Canvas de negócio
  Video_Streaming.mp4 .................... Vídeo demonstrativo (link do vídeo: https://youtu.be/mm8JXCbc-5s)
  README.txt ............................. Este arquivo

  FIAP - Agrosmart Docker/
    Dockerfile .................. Imagem Python 3.12 da aplicacao
    docker-compose.yml .......... Orquestracao (sobe com 1 comando)
    .dockerignore ............... Arquivos ignorados no build
    automacao_streaming.py ...... Aplicacao principal (Python 3)
    dados_agricolas.csv ......... Dados simulados dos sensores (entrada)
    pipeline_config.json ........ Configuracao do pipeline
    relatorio_intervencao.txt ... Exemplo de saida ja gerada
    explicacao_arquitetura.txt .. Detalhe da arquitetura Docker
    Print_da_aplicacao.png ...... Print da aplicacao em execucao
    Diagrama.png ................ Copia do diagrama

--------------------------------------------------------------------
3. PRE-REQUISITOS
--------------------------------------------------------------------
- Docker instalado e em execucao.
  Verifique com:   docker --version
  (Windows/Mac: Docker Desktop aberto. Linux: servico docker ativo.)

Nao e necessario instalar Python: ele ja vem dentro do container.

--------------------------------------------------------------------
4. COMO RODAR (PASSO A PASSO) - VIA DOCKER (recomendado)
--------------------------------------------------------------------
Passo 1. Abra o terminal e entre na pasta do Docker:

    cd "FIAP - Agrosmart Docker"

Passo 2. Suba a aplicacao (faz o build da imagem e executa):

    docker compose up --build

    (Se a sua versao do Docker for antiga, use:  docker-compose up --build)

Passo 3. Acompanhe no terminal. Voce vera as amostras sendo
recebidas "via Stream", uma a cada 3 segundos, com o diagnostico e
a acao executada para cada uma.

Passo 4. Ao final aparece a mensagem:

    [SUCESSO] Stream finalizado. Arquivo 'relatorio_intervencao.txt' gerado.

Passo 5. Confira o resultado no arquivo gerado dentro da pasta:

    relatorio_intervencao.txt

Passo 6 (opcional). Para encerrar e remover o container:

    docker compose down

--------------------------------------------------------------------
5. COMO RODAR SEM DOCKER (alternativa, precisa de Python 3)
--------------------------------------------------------------------
Dentro da pasta "FIAP - Agrosmart Docker", execute:

    python automacao_streaming.py

(Em alguns sistemas o comando e "python3" no lugar de "python".)
O comportamento e o mesmo: gera o "relatorio_intervencao.txt".

--------------------------------------------------------------------
6. MODELO DE NEGOCIO (BUSINESS MODEL CANVAS)
--------------------------------------------------------------------
- Canvas preenchido (documento): Business_Model_Canvas_AgroSmart.pdf
- Video explicando o modelo de negocio e a proposta de valor:
  https://youtu.be/goZGJKfLBTE

--------------------------------------------------------------------
8. INTEGRACAO DA SOLUCAO (ARQUITETURA, IoT, PROCESSAMENTO, AUTOMACAO)
--------------------------------------------------------------------

Rodar tudo de uma vez (precisa de Python 3, sem bibliotecas extras):

    python executar_pipeline_integrado.py

    (use --gerar-dados para recriar a serie simulada de sensores)

Depois abra 7_Automacao_Inteligente/saida/dashboard.html no navegador.

1) INTEGRACAO DA ARQUITETURA DA SOLUCAO
   Pasta: 4_Arquitetura_Solucao/
   - diagrama_arquitetura.svg/.png  fontes -> ingestao -> Data Lake ->
     decisao -> visualizacao, com o laco de comando para o campo
   - descricao_componentes.txt ..... papel de cada componente

2) COLETA DE DADOS DO AMBIENTE (IoT / TINKERCAD)
   Pasta: 5_Coleta_Dados_IoT/
   - agrosmart_no_sensor.ino ....... codigo do Arduino (TinkerCad)
   - esquema_ligacao_circuito.svg/.png  ligacao de sensores e atuadores
   - descricao_sensores.txt ........ sensores, montagem e exemplos de dados
   - serial_monitor_exemplo.txt .... saida do Monitor serial
   - dados_sensores_brutos.csv ..... 24 h de leituras de 3 talhoes (raw)
   - gerar_dados_simulados.py ...... gera a serie de 24 h
   - captura_simulacao_tinkercad.png  print da simulacao (adicionar)

3) PROCESSAMENTO E PREPARACAO DOS DADOS
   Pasta: 6_Processamento_Dados/
   - processar_dados.py ............ validacao, limpeza e transformacao
   - fluxo_dados.txt ............... fluxo raw -> trusted -> refined
   - saida/dados_processados.csv ... dataset processado
   - saida/quarentena.csv, saida/resumo_por_talhao.csv

4) AUTOMACAO INTELIGENTE BASEADA EM DADOS
   Pasta: 7_Automacao_Inteligente/
   - motor_decisao.py .............. motor de inferencia por regras
   - descricao_automacao.txt ....... regras, decisoes e exemplo de saida
   - dashboard_template.html ....... modelo do painel
   - saida/relatorio_alertas.txt, saida/alertas.json,
     saida/comandos_atuadores.txt, saida/dashboard.html,
     saida/print_dashboard.png
