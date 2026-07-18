from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from backtester import run_backtest
from data_loader import load_csv
from optimizer import choose_stable_parameters, parameter_sweep
from utils import ensure_dir


def run_walk_forward(
    data: pd.DataFrame,
    config: dict[str, Any],
    train_bars: int = 35040,
    test_bars: int = 17520,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    start = 0
    window_id = 1
    while start + train_bars + test_bars <= len(data):
        train = data.iloc[start : start + train_bars].reset_index(drop=True)
        test = data.iloc[start + train_bars : start + train_bars + test_bars].reset_index(drop=True)
        sweep = parameter_sweep(train, config)
        params = choose_stable_parameters(sweep)
        test_config = _copy_config(config)
        test_config.setdefault("strategy", {}).update(params)
        result = run_backtest(test, test_config)
        rows.append(
            {
                "window": window_id,
                "train_start": str(train.iloc[0]["time"]),
                "train_end": str(train.iloc[-1]["time"]),
                "test_start": str(test.iloc[0]["time"]),
                "test_end": str(test.iloc[-1]["time"]),
                **params,
                "test_trades": result.metrics.get("total_trades", 0),
                "test_profit_factor": result.metrics.get("profit_factor", 0.0),
                "test_net_profit": result.metrics.get("net_profit", 0.0),
                "test_max_drawdown": result.metrics.get("max_drawdown", 0.0),
            }
        )
        start += test_bars
        window_id += 1
    return pd.DataFrame(rows)


def walk_forward_from_config(config: dict[str, Any]) -> pd.DataFrame:
    data, _ = load_csv(config["backtest"].get("data_path", "data/EURUSD_M15.csv"))
    output_dir = ensure_dir(config["backtest"].get("output_dir", "reports/latest"))
    results = run_walk_forward(data, config)
    results.to_csv(output_dir / "walk_forward_results.csv", index=False)
    stable = not results.empty and (results["test_profit_factor"] > 1.0).mean() >= 0.60
    summary = [
        "# Walk-Forward Summary",
        "",
        f"Windows: {len(results)}",
        f"Stable test windows: {stable}",
        "Reject the strategy if test performance is unstable or concentrated in one window.",
    ]
    (output_dir / "walk_forward_summary.md").write_text("\n".join(summary), encoding="utf-8")
    return results


def _copy_config(config: dict[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, value in config.items():
        copied[key] = dict(value) if isinstance(value, dict) else value
    return copied
