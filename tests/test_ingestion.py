"""Tests for ingestion clients and DuckDB initialization."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import duckdb
import pytest

from ingestion import alpha_vantage_client, bcb_client, fred_client, loader


def _workspace_temp_path(name: str, suffix: str) -> Path:
    return Path.cwd() / f".test_ingestion_{name}_{uuid4().hex}{suffix}"


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
    monkeypatch: pytest.MonkeyPatch,
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

    temp_cache = _workspace_temp_path("alpha_cache", ".json")
    try:
        monkeypatch.setattr(alpha_vantage_client, "CACHE_PATH", temp_cache)
        monkeypatch.setattr(alpha_vantage_client, "_get_api_key", lambda: "test-key")
        monkeypatch.setattr(alpha_vantage_client.requests, "get", lambda *args, **kwargs: MockResponse())

        dataframe = alpha_vantage_client.fetch_equity("SPY", "2024-01-01")

        assert not dataframe.empty
        assert list(dataframe.columns) == ["date", "series_id", "value", "source"]
        assert dataframe["series_id"].eq("SPY").all()
        assert dataframe["source"].eq("ALPHA_VANTAGE").all()
    finally:
        temp_cache.unlink(missing_ok=True)


def test_initialize_db_creates_economic_indicators_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DuckDB initialization should create the economic_indicators table."""

    temp_db = _workspace_temp_path("macro_pulse_test", ".db")
    try:
        monkeypatch.setattr(loader, "get_connection", lambda: duckdb.connect(str(temp_db)))

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
    finally:
        temp_db.unlink(missing_ok=True)


def test_configure_duckdb_home_redirects_home_to_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DuckDB home should be redirected to a writable project-local directory."""

    redirected_home = _workspace_temp_path("duckdb_home", "")
    try:
        monkeypatch.setenv("MACRO_PULSE_DUCKDB_HOME", str(redirected_home))

        configured_path = loader._configure_duckdb_home()

        assert configured_path == redirected_home.resolve()
        assert redirected_home.exists()
        assert os.environ["HOME"] == str(redirected_home.resolve())
        assert os.environ["USERPROFILE"] == str(redirected_home.resolve())
    finally:
        if redirected_home.exists():
            for child in redirected_home.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            redirected_home.rmdir()


def test_get_connection_uses_local_storage_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local mode should open the configured project-local DuckDB file."""

    temp_db = _workspace_temp_path("macro_pulse_local", ".db")
    try:
        with duckdb.connect(str(temp_db)) as connection:
            connection.execute("CREATE TABLE economic_indicators (date DATE, series_id VARCHAR)")

        monkeypatch.setenv("MACRO_PULSE_STORAGE", "local")
        monkeypatch.setenv("MACRO_PULSE_LOCAL_DB", str(temp_db))

        with loader.get_connection(read_only=True) as connection:
            tables = connection.execute("SHOW TABLES").fetchall()

        assert ("economic_indicators",) in tables
        assert loader.get_active_backend()["kind"] == "local"
    finally:
        temp_db.unlink(missing_ok=True)


def test_get_connection_falls_back_to_local_when_motherduck_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto mode should fall back to the local database if MotherDuck fails."""

    temp_db = _workspace_temp_path("macro_pulse_fallback", ".db")
    try:
        with duckdb.connect(str(temp_db)) as connection:
            connection.execute("CREATE TABLE economic_indicators (date DATE, series_id VARCHAR)")

        monkeypatch.delenv("MACRO_PULSE_STORAGE", raising=False)
        monkeypatch.setenv("MACRO_PULSE_LOCAL_DB", str(temp_db))
        monkeypatch.setattr(loader, "_get_motherduck_connection", lambda: (_ for _ in ()).throw(RuntimeError("offline")))

        with loader.get_connection(read_only=True) as connection:
            tables = connection.execute("SHOW TABLES").fetchall()

        backend = loader.get_active_backend()
        assert ("economic_indicators",) in tables
        assert backend["kind"] == "local"
        assert "read-only" in (backend["detail"] or "")
    finally:
        temp_db.unlink(missing_ok=True)
