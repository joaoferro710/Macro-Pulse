"""Client helpers for Alpha Vantage market data."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

LOGGER = logging.getLogger(__name__)
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
CACHE_PATH = Path(__file__).resolve().parent / "alpha_vantage_cache.json"
TIMEOUT_SECONDS = 30
MIN_SECONDS_BETWEEN_CALLS = 1.2


class AlphaVantageAPIError(Exception):
    """Raised when the Alpha Vantage API returns an invalid response."""


def _get_api_key() -> str:
    """Return the configured Alpha Vantage API key from environment variables."""

    load_dotenv()
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise AlphaVantageAPIError(
            "ALPHA_VANTAGE_API_KEY is not configured. Add it to your .env file."
        )
    return api_key


def _load_cache() -> dict[str, dict]:
    """Load the local Alpha Vantage JSON cache from disk."""

    if not CACHE_PATH.exists():
        return {}

    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        LOGGER.warning("Alpha Vantage cache is corrupted. Rebuilding cache file.")
        return {}


def _get_last_call_timestamp(cache: dict[str, dict]) -> float | None:
    """Return the timestamp of the last uncached Alpha Vantage request."""

    metadata = cache.get("_meta", {})
    last_call = metadata.get("last_api_call_epoch")
    if isinstance(last_call, (int, float)):
        return float(last_call)
    return None


def _set_last_call_timestamp(cache: dict[str, dict], timestamp: float) -> None:
    """Persist the timestamp of the last uncached Alpha Vantage request."""

    cache.setdefault("_meta", {})
    cache["_meta"]["last_api_call_epoch"] = timestamp


def _save_cache(cache: dict[str, dict]) -> None:
    """Persist the Alpha Vantage JSON cache to disk."""

    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _cache_key(params: dict[str, str]) -> str:
    """Build a stable cache key for an Alpha Vantage request."""

    items = sorted((key, value) for key, value in params.items() if key != "apikey")
    return "&".join(f"{key}={value}" for key, value in items)


def _extract_payload(payload: dict, primary_key: str) -> dict[str, dict]:
    """Extract a time-series payload and raise helpful API errors when needed."""

    if "Error Message" in payload:
        raise AlphaVantageAPIError(payload["Error Message"])
    if "Information" in payload:
        raise AlphaVantageAPIError(payload["Information"])
    if "Note" in payload:
        raise AlphaVantageAPIError(payload["Note"])
    if not payload:
        raise AlphaVantageAPIError("Alpha Vantage returned an empty payload for this symbol.")

    series_payload = payload.get(primary_key)
    if not isinstance(series_payload, dict):
        raise AlphaVantageAPIError("Unexpected Alpha Vantage response payload.")

    return series_payload


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2),
    retry=retry_if_exception_type((requests.RequestException, AlphaVantageAPIError)),
    reraise=True,
)
def _request_with_cache(params: dict[str, str], primary_key: str) -> dict[str, dict]:
    """Fetch Alpha Vantage data, using a local JSON cache to avoid repeated calls."""

    cache = _load_cache()
    key = _cache_key(params)
    if key in cache:
        LOGGER.info("Using cached Alpha Vantage response for %s", key)
        return _extract_payload(cache[key], primary_key)

    api_key = _get_api_key()
    request_params = {**params, "apikey": api_key}
    last_call = _get_last_call_timestamp(cache)
    if last_call is not None:
        elapsed = time.time() - last_call
        if elapsed < MIN_SECONDS_BETWEEN_CALLS:
            time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)

    LOGGER.info("Fetching Alpha Vantage data for %s", key)
    response = requests.get(ALPHA_VANTAGE_BASE_URL, params=request_params, timeout=TIMEOUT_SECONDS)
    if response.status_code == 429:
        raise AlphaVantageAPIError("Alpha Vantage rate limit reached. Try again later.")
    if response.status_code >= 400:
        raise AlphaVantageAPIError(
            f"Alpha Vantage rejected the request with status {response.status_code}."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise AlphaVantageAPIError("Alpha Vantage returned a non-JSON response.") from exc

    _extract_payload(payload, primary_key)
    cache[key] = payload
    _set_last_call_timestamp(cache, time.time())
    _save_cache(cache)
    return payload[primary_key]


def _build_dataframe(
    rows: dict[str, dict],
    series_id: str,
    source: str,
    value_field: str,
    start_date: str,
) -> pd.DataFrame:
    """Normalize Alpha Vantage time-series rows into the shared schema."""

    records: list[dict[str, object]] = []
    start = pd.to_datetime(start_date)

    for date_str, values in rows.items():
        current_date = pd.to_datetime(date_str)
        if current_date < start:
            continue

        raw_value = values.get(value_field)
        if raw_value in (None, ""):
            continue

        records.append(
            {
                "date": current_date,
                "series_id": series_id,
                "value": float(raw_value),
                "source": source,
            }
        )

    if not records:
        raise AlphaVantageAPIError(f"Alpha Vantage returned no usable observations for {series_id}.")

    return pd.DataFrame(records).sort_values("date").reset_index(drop=True)


def fetch_equity(symbol: str, start_date: str) -> pd.DataFrame:
    """Fetch monthly equity or index data from Alpha Vantage.

    Parameters
    ----------
    symbol:
        Ticker or index symbol to fetch.
    start_date:
        Inclusive start date in ISO format.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ``date``, ``series_id``, ``value`` and ``source``.
    """

    rows = _request_with_cache(
        params={"function": "TIME_SERIES_MONTHLY", "symbol": symbol},
        primary_key="Monthly Time Series",
    )
    return _build_dataframe(rows, symbol, "ALPHA_VANTAGE", "4. close", start_date)


def fetch_fx(from_symbol: str, to_symbol: str, start_date: str) -> pd.DataFrame:
    """Fetch monthly FX data from Alpha Vantage.

    Parameters
    ----------
    from_symbol:
        Base currency code.
    to_symbol:
        Quote currency code.
    start_date:
        Inclusive start date in ISO format.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ``date``, ``series_id``, ``value`` and ``source``.
    """

    series_id = f"{from_symbol}/{to_symbol}"
    rows = _request_with_cache(
        params={
            "function": "FX_MONTHLY",
            "from_symbol": from_symbol,
            "to_symbol": to_symbol,
        },
        primary_key="Time Series FX (Monthly)",
    )
    return _build_dataframe(rows, series_id, "ALPHA_VANTAGE", "4. close", start_date)
