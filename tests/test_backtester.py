import pandas as pd

from backtester import run_backtest


def config() -> dict:
    return {
        "account": {"initial_capital": 1000},
        "trading": {"symbol": "EURUSD", "session_start": "07:00", "session_end": "16:00", "max_trades_per_day": 3},
        "risk": {"risk_per_trade": 0.005, "max_daily_loss": 0.02, "max_weekly_loss": 0.05, "max_total_drawdown": 0.10, "max_lot_size": 0.10, "min_lot_size": 0.01, "stop_loss_required": True},
        "execution": {"max_spread_points": 20},
        "backtest": {"initial_balance": 1000, "commission_per_lot": 7, "slippage_points": 1, "spread_points": 10},
        "strategy": {"name": "london_breakout", "atr_period": 3, "rolling_regime_bars": 20, "atr_stop_multiple": 1.0, "take_profit_r": 1.5, "time_stop_bars": 8},
    }


def make_frame() -> pd.DataFrame:
    times = pd.date_range("2025-01-06 00:00", periods=120, freq="15min", tz="UTC")
    rows = []
    for ts in times:
        price = 1.1000
        if ts.hour == 8 and ts.minute == 15:
            price = 1.1030
        if ts.hour == 8 and ts.minute == 30:
            rows.append({"time": ts, "open": 1.1030, "high": 1.1075, "low": 1.1025, "close": 1.1060, "tick_volume": 100, "spread": 10})
            continue
        rows.append({"time": ts, "open": price - 0.0002, "high": price + 0.0003, "low": price - 0.0003, "close": price, "tick_volume": 100, "spread": 10})
    return pd.DataFrame(rows)


def test_backtester_trade_accounting_records_costs_and_r_multiple() -> None:
    result = run_backtest(make_frame(), config())
    assert result.trades
    trade = result.trades[0]
    assert trade.commission > 0
    assert trade.exit_reason in {"take_profit", "stop_loss", "time_stop"}
    assert "profit_factor" in result.metrics
    assert "r_multiple" in trade.__dict__
