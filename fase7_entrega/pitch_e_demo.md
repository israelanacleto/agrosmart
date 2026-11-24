# Apresentação do produto: pitch (até 5 min) e demonstração técnica (5 a 8 min)

> **Requisito 6.** O conteúdo vem do `Business_Model_Canvas_AgroSmart.pdf` e do que o código faz. Nenhum número de mercado, preço ou cliente foi inventado. Onde o grupo não tem o dado, há um `[A PREENCHER]`, que pode ser removido.
> O BMC cita os canais **SmartTillage.com** e o app **SmartTillage** (Play Store/iOS). O produto e a plataforma se chamam **AgroSmart**, e SmartTillage aparece só como nome de canal, como está no Canvas.

---

## Parte A: pitch (≤ 5 min). Cada bloco cabe num slide

### Slide 1. Gancho (0:00–0:30)
> "Um talhão de sequeiro saiu de 43% para 17% de umidade do solo num único dia quente. Ninguém olhou a planilha a tempo. O AgroSmart viu às 16:30, avisou e mandou ligar a bomba. Às 22:00, quando o solo chegou a nível crítico, mandou de novo."

Os números são reais, do caso de teste: talhão T2 e comandos `'I'` em `comandos_atuadores.txt`.

### Slide 2. Problema (0:30–1:15)
- O produtor de médio porte monitora a lavoura **manualmente**. A análise depende de alguém ir a campo ou interpretar dados soltos.
- Doença fúngica, seca e falha de equipamento são **sinais que se combinam**, como umidade do ar alta por horas com temperatura favorável e foco de doença na propriedade. Uma regra isolada não enxerga essa combinação.
- Soluções que dependem de **satélite ou internet contínua** não servem para quem tem conectividade ruim no campo, nem para o grande produtor que **não quer os dados da lavoura fora da fazenda**.

### Slide 3. Solução (1:15–2:15)
O AgroSmart é uma plataforma de **monitoramento automático da lavoura**. Ela funciona assim:
1. **Sensores de campo** por talhão medem temperatura, umidade do ar e do solo, luz, movimento e chuva.
2. Um **data lake em camadas** (raw → trusted → refined) **rejeita dado ruim**. Sensor desconectado, pacote truncado e reenvio duplicado vão para a quarentena com o motivo.
3. Um **motor de decisão explicável**, com 15 regras encadeadas e 9 ações, cruza sensores, previsão do tempo e diagnósticos de doença. Ele classifica o risco por talhão (NORMAL → CRITICO), recomenda a ação e **comanda a bomba de irrigação**.
4. O **painel e os relatórios** dizem ao produtor **o quê, onde e por quê**. Todo alerta mostra as regras que o geraram.

### Slide 4. Diferencial competitivo (2:15–3:00)
Conforme o BMC:
- **Análise automática sem depender de satélite.** O processamento é local, e a conectividade prevista é em **rede mesh**.
- **IA local, oferecida pelo próprio serviço.** Os dados da lavoura não saem da propriedade.
- **Explicabilidade.** Cada decisão vem com a justificativa ("porque R02: umidade do solo abaixo de 20%"). Não é uma caixa-preta.
- **Economia de água.** O motor **adia a irrigação** se choveu ou se a previsão de chuva for ≥ 60% (regra A04).
- **Operação confiável**, mostrada na demo: execução contínua monitorada, logs estruturados, pipeline de segurança automatizado e container sem privilégios.

### Slide 5. Público-alvo (3:00–3:30)
Os segmentos de clientes do BMC são:
- **Produtores agrícolas de médio porte** que querem automatizar o monitoramento.
- **Produtores de grande porte** que preferem **privacidade** sobre os dados das lavouras e **não querem depender de conexão de internet**.

Mercado endereçável: `[A PREENCHER, se o grupo tiver fonte]`.

### Slide 6. Proposta de valor e modelo de negócio (3:30–4:30)
- **Proposta de valor:** manter a lavoura saudável **sem análise manual prévia**, com o banco de dados atualizado em rotina constante e estável.
- **Relacionamento:** perfil online.
- **Canais:** site SmartTillage.com, software de visualização e app mobile (Play Store e iOS).
- **Receitas** (BMC):
  - aluguel do software de monitoramento automatizado;
  - serviços premium de criação de agentes de IA específicos e de machine learning mais robusto;
  - valor de instalação e de suporte ao uso do sistema completo;
  - anúncios nos apps;
  - assinatura premium nos apps mobile.
