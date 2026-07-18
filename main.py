from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from backtester import backtest_from_config
from daily_review import generate_daily_review
from monte_carlo import monte_carlo_from_trades
from mt5_connector import MT5Connector
from recovery_manager import RecoveryConfig, evaluate_recovery
from risk_manager import AccountState, RiskLimits
from safety import SafetyContext, TradeRequest, validate_trade_request
from state_store import StateStore
from strategy import STRATEGY_REGISTRY, StrategyConfig
from utils import load_config, setup_logging
from walk_forward import walk_forward_from_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MT5 Codex Quant Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ["backtest", "walk-forward", "daily-review", "demo", "live"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", default="config.example.yaml")

    mc = sub.add_parser("monte-carlo")
    mc.add_argument("--trades", default="reports/latest/trades.csv")
    mc.add_argument("--config", default="config.example.yaml")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(args.config)
    logger = setup_logging("logs")

    if args.command == "backtest":
        result = backtest_from_config(config)
        logger.info("Backtest complete: %s trades, PF=%s", result.metrics.get("total_trades"), result.metrics.get("profit_factor"))
        return 0
    if args.command == "monte-carlo":
        result = monte_carlo_from_trades(
            args.trades,
            initial_equity=float(config["backtest"].get("initial_balance", 1000)),
            risk_per_trade=float(config["risk"].get("risk_per_trade", 0.005)),
            max_drawdown=float(config["risk"].get("max_total_drawdown", 0.10)),
        )
        logger.info("Monte Carlo complete: rejected=%s p95_dd=%.2f%%", result.strategy_rejected, result.p95_max_drawdown * 100)
        return 0
    if args.command == "walk-forward":
        results = walk_forward_from_config(config)
        logger.info("Walk-forward complete: %s windows", len(results))
        return 0
    if args.command == "daily-review":
        output_dir = Path(config["backtest"].get("output_dir", "reports/latest"))
        report = generate_daily_review(
            output_dir / "trades.csv",
            output_dir / "daily_review.json",
            date.today(),
            float(config["account"].get("initial_capital", 1000)),
        )
        logger.info("Daily review complete: pause=%s", report.get("trading_should_pause"))
        return 0
    if args.command in {"demo", "live"}:
        if args.command == "demo":
            return run_demo_once(config)
        return run_preflight(config, expected_mode=args.command)
    raise ValueError(args.command)


def run_preflight(config: dict, expected_mode: str) -> int:
    logger = setup_logging("logs")
    connector = MT5Connector(config.get("account", {}).get("mt5_terminal_path"))
    status = connector.initialize()
    account_cfg = config["account"]
    risk_cfg = config["risk"]
    execution_cfg = config["execution"]
    trading_cfg = config["trading"]
    recovery_cfg = config["recovery"]
    account = connector.account_state(
        float(account_cfg.get("initial_capital", 1000)),
        float(account_cfg.get("initial_capital", 1000)),
    )
    symbol_info = connector.symbol_info(trading_cfg["symbol"])
    spread = connector.spread_points(trading_cfg["symbol"])
    fallback_account = account or AccountState(
        balance=float(account_cfg.get("initial_capital", 1000)),
        equity=float(account_cfg.get("initial_capital", 1000)),
        initial_capital=float(account_cfg.get("initial_capital", 1000)),
        equity_peak=float(account_cfg.get("initial_capital", 1000)),
    )
    limits = RiskLimits(
        risk_per_trade=float(risk_cfg["risk_per_trade"]),
        max_daily_loss=float(risk_cfg["max_daily_loss"]),
        max_weekly_loss=float(risk_cfg["max_weekly_loss"]),
        max_total_drawdown=float(risk_cfg["max_total_drawdown"]),
        max_lot_size=float(risk_cfg["max_lot_size"]),
        min_lot_size=float(risk_cfg["min_lot_size"]),
        stop_loss_required=bool(risk_cfg.get("stop_loss_required", True)),
    )
    recovery = evaluate_recovery(
        fallback_account,
        limits.risk_per_trade,
        int(trading_cfg.get("max_trades_per_day", 3)),
        RecoveryConfig(
            enabled=bool(recovery_cfg.get("enabled", True)),
            warning_drawdown=float(recovery_cfg.get("warning_drawdown", 0.03)),
            defensive_drawdown=float(recovery_cfg.get("defensive_drawdown", 0.05)),
            shutdown_drawdown=float(recovery_cfg.get("shutdown_drawdown", 0.10)),
            reduce_risk_warning=float(recovery_cfg.get("reduce_risk_warning", 0.50)),
            reduce_risk_defensive=float(recovery_cfg.get("reduce_risk_defensive", 0.75)),
            allow_martingale=bool(recovery_cfg.get("allow_martingale", False)),
            allow_grid=bool(recovery_cfg.get("allow_grid", False)),
            allow_averaging_down=bool(recovery_cfg.get("allow_averaging_down", False)),
        ),
    )
    request = TradeRequest(
        symbol=trading_cfg["symbol"],
        side="long",
        entry_price=1.10000,
        stop_loss=1.09850,
        take_profit=1.10300,
    )
    context = SafetyContext(
        account_mode=str(account_cfg.get("mode", "demo")),
        live_trading_enabled=bool(account_cfg.get("live_trading_enabled", False)),
        kill_switch=bool(config["safety"].get("kill_switch", False)),
        terminal_connected=status.connected,
        market_open=True,
        current_spread_points=float(spread if spread is not None else 10**9),
        max_spread_points=float(execution_cfg.get("max_spread_points", 20)),
        require_stop_loss=bool(execution_cfg.get("require_stop_loss", True)),
        account=account,
        symbol_info=symbol_info,
        risk_limits=limits,
        recovery_state=recovery,
        expected_mode=expected_mode,
        expected_account_number=account_cfg.get("account_number"),
    )
    result = validate_trade_request(request, context)
    connector.shutdown()
    if not result.allowed:
        logger.warning("%s preflight refused trading: %s", expected_mode, result.reason)
        return 2 if expected_mode == "live" else 1
    logger.info("%s preflight passed. No order was placed by preflight.", expected_mode)
    return 0


def run_demo_once(config: dict) -> int:
    logger = setup_logging("logs")
    connector = MT5Connector(config.get("account", {}).get("mt5_terminal_path"))
    status = connector.initialize()
    if not status.connected:
        logger.warning("demo trading refused: %s", status.reason)
        return 1

    try:
        account_cfg = config["account"]
        trading_cfg = config["trading"]
        risk_cfg = config["risk"]
        execution_cfg = config["execution"]
        recovery_cfg = config["recovery"]
        strategy_cfg = config.get("strategy", {})

        account = connector.account_state(
            float(account_cfg.get("initial_capital", 25000)),
            float(account_cfg.get("initial_capital", 25000)),
        )
        symbol_info = connector.symbol_info(trading_cfg["symbol"])
        spread = connector.spread_points(trading_cfg["symbol"])
        if account is None:
            logger.warning("demo trading refused: account information unavailable")
            return 1

        limits = RiskLimits(
            risk_per_trade=float(risk_cfg["risk_per_trade"]),
            max_daily_loss=float(risk_cfg["max_daily_loss"]),
            max_weekly_loss=float(risk_cfg["max_weekly_loss"]),
            max_total_drawdown=float(risk_cfg["max_total_drawdown"]),
            max_lot_size=float(risk_cfg["max_lot_size"]),
            min_lot_size=float(risk_cfg["min_lot_size"]),
            stop_loss_required=bool(risk_cfg.get("stop_loss_required", True)),
        )
        recovery = evaluate_recovery(
            account,
            limits.risk_per_trade,
            int(trading_cfg.get("max_trades_per_day", 1)),
            RecoveryConfig(
                enabled=bool(recovery_cfg.get("enabled", True)),
                warning_drawdown=float(recovery_cfg.get("warning_drawdown", 0.03)),
                defensive_drawdown=float(recovery_cfg.get("defensive_drawdown", 0.05)),
                shutdown_drawdown=float(recovery_cfg.get("shutdown_drawdown", 0.08)),
                reduce_risk_warning=float(recovery_cfg.get("reduce_risk_warning", 0.50)),
                reduce_risk_defensive=float(recovery_cfg.get("reduce_risk_defensive", 0.75)),
                allow_martingale=bool(recovery_cfg.get("allow_martingale", False)),
                allow_grid=bool(recovery_cfg.get("allow_grid", False)),
                allow_averaging_down=bool(recovery_cfg.get("allow_averaging_down", False)),
            ),
        )
        data = connector.recent_rates(
            trading_cfg["symbol"],
            trading_cfg.get("timeframe", "M15"),
            count=max(1200, int(strategy_cfg.get("rolling_regime_bars", 5760)) + 250),
        )
        strategy_name = strategy_cfg.get("name", "htf_trend_pullback")
        strategy_config = StrategyConfig(
            name=strategy_name,
            ema_fast=int(strategy_cfg.get("ema_fast", 50)),
            ema_slow=int(strategy_cfg.get("ema_slow", 200)),
            pullback_ema=int(strategy_cfg.get("pullback_ema", 20)),
            atr_period=int(strategy_cfg.get("atr_period", 14)),
            atr_stop_multiple=float(strategy_cfg.get("atr_stop_multiple", 1.5)),
            take_profit_r=float(strategy_cfg.get("take_profit_r", 2.0)),
            time_stop_bars=int(strategy_cfg.get("time_stop_bars", 32)),
            atr_min_percentile=float(strategy_cfg.get("atr_min_percentile", 0.20)),
            atr_max_percentile=float(strategy_cfg.get("atr_max_percentile", 0.90)),
            rolling_regime_bars=int(strategy_cfg.get("rolling_regime_bars", 5760)),
            session_start=str(trading_cfg.get("session_start", "07:00")),
            session_end=str(trading_cfg.get("session_end", "16:00")),
            max_trades_per_day=int(trading_cfg.get("max_trades_per_day", 1)),
            max_spread_points=float(execution_cfg.get("max_spread_points", 50)),
            point=float(symbol_info.point if symbol_info else 0.01),
        )
        signals = STRATEGY_REGISTRY[strategy_name](data, strategy_config)
        if not signals:
            logger.info("demo scan complete: no valid %s signal on %s", strategy_name, trading_cfg["symbol"])
            return 0
        latest = signals[-1]
        if latest.bar_index < len(data) - 2:
            logger.info("demo scan complete: latest signal is stale at %s", latest.time)
            return 0
        if connector.open_position_count(trading_cfg["symbol"]) > 0:
            logger.info("demo scan complete: existing %s position present; no duplicate entry", trading_cfg["symbol"])
            return 0
        state = StateStore("state/demo_state.json")
        state_payload = state.load()
        signal_key = f"{trading_cfg['symbol']}:{strategy_name}:{latest.time}"
        if state_payload.get("last_signal_key") == signal_key:
            logger.info("demo scan complete: signal %s already handled", signal_key)
            return 0
        request = TradeRequest(
            symbol=trading_cfg["symbol"],
            side=latest.side,
            entry_price=latest.entry,
            stop_loss=latest.stop_loss,
            take_profit=latest.take_profit,
        )
        context = SafetyContext(
            account_mode=str(account_cfg.get("mode", "demo")),
            live_trading_enabled=bool(account_cfg.get("live_trading_enabled", False)),
            kill_switch=bool(config["safety"].get("kill_switch", False)),
            terminal_connected=status.connected,
            market_open=True,
            current_spread_points=float(spread if spread is not None else 10**9),
            max_spread_points=float(execution_cfg.get("max_spread_points", 50)),
            require_stop_loss=bool(execution_cfg.get("require_stop_loss", True)),
            account=account,
            symbol_info=symbol_info,
            risk_limits=limits,
            recovery_state=recovery,
            expected_mode="demo",
            expected_account_number=account_cfg.get("account_number"),
        )
        safety = validate_trade_request(request, context)
        if not safety.allowed:
            logger.warning("demo trade refused: %s", safety.reason)
            return 1
        result = connector.place_market_order(
            symbol=request.symbol,
            side=request.side,
            lots=safety.lot_size,
            stop_loss=request.stop_loss or 0.0,
            take_profit=request.take_profit,
            magic_number=int(account_cfg.get("magic_number", 260524)),
            deviation_points=int(execution_cfg.get("max_slippage_points", 20)),
            filling_policy=str(execution_cfg.get("order_filling_policy", "FOK")),
        )
        state.save({"last_signal_key": signal_key, "last_order_result": str(result)})
        logger.info("demo order sent: symbol=%s side=%s lots=%.2f result=%s", request.symbol, request.side, safety.lot_size, result)
        return 0
    finally:
        connector.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
