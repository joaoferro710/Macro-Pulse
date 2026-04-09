"""Tests for dashboard data assembly and read paths."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd
import pytest

from dashboard import app as dashboard_app


def _workspace_temp_file(name: str) -> Path:
    return Path.cwd() / f".test_dashboard_{name}_{uuid4().hex}.db"


def _seed_dashboard_db(db_path: Path) -> None:
    with duckdb.connect(str(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE economic_indicators (
                date DATE NOT NULL,
                series_id VARCHAR NOT NULL,
                series_name VARCHAR NOT NULL,
                value DOUBLE NOT NULL,
                source VARCHAR NOT NULL,
                loaded_at TIMESTAMP DEFAULT current_timestamp
            )
            """
        )
        connection.execute(
            """
            INSERT INTO economic_indicators (date, series_id, series_name, value, source, loaded_at)
            VALUES
                ('2026-01-31', 'SPY', 'S&P 500 ETF', 100.0, 'ALPHA_VANTAGE', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-02-28', 'SPY', 'S&P 500 ETF', 104.0, 'ALPHA_VANTAGE', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-03-31', 'SPY', 'S&P 500 ETF', 108.0, 'ALPHA_VANTAGE', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-04-09', 'SPY', 'S&P 500 ETF', 112.0, 'ALPHA_VANTAGE', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-01-31', 'EWZ', 'iShares MSCI Brazil ETF (Ibovespa proxy)', 50.0, 'ALPHA_VANTAGE', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-02-28', 'EWZ', 'iShares MSCI Brazil ETF (Ibovespa proxy)', 51.5, 'ALPHA_VANTAGE', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-03-31', 'EWZ', 'iShares MSCI Brazil ETF (Ibovespa proxy)', 53.0, 'ALPHA_VANTAGE', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-04-09', 'EWZ', 'iShares MSCI Brazil ETF (Ibovespa proxy)', 54.5, 'ALPHA_VANTAGE', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-04-09', 'T10Y2Y', 'US Treasury Yield Spread 10Y-2Y', 0.35, 'FRED', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-04-09', '432', 'Taxa SELIC', 10.5, 'BCB', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-04-09', '13522', 'IPCA acumulado 12 meses', 4.2, 'BCB', TIMESTAMP '2026-04-09 09:00:00'),
                ('2026-04-09', '1', 'USD/BRL', 5.1, 'BCB', TIMESTAMP '2026-04-09 09:00:00')
            """
        )


def test_indicator_catalog_and_source_status_read_from_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dashboard cached queries should read the expected metadata from DuckDB."""

    temp_db = _workspace_temp_file("dashboard_test")
    try:
        _seed_dashboard_db(temp_db)
        dashboard_app.indicator_catalog.clear()
        dashboard_app.source_status.clear()

        monkeypatch.setattr(
            dashboard_app,
            "get_connection",
            lambda read_only=True: duckdb.connect(str(temp_db), read_only=read_only),
        )

        catalog = dashboard_app.indicator_catalog()
        status = dashboard_app.source_status()

        assert list(catalog["series_id"])[:4] == ["T10Y2Y", "432", "13522", "1"]
        assert set(status["source"]) == {"ALPHA_VANTAGE", "BCB", "FRED"}
    finally:
        temp_db.unlink(missing_ok=True)


def test_investment_comparison_returns_two_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Investment comparison should build a two-row table for EWZ and SPY."""

    spy = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-09"]),
            "series_id": ["SPY"] * 4,
            "series_name": ["S&P 500 ETF"] * 4,
            "value": [100.0, 104.0, 108.0, 112.0],
            "source": ["ALPHA_VANTAGE"] * 4,
            "loaded_at": pd.to_datetime(["2026-04-09"] * 4),
        }
    )
    ewz = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-09"]),
            "series_id": ["EWZ"] * 4,
            "series_name": ["iShares MSCI Brazil ETF (Ibovespa proxy)"] * 4,
            "value": [50.0, 51.5, 53.0, 54.5],
            "source": ["ALPHA_VANTAGE"] * 4,
            "loaded_at": pd.to_datetime(["2026-04-09"] * 4),
        }
    )

    def fake_get_series(series_id: str, n_periods: int = 60) -> pd.DataFrame:
        frame = {"SPY": spy, "EWZ": ewz}[series_id]
        return frame.tail(n_periods).reset_index(drop=True)

    def fake_analyze_series(series_id: str, n_periods: int = 36) -> dict[str, pd.DataFrame]:
        frame = fake_get_series(series_id, n_periods).copy()
        frame["zscore"] = 0.0
        frame["is_anomaly"] = False
        return {"zscore_result": frame}

    monkeypatch.setattr(dashboard_app, "get_series", fake_get_series)
    monkeypatch.setattr(dashboard_app, "analyze_series", fake_analyze_series)
    monkeypatch.setattr(
        dashboard_app,
        "get_global_macro_snapshot",
        lambda: {
            "as_of_date": "2026-04-09",
            "united_states": {"current_regime": "normal"},
            "brazil": {"current_regime": "estabilidade"},
        },
    )
    dashboard_app.investment_comparison.clear()

    comparison = dashboard_app.investment_comparison()

    assert list(comparison["table"]["series_id"]) == ["SPY", "EWZ"]
    assert comparison["winner"]["series_id"] == "SPY"
    assert not comparison["evolution"].empty