- **Parcerias e recursos-chave:** IA de visão computacional agrícola, banco de dados agronômico e equipamentos de monitoramento e de processamento para IA.
- **Custos:**
  - desenvolvimento e manutenção (patches);
  - atualização do banco de dados;
  - auxílio na instalação;
  - cibersegurança de redes;
  - marketing.
- Preço por talhão ou hectare: `[A PREENCHER]`.

### Slide 7. Fechamento (4:30–5:00)
> "O AgroSmart transforma dados de campo em ação explicável, no talhão certo, na hora certa, sem depender de satélite. Hoje ele roda ponta a ponta, monitorado e auditado. O próximo passo é ligar os nós Arduino reais e a bomba física."

Próximos passos, que aparecem como propostas na arquitetura: Arduino em campo, envio Serial à bomba, API de clima ao vivo e câmeras.

---

## Parte B: demonstração técnica (5 a 8 min)

Preparação, feita antes de apresentar:
- Docker Desktop aberto, a imagem já construída (`docker build -t agrosmart:fase7 .`) e o repositório aberto no VS Code.
- Abas abertas no navegador: GitHub Actions (última execução verde), `7_Automacao_Inteligente/saida/dashboard.html` e `8_Execucao_Monitorada/saida/painel_operacao.html`.

| Tempo | Mostrar | Fala / o que destacar |
|---|---|---|
| 0:00–0:45 | `fase7_entrega/descricao_arquitetura_final.md` (diagrama Mermaid) | As 7 camadas: fontes → data lake → decisão → saídas, mais operação, process mining e DevSecOps. O que é real e o que é proposto (tracejado) |
| 0:45–2:00 | Terminal: `docker compose up --build` | Logs JSON passando: etapas com `duracao_ms`, os 3 `WARNING` de quarentena com o motivo, `Status do talhao: CRITICO` em T2. Em seguida, `docker compose ps` mostrando **healthy** |
| 2:00–2:45 | `5_Coleta_Dados_IoT/dados_sensores_brutos.csv`, linha 66 (−50,0 °C) e `6_.../saida/quarentena.csv` | Dado ruim não contamina a decisão: TMP36 desconectado, campo vazio, linha truncada e duplicada |
| 2:45–4:00 | `dashboard.html` e `relatorio_alertas.txt` | T2 CRITICO (solo em 17%), T3 ALTO (9,5 h de UR ≥ 85% com foco fúngico), T1 NORMAL. Ler um "porque R02…" para mostrar a explicabilidade. `comandos_atuadores.txt` com os dois `'I'` |
| 4:00–4:45 | `painel_operacao.html` | Indicadores do ciclo (144/3/1/140, 8 alertas e 2 comandos), tempo por etapa e histórico. Mostrar o teste de falha: `pytest -k falha` (o loop sobrevive a uma etapa quebrada) |
| 4:45–6:15 | `9_Process_Mining/saida/analise_processo.md` | Event log com 144 casos e 5 variantes. Gargalo: 100% da espera está em *recebida → validação*, de 30 min. O what-if com defasagem de 60 s cai para cerca de 57 s. A falha de sensor demora cerca de 60 min para virar alerta |
| 6:15–7:30 | GitHub → Actions → DevSecOps | 3 jobs: ruff + 21 testes, pip-audit + Trivy fs (segredo e misconfig), build, smoke em container (uid 10001, números conferidos, healthy) e Trivy na imagem. Contar o achado real do pip-audit (`filelock`, 17 CVEs) e a correção |
| 7:30–8:00 | `.env.example` / `Dockerfile` | Nenhum segredo no repositório, tudo configurável por ambiente, usuário não-root. Fechar com os próximos passos |

**Plano B**, caso o Docker falhe na hora: `python 8_Execucao_Monitorada/orquestrador.py --ciclos 2 --intervalo 5` produz exatamente os mesmos artefatos.
