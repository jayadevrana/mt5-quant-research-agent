from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from indicators import atr, donchian_high, donchian_low, ema, rolling_percentile, zscore
from utils import session_contains


@dataclass(frozen=True)
class StrategyConfig:
    name: str = "htf_trend_pullback"
    ema_fast: int = 50
    ema_slow: int = 200
    pullback_ema: int = 20
    atr_period: int = 14
    atr_stop_multiple: float = 1.5
    take_profit_r: float = 2.0
    time_stop_bars: int = 32
    atr_min_percentile: float = 0.20
    atr_max_percentile: float = 0.90
    rolling_regime_bars: int = 5760
    session_start: str = "07:00"
    session_end: str = "16:00"
    max_trades_per_day: int = 3
    max_spread_points: float = 20.0
    point: float = 0.00001


@dataclass(frozen=True)
class StrategySignal:
    bar_index: int
    time: pd.Timestamp
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_r: float
    time_stop_index: int
    setup: str
    quality: str = "A"


@dataclass(frozen=True)
class StrategyHypothesis:
    name: str
    symbol: str
    timeframe: str
    session: str
    entry_condition: str
    exit_condition: str
    stop_loss: str
    take_profit: str
    filters: str
    verdict: str


def _prepare_frame(frame: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    data = frame.copy().sort_values("time").reset_index(drop=True)
    data["ema_pullback"] = ema(data["close"], config.pullback_ema)
    data["atr"] = atr(data, config.atr_period)
    regime_window = min(config.rolling_regime_bars, max(30, len(data) // 2))
    data["atr_percentile"] = rolling_percentile(data["atr"], regime_window)
    data["candle_body"] = (data["close"] - data["open"]).abs()
    return data


def _attach_higher_timeframe(data: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    indexed = data.set_index("time")
    h1 = indexed.resample("1h", label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    h1 = h1.dropna().reset_index()
    h1["htf_ema_fast"] = ema(h1["close"], config.ema_fast)
    h1["htf_ema_slow"] = ema(h1["close"], config.ema_slow)
    h1 = h1[["time", "close", "htf_ema_fast", "htf_ema_slow"]].rename(columns={"close": "htf_close"})
    return pd.merge_asof(data.sort_values("time"), h1.sort_values("time"), on="time", direction="backward")


def generate_htf_trend_pullback_signals(
    frame: pd.DataFrame,
    config: StrategyConfig | None = None,
) -> list[StrategySignal]:
    cfg = config or StrategyConfig()
    data = _attach_higher_timeframe(_prepare_frame(frame, cfg), cfg)
    signals: list[StrategySignal] = []
    trades_by_day: dict[pd.Timestamp, int] = {}

    for index in range(2, len(data)):
        row = data.iloc[index]
        prev = data.iloc[index - 1]
        if pd.isna(row["atr"]) or pd.isna(row["atr_percentile"]) or pd.isna(row["htf_ema_slow"]):
            continue
        if not session_contains(row["time"], cfg.session_start, cfg.session_end):
            continue
        if int(row["time"].dayofweek) >= 5:
            continue
        if "spread" in data.columns and row["spread"] > cfg.max_spread_points:
            continue
        trade_day = row["time"].normalize()
        if trades_by_day.get(trade_day, 0) >= cfg.max_trades_per_day:
            continue
        if not (cfg.atr_min_percentile <= row["atr_percentile"] <= cfg.atr_max_percentile):
            continue

        atr_value = float(row["atr"])
        zone_distance = 0.25 * atr_value
        min_body = 0.25 * atr_value
        stop_distance = cfg.atr_stop_multiple * atr_value
        if stop_distance <= 0:
            continue

        long_regime = row["htf_ema_fast"] > row["htf_ema_slow"] and row["htf_close"] > row["htf_ema_slow"]
        short_regime = row["htf_ema_fast"] < row["htf_ema_slow"] and row["htf_close"] < row["htf_ema_slow"]
        touched_zone = abs(float(prev["close"]) - float(prev["ema_pullback"])) <= zone_distance
        body_ok = float(row["candle_body"]) >= min_body

        if long_regime and touched_zone and prev["close"] <= prev["ema_pullback"] and row["close"] > row["ema_pullback"] and body_ok:
            entry = float(row["close"])
            swing_stop = float(min(data.iloc[index - 2 : index + 1]["low"]))
            atr_stop = entry - stop_distance
            stop = min(atr_stop, swing_stop)
            risk = entry - stop
            if risk <= 0:
                continue
            signals.append(
                StrategySignal(
                    index,
                    row["time"],
                    "long",
                    entry,
                    stop,
                    entry + cfg.take_profit_r * risk,
                    risk,
                    min(len(data) - 1, index + cfg.time_stop_bars),
                    "htf_trend_pullback",
                )
            )
            trades_by_day[trade_day] = trades_by_day.get(trade_day, 0) + 1
        elif short_regime and touched_zone and prev["close"] >= prev["ema_pullback"] and row["close"] < row["ema_pullback"] and body_ok:
            entry = float(row["close"])
            swing_stop = float(max(data.iloc[index - 2 : index + 1]["high"]))
            atr_stop = entry + stop_distance
            stop = max(atr_stop, swing_stop)
            risk = stop - entry
            if risk <= 0:
                continue
            signals.append(
                StrategySignal(
                    index,
                    row["time"],
                    "short",
                    entry,
                    stop,
                    entry - cfg.take_profit_r * risk,
                    risk,
                    min(len(data) - 1, index + cfg.time_stop_bars),
                    "htf_trend_pullback",
                )
            )
            trades_by_day[trade_day] = trades_by_day.get(trade_day, 0) + 1
    return signals


def generate_london_breakout_signals(frame: pd.DataFrame, config: StrategyConfig | None = None) -> list[StrategySignal]:
    cfg = config or StrategyConfig()
    data = _prepare_frame(frame, cfg)
    signals: list[StrategySignal] = []
    for day, group in data.groupby(data["time"].dt.normalize()):
        range_window = group[(group["time"].dt.time >= pd.Timestamp("06:00").time()) & (group["time"].dt.time <= pd.Timestamp("08:00").time())]
        trade_window = group[(group["time"].dt.time > pd.Timestamp("08:00").time()) & (group["time"].dt.time <= pd.Timestamp("11:00").time())]
        if range_window.empty or trade_window.empty:
            continue
        high = float(range_window["high"].max())
        low = float(range_window["low"].min())
        width = high - low
        if width <= 0:
            continue
        for _, row in trade_window.iterrows():
            idx = int(row.name)
            if row["close"] > high:
                risk = max(width, cfg.atr_stop_multiple * float(row["atr"]))
                if risk > 0:
                    signals.append(StrategySignal(idx, row["time"], "long", float(row["close"]), float(row["close"]) - risk, float(row["close"]) + 1.5 * risk, risk, min(len(data) - 1, idx + cfg.time_stop_bars), "london_breakout", "B"))
                break
            if row["close"] < low:
                risk = max(width, cfg.atr_stop_multiple * float(row["atr"]))
                if risk > 0:
                    signals.append(StrategySignal(idx, row["time"], "short", float(row["close"]), float(row["close"]) + risk, float(row["close"]) - 1.5 * risk, risk, min(len(data) - 1, idx + cfg.time_stop_bars), "london_breakout", "B"))
                break
    return signals


def generate_random_baseline_signals(frame: pd.DataFrame, config: StrategyConfig | None = None, seed: int = 260524) -> list[StrategySignal]:
    cfg = config or StrategyConfig()
    rng = np.random.default_rng(seed)
    data = _prepare_frame(frame, cfg)
    candidates = data[data["time"].apply(lambda ts: session_contains(ts, cfg.session_start, cfg.session_end))].dropna()
    signals: list[StrategySignal] = []
    for day, group in candidates.groupby(candidates["time"].dt.normalize()):
        if group.empty:
            continue
        row = group.iloc[int(rng.integers(0, len(group)))]
        side = "long" if rng.random() >= 0.5 else "short"
        entry = float(row["close"])
        risk = cfg.atr_stop_multiple * float(row["atr"])
        if risk <= 0:
            continue
        stop = entry - risk if side == "long" else entry + risk
        take = entry + cfg.take_profit_r * risk if side == "long" else entry - cfg.take_profit_r * risk
        signals.append(StrategySignal(int(row.name), row["time"], side, entry, stop, take, risk, min(len(data) - 1, int(row.name) + cfg.time_stop_bars), "random_baseline", "R"))
    return signals


def hypothesis_catalog() -> list[StrategyHypothesis]:
    return [
        StrategyHypothesis("Higher-timeframe trend pullback", "EURUSD", "M15/H1", "07:00-16:00 UTC", "H1 EMA50/EMA200 trend plus M15 EMA20 pullback reclaim", "2R TP, ATR SL, or 32-bar time stop", "1.5 ATR beyond swing", "2.0R", "spread, ATR percentile, session, loss limits", "primary candidate"),
        StrategyHypothesis("London session breakout", "EURUSD/GBPUSD/USDJPY", "M15", "08:00-11:00 UTC", "Break 06:00-08:00 range", "1.5R TP or time stop", "range width or ATR", "1.5R", "range width, spread, max 1/day", "research candidate"),
        StrategyHypothesis("Asian range breakout", "EURUSD/USDJPY", "M15", "07:00-10:00 UTC", "Break 00:00-06:00 range", "ATR stop or time stop", "range width or ATR", "1.5R-2R", "range not too narrow/wide", "research candidate"),
        StrategyHypothesis("ATR compression expansion", "EURUSD", "M15", "London/NY", "ATR percentile below 25 then candle range above 75", "ATR SL/TP", "1.5 ATR", "1.5R-2R", "trend and spread filter", "research candidate"),
        StrategyHypothesis("Mean reversion after volatility spike", "EURUSD", "M15", "liquid sessions", "z-score from EMA after large ATR candle", "midline or time stop", "beyond spike extreme", "1R-1.5R", "avoid trend days", "research candidate"),
        StrategyHypothesis("Opening-session momentum", "EURUSD/GBPUSD", "M15", "London open", "first four M15 bars impulse", "ATR SL/TP", "ATR or impulse low/high", "1.5R", "spread and news filter", "research candidate"),
        StrategyHypothesis("MA trend continuation", "EURUSD", "M15/H1", "07:00-16:00 UTC", "EMA20/50 continuation with H1 trend", "ATR SL/TP", "1.5 ATR", "2R", "ATR and session filter", "research candidate"),
        StrategyHypothesis("Day/session filter", "EURUSD", "M15", "all sessions", "No standalone entries; filters existing setups", "N/A", "N/A", "N/A", "requires statistical significance", "meta-filter only"),
        StrategyHypothesis("Volatility regime breakout", "EURUSD", "M15", "London/NY", "Donchian break during high ATR expansion", "ATR SL/TP", "2 ATR", "2R", "high vol, spread filter", "research candidate"),
        StrategyHypothesis("Previous-day high/low sweep reversal", "EURUSD", "M15", "London/NY", "Break prior high/low then close back inside", "midpoint, 1.5R, or time stop", "beyond sweep", "1.5R", "spread, ATR, max 2/day", "research candidate"),
    ]


STRATEGY_REGISTRY: dict[str, Callable[[pd.DataFrame, StrategyConfig | None], list[StrategySignal]]] = {
    "htf_trend_pullback": generate_htf_trend_pullback_signals,
    "london_breakout": generate_london_breakout_signals,
    "random_baseline": generate_random_baseline_signals,
}
