"""Client helpers for the FRED economic data API."""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
import streamlit as st
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

LOGGER = logging.getLogger(__name__)
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
TIMEOUT_SECONDS = 30
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class FREDAPIError(Exception):
    """Raised when the FRED API returns an invalid response."""


def _get_api_key() -> str:
    """Return the configured FRED API key from Streamlit secrets or environment."""

    load_dotenv(dotenv_path=ENV_PATH)
    api_key = os.getenv("FRED_API_KEY")
    if api_key:
        return api_key
    try:
        api_key = st.secrets["FRED_API_KEY"]
    except Exception:
        api_key = None
    if not api_key:
        raise FREDAPIError(
            "FRED_API_KEY is not configured. Add it to .streamlit/secrets.toml or .env."
        )
    return api_key


def _validate_response(response: requests.Response) -> dict:
    """Validate a FRED HTTP response and return the parsed JSON payload."""

    if response.status_code == 400:
        raise FREDAPIError(
            "FRED rejected the request. Check the series id, date range, or API key."
        )
    if response.status_code == 429:
        raise FREDAPIError("FRED rate limit reached. Try again later.")
    if response.status_code >= 500:
        raise FREDAPIError("FRED is temporarily unavailable.")
    if response.status_code >= 400:
        raise FREDAPIError(f"FRED rejected the request with status {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise FREDAPIError("FRED returned a non-JSON response.") from exc

    error_message = payload.get("error_message")
    if error_message:
        lowered = error_message.lower()
        if "api key" in lowered:
            raise FREDAPIError("Invalid FRED API key.")
        if "not found" in lowered or "series" in lowered:
            raise FREDAPIError(f"FRED series not found: {error_message}")
        raise FREDAPIError(error_message)

    observations = payload.get("observations")
    if observations is None:
        raise FREDAPIError("FRED response did not include observations.")

    return payload


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2),
    retry=retry_if_exception_type((requests.RequestException, FREDAPIError)),
    reraise=True,
)
def fetch_series(
    series_id: str,
    start_date: str | date,
    end_date: str | date,
) -> pd.DataFrame:
    """Fetch a FRED series for the provided date range.

    Parameters
    ----------
    series_id:
        Identifier of the FRED series to fetch.
    start_date:
        Inclusive start date in ISO format or as a ``date`` object.
    end_date:
        Inclusive end date in ISO format or as a ``date`` object.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ``date``, ``series_id``, ``value`` and ``source``.
    """

    api_key = _get_api_key()
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": str(start_date),
        "observation_end": str(end_date),
    }

    LOGGER.info("Fetching FRED series %s", series_id)
    response = requests.get(FRED_BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
    payload = _validate_response(response)

    records: list[dict[str, object]] = []
    for item in payload["observations"]:
        raw_value = item.get("value")
        if raw_value in (None, "."):
            continue
        records.append(
            {
                "date": pd.to_datetime(item["date"]),
                "series_id": series_id,
                "value": float(raw_value),
                "source": "FRED",
            }
        )

    if not records:
        raise FREDAPIError(f"FRED returned no usable observations for series {series_id}.")

    return pd.DataFrame(records).sort_values("date").reset_index(drop=True)
