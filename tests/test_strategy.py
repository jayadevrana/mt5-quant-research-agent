import pandas as pd

from strategy import StrategyConfig, generate_london_breakout_signals, hypothesis_catalog


def make_breakout_frame() -> pd.DataFrame:
    times = pd.date_range("2025-01-06 00:00", periods=96, freq="15min", tz="UTC")
    rows = []
    for ts in times:
        price = 1.1000
        if ts.hour == 8 and ts.minute == 15:
            price = 1.1030
        rows.append({"time": ts, "open": price - 0.0002, "high": price + 0.0003, "low": price - 0.0003, "close": price, "tick_volume": 100, "spread": 10})
    return pd.DataFrame(rows)


def test_strategy_catalog_contains_exact_hypotheses() -> None:
    catalog = hypothesis_catalog()
    assert len(catalog) >= 10
    assert all(item.entry_condition for item in catalog)


def test_london_breakout_signal_generation_is_deterministic() -> None:
    cfg = StrategyConfig(atr_period=3, rolling_regime_bars=20)
    signals_a = generate_london_breakout_signals(make_breakout_frame(), cfg)
    signals_b = generate_london_breakout_signals(make_breakout_frame(), cfg)
    assert signals_a == signals_b
    assert signals_a
    assert signals_a[0].side == "long"
