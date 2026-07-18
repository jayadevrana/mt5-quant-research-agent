from risk_manager import AccountState, RiskLimits, SymbolInfo, calculate_position_size


def symbol() -> SymbolInfo:
    return SymbolInfo("EURUSD", 0.00001, 0.00001, 1.0, 100000, 0.01, 100.0, 0.01)


def limits() -> RiskLimits:
    return RiskLimits(0.01, 0.02, 0.05, 0.10, 0.10, 0.01)


def test_position_sizing_respects_tick_value_step_and_max_lot() -> None:
    account = AccountState(1000, 1000, 1000, 1000)
    result = calculate_position_size(account, symbol(), 1.1000, 1.0990, limits())
    assert result.allowed
    assert result.lot_size == 0.10


def test_missing_symbol_info_fails_safely() -> None:
    account = AccountState(1000, 1000, 1000, 1000)
    result = calculate_position_size(account, None, 1.1000, 1.0990, limits())
    assert not result.allowed
    assert "symbol info" in result.reason


def test_invalid_stop_loss_distance_rejected() -> None:
    account = AccountState(1000, 1000, 1000, 1000)
    result = calculate_position_size(account, symbol(), 1.1000, 1.1000, limits())
    assert not result.allowed
    assert "stop loss distance" in result.reason
