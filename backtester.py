from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from data_loader import load_csv
from report_generator import write_backtest_report
from risk_manager import AccountState, RiskLimits, SymbolInfo, calculate_position_size
from strategy import STRATEGY_REGISTRY, StrategyConfig
from utils import ensure_dir


@dataclass(frozen=True)
class BacktestTrade:
    entry_time: str
    exit_time: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    lots: float
    gross_pnl: float
    commission: float
    net_pnl: float
    r_multiple: float
    exit_reason: str
    duration_bars: int
    setup: str


@dataclass(frozen=True)
class BacktestResult:
    trades: list[BacktestTrade]
    equity_curve: pd.DataFrame
    metrics: dict[str, Any]


def default_symbol_info(symbol: str) -> SymbolInfo:
    if symbol.upper().startswith("XAU"):
        return SymbolInfo(
            symbol=symbol,
            point=0.01,
            tick_size=0.01,
            tick_value=1.0,
            contract_size=100,
            min_lot=0.01,
            max_lot=100.0,
            lot_step=0.01,
            digits=2,
        )
    return SymbolInfo(
        symbol=symbol,
        point=0.00001,
        tick_size=0.00001,
        tick_value=1.0,
        contract_size=100000,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        digits=5,
    )


def _pnl_for_move(side: str, entry: float, exit_price: float, lots: float, symbol_info: SymbolInfo) -> float:
    signed_move = exit_price - entry if side == "long" else entry - exit_price
    return signed_move / symbol_info.tick_size * symbol_info.tick_value * lots


def _simulate_exit(
    data: pd.DataFrame,
    signal_index: int,
    side: str,
    stop_loss: float,
    take_profit: float,
    time_stop_index: int,
    slippage_price: float,
) -> tuple[int, float, str]:
    for idx in range(signal_index + 1, min(time_stop_index, len(data) - 1) + 1):
        row = data.iloc[idx]
        if side == "long":
            if row["low"] <= stop_loss:
                return idx, stop_loss - slippage_price, "stop_loss"
            if row["high"] >= take_profit:
                return idx, take_profit - slippage_price, "take_profit"
        else:
            if row["high"] >= stop_loss:
                return idx, stop_loss + slippage_price, "stop_loss"
            if row["low"] <= take_profit:
                return idx, take_profit + slippage_price, "take_profit"
    idx = min(time_stop_index, len(data) - 1)
    return idx, float(data.iloc[idx]["close"]), "time_stop"


