"""Macroeconomic regime detection helpers for the dashboard and agent layers."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ingestion.loader import get_series

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

BRAZIL_HIGH_SELIC = 10.0
BRAZIL_HIGH_IPCA = 4.5
BRAZIL_WEAK_FX = 5.25


def _get_latest_observations(series_id: str, n_periods: int = 60) -> pd.DataFrame:
    """Return stored observations for a series with parsed dates."""

    dataframe = get_series(series_id=series_id, n_periods=n_periods)
    if dataframe.empty:
        raise ValueError(f"No data found for series_id={series_id}.")
    dataframe["date"] = pd.to_datetime(dataframe["date"])
    return dataframe


def detect_yield_curve_regime() -> dict[str, Any]:
    """Classify the current US yield-curve regime from the T10Y2Y spread.

    Returns
    -------
    dict[str, Any]
        Current regime, regime start date, latest spread and series metadata.
    """

    dataframe = _get_latest_observations("T10Y2Y", n_periods=240)
    latest_value = float(dataframe.iloc[-1]["value"])

    if latest_value < 0:
        current_regime = "inverted"
    elif abs(latest_value) < 0.25:
        current_regime = "flat"
    else:
        current_regime = "normal"

    regime_labels = []
    for value in dataframe["value"]:
        if value < 0:
            regime_labels.append("inverted")
        elif abs(float(value)) < 0.25:
            regime_labels.append("flat")
        else:
            regime_labels.append("normal")

    dataframe = dataframe.assign(regime=regime_labels)
    latest_date = dataframe.iloc[-1]["date"]
    regime_start = latest_date

    for _, row in dataframe.iloc[::-1].iterrows():
        if row["regime"] != current_regime:
            break
        regime_start = row["date"]

    return {
        "series_id": "T10Y2Y",
        "series_name": dataframe.iloc[-1]["series_name"],
        "current_regime": current_regime,
        "regime_start_date": regime_start.date().isoformat(),
        "latest_value": latest_value,
        "latest_date": latest_date.date().isoformat(),
    }


def detect_brazil_macro_regime() -> dict[str, Any]:
    """Classify Brazil's macro regime using SELIC, IPCA and USD/BRL.

    Returns
    -------
    dict[str, Any]
        Current regime plus the latest values used in the classification.
    """

    selic = _get_latest_observations("432").iloc[-1]
    ipca = _get_latest_observations("13522").iloc[-1]
    fx = _get_latest_observations("1").iloc[-1]

    selic_value = float(selic["value"])
    ipca_value = float(ipca["value"])
    fx_value = float(fx["value"])

    if ipca_value >= BRAZIL_HIGH_IPCA and fx_value >= BRAZIL_WEAK_FX and selic_value >= BRAZIL_HIGH_SELIC:
        regime = "estagflacao"
    elif selic_value >= BRAZIL_HIGH_SELIC and fx_value >= BRAZIL_WEAK_FX:
        regime = "contracao"
    elif selic_value < BRAZIL_HIGH_SELIC and ipca_value < BRAZIL_HIGH_IPCA and fx_value < BRAZIL_WEAK_FX:
        regime = "expansao"
    else:
        regime = "estabilidade"

    latest_date = max(
        pd.to_datetime(selic["date"]),
        pd.to_datetime(ipca["date"]),
        pd.to_datetime(fx["date"]),
    )

    return {
        "current_regime": regime,
        "latest_date": latest_date.date().isoformat(),
        "selic": {
            "series_id": "432",
            "value": selic_value,
            "date": pd.to_datetime(selic["date"]).date().isoformat(),
        },
        "ipca_12m": {
            "series_id": "13522",
            "value": ipca_value,
            "date": pd.to_datetime(ipca["date"]).date().isoformat(),
        },
        "usd_brl": {
            "series_id": "1",
            "value": fx_value,
            "date": pd.to_datetime(fx["date"]).date().isoformat(),
        },
    }


def get_global_macro_snapshot() -> dict[str, Any]:
    """Combine the US yield-curve regime and Brazil macro regime in one snapshot.

    Returns
    -------
    dict[str, Any]
        Consolidated snapshot used by the agent and dashboard layers.
    """

    us_regime = detect_yield_curve_regime()
    brazil_regime = detect_brazil_macro_regime()

    return {
        "as_of_date": max(us_regime["latest_date"], brazil_regime["latest_date"]),
        "united_states": us_regime,
        "brazil": brazil_regime,
    }


def main() -> None:
    """Print the current macro regime snapshot for CLI validation."""

    snapshot = get_global_macro_snapshot()
    LOGGER.info("US yield-curve regime: %s", snapshot["united_states"]["current_regime"])
    LOGGER.info("Brazil macro regime: %s", snapshot["brazil"]["current_regime"])
    LOGGER.info("%s", snapshot)


if __name__ == "__main__":
    main()
