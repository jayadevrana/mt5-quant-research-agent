# mt5_codex_quant_agent

Local MT5 quant research and guarded execution framework. The purpose is to discover whether a real, cost-adjusted mathematical edge exists, not to invent a fake profitable EA.

## Risk Warning

Trading FX and CFDs can lose money quickly. This project provides research tooling and safety controls, not financial advice and not a profit guarantee. Live trading is disabled by default and should remain disabled unless a strategy survives robust local validation and manual review.

## What This Project Does

- Imports MT5 or CSV OHLCV data.
- Cleans candles and applies spread, commission, and slippage.
- Tests exact, codeable strategy hypotheses.
- Calculates expectancy, drawdown, profit factor, R multiples, streaks, Sharpe, Sortino, MAR, and cost sensitivity.
- Runs walk-forward and Monte Carlo validation.
- Enforces position sizing, daily/weekly loss limits, drawdown limits, kill switch, and live-trading locks.
- Produces CSV trade logs, JSON metrics, Markdown summaries, and daily review reports.

## Installation

```bash
cd mt5-quant-research-agent
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The `MetaTrader5` Python package is only available on Windows. On macOS/Linux, use CSV data exported from MT5 for research and tests.

## MT5 Setup

1. Install MetaTrader 5 on Windows.
2. Open a demo account first.
3. Enable the symbols you want to test in Market Watch.
4. Download at least 3 years of M15 history, preferably 5+ years.
5. Export CSV with columns compatible with `time,open,high,low,close,tick_volume,spread`.
6. Place the file at `data/EURUSD_M15.csv` or update `backtest.data_path`.

## Python Setup

Copy the example config:

```bash
cp config.example.yaml config.yaml
```

Keep these defaults unless you have a specific reason:

- `account.mode: demo`
- `account.live_trading_enabled: false`
- `safety.kill_switch: false`
- `risk.stop_loss_required: true`
- `recovery.allow_martingale: false`
- `recovery.allow_grid: false`
- `recovery.allow_averaging_down: false`

## Run Backtest

```bash
python main.py backtest --config config.example.yaml
```

Outputs:

- `reports/latest/trades.csv`
- `reports/latest/equity_curve.csv`
- `reports/latest/metrics.json`
- `reports/latest/summary.md`

If no local data is available, the command fails honestly and tells you to provide MT5 history.

## Run Monte Carlo

```bash
python main.py monte-carlo --trades reports/latest/trades.csv
```

The strategy is rejected if Monte Carlo drawdown or risk-of-ruin exceeds configured limits.

## Run Walk-Forward Validation

```bash
python main.py walk-forward --config config.example.yaml
```

Outputs:

- `reports/latest/walk_forward_results.csv`
- `reports/latest/walk_forward_summary.md`

## Run Demo Mode

```bash
python main.py demo --config config.yaml
```

Demo mode still enforces spread, stop-loss, drawdown, loss-limit, connection, and symbol-info checks.

## Live Mode

Live mode is deliberately hostile to accidental use:

```bash
python main.py live --config config.yaml
```

It refuses to trade unless:

- `account.live_trading_enabled: true`
- `account.mode: live`
- stop loss is defined and valid
- symbol info and account equity are readable
- spread is below `execution.max_spread_points`
- terminal connection is healthy
- kill switch is off
- daily, weekly, and total drawdown limits are valid
- user explicitly configured live mode

This project is not safe for live trading by default.

## Strategy

The default production candidate is a higher-timeframe trend pullback with volatility filter on EURUSD M15:

- H1 EMA 50/200 defines trend.
- M15 pullback to EMA 20 creates setup.
- ATR controls stop distance and volatility regime.
- Take profit defaults to 2R.
- Time stop exits stale trades.
- Max 3 trades per day.

The default candidate is only a hypothesis. It is rejected unless local data proves it robust after costs.

## Safety Controls

- No martingale.
- No grid.
- No averaging down.
- No lot doubling after losses.
- No no-stop-loss trades.
- Kill switch.
- Max daily loss.
- Max weekly loss.
- Max total drawdown.
- Max lot size.
- Spread and slippage filters.
- Live trading lock.

## Recovery Modes

Recovery means controlled recovery through positive expectancy, not bigger bets.

- Mode 0 Normal: standard risk.
- Mode 1 Warning: reduced risk after 2-3% drawdown.
- Mode 2 Defensive: heavily reduced risk after 5% drawdown.
- Mode 3 Recovery: only A+ setups below initial capital if strategy remains statistically valid.
- Mode 4 Shutdown: stop new trades after max drawdown, abnormal losing streak, invalidated strategy behavior, broker execution issues, or connection instability.

## Daily Review

```bash
python main.py daily-review --config config.example.yaml
```

The report includes balances, equity, net P/L, net R, wins, losses, win rate, average win/loss, max intraday drawdown, spread/slippage, rule violations, recovery stage, and whether the system should continue, reduce risk, or pause.

The review does not emotionally modify the strategy. It can only recommend changes if statistical evidence supports them.

## Compare Against Claude

Claude must beat:

- Evidence-backed edge selection.
- Explicit rejection of unverified claims.
- Deterministic backtesting with transaction costs.
- Walk-forward and Monte Carlo validation.
- Strict live-trading refusal gates.
- No martingale or grid recovery.
- Unit tests proving unsafe trades are refused.

## Current Verdict

- Safe for demo: yes after tests pass and local MT5 data backtest completes.
- Safe for live: no by default.
- Profitability: unknown until local data validates the strategy.

## Author

Built by [Jayadev Rana](https://jayadevrana.in) — @bluealgocapital · [YouTube](https://www.youtube.com/@jayadevrana3657) · [GitHub](https://github.com/jayadevrana)
