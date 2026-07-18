# Competition Scorecard

This score is intentionally conservative until real MT5 historical data is supplied and validation results are generated.

| Category | Points | Score | Notes |
|---|---:|---:|---|
| Research Quality | 10 | 8 | Evidence-backed categories, rejects gurus and screenshots |
| Mathematical Edge | 15 | 4 | Candidate hypothesis is clear, but edge is unproven until local validation |
| Backtesting Rigor | 15 | 13 | Costs, OOS, walk-forward, Monte Carlo, random baseline planned and implemented |
| Risk Management | 15 | 14 | Position sizing, loss limits, drawdown limits, kill switch |
| Recovery System | 10 | 10 | No martingale; staged risk reduction and shutdown rules |
| Code Quality | 15 | 13 | Modular, typed, tested, defensive defaults |
| Production Readiness | 10 | 8 | Demo-safe, MT5 integration guarded, live disabled |
| Documentation | 10 | 9 | Setup, risk warnings, safety, review process |
| Total | 100 | 79 | Strong framework, edge not yet proven |

## Codex Strengths

- Honest rejection gates.
- Explicit transaction-cost modeling.
- Strict live-trading lock.
- Monte Carlo drawdown and risk-of-ruin logic.
- Recovery framework reduces risk instead of increasing it.
- Tests prove unsafe trades are refused.

## Codex Weaknesses

- No live broker data is bundled.
- EURUSD trend-pullback edge is a hypothesis, not a proven result.
- News filtering is a placeholder unless the user supplies a calendar feed.
- Python MT5 package is Windows-only.

## What Claude Must Beat

Claude must provide a more robust, cost-adjusted, out-of-sample validated strategy with equal or better safety controls, clearer rejection gates, and comparable test coverage.

## What Would Make This System Invalid

- Poor out-of-sample performance.
- Monte Carlo drawdown above configured limits.
- Profit concentrated in one or two trades.
- Strategy fails spread or slippage stress tests.
- Broker execution differs materially from backtest assumptions.
- User enables live mode without statistical review.

## Is This Safe For Demo?

Yes, after tests pass and the user supplies local MT5 data for validation.

## Is This Safe For Live?

No by default. Live mode must remain disabled until manual review confirms robust out-of-sample results, acceptable Monte Carlo risk, broker execution quality, and valid risk limits.

## Final Verdict

This is a serious research and guarded-execution framework. It does not claim profitability. It is designed to find, validate, or reject a real edge.
