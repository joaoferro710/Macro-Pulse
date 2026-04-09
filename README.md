# macro-pulse

Macro Pulse e um agente de inteligencia macroeconomica que coleta indicadores reais de fontes publicas, consolida tudo em DuckDB e transforma essas series em sinais acionaveis para acompanhamento de mercados. O projeto foi construido como peca de portfolio com foco em engenharia de dados leve, analytics quantitativo e automacao de narrativas economicas.

O pipeline combina ingestao incremental, deteccao de anomalias, classificacao de regimes macroeconomicos e geracao de briefings por LLM. O resultado e um fluxo enxuto, reproduzivel e facil de demonstrar em GitHub e LinkedIn, sem depender de infraestrutura pesada para funcionar localmente.

## Arquitetura

```text
APIs Publicas
├── FRED
├── Banco Central do Brasil (SGS)
└── Alpha Vantage
        |
        v
ingestion/
├── fred_client.py
├── bcb_client.py
├── alpha_vantage_client.py
└── loader.py
        |
        v
DuckDB (macro_pulse.db)
        |
        +--> analytics/
        |    ├── anomaly_detector.py
        |    └── regime_detector.py
        |
        +--> agent/
        |    ├── tools.py
        |    └── macro_agent.py
        |
        +--> dashboard/
        |    └── app.py
        |
        +--> scheduler/
             └── jobs.py
```

## Instalacao

1. Clone o repositorio:
   ```bash
   git clone <seu-repositorio>
   cd macro-pulse
   ```
2. Crie e ative um ambiente virtual:
   ```bash
   py -3.12 -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Instale as dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Copie o arquivo de exemplo de ambiente:
   ```bash
   copy .env.example .env
   ```
5. Preencha as chaves no `.env`.
6. Rode a ingestao inicial:
   ```bash
   python -m ingestion.loader
   ```

## Configuracao de API Keys

Preencha o arquivo `.env` com:

```env
FRED_API_KEY=your_fred_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

Onde obter:
- `FRED_API_KEY`: https://fred.stlouisfed.org/docs/api/api_key.html
- `ALPHA_VANTAGE_API_KEY`: https://www.alphavantage.co/support/#api-key
- `GROQ_API_KEY`: https://console.groq.com

## Rodando o Dashboard

Use o comando abaixo:

```bash
streamlit run dashboard/app.py
```

O dashboard exibe:
- cards com os indicadores mais recentes
- grafico temporal com anomalias destacadas
- status das fontes e regimes macroeconomicos
- briefing gerado pelo agente LLM

## Rodando os Testes

Execute:

```bash
pytest tests/ -v
```

## Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.12 |
| Armazenamento | DuckDB |
| Ingestao | Requests + Tenacity |
| Analytics | pandas, numpy, scipy |
| Agente LLM | LangChain + Groq + LLaMA 3.3 70B |
| Dashboard | Streamlit + Altair |
| Scheduler | APScheduler |
| Testes | pytest |
| Lint | ruff |

## Notas de Implementacao

- Nota de implementacao: o simbolo `^BVSP` nao retornou serie utilizavel via Alpha Vantage. Foi adotado `EWZ` (`iShares MSCI Brazil ETF`) como proxy do mercado acionario brasileiro. `EWZ` e negociado em USD na NYSE e reflete tanto o desempenho das principais empresas brasileiras quanto o efeito cambial.
- Nota de implementacao: a fase de geracao de briefing foi adaptada de OpenAI para Groq para permitir uso em camada gratuita com API compativel com o ecossistema LangChain.

## Screenshot

Adicione aqui uma captura de tela do dashboard depois de publicar ou gravar sua demonstracao.
