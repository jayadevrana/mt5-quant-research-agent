from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from utils import ensure_dir, write_json


def write_backtest_report(result: Any, output_dir: str | Path, extra: dict[str, Any] | None = None) -> None:
    target = ensure_dir(output_dir)
    trades = pd.DataFrame([asdict(trade) for trade in result.trades])
    trades.to_csv(target / "trades.csv", index=False)
    result.equity_curve.to_csv(target / "equity_curve.csv", index=False)
    payload = dict(result.metrics)
    if extra:
        payload.update(extra)
    write_json(target / "metrics.json", payload)
    summary = [
        "# Backtest Summary",
        "",
        f"Total trades: {payload.get('total_trades', 0)}",
        f"Net profit: {payload.get('net_profit', 0):.2f}",
        f"Profit factor: {payload.get('profit_factor', 0):.4f}",
        f"Expectancy: {payload.get('expectancy', 0):.4f}",
        f"Max drawdown: {payload.get('max_drawdown', 0):.2%}",
        f"Strategy rejected: {payload.get('strategy_rejected', False)}",
        "",
        "This report is not evidence of future profitability. Review OOS, walk-forward, Monte Carlo, and cost stress results before demo use.",
    ]
    (target / "summary.md").write_text("\n".join(summary), encoding="utf-8")
