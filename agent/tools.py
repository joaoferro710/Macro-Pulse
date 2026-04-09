"""LangChain tools for querying macro-pulse analytics and DuckDB data."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from analytics.anomaly_detector import analyze_series
from analytics.regime_detector import get_global_macro_snapshot
from ingestion.loader import get_series


class SeriesInput(BaseModel):
    """Input schema for one-series tools."""

    series_id: str = Field(..., description="Identifier of the economic series to inspect.")


class CompareSeriesInput(BaseModel):
    """Input schema for the series-comparison tool."""

    series_id_a: str = Field(..., description="First series identifier.")
    series_id_b: str = Field(..., description="Second series identifier.")


def _format_value(value: float) -> str:
    """Format numeric values for compact human-readable output."""

    return f"{value:,.2f}"


def get_series_data(series_id: str) -> str:
    """Return the latest 12 observations for one series formatted as plain text.

    Parameters
    ----------
    series_id:
        Identifier of the series stored in DuckDB.

    Returns
    -------
    str
        Human-readable table of the latest 12 observations.
    """

    dataframe = get_series(series_id=series_id, n_periods=12)
    if dataframe.empty:
        return (
            f"No data found for series_id={series_id}. "
            "Use one of the stored ids such as FEDFUNDS, CPIAUCSL, UNRATE, GDP, "
            "T10Y2Y, 432, 13522, 1, 4380, EWZ, SPY or USD/BRL."
        )

    lines = [
        f"Series: {dataframe.iloc[-1]['series_name']} ({series_id})",
        f"Source: {dataframe.iloc[-1]['source']}",
        "Latest 12 observations:",
    ]
    for _, row in dataframe.iterrows():
        lines.append(f"- {pd.to_datetime(row['date']).date()}: {_format_value(float(row['value']))}")
    return "\n".join(lines)


def detect_anomalies_tool(series_id: str) -> str:
    """Return the anomaly summary for a stored series.

    Parameters
    ----------
    series_id:
        Identifier of the series stored in DuckDB.

    Returns
    -------
    str
        Human-readable anomaly summary and recent flagged dates.
    """

    try:
        analysis = analyze_series(series_id=series_id, n_periods=60)
    except ValueError:
        return (
            f"No anomaly analysis is available for series_id={series_id}. "
            "Use one of the stored ids such as FEDFUNDS, CPIAUCSL, UNRATE, GDP, "
            "T10Y2Y, 432, 13522, 1, 4380, EWZ, SPY or USD/BRL."
        )
    zscore_result = analysis["zscore_result"]
    cusum_result = analysis["cusum_result"]

    recent_anomalies = zscore_result.loc[zscore_result["is_anomaly"]].tail(5)
    recent_changepoints = cusum_result.loc[cusum_result["is_changepoint"]].tail(5)

    lines = [analysis["summary"]]
    if recent_anomalies.empty:
        lines.append("Recent Z-score anomalies: none.")
    else:
        lines.append("Recent Z-score anomalies:")
        for _, row in recent_anomalies.iterrows():
            lines.append(
                f"- {pd.to_datetime(row['date']).date()}: value={_format_value(float(row['value']))}, "
                f"zscore={float(row['zscore']):.2f}"
            )

    if recent_changepoints.empty:
        lines.append("Recent CUSUM changepoints: none.")
    else:
        lines.append("Recent CUSUM changepoints:")
        for _, row in recent_changepoints.iterrows():
            lines.append(
                f"- {pd.to_datetime(row['date']).date()}: value={_format_value(float(row['value']))}, "
                f"cusum_pos={float(row['cusum_pos']):.2f}, cusum_neg={float(row['cusum_neg']):.2f}"
            )

    return "\n".join(lines)


def get_macro_regime() -> str:
    """Return a JSON-formatted global macro regime snapshot.

    Returns
    -------
    str
        Serialized macro regime snapshot.
    """

    snapshot = get_global_macro_snapshot()
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


def compare_series(series_id_a: str, series_id_b: str) -> str:
    """Compare two stored series using recent correlation and momentum.

    Parameters
    ----------
    series_id_a:
        First series identifier.
    series_id_b:
        Second series identifier.

    Returns
    -------
    str
        Human-readable comparison summary.
    """

    dataframe_a = get_series(series_id=series_id_a, n_periods=24)
    dataframe_b = get_series(series_id=series_id_b, n_periods=24)
    if dataframe_a.empty or dataframe_b.empty:
        return (
            "One or both series were not found in DuckDB. "
            "Use stored ids such as FEDFUNDS, CPIAUCSL, UNRATE, GDP, T10Y2Y, "
            "432, 13522, 1, 4380, EWZ, SPY or USD/BRL."
        )

    merged = dataframe_a.loc[:, ["date", "value"]].rename(columns={"value": "value_a"}).merge(
        dataframe_b.loc[:, ["date", "value"]].rename(columns={"value": "value_b"}),
        on="date",
        how="inner",
    )
    if len(merged) < 3:
        return "Not enough overlapping observations to compare the selected series."

    correlation = float(merged["value_a"].corr(merged["value_b"]))
    latest = merged.iloc[-1]
    previous = merged.iloc[-2]
    delta_a = float(latest["value_a"] - previous["value_a"])
    delta_b = float(latest["value_b"] - previous["value_b"])

    divergence = "same direction"
    if delta_a == 0 or delta_b == 0:
        divergence = "mixed / flat movement"
    elif (delta_a > 0) != (delta_b > 0):
        divergence = "opposite directions"

    return "\n".join(
        [
            f"Comparison between {series_id_a} and {series_id_b}:",
            f"- Overlapping observations: {len(merged)}",
            f"- Correlation over the overlap: {correlation:.2f}",
            f"- Latest date: {pd.to_datetime(latest['date']).date()}",
            f"- Latest values: {series_id_a}={_format_value(float(latest['value_a']))}, "
            f"{series_id_b}={_format_value(float(latest['value_b']))}",
            f"- Most recent directional signal: {divergence}",
            f"- Recent deltas: {series_id_a}={delta_a:.2f}, {series_id_b}={delta_b:.2f}",
        ]
    )


def build_tools() -> list[BaseTool]:
    """Build and return all tools used by the macro agent.

    Returns
    -------
    list[BaseTool]
        LangChain tools configured for the macro-pulse agent.
    """

    return [
        StructuredTool.from_function(
            func=get_series_data,
            name="GetSeriesDataTool",
            description="Get the latest 12 observations for one macroeconomic series.",
            args_schema=SeriesInput,
        ),
        StructuredTool.from_function(
            func=detect_anomalies_tool,
            name="DetectAnomaliesTool",
            description="Get the anomaly and changepoint summary for one series.",
            args_schema=SeriesInput,
        ),
        StructuredTool.from_function(
            func=get_macro_regime,
            name="GetMacroRegimeTool",
            description="Get the current macro regime snapshot for Brazil and the United States.",
        ),
        StructuredTool.from_function(
            func=compare_series,
            name="CompareSeriesTool",
            description="Compare two macroeconomic series using overlap, correlation and recent deltas.",
            args_schema=CompareSeriesInput,
        ),
    ]
