"""Tests for anomaly detection and macro regime classification."""

from __future__ import annotations

import pandas as pd
import pytest

from analytics import anomaly_detector, regime_detector


def test_detect_zscore_flags_injected_outlier() -> None:
    """Rolling Z-score should flag a clear synthetic outlier."""

    index = pd.date_range("2024-01-01", periods=30, freq="ME")
    values = [10.0] * 29 + [30.0]
    series = pd.Series(values, index=index)

    result = anomaly_detector.detect_zscore(series, window=12, threshold=2.0)

    assert bool(result.iloc[-1]["is_anomaly"]) is True


def test_detect_cusum_flags_known_level_shift() -> None:
    """CUSUM should detect a changepoint after a level shift."""

    index = pd.date_range("2024-01-01", periods=40, freq="ME")
    values = [5.0] * 20 + [15.0] * 20
    series = pd.Series(values, index=index)

    result = anomaly_detector.detect_cusum(series, threshold=3.0, drift=0.2)

    assert result["is_changepoint"].any()


@pytest.mark.parametrize(
    ("latest_value", "expected_regime"),
    [
        (0.60, "normal"),
        (0.10, "flat"),
        (-0.25, "inverted"),
    ],
)
def test_detect_yield_curve_regime_classifies_each_regime(
    monkeypatch: pytest.MonkeyPatch,
    latest_value: float,
    expected_regime: str,
) -> None:
    """Yield-curve regime detector should classify normal, flat and inverted states."""

    dataframe = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=5, freq="D"),
            "series_id": ["T10Y2Y"] * 5,
            "series_name": ["US Treasury Yield Spread 10Y-2Y"] * 5,
            "value": [0.50, 0.45, 0.40, 0.35, latest_value],
            "source": ["FRED"] * 5,
            "loaded_at": pd.date_range("2025-01-01", periods=5, freq="D"),
        }
    )

    monkeypatch.setattr(regime_detector, "get_series", lambda series_id, n_periods=60: dataframe)

    result = regime_detector.detect_yield_curve_regime()

    assert result["current_regime"] == expected_regime
