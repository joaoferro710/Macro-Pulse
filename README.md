# macro-pulse

> Agente de inteligencia macroeconomica: coleta indicadores reais, detecta anomalias estatisticas e gera briefings analiticos diarios via LLM.

---

## Motivacao

Acompanhar o cenario macroeconomico exige consolidar dados de multiplas fontes, identificar o que mudou e traduzir isso em linguagem acionavel. Na pratica, grande parte desse trabalho ainda e repetitiva, manual e espalhada entre planilhas, portais de dados e anotacoes.

O macro-pulse automatiza essa cadeia de ponta a ponta: ingestao incremental de APIs publicas, persistencia local em DuckDB, deteccao estatistica de anomalias, classificacao de regimes economicos, geracao de briefings via LLM e visualizacao em dashboard interativo. O projeto foi construido para portfolio, com stack leve, reproduzivel e orientada a demonstracao tecnica.

---

## Demonstracao

> Adicione aqui um GIF ou screenshot do dashboard em funcionamento apos o deploy.

---

## Arquitetura

```text
FONTES DE DADOS
FRED | BCB (SGS) | Alpha Vantage
          |
          v
ingestion/
fred_client.py | bcb_client.py | alpha_vantage_client.py | loader.py
          |
          v
DuckDB (macro_pulse.db)
economic_indicators | briefings
      |                    |
      |                    +--> agent/
      |                         tools.py
      |                         macro_agent.py
      |
      +--> analytics/
      |    anomaly_detector.py
      |    regime_detector.py
      |
      +--> dashboard/
      |    app.py
      |
      +--> scheduler/
           jobs.py
```

---

## Indicadores monitorados

### Estados Unidos (FRED)

| Serie | Descricao |
|---|---|
| `FEDFUNDS` | Taxa de juros do Federal Reserve |
| `CPIAUCSL` | Inflacao CPI dos EUA |
| `UNRATE` | Taxa de desemprego dos EUA |
| `GDP` | PIB trimestral dos EUA |
| `T10Y2Y` | Spread da curva de juros 10Y-2Y |

### Brasil (Banco Central - SGS)

| Codigo | Descricao |
|---|---|
| `432` | Taxa SELIC |
| `13522` | IPCA acumulado em 12 meses |
| `1` | Cambio USD/BRL |
| `4380` | PIB Brasil - variacao trimestral |

### Mercado (Alpha Vantage)

| Simbolo | Descricao |
|---|---|
| `EWZ` | iShares MSCI Brazil ETF (proxy do mercado brasileiro) |
| `SPY` | SPDR S&P 500 ETF |
| `USD/BRL` | Cambio via endpoint FX Monthly |

---

## Deteccao de anomalias

O projeto aplica dois algoritmos estatisticos sobre as series armazenadas no DuckDB:

**Z-score rolling**
Usa janela movel para identificar observacoes que se afastam materialmente do comportamento recente da serie. E util para detectar picos e vales isolados.

**CUSUM**
Identifica mudancas persistentes no nivel medio da serie, mesmo quando o movimento nao aparece como um outlier pontual. E util para capturar mudancas de regime mais graduais.

A combinacao dos dois cobre tanto choques abruptos quanto desvios cumulativos.

---

## Classificacao de regimes macroeconomicos

O sistema monitora dois contextos principais:

**Curva de juros americana**
Classificada a partir da serie `T10Y2Y` em `normal`, `flat` ou `inverted`.

**Regime macro brasileiro**
Classificado a partir da combinacao de SELIC, IPCA e USD/BRL em `expansao`, `contracao`, `estagflacao` ou `estabilidade`.

Os thresholds ficam explicitos no codigo, em [regime_detector.py](C:/Users/Felipe/macro-pulse/analytics/regime_detector.py).

---

## Stack

| Camada | Tecnologia | Papel no projeto |
|---|---|---|
| Linguagem | Python 3.11+ | Base do projeto |
| Armazenamento | DuckDB | Persistencia analitica local |
| Ingestao | requests + tenacity | Coleta com retry e backoff |
| Analytics | pandas + numpy + scipy | Z-score, CUSUM e preparo de series |
| Agente LLM | LangChain + Groq + LLaMA 3.3 70B | Geracao dos briefings macroeconomicos |
| Dashboard | Streamlit + Altair | Visualizacao interativa |
| Scheduler | APScheduler | Jobs diarios no proprio servico web |
| Testes | pytest | Validacao automatizada |
| Lint | ruff | Higiene de codigo |

---

## Decisoes de implementacao

**EWZ como proxy do mercado acionario brasileiro**
O simbolo `^BVSP` nao retornou serie utilizavel via Alpha Vantage durante a implementacao. Por isso, o projeto adotou `EWZ` como proxy do mercado brasileiro. Como ele e negociado em USD, a serie tambem captura parte do efeito cambial.

