from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from risk_manager import AccountState, SymbolInfo


@dataclass(frozen=True)
class TerminalStatus:
    connected: bool
    trade_allowed: bool
    reason: str = ""


class MT5Connector:
    def __init__(self, terminal_path: str | None = None) -> None:
        self._mt5: Any | None = None
        self.terminal_path = terminal_path

    def initialize(self) -> TerminalStatus:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError:
            return TerminalStatus(False, False, "MetaTrader5 package unavailable")
        self._mt5 = mt5
        initialized = mt5.initialize(path=self.terminal_path) if self.terminal_path else mt5.initialize()
        if not initialized:
            return TerminalStatus(False, False, f"MT5 initialize failed: {mt5.last_error()}")
        terminal = mt5.terminal_info()
        if terminal is None:
            return TerminalStatus(False, False, "terminal info unavailable")
        return TerminalStatus(bool(terminal.connected), bool(terminal.trade_allowed), "")

    def shutdown(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()

    def account_state(self, initial_capital: float, equity_peak: float) -> AccountState | None:
        if self._mt5 is None:
            return None
        info = self._mt5.account_info()
        if info is None:
            return None
        return AccountState(
            balance=float(info.balance),
            equity=float(info.equity),
            initial_capital=initial_capital,
            equity_peak=max(equity_peak, float(info.equity)),
            login=int(info.login),
            server=str(info.server),
            trade_mode=int(info.trade_mode),
        )

    def symbol_info(self, symbol: str) -> SymbolInfo | None:
        if self._mt5 is None:
            return None
        raw = self._mt5.symbol_info(symbol)
        if raw is not None and not raw.visible:
            self._mt5.symbol_select(symbol, True)
        info = self._mt5.symbol_info(symbol)
        if info is None:
            return None
        return SymbolInfo(
            symbol=symbol,
            point=float(info.point),
            tick_size=float(info.trade_tick_size),
            tick_value=float(info.trade_tick_value),
            contract_size=float(info.trade_contract_size),
            min_lot=float(info.volume_min),
            max_lot=float(info.volume_max),
            lot_step=float(info.volume_step),
            digits=int(info.digits),
        )

    def spread_points(self, symbol: str) -> float | None:
        if self._mt5 is None:
            return None
        tick = self._mt5.symbol_info_tick(symbol)
        info = self._mt5.symbol_info(symbol)
        if tick is None or info is None:
            return None
        return float((tick.ask - tick.bid) / info.point)

    def open_position_count(self, symbol: str) -> int:
        if self._mt5 is None:
            return 0
        positions = self._mt5.positions_get(symbol=symbol)
        if positions is None:
            return 0
        return len(positions)

    def place_market_order(
        self,
        symbol: str,
        side: str,
        lots: float,
        stop_loss: float,
        take_profit: float | None,
        magic_number: int,
        deviation_points: int,
        filling_policy: str,
    ) -> Any:
        if self._mt5 is None:
            raise RuntimeError("MT5 is not initialized")
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError("symbol tick unavailable")
        order_type = self._mt5.ORDER_TYPE_BUY if side == "long" else self._mt5.ORDER_TYPE_SELL
        price = tick.ask if side == "long" else tick.bid
        filling = self._mt5.ORDER_FILLING_FOK
        if filling_policy.upper() == "IOC":
            filling = self._mt5.ORDER_FILLING_IOC
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lots,
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit or 0.0,
            "deviation": deviation_points,
            "magic": magic_number,
            "comment": "mt5_codex_quant_agent",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        return self._mt5.order_send(request)

    def recent_rates(self, symbol: str, timeframe: str, count: int = 1000) -> pd.DataFrame:
        if self._mt5 is None:
            raise RuntimeError("MT5 is not initialized")
        timeframe_map: dict[str, Any] = {
            "M1": self._mt5.TIMEFRAME_M1,
            "M5": self._mt5.TIMEFRAME_M5,
            "M15": self._mt5.TIMEFRAME_M15,
            "M30": self._mt5.TIMEFRAME_M30,
            "H1": self._mt5.TIMEFRAME_H1,
            "H4": self._mt5.TIMEFRAME_H4,
            "D1": self._mt5.TIMEFRAME_D1,
        }
        if timeframe not in timeframe_map:
            raise ValueError(f"Unsupported MT5 timeframe: {timeframe}")
        rates = self._mt5.copy_rates_from_pos(symbol, timeframe_map[timeframe], 0, count)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No recent rates returned for {symbol} {timeframe}")
        frame = pd.DataFrame(rates)
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        if "tick_volume" not in frame.columns:
            frame["tick_volume"] = 0
        if "spread" not in frame.columns:
            frame["spread"] = 0
        return frame[["time", "open", "high", "low", "close", "tick_volume", "spread"]]