def run_backtest(
    data: pd.DataFrame,
    config: dict[str, Any],
    symbol_info: SymbolInfo | None = None,
    strategy_name: str | None = None,
) -> BacktestResult:
    account_cfg = config["account"]
    risk_cfg = config["risk"]
    trading_cfg = config["trading"]
    execution_cfg = config["execution"]
    backtest_cfg = config["backtest"]
    strategy_cfg = config.get("strategy", {})
    symbol_info = symbol_info or default_symbol_info(str(trading_cfg["symbol"]))
    strategy_name = strategy_name or strategy_cfg.get("name", "htf_trend_pullback")
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    strategy_config = StrategyConfig(
        name=strategy_name,
        ema_fast=int(strategy_cfg.get("ema_fast", 50)),
        ema_slow=int(strategy_cfg.get("ema_slow", 200)),
        pullback_ema=int(strategy_cfg.get("pullback_ema", 20)),
        atr_period=int(strategy_cfg.get("atr_period", 14)),
        atr_stop_multiple=float(strategy_cfg.get("atr_stop_multiple", 1.5)),
        take_profit_r=float(strategy_cfg.get("take_profit_r", 2.0)),
        time_stop_bars=int(strategy_cfg.get("time_stop_bars", 32)),
        atr_min_percentile=float(strategy_cfg.get("atr_min_percentile", 0.20)),
        atr_max_percentile=float(strategy_cfg.get("atr_max_percentile", 0.90)),
        rolling_regime_bars=int(strategy_cfg.get("rolling_regime_bars", 5760)),
        session_start=str(trading_cfg.get("session_start", "07:00")),
        session_end=str(trading_cfg.get("session_end", "16:00")),
        max_trades_per_day=int(trading_cfg.get("max_trades_per_day", 3)),
        max_spread_points=float(execution_cfg.get("max_spread_points", 20)),
        point=symbol_info.point,
    )
    limits = RiskLimits(
        risk_per_trade=float(risk_cfg["risk_per_trade"]),
        max_daily_loss=float(risk_cfg["max_daily_loss"]),
        max_weekly_loss=float(risk_cfg["max_weekly_loss"]),
        max_total_drawdown=float(risk_cfg["max_total_drawdown"]),
        max_lot_size=float(risk_cfg["max_lot_size"]),
        min_lot_size=float(risk_cfg["min_lot_size"]),
        stop_loss_required=bool(risk_cfg.get("stop_loss_required", True)),
    )
    data = data.copy().sort_values("time").reset_index(drop=True)
    signals = STRATEGY_REGISTRY[strategy_name](data, strategy_config)
    signal_by_index = {signal.bar_index: signal for signal in signals}

    balance = float(backtest_cfg.get("initial_balance", account_cfg.get("initial_capital", 1000)))
    equity_peak = balance
    open_until = -1
    trades: list[BacktestTrade] = []
    equity_rows: list[dict[str, Any]] = []
    spread_price = float(backtest_cfg.get("spread_points", 0)) * symbol_info.point
    slippage_price = float(backtest_cfg.get("slippage_points", 0)) * symbol_info.point
    commission_per_lot = float(backtest_cfg.get("commission_per_lot", 0))

    for idx, row in data.iterrows():
        if idx <= open_until:
            equity_rows.append({"time": row["time"], "equity": balance, "balance": balance})
            continue
        signal = signal_by_index.get(int(idx))
        if signal is None:
            equity_rows.append({"time": row["time"], "equity": balance, "balance": balance})
            continue

        entry = signal.entry + spread_price / 2 + slippage_price if signal.side == "long" else signal.entry - spread_price / 2 - slippage_price
        account = AccountState(balance, balance, float(account_cfg["initial_capital"]), equity_peak)
        sizing = calculate_position_size(account, symbol_info, entry, signal.stop_loss, limits)
        if not sizing.allowed:
            equity_rows.append({"time": row["time"], "equity": balance, "balance": balance})
            continue
        exit_idx, exit_price, exit_reason = _simulate_exit(
            data,
            signal.bar_index,
            signal.side,
            signal.stop_loss,
            signal.take_profit,
            signal.time_stop_index,
            slippage_price,
        )
        gross = _pnl_for_move(signal.side, entry, exit_price, sizing.lot_size, symbol_info)
        commission = commission_per_lot * sizing.lot_size
        net = gross - commission
        balance += net
        equity_peak = max(equity_peak, balance)
        risk_cash = max(1e-12, sizing.risk_amount)
        trade = BacktestTrade(
            entry_time=str(signal.time),
            exit_time=str(data.iloc[exit_idx]["time"]),
            symbol=str(trading_cfg["symbol"]),
            side=signal.side,
            entry_price=round(entry, symbol_info.digits),
            exit_price=round(float(exit_price), symbol_info.digits),
            stop_loss=round(signal.stop_loss, symbol_info.digits),
            take_profit=round(signal.take_profit, symbol_info.digits),
            lots=sizing.lot_size,
            gross_pnl=gross,
            commission=commission,
            net_pnl=net,
            r_multiple=net / risk_cash,
            exit_reason=exit_reason,
            duration_bars=exit_idx - signal.bar_index,
            setup=signal.setup,
        )
        trades.append(trade)
        open_until = exit_idx
        equity_rows.append({"time": row["time"], "equity": balance, "balance": balance})

    equity_curve = pd.DataFrame(equity_rows)
    metrics = calculate_metrics(trades, equity_curve, float(backtest_cfg.get("initial_balance", 1000)))
    return BacktestResult(trades, equity_curve, metrics)


