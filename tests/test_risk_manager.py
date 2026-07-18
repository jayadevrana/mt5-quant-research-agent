from risk_manager import AccountState, RiskLimits, daily_loss_breached, drawdown_from_initial, drawdown_from_peak, weekly_loss_breached


def test_drawdown_calculation_uses_initial_and_peak() -> None:
    account = AccountState(balance=950, equity=950, initial_capital=1000, equity_peak=1100)
    assert drawdown_from_initial(account) == 0.05
    assert round(drawdown_from_peak(account), 4) == 0.1364


def test_daily_and_weekly_loss_limits() -> None:
    limits = RiskLimits(0.005, 0.02, 0.05, 0.10, 0.10, 0.01)
    account = AccountState(1000, 1000, 1000, 1000, daily_pnl=-21, weekly_pnl=-51)
    assert daily_loss_breached(account, limits)
    assert weekly_loss_breached(account, limits)
