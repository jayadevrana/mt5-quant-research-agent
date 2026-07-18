from monte_carlo import run_monte_carlo


def test_monte_carlo_reports_risk_and_rejection_flag() -> None:
    result = run_monte_carlo([1.0, -1.0, 0.5, -0.5, 2.0], simulations=100, max_drawdown=0.01)
    assert result.p95_max_drawdown >= 0
    assert result.probability_breaching_max_drawdown >= 0
    assert isinstance(result.strategy_rejected, bool)
