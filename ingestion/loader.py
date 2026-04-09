"""Coordinators for loading macroeconomic data into DuckDB."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Callable

import duckdb
import pandas as pd

from ingestion.alpha_vantage_client import AlphaVantageAPIError, fetch_equity, fetch_fx
from ingestion.bcb_client import BCBAPIError, fetch_series as fetch_bcb_series
from ingestion.fred_client import FREDAPIError, fetch_series as fetch_fred_series

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "macro_pulse.db"

FRED_SERIES = {
    "FEDFUNDS": "Federal Funds Rate",
    "CPIAUCSL": "US Consumer Price Index",
    "UNRATE": "US Unemployment Rate",
    "GDP": "US Gross Domestic Product",
    "T10Y2Y": "US Treasury Yield Spread 10Y-2Y",
}

BCB_SERIES = {
    "432": "Taxa SELIC",
    "13522": "IPCA acumulado 12 meses",
    "1": "USD/BRL",
    "4380": "PIB Brasil variacao trimestral",
}

ALPHA_VANTAGE_SERIES = {
    "EWZ": "iShares MSCI Brazil ETF (Ibovespa proxy)",
    "SPY": "S&P 500 ETF",
    "USD/BRL": "USD/BRL Alpha Vantage",
}


def get_connection() -> duckdb.DuckDBPyConnection:
    """Create and return a connection to the local DuckDB database."""

    return duckdb.connect(str(DB_PATH))


def initialize_db() -> None:
    """Create the DuckDB database and economic indicators table if needed."""

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS economic_indicators (
                date DATE NOT NULL,
                series_id VARCHAR NOT NULL,
                series_name VARCHAR NOT NULL,
                value DOUBLE NOT NULL,
                source VARCHAR NOT NULL,
                loaded_at TIMESTAMP DEFAULT current_timestamp,
                PRIMARY KEY (date, series_id)
            )
            """
        )


def _upsert_dataframe(dataframe: pd.DataFrame) -> int:
    """Insert or replace indicator rows into DuckDB and return affected row count."""

    if dataframe.empty:
        return 0

    ordered = dataframe.loc[:, ["date", "series_id", "series_name", "value", "source"]].copy()
    ordered["date"] = pd.to_datetime(ordered["date"]).dt.date

    with get_connection() as connection:
        connection.register("indicator_batch", ordered)
        connection.execute(
            """
            INSERT OR REPLACE INTO economic_indicators (date, series_id, series_name, value, source)
            SELECT date, series_id, series_name, value, source
            FROM indicator_batch
            """
        )
        connection.unregister("indicator_batch")

    return len(ordered)


def _fetch_fred_bundle(start_date: str, end_date: str) -> list[pd.DataFrame]:
    """Fetch all configured FRED series and return normalized dataframes."""

    frames: list[pd.DataFrame] = []
    for series_id, series_name in FRED_SERIES.items():
        frame = fetch_fred_series(series_id=series_id, start_date=start_date, end_date=end_date)
        frame["series_name"] = series_name
        frames.append(frame)
    return frames


def _fetch_bcb_bundle(start_date: str, end_date: str) -> list[pd.DataFrame]:
    """Fetch all configured BCB series and return normalized dataframes."""

    frames: list[pd.DataFrame] = []
    for series_id, series_name in BCB_SERIES.items():
        frame = fetch_bcb_series(series_code=series_id, start_date=start_date, end_date=end_date)
        frame["series_name"] = series_name
        frames.append(frame)
    return frames


def _fetch_alpha_bundle(start_date: str) -> list[pd.DataFrame]:
    """Fetch all configured Alpha Vantage series and return normalized dataframes."""

    frames: list[pd.DataFrame] = []
    ewz = fetch_equity(symbol="EWZ", start_date=start_date)
    ewz["series_name"] = ALPHA_VANTAGE_SERIES["EWZ"]
    frames.append(ewz)

    spy = fetch_equity(symbol="SPY", start_date=start_date)
    spy["series_name"] = ALPHA_VANTAGE_SERIES["SPY"]
    frames.append(spy)

    usd_brl = fetch_fx(from_symbol="USD", to_symbol="BRL", start_date=start_date)
    usd_brl["series_name"] = ALPHA_VANTAGE_SERIES["USD/BRL"]
    frames.append(usd_brl)

    return frames


def load_all(start_date: str = "2010-01-01") -> dict[str, int]:
    """Load all configured data sources into DuckDB.

    Parameters
    ----------
    start_date:
        Inclusive start date in ISO format for all sources.

    Returns
    -------
    dict[str, int]
        Number of inserted rows per source.
    """

    initialize_db()
    end_date = date.today().isoformat()
    inserted_counts: dict[str, int] = defaultdict(int)

    loaders: list[tuple[str, Callable[[], list[pd.DataFrame]], tuple[type[Exception], ...]]] = [
        ("FRED", lambda: _fetch_fred_bundle(start_date, end_date), (FREDAPIError,)),
        ("BCB", lambda: _fetch_bcb_bundle(start_date, end_date), (BCBAPIError,)),
        ("ALPHA_VANTAGE", lambda: _fetch_alpha_bundle(start_date), (AlphaVantageAPIError,)),
    ]

    for source_name, loader_fn, expected_errors in loaders:
        try:
            for frame in loader_fn():
                inserted_counts[source_name] += _upsert_dataframe(frame)
        except expected_errors as exc:
            LOGGER.error("Failed to load %s data: %s", source_name, exc)
            raise
        except Exception:
            LOGGER.exception("Unexpected error while loading %s data.", source_name)
            raise

    for source_name, total in inserted_counts.items():
        LOGGER.info("Inserted or replaced %s rows from %s", total, source_name)

    return dict(inserted_counts)


def get_series(series_id: str, n_periods: int = 60) -> pd.DataFrame:
    """Return the latest N observations for a series from DuckDB.

    Parameters
    ----------
    series_id:
        Series identifier stored in DuckDB.
    n_periods:
        Number of most recent rows to return.

    Returns
    -------
    pd.DataFrame
        DataFrame sorted by date ascending.
    """

    query = """
        SELECT date, series_id, series_name, value, source, loaded_at
        FROM economic_indicators
        WHERE series_id = ?
        ORDER BY date DESC
        LIMIT ?
    """
    with get_connection() as connection:
        dataframe = connection.execute(query, [series_id, n_periods]).fetchdf()
    return dataframe.sort_values("date").reset_index(drop=True)


def main() -> None:
    """Run the full ingestion flow and log inserted counts per source."""

    inserted_counts = load_all()
    for source_name, total in inserted_counts.items():
        LOGGER.info("%s total rows loaded: %s", source_name, total)


if __name__ == "__main__":
    main()
