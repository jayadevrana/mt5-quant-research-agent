from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mt5_connector import MT5Connector
from safety import SafetyContext, SafetyResult, TradeRequest, validate_trade_request


@dataclass(frozen=True)
class ExecutionResult:
    placed: bool
    reason: str
    lots: float = 0.0
    broker_result: Any | None = None


class ExecutionEngine:
    def __init__(self, connector: MT5Connector) -> None:
        self.connector = connector

    def evaluate(self, request: TradeRequest, context: SafetyContext) -> SafetyResult:
        return validate_trade_request(request, context)

    def place_order(
        self,
        request: TradeRequest,
        context: SafetyContext,
        magic_number: int,
        deviation_points: int,
        filling_policy: str,
    ) -> ExecutionResult:
        safety = self.evaluate(request, context)
        if not safety.allowed:
            return ExecutionResult(False, safety.reason)
        if request.stop_loss is None:
            return ExecutionResult(False, "stop loss missing after safety validation")
        broker_result = self.connector.place_market_order(
            symbol=request.symbol,
            side=request.side,
            lots=safety.lot_size,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            magic_number=magic_number,
            deviation_points=deviation_points,
            filling_policy=filling_policy,
        )
        return ExecutionResult(True, "order sent", safety.lot_size, broker_result)
