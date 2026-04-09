# macro-pulse

> Agente de inteligencia macroeconomica: coleta indicadores reais, detecta anomalias estatisticas e gera briefings analiticos diarios via LLM.

---

## Motivacao

Acompanhar o cenario macroeconomico exige consolidar dados de multiplas fontes, identificar o que mudou e transformar sinais dispersos em leitura acionavel. Na pratica, grande parte desse trabalho ainda e manual, repetitiva e espalhada entre planilhas, portais de dados e anotacoes.

O macro-pulse foi construido para automatizar essa cadeia de ponta a ponta: ingestao de dados reais de APIs publicas, persistencia analitica em DuckDB hospedado no MotherDuck, deteccao estatistica de anomalias, classificacao de regimes macroeconomicos, geracao automatizada de briefings via LLM e visualizacao em dashboard interativo. O projeto foi desenhado como portfolio profissional, com codigo organizado, fluxo reproduzivel e estrutura proxima de um ambiente de producao.

---

## Arquitetura

```text
APIs Publicas
FRED | BCB (SGS) | Alpha Vantage
          |
          v
ingestion/
fred_client.py | bcb_client.py | alpha_vantage_client.py | loader.py
          |
          v
MotherDuck (DuckDB hospedado)
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
      +--> app.py
      |
      +--> scheduler/
           jobs.py
```

---

## Fontes de dados reais

### 1. FRED API

- URL base: `https://api.stlouisfed.org/fred/series/observations`
- Chave: `FRED_API_KEY`
- Series monitoradas:
  - `FEDFUNDS` - Taxa de juros do Fed
  - `CPIAUCSL` - Inflacao CPI dos EUA
  - `UNRATE` - Taxa de desemprego dos EUA
  - `GDP` - PIB dos EUA
  - `T10Y2Y` - Spread da curva 10Y-2Y

### 2. BCB API

- URL base: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados`
- Sem autenticacao
- Series monitoradas:
  - `432` - Taxa SELIC
  - `13522` - IPCA acumulado em 12 meses
  - `1` - Cambio USD/BRL
  - `4380` - PIB Brasil variacao trimestral

### 3. Alpha Vantage API

- URL base: `https://www.alphavantage.co/query`
- Chave: `ALPHA_VANTAGE_API_KEY` ou `ALPHA_VANTAGE_KEY`
- Series monitoradas:
  - `EWZ` - Proxy do mercado brasileiro
  - `SPY` - Proxy do mercado americano
  - `USD/BRL` - Cambio via endpoint FX Monthly

---

## Indicadores monitorados

### Estados Unidos

| Serie | Descricao |
|---|---|
| `FEDFUNDS` | Taxa de juros do Federal Reserve |
| `CPIAUCSL` | Inflacao CPI dos EUA |
| `UNRATE` | Taxa de desemprego dos EUA |
| `GDP` | PIB trimestral dos EUA |
| `T10Y2Y` | Spread da curva de juros 10Y-2Y |

### Brasil

| Codigo | Descricao |
|---|---|
| `432` | Taxa SELIC |
| `13522` | IPCA acumulado em 12 meses |
| `1` | Cambio USD/BRL |
| `4380` | PIB Brasil variacao trimestral |

### Mercado

| Simbolo | Descricao |
|---|---|
| `EWZ` | iShares MSCI Brazil ETF |
| `SPY` | SPDR S&P 500 ETF |
| `USD/BRL` | Cambio via endpoint FX Monthly |

---

## Deteccao de anomalias

O projeto aplica dois algoritmos estatisticos sobre as series armazenadas no MotherDuck:

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
| Armazenamento | DuckDB + MotherDuck | Persistencia analitica em nuvem |
| Ingestao | requests + tenacity | Coleta com retry e backoff |
| Analytics | pandas + numpy + scipy | Z-score, CUSUM e preparo de series |
| Agente LLM | LangChain + Groq + LLaMA 3.3 70B | Geracao dos briefings macroeconomicos |
| Dashboard | Streamlit + Altair | Visualizacao interativa |
| Scheduler | APScheduler | Jobs diarios locais |
| Ambiente | python-dotenv + st.secrets | Segredos e configuracao |
| Testes | pytest | Validacao automatizada |
| Lint | ruff | Higiene de codigo |

---

## Decisoes de implementacao

**EWZ como proxy do mercado acionario brasileiro**  
O simbolo `^BVSP` nao retornou serie utilizavel via Alpha Vantage durante a implementacao. Por isso, o projeto adotou `EWZ` como proxy do mercado brasileiro. Como ele e negociado em USD, a serie tambem captura parte do efeito cambial.

**Groq em lugar de OpenAI**  
A camada de agente foi implementada com Groq para manter compatibilidade com o ecossistema LangChain e viabilizar uso sem depender de billing da OpenAI API.

**DuckDB + MotherDuck em lugar de banco servidor tradicional**  
Para este caso de uso, DuckDB entrega simplicidade analitica e o MotherDuck adiciona persistencia em nuvem sem exigir operacao de banco dedicado.

