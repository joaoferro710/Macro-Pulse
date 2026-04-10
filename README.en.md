# Macro Pulse

[🇧🇷 Português](README.md) | [🇺🇸 English](README.en.md)

> AI-powered macroeconomic intelligence agent that ingests real-world indicators, detects statistical anomalies, and generates daily analytical briefings through an LLM.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-MotherDuck-FFF000?style=flat&logo=duckdb&logoColor=black)
![LangChain](https://img.shields.io/badge/LangChain-Groq-1C3C3C?style=flat&logo=langchain&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat)

---

## Demo

![Macro Pulse dashboard demo](docs/media/Macro-pulse.gif)

---

## Overview

The U.S. interest-rate cycle directly affects capital flows into emerging markets. When the Fed tightens monetary policy, yield differentials shrink, the dollar strengthens, and pressure on the Brazilian exchange rate and SELIC increases. Monitoring this mechanism in real time requires consolidating data from multiple sources, identifying relevant statistical deviations, and translating them into actionable language, a workflow that is still largely manual.

Macro Pulse automates this pipeline end to end:

- **Incremental ingestion** from public APIs (FRED, BCB/SGS, Alpha Vantage)
- **Analytical persistence** in DuckDB hosted on MotherDuck, with automatic local fallback
- **Statistical anomaly detection** through rolling Z-score and CUSUM
- **Macroeconomic regime classification** for the U.S. and Brazil
- **Briefing generation** through an LLM agent with LangChain + Groq + LLaMA 3.3 70B
- **Interactive dashboard** in Streamlit with PT-BR and EN support

The project was designed as a professional portfolio case, with organized code, a reproducible workflow, and a structure close to a production environment.

---

## Architecture

```
Public APIs
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

## Monitored Indicators

### United States - FRED

| Series | Description |
|---|---|
| `FEDFUNDS` | Federal Reserve interest rate |
| `CPIAUCSL` | CPI inflation |
| `UNRATE` | Unemployment rate |
| `GDP` | Quarterly GDP |
| `T10Y2Y` | 10Y-2Y yield curve spread |

### Brazil - Central Bank (SGS)

| Code | Description |
|---|---|
| `432` | SELIC rate |
| `13522` | 12-month accumulated IPCA |
| `1` | USD/BRL exchange rate |
| `4380` | GDP - quarterly change |

### Market - Alpha Vantage

| Symbol | Description |
|---|---|
| `EWZ` | iShares MSCI Brazil ETF (Ibovespa proxy) |
| `SPY` | SPDR S&P 500 ETF |
| `USD/BRL` | FX data through the FX Monthly endpoint |

---

## Anomaly Detection

Two statistical algorithms are applied to each stored time series:

**Rolling Z-score** - uses a moving window to identify observations that materially deviate from recent behavior. Effective for capturing isolated spikes and drops.

**CUSUM** - identifies persistent changes in the mean level of the series, even when the movement does not appear as a point outlier. Effective for capturing cumulative deviations and more gradual regime shifts.

The combination of both methods covers abrupt shocks as well as longer-term drifts.

---

## Regime Classification

**U.S. yield curve** - classified from the `T10Y2Y` spread:

| Regime | Condition |
|---|---|
| `normal` | spread > 0.25 |
| `flat` | \|spread\| <= 0.25 |
| `inverted` | spread < 0 |

**Brazilian macro regime** - classified from the combination of SELIC, IPCA, and USD/BRL:

| Regime | Condition |
|---|---|
| `expansao` | low SELIC, controlled inflation, appreciated FX |
| `estabilidade` | mixed conditions with no dominant pressure |
| `contracao` | high SELIC, depreciated FX |
| `estagflacao` | high SELIC + elevated IPCA + depreciated FX |

Thresholds are explicitly defined in [`analytics/regime_detector.py`](analytics/regime_detector.py).

---

## Storage Modes

The project supports three modes, configurable through the `MACRO_PULSE_STORAGE` environment variable:

| Mode | Behavior |
|---|---|
| `auto` *(default)* | Tries MotherDuck first; if it fails, falls back to local `macro_pulse.db` in read-only mode and shows a dashboard warning |
| `motherduck` | Requires a MotherDuck connection and fails explicitly if unavailable |
| `local` | Always uses the local `macro_pulse.db` file without trying a remote connection |

To point to a different local database file, define `MACRO_PULSE_LOCAL_DB`.

On the first MotherDuck connection, DuckDB downloads extensions and creates a cache under `.duckdb_home/` at the project root. That folder is already listed in `.gitignore`.

---

## Stack

| Layer | Technology | Role |
|---|---|---|
| Language | Python 3.11+ | Project foundation |
| Storage | DuckDB + MotherDuck | Cloud analytical persistence with local fallback |
| Ingestion | requests + tenacity | Data collection with retry and backoff |
| Analytics | pandas + numpy + scipy | Z-score, CUSUM, and time-series preparation |
| LLM Agent | LangChain + Groq + LLaMA 3.3 70B | Macroeconomic briefing generation |
| Dashboard | Streamlit + Altair | Interactive visualization (PT-BR / EN) |
| Scheduler | APScheduler | Daily jobs integrated into the web service |
| Configuration | python-dotenv + st.secrets | Local and cloud secrets |
| Tests | pytest | Automated validation |
| Lint | ruff | Code hygiene |

---

## Implementation Decisions

**EWZ as a proxy for the Brazilian equity market**  
The `^BVSP` symbol did not return a usable series through Alpha Vantage. The project adopted `EWZ` as a proxy; since it is traded in USD, the series also captures part of the FX effect, which is relevant for the combined macro view.

**Groq instead of OpenAI**  
The agent layer was implemented with Groq to keep compatibility with the LangChain ecosystem and remove dependency on OpenAI API billing. The LLaMA 3.3 70B model delivers sufficient quality for analytical briefings within the free tier.

**DuckDB + MotherDuck instead of a traditional server database**  
For this use case, DuckDB provides analytical simplicity with native SQL over DataFrames. MotherDuck adds cloud persistence without requiring a dedicated database operation, while keeping the local `.db` file as a natural development fallback.

**Streamlit Community Cloud as the main deployment target**  
Combined with MotherDuck, it offers simple deployment, zero cost, and persistence across releases with much less operational complexity than a VPS plus managed database.

---

## Tests

| Suite | Coverage |
|---|---|
| `test_ingestion.py` | FRED, BCB, and Alpha Vantage clients; upsert and deduplication in DuckDB |
| `test_analytics.py` | Rolling Z-score, CUSUM, changepoint detection, and regime classification |
| `test_agent.py` | Briefing generation and persistence; fallback without API key |
| `test_dashboard.py` | Headless Streamlit smoke test |

```bash
pytest tests/ -v
```

---

## Repository Structure

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
├── README.md
└── README.en.md
```

---

## Local Setup

### Prerequisites

- Python 3.11+
- Git
- MotherDuck token - see [Configuration](#configuration)

### Step by Step

```bash
# 1. Clone the repository
git clone https://github.com/joaoferro710/Macro-Pulse.git
cd Macro-Pulse

# 2. Create and activate the virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env            # Windows
# cp .env.example .env            # macOS / Linux

# 5. Seed the database with historical data (run once)
python scripts/seed_motherduck.py

# 6. Start the dashboard
streamlit run app.py
```

> On Windows, replace `python` with `.\.venv\Scripts\python` and `streamlit` with `.\.venv\Scripts\streamlit` if the executables are not available in the active environment PATH.

---

## Configuration

Fill in the `.env` file with your keys. All available variables are documented in `.env.example`.

```env
# Storage
MOTHERDUCK_TOKEN=your_motherduck_token_here
MACRO_PULSE_STORAGE=auto          # auto | motherduck | local
MACRO_PULSE_LOCAL_DB=macro_pulse.db

# External APIs
FRED_API_KEY=your_fred_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

| Variable | Where to get it | Cost |
|---|---|---|
| `MOTHERDUCK_TOKEN` | [app.motherduck.com](https://app.motherduck.com) | Free up to 10 GB |
| `FRED_API_KEY` | [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html) | Free |
| `ALPHA_VANTAGE_API_KEY` | [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) | Free (25 req/day) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Free |

---

## Usage

```bash
# Initial database seed (first time only)
python scripts/seed_motherduck.py

# Manual data ingestion
python -m ingestion.loader

# Generate briefing from the command line
python -m agent.macro_agent

# Start the daily job scheduler
python -m scheduler.jobs

# Start the dashboard
streamlit run app.py

# Dashboard smoke test (headless mode)
streamlit run app.py --server.headless true

# Run tests
pytest tests/ -v

# Lint
ruff check .
```

---

## Deploy on Streamlit Community Cloud

The repository already includes all required files. The full deployment flow is documented in [`README_DEPLOY.md`](README_DEPLOY.md).

Deployment summary:

1. Publish the repository to GitHub
2. Run the initial seed: `python scripts/seed_motherduck.py`
3. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app
4. Connect the repository and set `app.py` as the main file
5. In **Advanced settings -> Secrets**, add `MOTHERDUCK_TOKEN`, `GROQ_API_KEY`, `FRED_API_KEY`, and `ALPHA_VANTAGE_KEY`
6. Trigger the deployment - the app will be available at a public Streamlit URL

**Total cost: R$ 0.00.** All services use free tiers that are sufficient for this use case.

---

## Next Steps

- [ ] Email alerts when critical anomalies are detected
- [ ] Additional coverage for commodities and long-term rates
- [ ] Searchable history of generated briefings
- [ ] Backtesting macro events against detected anomalies
- [ ] Simple authentication for dashboard access control

---

## Contributing

Suggestions and issues are welcome. Open an [issue](https://github.com/joaoferro710/Macro-Pulse/issues) describing the problem or improvement before submitting a PR.

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more details.
