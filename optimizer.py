from __future__ import annotations

from itertools import product
from typing import Any

import pandas as pd

from backtester import run_backtest


def parameter_sweep(data: pd.DataFrame, base_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    stop_values = [1.2, 1.5, 1.8]
    target_values = [1.5, 2.0, 2.5]
    for stop_multiple, target_r in product(stop_values, target_values):
        config = _copy_config(base_config)
        config.setdefault("strategy", {})
        config["strategy"]["atr_stop_multiple"] = stop_multiple
        config["strategy"]["take_profit_r"] = target_r
        result = run_backtest(data, config)
        rows.append(
            {
                "atr_stop_multiple": stop_multiple,
                "take_profit_r": target_r,
                "total_trades": result.metrics.get("total_trades", 0),
                "net_profit": result.metrics.get("net_profit", 0.0),
                "profit_factor": result.metrics.get("profit_factor", 0.0),
                "max_drawdown": result.metrics.get("max_drawdown", 0.0),
                "expectancy": result.metrics.get("expectancy", 0.0),
            }
        )
    return pd.DataFrame(rows)


def choose_stable_parameters(results: pd.DataFrame) -> dict[str, float]:
    if results.empty:
        return {"atr_stop_multiple": 1.5, "take_profit_r": 2.0}
    viable = results[(results["total_trades"] >= 20) & (results["profit_factor"] > 1.05)]
    if viable.empty:
        return {"atr_stop_multiple": 1.5, "take_profit_r": 2.0}
    viable = viable.sort_values(["profit_factor", "max_drawdown"], ascending=[False, True])
    row = viable.iloc[min(1, len(viable) - 1)]
    return {"atr_stop_multiple": float(row["atr_stop_multiple"]), "take_profit_r": float(row["take_profit_r"])}


def _copy_config(config: dict[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, value in config.items():
        copied[key] = dict(value) if isinstance(value, dict) else value
    return copied