**Groq em lugar de OpenAI**
A camada de agente foi implementada com Groq para manter compatibilidade com o ecossistema LangChain e viabilizar uso sem depender de billing da OpenAI API.

**DuckDB em lugar de banco servidor**
Para este caso de uso, DuckDB entrega simplicidade operacional, boa performance analitica e zero overhead de infraestrutura.

**APScheduler em lugar de Airflow**
Como o projeto executa apenas dois jobs diarios, APScheduler cobre a necessidade com muito menos complexidade operacional. No deploy do Render, ele pode rodar dentro do proprio servico web para atualizar o DuckDB local persistido em disco.

---

## Instalacao

### Pre-requisitos

- Python 3.11+
- Git

### Passo a passo

```bash
git clone https://github.com/seu-usuario/macro-pulse.git
cd macro-pulse

py -3.12 -m venv .venv
.\.venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env

python -m ingestion.loader

streamlit run dashboard/app.py
```

---

## Configuracao de API keys

Preencha o arquivo `.env` com:

```env
FRED_API_KEY=your_fred_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

Links usados no projeto:

- `FRED_API_KEY`: https://fred.stlouisfed.org/docs/api/api_key.html
- `ALPHA_VANTAGE_API_KEY`: https://www.alphavantage.co/support/#api-key
- `GROQ_API_KEY`: https://console.groq.com

---

## Uso

### Ingestao manual

```bash
python -m ingestion.loader
```

### Gerar briefing manualmente

```bash
python -m agent.macro_agent
```

### Iniciar o scheduler

```bash
python -m scheduler.jobs
```

### Rodar o dashboard

```bash
streamlit run dashboard/app.py
```

### Rodar os testes

```bash
pytest tests/ -v
```

### Rodar lint

```bash
ruff check .
```

---

## Deploy no Render

O repositorio inclui [render.yaml](C:/Users/Felipe/macro-pulse/render.yaml) e [runtime.txt](C:/Users/Felipe/macro-pulse/runtime.txt) para deploy do dashboard.

O blueprint foi configurado para a abordagem mais simples que funciona com DuckDB local:

- um unico servico web com Streamlit
- disco persistente montado em `/data`
- banco em `MACRO_PULSE_DB_PATH=/data/macro_pulse.db`
- `preDeployCommand` para carga inicial e briefing inicial
- scheduler interno ativado por `ENABLE_INTERNAL_SCHEDULER=true`
- `startCommand` apontando para `python dashboard/serve.py`, que sobe o scheduler antes do Streamlit

Com isso, o proprio servico web atualiza os dados diariamente no mesmo banco que o dashboard le.

1. Publique o repositorio no GitHub.
2. Acesse https://dashboard.render.com e crie um novo `Blueprint`.
3. Conecte o repositorio `macro-pulse`.
4. Confirme a leitura do `render.yaml`.
5. Escolha um plano compativel com persistent disk.
6. Adicione no painel do Render as variaveis `FRED_API_KEY`, `ALPHA_VANTAGE_API_KEY` e `GROQ_API_KEY`.
7. Dispare o deploy e acompanhe a URL publica do Streamlit.

### Agenda diaria em producao

Quando `ENABLE_INTERNAL_SCHEDULER=true`, `dashboard/serve.py` inicia o APScheduler em background antes de subir o Streamlit e executa:

- ingestao diaria as `08:00` (`America/Sao_Paulo`)
- briefing diario as `08:30` (`America/Sao_Paulo`)

### Observacao importante

Cron jobs separados do Render nao sao a melhor opcao para esta arquitetura com DuckDB local, porque o dashboard precisa ler o mesmo arquivo de banco mantido pelo servico web. Por isso, a estrategia adotada aqui e manter o scheduler dentro do mesmo servico e persistir o banco em disco.

---

## Estrutura do repositorio

```text
macro-pulse/
|-- ingestion/
|   |-- fred_client.py
|   |-- bcb_client.py
|   |-- alpha_vantage_client.py
|   `-- loader.py
|-- analytics/
|   |-- anomaly_detector.py
|   `-- regime_detector.py
|-- agent/
|   |-- tools.py
|   `-- macro_agent.py
|-- dashboard/
|   `-- app.py
|-- scheduler/
|   `-- jobs.py
|-- tests/
|   |-- test_ingestion.py
|   |-- test_analytics.py
|   `-- test_agent.py
|-- .env.example
|-- render.yaml
|-- runtime.txt
|-- requirements.txt
`-- README.md
```

---

## Proximos passos

- Alertas por email quando anomalias criticas forem detectadas
- Cobertura adicional de commodities e juros longos
- Historico pesquisavel de briefings
- Backtesting de eventos macro contra as anomalias detectadas
