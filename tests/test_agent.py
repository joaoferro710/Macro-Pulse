"""Tests for macro briefing generation and retrieval."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from agent import macro_agent


class FakeExecutor:
    """Small fake executor used to mock LangChain agent execution."""

    def invoke(self, inputs: dict) -> dict:
        """Return a deterministic briefing payload."""

        topic = inputs["topic"]
        return {
            "output": (
                f"Briefing sobre {topic}. "
                "Federal Funds Rate em 4.33 em 2025-04-01. "
                "SELIC em 14.75 em 2026-04-09. "
                "USD/BRL em 5.09 em 2026-04-08. "
                "T10Y2Y em 0.50 em 2026-04-08. "
                "IPCA 12m em 3.81 em 2026-02-01. "
                "SPY e EWZ mostram relação relevante. "
                "Pontos de atenção: inflação, juros e câmbio."
            )
        }


def _temp_connection_factory(db_path: Path):
    """Create a reusable connection factory for a temporary DuckDB database."""

    def _connect():
        return duckdb.connect(str(db_path))

    return _connect


def test_generate_briefing_saves_to_duckdb(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """generate_briefing should persist the generated content in DuckDB."""

    temp_db = tmp_path / "macro_agent_test.db"
    monkeypatch.setattr(macro_agent, "get_connection", _temp_connection_factory(temp_db))
    monkeypatch.setattr(macro_agent, "_build_agent_executor", lambda: FakeExecutor())
    monkeypatch.setattr(macro_agent, "_ensure_minimum_briefing_quality", lambda content: content)

    content = macro_agent.generate_briefing("Brasil")
    latest = macro_agent.get_latest_briefing()

    assert "Federal Funds Rate" in content
    assert latest is not None
    assert latest["topic"] == "Brasil"
    assert "SELIC" in latest["content"]


def test_get_latest_briefing_returns_most_recent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """get_latest_briefing should return the most recent stored briefing."""

    temp_db = tmp_path / "macro_agent_latest.db"
    monkeypatch.setattr(macro_agent, "get_connection", _temp_connection_factory(temp_db))

    macro_agent.initialize_briefings_table()
    with macro_agent.get_connection() as connection:
        connection.execute(
            """
            INSERT INTO briefings (id, topic, content, generated_at)
            VALUES
                ('1', 'antigo', 'briefing antigo', TIMESTAMP '2026-04-08 08:00:00'),
                ('2', 'novo', 'briefing novo', TIMESTAMP '2026-04-09 08:00:00')
            """
        )

    latest = macro_agent.get_latest_briefing()

    assert latest is not None
    assert latest["id"] == "2"
    assert latest["topic"] == "novo"
