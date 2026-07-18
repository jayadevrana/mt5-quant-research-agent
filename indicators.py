from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    if period <= 0:
        raise ValueError("EMA period must be positive")
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    if period <= 0:
        raise ValueError("ATR period must be positive")
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(period, min_periods=period).mean()


def rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    if window <= 1:
        raise ValueError("window must be greater than 1")

    def percentile(values: np.ndarray) -> float:
        last = values[-1]
        return float(np.sum(values <= last) / len(values))

    return series.rolling(window, min_periods=max(20, min(window, 100))).apply(percentile, raw=True)


def donchian_high(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).max()


def donchian_low(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).min()


def zscore(series: pd.Series, period: int) -> pd.Series:
    mean = series.rolling(period, min_periods=period).mean()
    std = series.rolling(period, min_periods=period).std(ddof=0)
    return (series - mean) / std.replace(0, np.nan)
