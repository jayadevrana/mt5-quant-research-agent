# Currency Pair Selection

This is a broker-neutral starting score. The system should recalculate execution suitability from local MT5 history when available, especially spread, slippage, tick value, swap, and data gaps.

Scores are 1 to 10 where 10 is best for a small, systematic MT5 account. News risk and swap impact are scored as controllability, not magnitude.

| Symbol | Liquidity | Spread Efficiency | Slippage Risk | ATR Opportunity | Trend | Mean Reversion | Breakout | News Risk Control | Swap Control | Data Quality | Broker Execution | Automation | Small Account | Drawdown Control | Total | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| EURUSD | 10 | 10 | 9 | 6 | 6 | 7 | 6 | 7 | 8 | 10 | 10 | 10 | 10 | 9 | 118 | Best beginner systematic symbol and final default |
| USDJPY | 9 | 8 | 8 | 7 | 8 | 6 | 7 | 6 | 6 | 9 | 8 | 8 | 8 | 7 | 105 | Strong trend candidate, watch intervention/news |
| GBPUSD | 8 | 7 | 7 | 8 | 7 | 6 | 8 | 5 | 6 | 9 | 7 | 8 | 7 | 6 | 99 | Opportunity, but more volatile |
| AUDUSD | 7 | 7 | 7 | 6 | 6 | 6 | 6 | 6 | 6 | 8 | 7 | 7 | 8 | 7 | 94 | Useful secondary regime tests |
| USDCAD | 7 | 7 | 7 | 6 | 6 | 6 | 6 | 5 | 6 | 8 | 7 | 7 | 7 | 7 | 92 | Oil/news sensitivity |
| USDCHF | 7 | 7 | 7 | 5 | 5 | 6 | 5 | 6 | 6 | 8 | 7 | 7 | 8 | 7 | 91 | Lower opportunity, safer liquidity |
| EURJPY | 7 | 6 | 6 | 8 | 7 | 5 | 7 | 5 | 5 | 8 | 6 | 7 | 6 | 5 | 88 | Trend candidate, wider risk |
| NZDUSD | 6 | 6 | 6 | 6 | 6 | 5 | 6 | 5 | 5 | 7 | 6 | 6 | 6 | 6 | 81 | Lower liquidity |
| GBPJPY | 6 | 5 | 5 | 9 | 8 | 4 | 8 | 4 | 4 | 7 | 5 | 6 | 4 | 4 | 79 | Volatile, difficult drawdown control |
| XAUUSD | 5 | 3 | 3 | 10 | 7 | 5 | 8 | 3 | 3 | 6 | 4 | 5 | 2 | 3 | 67 | Avoid unless broker conditions pass strict checks |

## Recommendations

- Best symbol for beginner systematic trading: EURUSD.
- Best symbol for trend-following: USDJPY or GBPJPY, but EURUSD remains safer for v1.
- Best symbol for intraday mean-reversion: EURUSD.
- Best symbol for breakout trading: GBPUSD or USDJPY after cost validation.
- Best symbol to avoid: XAUUSD for small accounts unless spread, slippage, volatility, and sizing are broker-verified.
- Final selected symbol for this project: EURUSD M15.
