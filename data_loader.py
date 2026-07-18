from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class DataQualityReport:
    rows_before: int
    rows_after: int
    duplicate_rows: int
    bad_candles_removed: int
    missing_values_removed: int


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = {column: column.strip().lower() for column in frame.columns}
    frame = frame.rename(columns=renamed).copy()
    if "date" in frame.columns and "time" in frame.columns:
        frame["time"] = frame["date"].astype(str) + " " + frame["time"].astype(str)
    required = {"time", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")
    frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    for column in ["open", "high", "low", "close", "tick_volume", "volume", "spread"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "tick_volume" not in frame.columns:
        frame["tick_volume"] = frame.get("volume", 0)
    if "spread" not in frame.columns:
        frame["spread"] = 0
    return frame[["time", "open", "high", "low", "close", "tick_volume", "spread"]]


def clean_ohlcv(frame: pd.DataFrame) -> tuple[pd.DataFrame, DataQualityReport]:
    rows_before = len(frame)
    frame = normalize_ohlcv(frame)
    missing_before = len(frame)
    frame = frame.dropna(subset=["time", "open", "high", "low", "close"])
    missing_removed = missing_before - len(frame)
    duplicate_rows = int(frame.duplicated(subset=["time"]).sum())
    frame = frame.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
    valid = (
        (frame["high"] >= frame[["open", "close"]].max(axis=1))
        & (frame["low"] <= frame[["open", "close"]].min(axis=1))
        & (frame["high"] >= frame["low"])
        & (frame["open"] > 0)
        & (frame["high"] > 0)
        & (frame["low"] > 0)
        & (frame["close"] > 0)
    )
    bad_removed = int((~valid).sum())
    frame = frame.loc[valid].reset_index(drop=True)
    report = DataQualityReport(
        rows_before=rows_before,
        rows_after=len(frame),
        duplicate_rows=duplicate_rows,
        bad_candles_removed=bad_removed,
        missing_values_removed=missing_removed,
    )
    return frame, report


def load_csv(path: str | Path) -> tuple[pd.DataFrame, DataQualityReport]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(
            f"Historical data not found: {source}. Export MT5 data or update backtest.data_path."
        )
    raw = pd.read_csv(source)
    return clean_ohlcv(raw)


def load_mt5_rates(symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError as exc:
        raise RuntimeError("MetaTrader5 package is unavailable. Use CSV data on this platform.") from exc

    timeframe_map: dict[str, Any] = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    if timeframe not in timeframe_map:
        raise ValueError(f"Unsupported MT5 timeframe: {timeframe}")
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    rates = mt5.copy_rates_range(
        symbol,
        timeframe_map[timeframe],
        pd.Timestamp(start, tz="UTC").to_pydatetime(),
        pd.Timestamp(end, tz="UTC").to_pydatetime(),
    )
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No MT5 rates returned for {symbol} {timeframe}")
    frame = pd.DataFrame(rates)
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    cleaned, _ = clean_ohlcv(frame)
    return cleaned
