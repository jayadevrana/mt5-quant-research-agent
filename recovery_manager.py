from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from risk_manager import AccountState, drawdown_from_initial, drawdown_from_peak


class RecoveryMode(IntEnum):
    NORMAL = 0
    WARNING = 1
    DEFENSIVE = 2
    RECOVERY = 3
    SHUTDOWN = 4


@dataclass(frozen=True)
class RecoveryConfig:
    enabled: bool = True
    warning_drawdown: float = 0.03
    defensive_drawdown: float = 0.05
    shutdown_drawdown: float = 0.10
    reduce_risk_warning: float = 0.50
    reduce_risk_defensive: float = 0.75
    allow_martingale: bool = False
    allow_grid: bool = False
    allow_averaging_down: bool = False


@dataclass(frozen=True)
class RecoveryState:
    mode: RecoveryMode
    allowed_risk_per_trade: float
    allowed_trades_per_day: int
    trading_allowed: bool
    strategy_invalidated: bool
    shutdown_required: bool
    reason: str


def evaluate_recovery(
    account: AccountState,
    base_risk_per_trade: float,
    max_trades_per_day: int,
    config: RecoveryConfig,
    strategy_statistically_valid: bool = True,
    losing_streak_limit: int = 3,
    execution_abnormal: bool = False,
) -> RecoveryState:
    if not config.enabled:
        return RecoveryState(
            RecoveryMode.NORMAL,
            base_risk_per_trade,
            max_trades_per_day,
            True,
            False,
            False,
            "recovery disabled",
        )
    if config.allow_martingale or config.allow_grid or config.allow_averaging_down:
        return RecoveryState(RecoveryMode.SHUTDOWN, 0.0, 0, False, True, True, "unsafe recovery config")

    initial_dd = drawdown_from_initial(account)
    peak_dd = drawdown_from_peak(account)
    effective_dd = max(initial_dd, peak_dd)

    if (
        effective_dd >= config.shutdown_drawdown
        or account.consecutive_losses > losing_streak_limit
        or execution_abnormal
    ):
        return RecoveryState(RecoveryMode.SHUTDOWN, 0.0, 0, False, True, True, "shutdown trigger")
    if not strategy_statistically_valid:
        return RecoveryState(RecoveryMode.SHUTDOWN, 0.0, 0, False, True, True, "strategy invalidated")
    if account.equity < account.initial_capital and effective_dd >= config.defensive_drawdown:
        return RecoveryState(
            RecoveryMode.RECOVERY,
            base_risk_per_trade * (1.0 - config.reduce_risk_defensive),
            1,
            True,
            False,
            False,
            "below initial capital; recovery mode",
        )
    if effective_dd >= config.defensive_drawdown:
        return RecoveryState(
            RecoveryMode.DEFENSIVE,
            base_risk_per_trade * (1.0 - config.reduce_risk_defensive),
            1,
            True,
            False,
            False,
            "defensive drawdown threshold reached",
        )
    if effective_dd >= config.warning_drawdown * (2.0 / 3.0):
        return RecoveryState(
            RecoveryMode.WARNING,
            base_risk_per_trade * (1.0 - config.reduce_risk_warning),
            max(1, max_trades_per_day // 2),
            True,
            False,
            False,
            "warning drawdown threshold reached",
        )
    return RecoveryState(
        RecoveryMode.NORMAL,
        base_risk_per_trade,
        max_trades_per_day,
        True,
        False,
        False,
        "normal mode",
    )
