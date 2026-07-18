from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from recovery_manager import RecoveryConfig, evaluate_recovery
from risk_manager import AccountState
from utils import write_json


def generate_daily_review(
    trades_path: str | Path,
    report_path: str | Path,
    review_date: date | None,
    initial_capital: float,
    equity_peak: float | None = None,
) -> dict[str, Any]:
    path = Path(trades_path)
    if not path.exists():
        report = {
            "date": str(review_date or date.today()),
            "trades": 0,
            "should_continue_tomorrow": False,
            "trading_should_pause": True,
            "notes": "No trade log found. Run a backtest or demo session first.",
        }
        write_json(report_path, report)
        return report
    trades = pd.read_csv(path)
    if trades.empty:
        day_trades = trades
    else:
        trades["entry_time"] = pd.to_datetime(trades["entry_time"], utc=True)
        target_date = review_date or trades["entry_time"].dt.date.max()
        day_trades = trades[trades["entry_time"].dt.date == target_date]
    net_pnl = float(day_trades["net_pnl"].sum()) if not day_trades.empty else 0.0
    ending_equity = initial_capital + net_pnl
    account = AccountState(
        balance=ending_equity,
        equity=ending_equity,
        initial_capital=initial_capital,
        equity_peak=max(equity_peak or initial_capital, ending_equity),
        daily_pnl=net_pnl,
    )
    recovery = evaluate_recovery(account, 0.005, 3, RecoveryConfig())
    wins = day_trades[day_trades["net_pnl"] > 0] if not day_trades.empty else day_trades
    losses = day_trades[day_trades["net_pnl"] < 0] if not day_trades.empty else day_trades
    report = {
        "date": str(review_date or date.today()),
        "starting_balance": initial_capital,
        "ending_balance": ending_equity,
        "starting_equity": initial_capital,
        "ending_equity": ending_equity,
        "net_pnl": net_pnl,
        "net_r": float(day_trades["r_multiple"].sum()) if not day_trades.empty else 0.0,
        "number_of_trades": int(len(day_trades)),
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate": float(len(wins) / len(day_trades)) if len(day_trades) else 0.0,
        "average_win": float(wins["net_pnl"].mean()) if len(wins) else 0.0,
        "average_loss": float(losses["net_pnl"].mean()) if len(losses) else 0.0,
        "largest_win": float(day_trades["net_pnl"].max()) if len(day_trades) else 0.0,
        "largest_loss": float(day_trades["net_pnl"].min()) if len(day_trades) else 0.0,
        "max_intraday_drawdown": max(0.0, -net_pnl / initial_capital),
        "average_spread": None,
        "average_slippage": None,
        "rule_violations": [],
        "recovery_stage": int(recovery.mode),
        "should_continue_tomorrow": recovery.trading_allowed and not recovery.shutdown_required,
        "risk_should_be_reduced": int(recovery.mode) >= 1,
        "trading_should_pause": recovery.shutdown_required,
        "notes_for_human_review": "Do not modify strategy rules emotionally. Require statistical evidence.",
    }
    write_json(report_path, report)
    return report
