from __future__ import annotations

from dataclasses import dataclass

from recovery_manager import RecoveryState
from risk_manager import (
    AccountState,
    RiskLimits,
    SymbolInfo,
    calculate_position_size,
    daily_loss_breached,
    total_drawdown_breached,
    validate_symbol_info,
    weekly_loss_breached,
)


@dataclass(frozen=True)
class TradeRequest:
    symbol: str
    side: str
    entry_price: float
    stop_loss: float | None
    take_profit: float | None
    requested_lots: float | None = None


@dataclass(frozen=True)
class SafetyContext:
    account_mode: str
    live_trading_enabled: bool
    kill_switch: bool
    terminal_connected: bool
    market_open: bool
    current_spread_points: float
    max_spread_points: float
    require_stop_loss: bool
    account: AccountState | None
    symbol_info: SymbolInfo | None
    risk_limits: RiskLimits
    recovery_state: RecoveryState
    expected_mode: str = "demo"
    expected_account_number: int | None = None


@dataclass(frozen=True)
class SafetyResult:
    allowed: bool
    reason: str
    lot_size: float = 0.0


def validate_trade_request(request: TradeRequest, context: SafetyContext) -> SafetyResult:
    if context.kill_switch:
        return SafetyResult(False, "kill switch enabled")
    if context.account_mode not in {"demo", "live", "backtest"}:
        return SafetyResult(False, "invalid account mode")
    if context.account_mode == "demo" and context.account is not None and context.account.trade_mode == 2:
        return SafetyResult(False, "connected account is live, not demo")
    if context.expected_mode == "live":
        if context.account_mode != "live" or not context.live_trading_enabled:
            return SafetyResult(False, "live trading lock")
    elif context.account_mode == "live" and not context.live_trading_enabled:
        return SafetyResult(False, "live trading disabled")
    if not context.terminal_connected:
        return SafetyResult(False, "terminal disconnected")
    if not context.market_open:
        return SafetyResult(False, "market closed")
    if context.current_spread_points > context.max_spread_points:
        return SafetyResult(False, "spread too high")
    if context.require_stop_loss and request.stop_loss is None:
        return SafetyResult(False, "stop loss required")
    if context.account is None:
        return SafetyResult(False, "account information unavailable")
    if (
        context.expected_account_number is not None
        and context.account.login != context.expected_account_number
    ):
        return SafetyResult(False, "account number mismatch")
    symbol_error = validate_symbol_info(context.symbol_info)
    if symbol_error:
        return SafetyResult(False, symbol_error)
    if daily_loss_breached(context.account, context.risk_limits):
        return SafetyResult(False, "daily loss limit breached")
    if weekly_loss_breached(context.account, context.risk_limits):
        return SafetyResult(False, "weekly loss limit breached")
    if total_drawdown_breached(context.account, context.risk_limits):
        return SafetyResult(False, "drawdown limit breached")
    if not context.recovery_state.trading_allowed or context.recovery_state.shutdown_required:
        return SafetyResult(False, f"recovery manager blocked trading: {context.recovery_state.reason}")
    sizing = calculate_position_size(
        account=context.account,
        symbol_info=context.symbol_info,
        entry_price=request.entry_price,
        stop_loss=request.stop_loss,
        limits=context.risk_limits,
        allowed_risk_per_trade=context.recovery_state.allowed_risk_per_trade,
    )
    if not sizing.allowed:
        return SafetyResult(False, f"risk calculation failed: {sizing.reason}")
    if request.requested_lots is not None and request.requested_lots > sizing.lot_size:
        return SafetyResult(False, "requested lot size exceeds allowed lot size")
    return SafetyResult(True, "trade allowed", request.requested_lots or sizing.lot_size)