**Streamlit Community Cloud como alvo principal de deploy**  
Como o projeto precisa de deploy simples, custo zero e compartilhamento rapido, a combinacao de Streamlit Community Cloud com MotherDuck cobre a necessidade com muito menos complexidade operacional.

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
```

Preencha o `.env` com suas chaves e token.

Depois disso, rode o seed inicial:

```bash
.\.venv\Scripts\python scripts/seed_motherduck.py
```

E suba o dashboard localmente:

```bash
.\.venv\Scripts\python -m streamlit run app.py
```

Na primeira conexao com o MotherDuck, o DuckDB baixa extensoes e cria cache local em `.duckdb_home/` dentro do proprio repositorio. Essa pasta ja esta no `.gitignore`.

Se o MotherDuck estiver indisponivel, o dashboard agora tenta cair automaticamente para o arquivo local `macro_pulse.db` em modo leitura, para que a interface continue abrindo com os dados ja seedados.

---

## Configuracao de API keys

Preencha o arquivo `.env` com:

```env
MOTHERDUCK_TOKEN=your_motherduck_token_here
FRED_API_KEY=your_fred_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

Links usados no projeto:

- `MOTHERDUCK_TOKEN`: https://app.motherduck.com
- `FRED_API_KEY`: https://fred.stlouisfed.org/docs/api/api_key.html
- `ALPHA_VANTAGE_API_KEY`: https://www.alphavantage.co/support/#api-key
- `GROQ_API_KEY`: https://console.groq.com

---

## Uso

### Seed inicial do banco

```bash
.\.venv\Scripts\python scripts/seed_motherduck.py
```

### Ingestao manual

```bash
.\.venv\Scripts\python -m ingestion.loader
```

### Gerar briefing manualmente

```bash
.\.venv\Scripts\python -m agent.macro_agent
```

### Iniciar o scheduler

```bash
.\.venv\Scripts\python -m scheduler.jobs
```

### Rodar o dashboard

```bash
.\.venv\Scripts\python -m streamlit run app.py
```

### Rodar os testes

```bash
.\.venv\Scripts\python -m pytest tests/ -v
```

### Smoke test do dashboard

```bash
.\.venv\Scripts\python -m streamlit run app.py --server.headless true
```

Se o MotherDuck nao responder, o app deve continuar abrindo em fallback local e exibir um aviso no topo informando que esta lendo de `macro_pulse.db`.

### Rodar lint

```bash
.\.venv\Scripts\python -m ruff check .
```

---

## Deploy no Streamlit Community Cloud

O repositorio inclui [app.py](C:/Users/Felipe/macro-pulse/app.py), [.streamlit/config.toml](C:/Users/Felipe/macro-pulse/.streamlit/config.toml), [.streamlit/secrets.toml.example](C:/Users/Felipe/macro-pulse/.streamlit/secrets.toml.example) e [README_DEPLOY.md](C:/Users/Felipe/macro-pulse/README_DEPLOY.md) para deploy do dashboard.

O fluxo foi configurado para a abordagem mais simples que funciona com MotherDuck:

- app publico via Streamlit Community Cloud
- banco `macro_pulse` hospedado no MotherDuck
- secrets via `.streamlit/secrets.toml`
- `app.py` na raiz como entrypoint do deploy
- script de seed para carga historica inicial

Com isso, o dashboard le e escreve direto no MotherDuck, sem depender de arquivo `.db` local.

1. Publique o repositorio no GitHub.
2. Execute o seed inicial com `.\.venv\Scripts\python scripts/seed_motherduck.py`.
3. Acesse https://share.streamlit.io e crie um novo app.
4. Conecte o repositorio `macro-pulse`.
5. Defina `app.py` como arquivo principal.
6. Adicione em **Secrets** as variaveis `MOTHERDUCK_TOKEN`, `GROQ_API_KEY`, `FRED_API_KEY` e `ALPHA_VANTAGE_KEY`.
7. Dispare o deploy e acompanhe a URL publica do Streamlit.

### Observacao importante

O botao de atualizacao no sidebar continua chamando `load_all()` normalmente, mas agora grava direto no MotherDuck. A carga historica inicial deve ser feita antes do primeiro deploy com `.\.venv\Scripts\python scripts/seed_motherduck.py`.

Veja o passo a passo em [README_DEPLOY.md](C:/Users/Felipe/macro-pulse/README_DEPLOY.md).

## Modos de armazenamento

O projeto suporta tres modos via variavel `MACRO_PULSE_STORAGE`:

- `auto` - tenta MotherDuck primeiro e faz fallback para `macro_pulse.db` local se a conexao remota falhar
- `motherduck` - exige conexao com MotherDuck
- `local` - usa sempre o arquivo local `macro_pulse.db`

Opcionalmente, voce pode apontar outro arquivo local com `MACRO_PULSE_LOCAL_DB`.

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
|-- .streamlit/
|   |-- config.toml
|   `-- secrets.toml.example
|-- scripts/
|   `-- seed_motherduck.py
|-- app.py
|-- scheduler/
|   `-- jobs.py
|-- tests/
|   |-- test_ingestion.py
|   |-- test_analytics.py
|   |-- test_dashboard.py
|   `-- test_agent.py
|-- .env.example
|-- README_DEPLOY.md
|-- render.yaml
|-- runtime.txt
|-- requirements.txt
`-- README.md
```

---

## Screenshot

Adicione aqui uma captura de tela do dashboard depois de publicar ou gravar sua demonstracao.
