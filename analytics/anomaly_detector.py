"""Anomaly detection routines for macroeconomic time series."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from ingestion.loader import get_series

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

DEFAULT_SERIES_FOR_CLI = ("T10Y2Y", "432", "USD/BRL")


def detect_zscore(
    series: pd.Series,
    window: int = 24,
    threshold: float = 2.5,
) -> pd.DataFrame:
    """Detect anomalies in a series using a rolling Z-score.

    Parameters
    ----------
    series:
        Time series indexed by date.
    window:
        Rolling window size used to compute mean and standard deviation.
    threshold:
        Absolute Z-score threshold used to flag anomalies.

    Returns
    -------
    pd.DataFrame
        DataFrame with ``date``, ``value``, ``zscore`` and ``is_anomaly`` columns.
    """

    cleaned = series.dropna().sort_index()
    if cleaned.empty:
        return pd.DataFrame(columns=["date", "value", "zscore", "is_anomaly"])

    rolling_mean = cleaned.rolling(window=window, min_periods=max(5, window // 3)).mean()
    rolling_std = cleaned.rolling(window=window, min_periods=max(5, window // 3)).std(ddof=0)
    zscore = (cleaned - rolling_mean) / rolling_std.replace(0, np.nan)

    result = pd.DataFrame(
        {
            "date": cleaned.index,
            "value": cleaned.values,
            "zscore": zscore.values,
        }
    )
    result["is_anomaly"] = result["zscore"].abs() > threshold
    return result.reset_index(drop=True)


def detect_cusum(
    series: pd.Series,
    threshold: float = 5.0,
    drift: float = 0.5,
) -> pd.DataFrame:
    """Detect change points in a series using a two-sided CUSUM algorithm.

    Parameters
    ----------
    series:
        Time series indexed by date.
    threshold:
        Control limit used to flag cumulative deviations.
    drift:
        Drift adjustment applied at each step to reduce false positives.

    Returns
    -------
    pd.DataFrame
        DataFrame with ``date``, ``value``, ``cusum_pos``, ``cusum_neg`` and
        ``is_changepoint`` columns.
    """

    cleaned = series.dropna().sort_index()
    if cleaned.empty:
        return pd.DataFrame(
            columns=["date", "value", "cusum_pos", "cusum_neg", "is_changepoint"]
        )

    values = cleaned.to_numpy(dtype=float)
    mean_value = float(np.mean(values))
    std_value = float(np.std(values, ddof=0))
    scale = std_value if std_value > 0 else 1.0

    positive: list[float] = []
    negative: list[float] = []
    changepoints: list[bool] = []
    pos_sum = 0.0
    neg_sum = 0.0

    for value in values:
        normalized = (value - mean_value) / scale
        pos_sum = max(0.0, pos_sum + normalized - drift)
        neg_sum = min(0.0, neg_sum + normalized + drift)
        is_changepoint = pos_sum > threshold or abs(neg_sum) > threshold
        changepoints.append(is_changepoint)
        positive.append(pos_sum)
        negative.append(neg_sum)
        if is_changepoint:
            pos_sum = 0.0
            neg_sum = 0.0

    return pd.DataFrame(
        {
            "date": cleaned.index,
            "value": values,
            "cusum_pos": positive,
            "cusum_neg": negative,
            "is_changepoint": changepoints,
        }
    ).reset_index(drop=True)


def analyze_series(series_id: str, n_periods: int = 60) -> dict[str, Any]:
    """Analyze one stored series with Z-score and CUSUM detectors.

    Parameters
    ----------
    series_id:
        Identifier of the series stored in DuckDB.
    n_periods:
        Number of latest observations used in the analysis.

    Returns
    -------
    dict[str, Any]
        Summary with current value, date, anomaly counts and human-readable text.
    """

    dataframe = get_series(series_id=series_id, n_periods=n_periods)
    if dataframe.empty:
        raise ValueError(f"No data found for series_id={series_id}.")

    indexed_series = dataframe.set_index(pd.to_datetime(dataframe["date"]))["value"]
    zscore_result = detect_zscore(indexed_series)
    cusum_result = detect_cusum(indexed_series)

    latest_row = dataframe.iloc[-1]
    latest_zscore = zscore_result.iloc[-1]["zscore"] if not zscore_result.empty else np.nan
    anomaly_count = int(zscore_result["is_anomaly"].sum()) if not zscore_result.empty else 0
    changepoint_count = (
        int(cusum_result["is_changepoint"].sum()) if not cusum_result.empty else 0
    )

    summary = (
        f"{latest_row['series_name']} ({series_id}) encerrou em {latest_row['value']:.2f} "
        f"na data {pd.to_datetime(latest_row['date']).date()}. "
        f"Foram detectadas {anomaly_count} anomalias por Z-score "
        f"e {changepoint_count} pontos de mudança por CUSUM nos últimos {len(dataframe)} períodos. "
        f"O Z-score mais recente foi {float(latest_zscore):.2f}."
    )

    return {
        "series_id": series_id,
        "series_name": latest_row["series_name"],
        "latest_value": float(latest_row["value"]),
        "latest_date": pd.to_datetime(latest_row["date"]).date().isoformat(),
        "zscore_anomalies": anomaly_count,
        "cusum_changepoints": changepoint_count,
        "summary": summary,
        "zscore_result": zscore_result,
        "cusum_result": cusum_result,
    }


def main() -> None:
    """Print anomaly summaries for default series used in Phase 2 validation."""

    for series_id in DEFAULT_SERIES_FOR_CLI:
        analysis = analyze_series(series_id)
        LOGGER.info("Series %s analysis", series_id)
        LOGGER.info("%s", analysis["summary"])


if __name__ == "__main__":
    main()
