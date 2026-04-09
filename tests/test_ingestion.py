"""Tests for ingestion clients and DuckDB initialization."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest

from ingestion import alpha_vantage_client, bcb_client, fred_client, loader


def test_fred_fetch_series_returns_expected_columns() -> None:
    """FRED should return a non-empty dataframe with the shared schema."""

    if not os.getenv("FRED_API_KEY") and not Path(".env").exists():
        pytest.skip("FRED_API_KEY is not configured for live ingestion testing.")

    dataframe = fred_client.fetch_series("FEDFUNDS", "2024-01-01", "2024-12-31")

    assert not dataframe.empty
    assert list(dataframe.columns) == ["date", "series_id", "value", "source"]
    assert dataframe["series_id"].eq("FEDFUNDS").all()
    assert dataframe["source"].eq("FRED").all()


def test_bcb_fetch_series_returns_non_empty_dataframe() -> None:
    """BCB should return a non-empty dataframe for a public series."""

    dataframe = bcb_client.fetch_series(432, "2024-01-01", "2024-12-31")

    assert not dataframe.empty
    assert set(dataframe.columns) == {"date", "series_id", "value", "source"}
    assert dataframe["series_id"].eq("432").all()
    assert dataframe["source"].eq("BCB").all()


def test_alpha_vantage_fetch_equity_uses_mocked_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Alpha Vantage equity fetch should parse the expected monthly payload."""

    class MockResponse:
        """Simple mock response for the Alpha Vantage client."""

        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "Monthly Time Series": {
                    "2024-02-29": {"4. close": "102.50"},
                    "2024-01-31": {"4. close": "100.00"},
                }
            }

    monkeypatch.setattr(alpha_vantage_client, "CACHE_PATH", tmp_path / "alpha_cache.json")
    monkeypatch.setattr(alpha_vantage_client, "_get_api_key", lambda: "test-key")
    monkeypatch.setattr(alpha_vantage_client.requests, "get", lambda *args, **kwargs: MockResponse())

    dataframe = alpha_vantage_client.fetch_equity("SPY", "2024-01-01")

    assert not dataframe.empty
    assert list(dataframe.columns) == ["date", "series_id", "value", "source"]
    assert dataframe["series_id"].eq("SPY").all()
    assert dataframe["source"].eq("ALPHA_VANTAGE").all()


def test_initialize_db_creates_economic_indicators_table(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """DuckDB initialization should create the economic_indicators table."""

    temp_db = tmp_path / "macro_pulse_test.db"
    monkeypatch.setattr(loader, "DB_PATH", temp_db)

    loader.initialize_db()

    with duckdb.connect(str(temp_db)) as connection:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'economic_indicators'
            """
        ).fetchone()[0]

    assert count == 1
