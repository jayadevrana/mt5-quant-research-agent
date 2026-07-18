# RawStructurePortfolioEA Build Report

## Output

- Built: `mt5_codex_quant_agent/mql5/RawStructurePortfolioEA.mq5`
- Existing file preserved: `mt5_codex_quant_agent/mql5/ExecutionBridgeEA.mq5`
- Attach/deploy status: not attached, not deployed
- Default trading status: `EnableTrading=false`, dry-run logging only

## What Was Built

I built one MT5 Expert Advisor suite with two internal strategy modules and one shared master controller:

- `TrendModule`: directional expansion / break-of-structure module.
- `RangeModule`: sideways range / sweep-rejection module.
- `MasterRiskManager`: shared risk gates, symbol lock, currency exposure, portfolio exposure, daily target, loss stops, drawdown stop, recovery mode, spread/slippage/session/news filters.
- `ExecutionEngine`: sends orders only with hard SL and hard 5R TP after broker stop-level, freeze-level, lot-step, margin, spread-to-risk, and slippage-to-risk checks.
- `Logger`: writes signal, rejection, dry-run, order, and management events to a common MT5 CSV file.
- Multi-timeframe regime handling: `StructureTimeframe` acts as the higher-timeframe authority and `ExecutionTimeframe` is used for setup/entry confirmation. If they disagree, the symbol is treated as `UNSAFE`.

## Non-Indicator Rules

The EA does not call indicator handles or indicator buffers for entries/exits. The source was checked for common indicator calls:

- No `iCustom`
- No `iMA`
- No `iRSI`
- No `iMACD`
- No `iBands`
- No `iADX`
- No `iStochastic`
- No `iIchimoku`
- No `iATR`
- No `CopyBuffer`

Signal logic is based on raw `CopyRates` OHLC data, candle ranges/bodies/wicks, close location, confirmed swing highs/lows, break-of-structure closes, range containment, spread, time filters, and execution metrics.

## Trend EA Logic

The trend module:

- Detects confirmed swing highs/lows with raw candle comparisons.
- Requires rising swing lows for bullish mode or falling swing highs for bearish mode.
- Requires a completed candle close beyond structure plus a BOS buffer.
- Requires displacement versus median candle body/range behavior.
- Rejects abnormal candles.
- Creates a breakout-retest setup and waits for rejection/acceptance.
- Enters only after confirmation beyond the rejection candle.
- Places structural SL beyond the retest/origin extreme plus buffer.
- Places hard TP at exactly 5R.
- Rejects trend trades when a nearer opposing swing blocks the 5R path.

## Range EA Logic

The range module:

- Builds upper/lower boundary zones from clustered swing highs/lows.
- Requires minimum range age, minimum touches per side, containment ratio, and enough width.
- Rejects ranges with recent BOS closes outside the boundary.
- Waits for a boundary sweep and rejection candle.
- Enters only after confirmation.
- Places hard SL beyond the sweep extreme plus buffer.
- Places hard TP at exactly 5R.
- Rejects range trades if the 5R target does not fit inside the opposite danger zone.

## Risk Controls

Implemented controls include:

- One open position per symbol for this EA magic number.
- No trend/range conflict on the same symbol.
- Max risk per trade, symbol, currency, strategy family, and portfolio.
- Daily closed-profit stop at `DailyProfitTargetPct` of `InitialCapital`.
- Daily, weekly, and monthly loss stops.
- Max drawdown stop.
- Consecutive-loss stop.
- Loss cooldown per symbol.
- Spread-to-risk and slippage-to-risk filters.
- Broker stop-level/freeze-level validation.
- Min free-margin multiple and max used-margin cap.
- Friday/weekend and rollover filters.
- Optional MT5 economic-calendar high-impact news filter.

## Recovery Mode

Recovery is capped and conservative:

- No averaging down.
- No grid.
- No lot doubling after a loss.
- No SL widening or SL removal.
- Activates only when no EA positions are open and balance/equity are below `InitialCapital`.
- Uses `0.30%`, `0.35%`, or `0.40%` risk depending on deficit.
- Disables after two consecutive recovery losses, excess drawdown, slippage degradation, or recovery above initial capital.

## Trade Management

The EA manages open positions with:

- No break-even before `BreakEvenAfterR`, default `1.2R`.
- Break-even only to entry plus estimated spread/slippage cost.
- Trend trailing only after `TrailAfterTrendR`, default `2R`.
- Range trailing only after `TrailAfterRangeR`, default `3R`.
- Optional structural trailing behind raw minor swings.
- Optional +1R lock after `LockOneRAfterR`, default `3R`.

## Verification Performed Here

- Created source file without modifying the existing bridge EA.
- Confirmed no common MQL indicator calls are present.
- Confirmed the EA defaults to dry-run mode.
- Checked the workspace for MetaEditor/Wine; neither is installed here.

## Not Yet Verified

This macOS workspace cannot compile `.mq5` to `.ex5` because MetaEditor is not available. Next required validation steps are:

- Compile `RawStructurePortfolioEA.mq5` in MetaEditor on Windows.
- Fix any broker/build-specific MQL compile warnings.
- Run MT5 Strategy Tester in visual dry-run mode first.
- Confirm CSV logs show accepted and rejected trades correctly.
- Run real-tick backtests before any demo attachment.
- Keep `EnableTrading=false` until compile, tester, and demo behavior are reviewed.
