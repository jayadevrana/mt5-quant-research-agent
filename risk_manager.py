from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from utils import floor_to_step


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    min_lot: float
    max_lot: float
    lot_step: float
    digits: int = 5


@dataclass(frozen=True)
class AccountState:
    balance: float
    equity: float
    initial_capital: float
    equity_peak: float
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    consecutive_losses: int = 0
    login: int | None = None
    server: str | None = None
    trade_mode: int | None = None


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade: float
    max_daily_loss: float
    max_weekly_loss: float
    max_total_drawdown: float
    max_lot_size: float
    min_lot_size: float
    stop_loss_required: bool = True


@dataclass(frozen=True)
class PositionSizeResult:
    allowed: bool
    lot_size: float
    risk_amount: float
    money_per_lot_at_stop: float
    reason: str = ""


def drawdown_from_initial(account: AccountState) -> float:
    if account.initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    return max(0.0, (account.initial_capital - account.equity) / account.initial_capital)


def drawdown_from_peak(account: AccountState) -> float:
    if account.equity_peak <= 0:
        raise ValueError("equity_peak must be positive")
    return max(0.0, (account.equity_peak - account.equity) / account.equity_peak)


def validate_symbol_info(symbol_info: SymbolInfo | None) -> str | None:
    if symbol_info is None:
        return "symbol info unavailable"
    fields = [
        symbol_info.point,
        symbol_info.tick_size,
        symbol_info.tick_value,
        symbol_info.contract_size,
        symbol_info.min_lot,
        symbol_info.max_lot,
        symbol_info.lot_step,
    ]
    if any(value <= 0 or not isfinite(value) for value in fields):
        return "invalid symbol info values"
    if symbol_info.min_lot > symbol_info.max_lot:
        return "min lot exceeds max lot"
    return None


def calculate_position_size(
    account: AccountState,
    symbol_info: SymbolInfo | None,
    entry_price: float,
    stop_loss: float | None,
    limits: RiskLimits,
    allowed_risk_per_trade: float | None = None,
) -> PositionSizeResult:
    symbol_error = validate_symbol_info(symbol_info)
    if symbol_error:
        return PositionSizeResult(False, 0.0, 0.0, 0.0, symbol_error)
    assert symbol_info is not None
    if limits.stop_loss_required and stop_loss is None:
        return PositionSizeResult(False, 0.0, 0.0, 0.0, "stop loss required")
    if stop_loss is None:
        return PositionSizeResult(False, 0.0, 0.0, 0.0, "stop loss missing")
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0 or not isfinite(stop_distance):
        return PositionSizeResult(False, 0.0, 0.0, 0.0, "invalid stop loss distance")
    if account.equity <= 0:
        return PositionSizeResult(False, 0.0, 0.0, 0.0, "account equity invalid")
    risk_fraction = allowed_risk_per_trade if allowed_risk_per_trade is not None else limits.risk_per_trade
    if risk_fraction <= 0 or risk_fraction > 0.05:
        return PositionSizeResult(False, 0.0, 0.0, 0.0, "risk fraction invalid")
    risk_amount = account.equity * risk_fraction
    money_per_lot_at_stop = stop_distance / symbol_info.tick_size * symbol_info.tick_value
    if money_per_lot_at_stop <= 0 or not isfinite(money_per_lot_at_stop):
        return PositionSizeResult(False, 0.0, 0.0, 0.0, "stop value invalid")
    raw_lots = risk_amount / money_per_lot_at_stop
    capped_max = min(symbol_info.max_lot, limits.max_lot_size)
    lot_size = floor_to_step(raw_lots, symbol_info.lot_step)
    lot_size = max(0.0, min(lot_size, capped_max))
    if lot_size < max(symbol_info.min_lot, limits.min_lot_size):
        return PositionSizeResult(False, 0.0, risk_amount, money_per_lot_at_stop, "lot size below minimum")
    return PositionSizeResult(True, round(lot_size, 8), risk_amount, money_per_lot_at_stop)


def daily_loss_breached(account: AccountState, limits: RiskLimits) -> bool:
    return account.daily_pnl <= -abs(account.initial_capital * limits.max_daily_loss)


def weekly_loss_breached(account: AccountState, limits: RiskLimits) -> bool:
    return account.weekly_pnl <= -abs(account.initial_capital * limits.max_weekly_loss)


def total_drawdown_breached(account: AccountState, limits: RiskLimits) -> bool:
    return max(drawdown_from_initial(account), drawdown_from_peak(account)) >= limits.max_total_drawdown
