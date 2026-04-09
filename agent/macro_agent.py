"""LLM-powered macro briefing generation built on LangChain and Groq."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq

from analytics.anomaly_detector import analyze_series
from analytics.regime_detector import get_global_macro_snapshot
from agent.tools import build_tools
from ingestion.loader import get_connection, get_series

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

SYSTEM_PROMPT = """
Você é um analista macroeconômico sênior especializado em mercados emergentes,
com foco em Brasil e correlações com o ciclo econômico dos EUA.

Seu trabalho é gerar briefings econômicos concisos, precisos e acionáveis,
baseados exclusivamente nos dados fornecidos pelas ferramentas disponíveis.

Ao gerar um briefing:
- Sempre cite os valores mais recentes com suas datas
- Destaque anomalias detectadas e o que elas podem sinalizar
- Conecte indicadores dos EUA com possíveis impactos no Brasil
- Seja direto: termine com 2-3 pontos de atenção para a próxima semana
- Não especule além dos dados disponíveis
- Use linguagem profissional mas acessível
""".strip()


def _ensure_groq_api_key() -> str:
    """Return the configured Groq API key or raise a helpful error."""

    load_dotenv(dotenv_path=ENV_PATH)
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured. Add it to your .env file.")
    return api_key


def initialize_briefings_table() -> None:
    """Create the DuckDB table used to store generated briefings."""

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS briefings (
                id VARCHAR PRIMARY KEY,
                topic VARCHAR NOT NULL,
                content TEXT NOT NULL,
                generated_at TIMESTAMP DEFAULT current_timestamp
            )
            """
        )


def _build_agent_executor() -> AgentExecutor:
    """Create the LangChain agent executor used for briefing generation."""

    api_key = _ensure_groq_api_key()
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        api_key=api_key,
    )
    tools = build_tools()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            (
                "human",
                (
                    "Gere um briefing macroeconômico sobre o tópico: {topic}.\n"
                    "Use as ferramentas para buscar dados reais antes de concluir.\n"
                    "O briefing final deve ter entre 220 e 320 palavras.\n"
                    "Estruture a resposta com 2-3 parágrafos analíticos e feche com 2-3 pontos de atenção.\n"
                    "Mencione pelo menos 3 indicadores com valores reais e datas."
                ),
            ),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=8)


def _save_briefing(topic: str, content: str) -> None:
    """Persist one generated briefing in DuckDB."""

    initialize_briefings_table()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO briefings (id, topic, content)
            VALUES (?, ?, ?)
            """,
            [str(uuid4()), topic, content],
        )


def _build_supporting_context() -> str:
    """Build a deterministic factual appendix from the stored macro data."""

    indicator_ids = ["FEDFUNDS", "CPIAUCSL", "UNRATE", "432", "13522", "1"]
    indicator_lines: list[str] = []
    for series_id in indicator_ids:
        dataframe = get_series(series_id=series_id, n_periods=2)
        if dataframe.empty:
            continue
        latest = dataframe.iloc[-1]
        indicator_lines.append(
            f"- {latest['series_name']} ({series_id}): {float(latest['value']):.2f} em "
            f"{latest['date']}"
        )

    anomaly_lines: list[str] = []
    for series_id in ["T10Y2Y", "USD/BRL", "432"]:
        try:
            analysis = analyze_series(series_id=series_id, n_periods=60)
        except ValueError:
            continue
        anomaly_lines.append(
            f"- {analysis['series_name']} ({series_id}): "
            f"{analysis['zscore_anomalies']} anomalias por Z-score, "
            f"{analysis['cusum_changepoints']} mudanças por CUSUM, "
            f"último valor {analysis['latest_value']:.2f} em {analysis['latest_date']}"
        )

    snapshot = get_global_macro_snapshot()
    support_sections = [
        "Contexto factual adicional baseado no banco local:",
        "Indicadores recentes:",
        *indicator_lines,
        "Alertas quantitativos recentes:",
        *anomaly_lines,
        (
            "Regimes atuais: "
            f"EUA em {snapshot['united_states']['current_regime']} desde "
            f"{snapshot['united_states']['regime_start_date']}; "
            f"Brasil em {snapshot['brazil']['current_regime']} na data de "
            f"{snapshot['brazil']['latest_date']}."
        ),
    ]
    return "\n".join(support_sections)


def _ensure_minimum_briefing_quality(content: str) -> str:
    """Expand the stored briefing with deterministic facts when it is too short."""

    word_count = len(content.split())
    if word_count >= 200:
        return content

    appendix = _build_supporting_context()
    return f"{content.strip()}\n\n{appendix}".strip()


def generate_briefing(topic: str = "visão geral") -> str:
    """Generate and store a macro briefing for the requested topic.

    Parameters
    ----------
    topic:
        Topic that should guide the economic briefing.

    Returns
    -------
    str
        Generated briefing text.
    """

    initialize_briefings_table()
    executor = _build_agent_executor()
    result: dict[str, Any] = executor.invoke({"topic": topic})
    content = _ensure_minimum_briefing_quality(str(result["output"]).strip())
    _save_briefing(topic=topic, content=content)
    LOGGER.info("Generated briefing for topic: %s", topic)
    return content


def get_latest_briefing() -> dict[str, Any] | None:
    """Return the latest generated briefing stored in DuckDB.

    Returns
    -------
    dict[str, Any] | None
        Latest briefing row or ``None`` when no briefing exists yet.
    """

    initialize_briefings_table()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, topic, content, generated_at
            FROM briefings
            ORDER BY generated_at DESC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "topic": row[1],
        "content": row[2],
        "generated_at": row[3],
    }


def main() -> None:
    """Generate and print a default macro briefing from the command line."""

    briefing = generate_briefing()
    print(briefing)


if __name__ == "__main__":
    main()