def calculate_metrics(trades: list[BacktestTrade], equity_curve: pd.DataFrame, initial_balance: float) -> dict[str, Any]:
    if not trades:
        return {
            "strategy_rejected": True,
            "rejection_reasons": ["no trades"],
            "total_trades": 0,
            "net_profit": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "max_drawdown": 0.0,
        }
    pnl = np.array([trade.net_pnl for trade in trades], dtype=float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    win_rate = float(len(wins) / len(pnl))
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(abs(losses.mean())) if len(losses) else 0.0
    expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss
    profit_factor = float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else float("inf")
    equity = equity_curve["equity"].astype(float) if not equity_curve.empty else pd.Series([initial_balance])
    running_peak = equity.cummax()
    drawdowns = (running_peak - equity) / running_peak.replace(0, np.nan)
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    downside = returns[returns < 0]
    sharpe = float(np.sqrt(252) * returns.mean() / returns.std(ddof=0)) if len(returns) > 1 and returns.std(ddof=0) > 0 else 0.0
    sortino = float(np.sqrt(252) * returns.mean() / downside.std(ddof=0)) if len(downside) > 1 and downside.std(ddof=0) > 0 else 0.0
    net_profit = float(equity.iloc[-1] - initial_balance)
    max_dd = float(drawdowns.max()) if len(drawdowns) else 0.0
    years = max(1e-9, len(equity) / (252 * 24 * 4))
    cagr_proxy = (float(equity.iloc[-1]) / initial_balance) ** (1.0 / years) - 1.0 if initial_balance > 0 and equity.iloc[-1] > 0 else -1.0
    streaks = _streaks(pnl)
    gross_loss = abs(float(losses.sum())) if len(losses) else 0.0
    metrics = {
        "strategy_rejected": False,
        "rejection_reasons": [],
        "total_trades": int(len(trades)),
        "win_rate": win_rate,
        "average_win": avg_win,
        "average_loss": avg_loss,
        "average_r_multiple": float(np.mean([trade.r_multiple for trade in trades])),
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "net_profit": net_profit,
        "max_drawdown": max_dd,
        "average_drawdown": float(drawdowns.mean()) if len(drawdowns) else 0.0,
        "recovery_factor": float(net_profit / (max_dd * initial_balance)) if max_dd > 0 else 0.0,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "mar_ratio": float(cagr_proxy / max_dd) if max_dd > 0 else 0.0,
        "longest_losing_streak": streaks["loss"],
        "longest_winning_streak": streaks["win"],
        "average_trade_duration_bars": float(np.mean([trade.duration_bars for trade in trades])),
        "exposure_time": float(sum(trade.duration_bars for trade in trades) / max(1, len(equity))),
        "gross_profit": float(wins.sum()) if len(wins) else 0.0,
        "gross_loss": gross_loss,
    }
    return metrics


def _streaks(pnl: np.ndarray) -> dict[str, int]:
    longest_win = longest_loss = current_win = current_loss = 0
    for value in pnl:
        if value > 0:
            current_win += 1
            current_loss = 0
        elif value < 0:
            current_loss += 1
            current_win = 0
        else:
            current_win = current_loss = 0
        longest_win = max(longest_win, current_win)
        longest_loss = max(longest_loss, current_loss)
    return {"win": longest_win, "loss": longest_loss}


def backtest_from_config(config: dict[str, Any]) -> BacktestResult:
    data_path = config["backtest"].get("data_path", "data/EURUSD_M15.csv")
    data, quality = load_csv(data_path)
    start = pd.Timestamp(config["backtest"]["start_date"], tz="UTC")
    end = pd.Timestamp(config["backtest"]["end_date"], tz="UTC")
    data = data[(data["time"] >= start) & (data["time"] <= end)].reset_index(drop=True)
    result = run_backtest(data, config)
    output_dir = ensure_dir(config["backtest"].get("output_dir", "reports/latest"))
    write_backtest_report(result, output_dir, extra={"data_quality": asdict(quality)})
    return result
