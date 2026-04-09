"""Client helpers for Banco Central do Brasil time series."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

LOGGER = logging.getLogger(__name__)
BCB_URL_TEMPLATE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_code}/dados"
TIMEOUT_SECONDS = 30
MAX_WINDOW_DAYS = 3652


class BCBAPIError(Exception):
    """Raised when the BCB API returns an invalid response."""


def _validate_response(response: requests.Response, series_code: str) -> list[dict[str, str]]:
    """Validate a BCB HTTP response and return the parsed payload."""

    if response.status_code == 404:
        raise BCBAPIError(f"BCB series not found: {series_code}")
    if response.status_code == 429:
        raise BCBAPIError("BCB rate limit reached. Try again later.")
    if response.status_code >= 500:
        raise BCBAPIError("BCB is temporarily unavailable.")
    if response.status_code >= 400:
        raise BCBAPIError(f"BCB rejected the request with status {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise BCBAPIError("BCB returned a non-JSON response.") from exc

    if not isinstance(payload, list):
        raise BCBAPIError(f"Unexpected BCB response for series {series_code}.")

    return payload


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2),
    retry=retry_if_exception_type((requests.RequestException, BCBAPIError)),
    reraise=True,
)
def _fetch_window(
    series_code: str | int,
    start_date: str | date,
    end_date: str | date,
) -> pd.DataFrame:
    """Fetch one BCB series window for the provided date range.

    Parameters
    ----------
    series_code:
        Numeric BCB series code.
    start_date:
        Inclusive start date in ISO format or as a ``date`` object.
    end_date:
        Inclusive end date in ISO format or as a ``date`` object.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ``date``, ``series_id``, ``value`` and ``source``.
    """
    series_code = str(series_code)
    params = {
        "formato": "json",
        "dataInicial": pd.to_datetime(start_date).strftime("%d/%m/%Y"),
        "dataFinal": pd.to_datetime(end_date).strftime("%d/%m/%Y"),
    }

    LOGGER.info("Fetching BCB series %s", series_code)
    response = requests.get(
        BCB_URL_TEMPLATE.format(series_code=series_code),
        params=params,
        timeout=TIMEOUT_SECONDS,
    )
    payload = _validate_response(response, series_code)

    records: list[dict[str, object]] = []
    for item in payload:
        raw_value = item.get("valor")
        if raw_value in (None, ""):
            continue
        normalized_value = str(raw_value).replace(",", ".")
        records.append(
            {
                "date": pd.to_datetime(item["data"], format="%d/%m/%Y"),
                "series_id": series_code,
                "value": float(normalized_value),
                "source": "BCB",
            }
        )

    if not records:
        raise BCBAPIError(f"BCB returned no usable observations for series {series_code}.")

    return pd.DataFrame(records).sort_values("date").reset_index(drop=True)


def _build_date_windows(start_date: str | date, end_date: str | date) -> list[tuple[date, date]]:
    """Split a BCB request into windows supported by daily series."""

    start = pd.to_datetime(start_date).date()
    end = pd.to_datetime(end_date).date()
    windows: list[tuple[date, date]] = []

    current_start = start
    while current_start <= end:
        current_end = min(current_start + timedelta(days=MAX_WINDOW_DAYS - 1), end)
        windows.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)

    return windows


def fetch_series(
    series_code: str | int,
    start_date: str | date,
    end_date: str | date,
) -> pd.DataFrame:
    """Fetch a BCB series for the provided date range.

    Parameters
    ----------
    series_code:
        Numeric BCB series code.
    start_date:
        Inclusive start date in ISO format or as a ``date`` object.
    end_date:
        Inclusive end date in ISO format or as a ``date`` object.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ``date``, ``series_id``, ``value`` and ``source``.
    """

    frames: list[pd.DataFrame] = []
    for window_start, window_end in _build_date_windows(start_date, end_date):
        frames.append(_fetch_window(series_code, window_start, window_end))

    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(subset=["date", "series_id"]).sort_values("date").reset_index(
        drop=True
    )
