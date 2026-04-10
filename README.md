# Macro Pulse

> Agente de inteligência macroeconômica: coleta indicadores reais, detecta anomalias estatísticas e gera briefings analíticos diários via LLM.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-MotherDuck-FFF000?style=flat&logo=duckdb&logoColor=black)
![LangChain](https://img.shields.io/badge/LangChain-Groq-1C3C3C?style=flat&logo=langchain&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat)

---

## Demonstração

![Demonstração do dashboard Macro Pulse](docs/media/Macro-pulse.gif)

---

## Visão geral

O ciclo de juros americano afeta diretamente o fluxo de capital para mercados emergentes. Quando o Fed aperta a política monetária, o diferencial de juros se estreita, o dólar se fortalece e a pressão sobre câmbio e SELIC brasileira aumenta. Monitorar esse mecanismo em tempo real exige consolidar dados de múltiplas fontes, identificar desvios estatísticos relevantes e traduzir tudo isso em linguagem acionável — um trabalho que ainda é amplamente manual.

O Macro Pulse automatiza essa cadeia de ponta a ponta:

- **Ingestão incremental** de APIs públicas (FRED, BCB/SGS, Alpha Vantage)
- **Persistência analítica** em DuckDB hospedado no MotherDuck, com fallback local automático
- **Detecção estatística** de anomalias via Z-score rolling e CUSUM
- **Classificação de regimes** macroeconômicos para EUA e Brasil
- **Geração de briefings** via agente LLM com LangChain + Groq + LLaMA 3.3 70B
- **Dashboard interativo** em Streamlit com suporte a PT-BR e EN

O projeto foi desenhado como portfólio profissional, com código organizado, fluxo reproduzível e estrutura próxima de um ambiente de produção.

---

## Arquitetura

```
APIs Públicas
┌──────────┐  ┌──────────┐  ┌─────────────────┐
│   FRED   │  │ BCB/SGS  │  │  Alpha Vantage  │
└────┬─────┘  └────┬─────┘  └───────┬─────────┘
     └─────────────┴────────────────┘
                   │
             ingestion/
          (loader.py + clients)
                   │
                   ▼
         MotherDuck (DuckDB)
      ┌────────────────────────┐
      │  economic_indicators   │
      │       briefings        │
      └───────────┬────────────┘
                  │
       ┌──────────┴──────────┐
       │                     │
  analytics/             agent/
  anomaly_detector    macro_agent
  regime_detector        tools
       │                     │
       └──────────┬──────────┘
                  │
              app.py
           (Streamlit)
```

---

## Indicadores monitorados

### Estados Unidos — FRED

| Série | Descrição |
|---|---|
| `FEDFUNDS` | Taxa de juros do Federal Reserve |
| `CPIAUCSL` | Inflação CPI |
| `UNRATE` | Taxa de desemprego |
| `GDP` | PIB trimestral |
| `T10Y2Y` | Spread da curva de juros 10Y-2Y |

### Brasil — Banco Central (SGS)

| Código | Descrição |
|---|---|
| `432` | Taxa SELIC |
| `13522` | IPCA acumulado em 12 meses |
| `1` | Câmbio USD/BRL |
| `4380` | PIB — variação trimestral |

### Mercado — Alpha Vantage

| Símbolo | Descrição |
|---|---|
| `EWZ` | iShares MSCI Brazil ETF (proxy do Ibovespa) |
| `SPY` | SPDR S&P 500 ETF |
| `USD/BRL` | Câmbio via endpoint FX Monthly |

---

## Detecção de anomalias

Dois algoritmos estatísticos são aplicados sobre cada série armazenada:

**Z-score rolling** — usa janela móvel para identificar observações que se afastam materialmente do comportamento recente. Eficaz para capturar picos e vales isolados.

**CUSUM** — identifica mudanças persistentes no nível médio da série, mesmo quando o movimento não aparece como outlier pontual. Eficaz para capturar desvios cumulativos e mudanças de regime mais graduais.

A combinação dos dois cobre tanto choques abruptos quanto drifts de longo prazo.

---

## Classificação de regimes

**Curva de juros americana** — classificada a partir do spread `T10Y2Y`:

| Regime | Condição |
|---|---|
| `normal` | spread > 0.25 |
| `flat` | \|spread\| ≤ 0.25 |
| `inverted` | spread < 0 |

**Regime macro brasileiro** — classificado a partir da combinação de SELIC, IPCA e USD/BRL:

| Regime | Condição |
|---|---|
| `expansao` | SELIC baixa, IPCA controlado, câmbio apreciado |
| `estabilidade` | condições mistas sem pressão dominante |
| `contracao` | SELIC alta, câmbio depreciado |
| `estagflacao` | SELIC alta + IPCA elevado + câmbio depreciado |

Os thresholds estão explícitos em [`analytics/regime_detector.py`](analytics/regime_detector.py).

---

## Modos de armazenamento

O projeto suporta três modos, configuráveis via variável de ambiente `MACRO_PULSE_STORAGE`:

| Modo | Comportamento |
|---|---|
| `auto` *(padrão)* | Tenta MotherDuck primeiro; em caso de falha, cai para `macro_pulse.db` local em modo leitura e exibe aviso no dashboard |
| `motherduck` | Exige conexão com MotherDuck; falha explicitamente se indisponível |
| `local` | Usa sempre o arquivo local `macro_pulse.db`, sem tentar conexão remota |

Para apontar um arquivo local diferente do padrão, defina `MACRO_PULSE_LOCAL_DB`.

Na primeira conexão com o MotherDuck, o DuckDB baixa extensões e cria cache em `.duckdb_home/` na raiz do projeto. Essa pasta já está no `.gitignore`.

---

## Stack

| Camada | Tecnologia | Papel |
|---|---|---|
| Linguagem | Python 3.11+ | Base do projeto |
| Armazenamento | DuckDB + MotherDuck | Persistência analítica em nuvem com fallback local |
| Ingestão | requests + tenacity | Coleta com retry e backoff automático |
| Analytics | pandas + numpy + scipy | Z-score, CUSUM e preparação de séries |
| Agente LLM | LangChain + Groq + LLaMA 3.3 70B | Geração dos briefings macroeconômicos |
| Dashboard | Streamlit + Altair | Visualização interativa (PT-BR / EN) |
| Scheduler | APScheduler | Jobs diários integrados ao serviço web |
| Configuração | python-dotenv + st.secrets | Segredos locais e em nuvem |
| Testes | pytest | Validação automatizada |
| Lint | ruff | Higiene de código |

---

## Decisões de implementação

**EWZ como proxy do mercado acionário brasileiro**
O símbolo `^BVSP` não retornou série utilizável via Alpha Vantage. O projeto adotou `EWZ` como proxy; por ser negociado em USD, a série também captura parte do efeito cambial, o que é relevante para a leitura macro conjunta.

**Groq no lugar de OpenAI**
A camada de agente foi implementada com Groq para manter compatibilidade com o ecossistema LangChain e eliminar dependência de billing da OpenAI API. O modelo LLaMA 3.3 70B entrega qualidade suficiente para briefings analíticos dentro do tier gratuito.

**DuckDB + MotherDuck no lugar de banco servidor tradicional**
Para este caso de uso, DuckDB entrega simplicidade analítica com SQL nativo sobre DataFrames. O MotherDuck adiciona persistência em nuvem sem exigir operação de banco dedicado, mantendo o `.db` local como fallback natural para desenvolvimento.

**Streamlit Community Cloud como alvo principal de deploy**
A combinação com MotherDuck cobre deploy simples, custo zero e persistência entre publicações com bem menos complexidade operacional do que uma VPS com banco gerenciado.

---

## Testes

| Suite | Cobertura |
|---|---|
| `test_ingestion.py` | Clientes FRED, BCB e Alpha Vantage; upsert e deduplicação no DuckDB |
| `test_analytics.py` | Z-score rolling, CUSUM, detecção de changepoints e classificação de regimes |
| `test_agent.py` | Geração e persistência de briefings; fallback sem chave de API |
| `test_dashboard.py` | Smoke test do Streamlit em modo headless |

```bash
pytest tests/ -v
```

---

## Estrutura do repositório

```
macro-pulse/
├── ingestion/
│   ├── fred_client.py
│   ├── bcb_client.py
│   ├── alpha_vantage_client.py
│   └── loader.py
├── analytics/
│   ├── anomaly_detector.py
│   └── regime_detector.py
├── agent/
│   ├── tools.py
│   └── macro_agent.py
├── scheduler/
│   └── jobs.py
├── scripts/
│   └── seed_motherduck.py
├── tests/
│   ├── test_ingestion.py
│   ├── test_analytics.py
│   ├── test_agent.py
│   └── test_dashboard.py
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── app.py
├── requirements.txt
├── runtime.txt
├── .env.example
├── .gitignore
├── README_DEPLOY.md
└── README.md
```

---

## Instalação local

### Pré-requisitos

- Python 3.11+
- Git
- Token do MotherDuck — ver [Configuração](#configuração)

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/joaoferro710/Macro-Pulse.git
cd Macro-Pulse

# 2. Crie e ative o ambiente virtual
py -3.12 -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # macOS / Linux

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
copy .env.example .env            # Windows
# cp .env.example .env            # macOS / Linux

# 5. Popule o banco com dados históricos (executar uma vez)
python scripts/seed_motherduck.py

# 6. Inicie o dashboard
streamlit run app.py
```

> No Windows, substitua `python` por `.\.venv\Scripts\python` e `streamlit` por `.\.venv\Scripts\streamlit` caso os executáveis não estejam no PATH do ambiente ativo.

---

## Configuração

Preencha o arquivo `.env` com suas chaves. Todas as variáveis disponíveis estão documentadas em `.env.example`.

```env
# Armazenamento
MOTHERDUCK_TOKEN=your_motherduck_token_here
MACRO_PULSE_STORAGE=auto          # auto | motherduck | local
MACRO_PULSE_LOCAL_DB=macro_pulse.db

# APIs externas
FRED_API_KEY=your_fred_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

| Variável | Onde obter | Custo |
|---|---|---|
| `MOTHERDUCK_TOKEN` | [app.motherduck.com](https://app.motherduck.com) | Gratuito até 10 GB |
| `FRED_API_KEY` | [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html) | Gratuito |
| `ALPHA_VANTAGE_API_KEY` | [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) | Gratuito (25 req/dia) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Gratuito |

---

## Uso

```bash
# Seed inicial do banco (apenas na primeira vez)
python scripts/seed_motherduck.py

# Ingestão manual de dados
python -m ingestion.loader

# Gerar briefing via linha de comando
python -m agent.macro_agent

# Iniciar o scheduler de jobs diários
python -m scheduler.jobs

# Iniciar o dashboard
streamlit run app.py

# Smoke test do dashboard (modo headless)
streamlit run app.py --server.headless true

# Rodar os testes
pytest tests/ -v

# Lint
ruff check .
```

---

## Deploy no Streamlit Community Cloud

O repositório já inclui todos os arquivos necessários. O fluxo completo está documentado em [`README_DEPLOY.md`](README_DEPLOY.md).

Resumo dos passos:

1. Publique o repositório no GitHub
2. Execute o seed inicial: `python scripts/seed_motherduck.py`
3. Acesse [share.streamlit.io](https://share.streamlit.io) e crie um novo app
4. Conecte o repositório e defina `app.py` como arquivo principal
5. Em **Advanced settings → Secrets**, adicione `MOTHERDUCK_TOKEN`, `GROQ_API_KEY`, `FRED_API_KEY` e `ALPHA_VANTAGE_KEY`
6. Dispare o deploy — o app ficará disponível em uma URL pública do Streamlit

**Custo total: R$ 0,00.** Todos os serviços utilizam tier gratuito suficiente para este caso de uso.

---

## Próximos passos

- [ ] Alertas por e-mail quando anomalias críticas forem detectadas
- [ ] Cobertura adicional de commodities e juros longos
- [ ] Histórico pesquisável de briefings gerados
- [ ] Backtesting de eventos macro contra as anomalias detectadas
- [ ] Autenticação simples para controle de acesso ao dashboard

---

## Contribuindo

Sugestões e issues são bem-vindas. Abra uma [issue](https://github.com/joaoferro710/Macro-Pulse/issues) descrevendo o problema ou a melhoria antes de submeter um PR.

---

## Licença

Distribuído sob a licença MIT. Veja [`LICENSE`](LICENSE) para mais detalhes.
