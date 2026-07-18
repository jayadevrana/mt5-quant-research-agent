from recovery_manager import RecoveryMode, RecoveryState
from risk_manager import AccountState, RiskLimits, SymbolInfo
from safety import SafetyContext, TradeRequest, validate_trade_request


def context(**overrides) -> SafetyContext:
    base = {
        "account_mode": "demo",
        "live_trading_enabled": False,
        "kill_switch": False,
        "terminal_connected": True,
        "market_open": True,
        "current_spread_points": 10,
        "max_spread_points": 20,
        "require_stop_loss": True,
        "account": AccountState(1000, 1000, 1000, 1000),
        "symbol_info": SymbolInfo("EURUSD", 0.00001, 0.00001, 1.0, 100000, 0.01, 100, 0.01),
        "risk_limits": RiskLimits(0.005, 0.02, 0.05, 0.10, 0.10, 0.01),
        "recovery_state": RecoveryState(RecoveryMode.NORMAL, 0.005, 3, True, False, False, "ok"),
        "expected_mode": "demo",
    }
    base.update(overrides)
    return SafetyContext(**base)


def request() -> TradeRequest:
    return TradeRequest("EURUSD", "long", 1.1000, 1.0990, 1.1020)


def test_spread_filter_blocks_trade() -> None:
    result = validate_trade_request(request(), context(current_spread_points=25))
    assert not result.allowed
    assert "spread" in result.reason


def test_live_trading_lock_refuses_live() -> None:
    result = validate_trade_request(request(), context(account_mode="demo", expected_mode="live"))
    assert not result.allowed
    assert "live trading lock" in result.reason


def test_kill_switch_blocks_trade() -> None:
    result = validate_trade_request(request(), context(kill_switch=True))
    assert not result.allowed
    assert "kill switch" in result.reason


def test_daily_loss_blocks_trade() -> None:
    account = AccountState(1000, 1000, 1000, 1000, daily_pnl=-25)
    result = validate_trade_request(request(), context(account=account))
    assert not result.allowed
    assert "daily loss" in result.reason


def test_account_number_mismatch_blocks_trade() -> None:
    account = AccountState(1000, 1000, 1000, 1000, login=111111)
    result = validate_trade_request(request(), context(account=account, expected_account_number=25296434))
    assert not result.allowed
    assert "account number mismatch" in result.reason


def test_demo_mode_refuses_actual_live_account() -> None:
    account = AccountState(1000, 1000, 1000, 1000, login=25296434, trade_mode=2)
    result = validate_trade_request(request(), context(account=account, account_mode="demo"))
    assert not result.allowed
    assert "live, not demo" in result.reason
