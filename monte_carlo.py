from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from utils import write_json


@dataclass(frozen=True)
class MonteCarloResult:
    median_final_equity: float
    p05_final_equity: float
    p95_final_equity: float
    median_max_drawdown: float
    p95_max_drawdown: float
    probability_breaching_max_drawdown: float
    probability_losing_initial_threshold: float
    estimated_risk_of_ruin: float
    strategy_rejected: bool


def run_monte_carlo(
    r_multiples: list[float] | np.ndarray,
    initial_equity: float = 1000.0,
    risk_per_trade: float = 0.005,
    simulations: int = 1000,
    max_drawdown: float = 0.10,
    ruin_threshold: float = 0.50,
    seed: int = 260524,
) -> MonteCarloResult:
    values = np.asarray(r_multiples, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return MonteCarloResult(0, 0, 0, 0, 1, 1, 1, 1, True)
    rng = np.random.default_rng(seed)
    finals: list[float] = []
    drawdowns: list[float] = []
    breached = 0
    below_threshold = 0
    ruined = 0
    for _ in range(simulations):
        sample = rng.choice(values, size=len(values), replace=True)
        equity = initial_equity
        peak = initial_equity
        max_dd = 0.0
        for r_value in sample:
            equity *= max(0.0, 1.0 + r_value * risk_per_trade)
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else 1.0
            max_dd = max(max_dd, dd)
        finals.append(equity)
        drawdowns.append(max_dd)
        breached += int(max_dd >= max_drawdown)
        below_threshold += int(equity <= initial_equity * (1.0 - max_drawdown))
        ruined += int(equity <= initial_equity * ruin_threshold)
    result = MonteCarloResult(
        median_final_equity=float(np.percentile(finals, 50)),
        p05_final_equity=float(np.percentile(finals, 5)),
        p95_final_equity=float(np.percentile(finals, 95)),
        median_max_drawdown=float(np.percentile(drawdowns, 50)),
        p95_max_drawdown=float(np.percentile(drawdowns, 95)),
        probability_breaching_max_drawdown=float(breached / simulations),
        probability_losing_initial_threshold=float(below_threshold / simulations),
        estimated_risk_of_ruin=float(ruined / simulations),
        strategy_rejected=bool(np.percentile(drawdowns, 95) >= max_drawdown or ruined / simulations > 0.05),
    )
    return result


def monte_carlo_from_trades(
    trades_path: str | Path,
    output_path: str | Path = "reports/latest/monte_carlo.json",
    initial_equity: float = 1000.0,
    risk_per_trade: float = 0.005,
    max_drawdown: float = 0.10,
) -> MonteCarloResult:
    trades = pd.read_csv(trades_path)
    if "r_multiple" not in trades.columns:
        raise ValueError("trades file must contain r_multiple")
    result = run_monte_carlo(
        trades["r_multiple"].dropna().to_numpy(),
        initial_equity=initial_equity,
        risk_per_trade=risk_per_trade,
        max_drawdown=max_drawdown,
    )
    write_json(output_path, result.__dict__)
    return result
