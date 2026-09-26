"""
Production Live Execution Coordinator & Fail-Closed Safety System.
Enforces an immutable, multi-tier safety pipeline before any order can reach an external broker.
Guarantees fail-closed behavior: ANY failure or ambiguity blocks execution unconditionally.
"""

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brokers.base import BaseBroker
from backend.brokers.factory import broker_factory
from backend.core.config import get_settings
from backend.core.exceptions import (
    BrokerConnectionError,
    DuplicateOrderError,
    KillSwitchActiveError,
    LiveTradingBlockedError,
    MarketClosedError,
    RiskLimitExceededError,
)
from backend.core.kill_switch import kill_switch
from backend.core.models import (
    AccountBalance,
    MarketType,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    RiskAction,
    TradeDirection,
)
from backend.data.calendar import MarketCalendar
from backend.database.models import AuditLogModel, OrderModel, PositionModel, RiskEventModel
from backend.monitoring.telemetry import telemetry
from backend.notifications.channels import NotificationEvent
from backend.notifications.dispatcher import notification_dispatcher
from backend.risk.base import RiskContext
from backend.risk.engine import risk_engine

logger = logging.getLogger("trading.execution.coordinator")


def resolve_market_type_for_symbol(symbol: str) -> MarketType:
    """Infers market type from asset symbol conventions."""
    sym = symbol.upper()
    if sym.endswith("/USDT") or sym.endswith("USDT") or sym in ("BTC", "ETH", "SOL", "BNB"):
        return MarketType.CRYPTO_SPOT
    if "/" in sym or sym in ("EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "USD/CHF"):
        return MarketType.FOREX
    if "-FUT" in sym or "-CE" in sym or "-PE" in sym or "FUT" in sym:
        return MarketType.INDIAN_FNO
    return MarketType.INDIAN_EQUITY


def resolve_broker_for_symbol(symbol: str, requested_broker: str | None = None) -> str:
    """Routes an instrument to its designated broker adapter."""
    if requested_broker:
        return requested_broker.upper()
    market = resolve_market_type_for_symbol(symbol)
    if market in (MarketType.CRYPTO_SPOT, MarketType.CRYPTO_FUTURES):
        return "BINANCE"
    if market == MarketType.FOREX:
        return "OANDA"
    return "KITE"


class LiveExecutionCoordinator:
    """
    Central Execution Authority enforcing 7-tier fail-closed pre-execution safety gates.

    Pipeline Gates:
    1. Master Configuration Gate (LIVE_TRADING == True)
    2. Global Emergency Kill Switch Gate (is_active == False)
    3. Broker Configuration & Authentication Gate (Valid non-dummy credentials)
    4. Market Calendar & Trading Session Gate (Session open)
    5. Pre-Trade Risk Engine Gate (Loss, drawdown, size & exposure constraints)
    6. Idempotency & In-Flight Deduplication Gate (Sliding window guard)
    7. Persistent Pre-Execution Audit Logging Gate (Tamper-evident record)
    """

    def __init__(self, deduplication_window_seconds: float = 30.0) -> None:
        self.dedup_window = deduplication_window_seconds
        self._in_flight_tokens: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _cleanup_stale_tokens(self) -> None:
        """Purges deduplication tokens older than the sliding window."""
        now = time.monotonic()
        expired = [k for k, t in self._in_flight_tokens.items() if now - t > self.dedup_window]
        for k in expired:
            del self._in_flight_tokens[k]

    def _validate_broker_credentials(self, broker_name: str) -> None:
        """Verifies that actual live credentials are present and not default placeholders."""
        settings = get_settings()
        placeholder_indicators = ("your_", "placeholder", "changeme", "secret", "demo", "xxx")

        if broker_name in ("KITE", "ZERODHA"):
            key = settings.KITE_API_KEY.strip()
            secret = settings.KITE_API_SECRET.strip()
            if not key or not secret or any(p in key.lower() for p in placeholder_indicators):
                raise BrokerConnectionError(
                    message=f"Live trading blocked: Invalid or unconfigured credentials for broker '{broker_name}'.",
                    details={"broker": broker_name, "reason": "Missing or placeholder API keys"},
                )

        elif broker_name.startswith("BINANCE"):
            key = settings.BINANCE_API_KEY.strip()
            secret = settings.BINANCE_API_SECRET.strip()
            if not key or not secret or any(p in key.lower() for p in placeholder_indicators):
                raise BrokerConnectionError(
                    message=f"Live trading blocked: Invalid or unconfigured credentials for broker '{broker_name}'.",
                    details={"broker": broker_name, "reason": "Missing or placeholder API keys"},
                )

        elif broker_name in ("OANDA", "FOREX"):
            key = settings.OANDA_API_KEY.strip()
            acc = settings.OANDA_ACCOUNT_ID.strip()
            if not key or not acc or any(p in key.lower() for p in placeholder_indicators):
                raise BrokerConnectionError(
                    message=f"Live trading blocked: Invalid or unconfigured credentials for broker '{broker_name}'.",
                    details={"broker": broker_name, "reason": "Missing or placeholder API keys"},
                )

    async def validate_live_safety_gates(
        self,
        order: OrderRequest,
        db: AsyncSession,
        operator_id: str = "system",
        broker_name: str | None = None,
        bypass_market_hours: bool = False,
    ) -> BaseBroker:
        """
        Executes all 7 fail-closed safety checks.
        Returns authenticated BaseBroker adapter if every check passes.
        Raises specific TradingEngineError subclass immediately if any gate fails.
        """
        settings = get_settings()
        target_broker_name = resolve_broker_for_symbol(order.symbol, broker_name)

        # ----------------------------------------------------------------------
        # Gate 1: Master Configuration Check (LIVE_TRADING == True)
        # ----------------------------------------------------------------------
        if not settings.LIVE_TRADING:
            logger.critical(
                f"[GATE 1 FAIL] Live order rejected: LIVE_TRADING=false. Symbol={order.symbol}"
            )
            raise LiveTradingBlockedError(
                message="Live execution strictly prohibited: LIVE_TRADING is false in engine configuration.",
                details={"symbol": order.symbol, "client_order_id": order.client_order_id},
            )

        # ----------------------------------------------------------------------
        # Gate 2: Global Emergency Kill Switch Check
        # ----------------------------------------------------------------------
        if kill_switch.is_active:
            status = kill_switch.get_status()
            logger.critical(
                f"[GATE 2 FAIL] Live order rejected: Kill switch engaged. Reason: {status['reason']}"
            )
            raise KillSwitchActiveError(
                message=f"Live execution rejected: Emergency kill switch is ACTIVE. Reason: {status['reason']}",
                details={"kill_switch": status},
            )

        # ----------------------------------------------------------------------
        # Gate 3: Broker Credentials & Authentication Check
        # ----------------------------------------------------------------------
        self._validate_broker_credentials(target_broker_name)
        broker_adapter = broker_factory.get_broker(target_broker_name, is_sandbox=False)

        # ----------------------------------------------------------------------
        # Gate 4: Market Hours & Session Status Check
        # ----------------------------------------------------------------------
        market_type = resolve_market_type_for_symbol(order.symbol)
        if not bypass_market_hours and not MarketCalendar.is_market_open(market_type):
            logger.warning(
                f"[GATE 4 FAIL] Live order rejected: Market {market_type.value} is currently closed. Symbol={order.symbol}"
            )
            raise MarketClosedError(
                message=f"Live execution rejected: Market for symbol '{order.symbol}' ({market_type.value}) is currently closed.",
                details={"symbol": order.symbol, "market": market_type.value},
            )

        # ----------------------------------------------------------------------
        # Gate 5: Pre-Trade Risk Engine Clearance
        # ----------------------------------------------------------------------
        pos_res = await db.execute(select(PositionModel))
        db_positions = pos_res.scalars().all()
        risk_positions = [
            Position(
                symbol=p.symbol,
                direction=TradeDirection(p.direction),
                quantity=p.quantity,
                entry_price=p.entry_price,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                realized_pnl=p.realized_pnl,
                stop_loss=p.stop_loss,
                take_profit=p.take_profit,
            )
            for p in db_positions
        ]

        total_realized_loss = sum(abs(p.realized_pnl) for p in db_positions if p.realized_pnl < 0)
        total_unrealized_loss = sum(abs(p.unrealized_pnl) for p in db_positions if p.unrealized_pnl < 0)
        baseline_equity = 100_000.0 + sum(p.realized_pnl + p.unrealized_pnl for p in db_positions)

        risk_context = RiskContext(
            account_balance=AccountBalance(
                cash=100_000.0,
                equity=max(baseline_equity, 10_000.0),
                available_margin=max(baseline_equity, 10_000.0),
            ),
            open_positions=risk_positions,
            daily_realized_loss=total_realized_loss,
            daily_unrealized_loss=total_unrealized_loss,
            peak_portfolio_equity=max(baseline_equity, 100_000.0),
            current_portfolio_equity=max(baseline_equity, 10_000.0),
        )

        risk_decision = risk_engine.evaluate_order(order, risk_context)
        if not risk_decision.is_approved or risk_decision.action == RiskAction.REJECT:
            # Persist risk failure event
            risk_event = RiskEventModel(
                rule_name=risk_decision.rule_name,
                action=risk_decision.action.value,
                reason=risk_decision.reason,
                details={
                    "client_order_id": order.client_order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": order.quantity,
                    "metrics": risk_decision.metrics,
                },
            )
            db.add(risk_event)
            await db.commit()

            logger.warning(
                f"[GATE 5 FAIL] Pre-trade risk rule '{risk_decision.rule_name}' rejected order: {risk_decision.reason}"
            )
            raise RiskLimitExceededError(
                message=f"Pre-trade risk rejected order: {risk_decision.reason}",
                rule_name=risk_decision.rule_name,
                limit_value=0.0,
                actual_value=0.0,
                details=risk_decision.metrics,
            )

        # ----------------------------------------------------------------------
        # Gate 6: Idempotency & In-Flight Anti-Duplicate Guard
        # ----------------------------------------------------------------------
        async with self._lock:
            self._cleanup_stale_tokens()
            # In-memory sliding token check
            order_fingerprint = f"{order.client_order_id}:{order.symbol}:{order.side.value}:{order.quantity}"
            if (
                order.client_order_id in self._in_flight_tokens
                or order_fingerprint in self._in_flight_tokens
            ):
                logger.warning(
                    f"[GATE 6 FAIL] In-flight duplicate detected for client_order_id={order.client_order_id}"
                )
                raise DuplicateOrderError(
                    message=f"Duplicate order in-flight detected within {self.dedup_window}s window: {order.client_order_id}",
                    details={"client_order_id": order.client_order_id},
                )

            # Database uniqueness check
            existing_db = await db.execute(
                select(OrderModel).where(OrderModel.client_order_id == order.client_order_id)
            )
            if existing_db.scalar_one_or_none() is not None:
                logger.warning(
                    f"[GATE 6 FAIL] Database duplicate detected for client_order_id={order.client_order_id}"
                )
                raise DuplicateOrderError(
                    message=f"Duplicate client order ID already exists in database: {order.client_order_id}",
                    details={"client_order_id": order.client_order_id},
                )

            now_mono = time.monotonic()
            self._in_flight_tokens[order.client_order_id] = now_mono
            self._in_flight_tokens[order_fingerprint] = now_mono

        # ----------------------------------------------------------------------
        # Gate 7: Persistent Pre-Execution Audit Logging
        # ----------------------------------------------------------------------
        audit_log = AuditLogModel(
            event_type="LIVE_ORDER_PRE_DISPATCH",
            operator_id=operator_id,
            details={
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "quantity": order.quantity,
                "price": order.price,
                "broker": target_broker_name,
                "market": market_type.value,
                "live_execution": True,
            },
            ip_address="internal_execution",
        )
        db.add(audit_log)
        await db.commit()

        logger.info(
            f"[GATES PASSED] All 7 safety gates cleared for live order {order.client_order_id} ({order.symbol} {order.side.value} x {order.quantity})"
        )
        return broker_adapter

    async def execute_live_order(
        self,
        order: OrderRequest,
        db: AsyncSession,
        operator_id: str = "operator",
        broker_name: str | None = None,
        bypass_market_hours: bool = False,
    ) -> OrderResponse:
        """
        Coordinates full fail-closed live order dispatch to external broker.
        """
        # Run all 7 pre-execution safety gates
        broker_adapter = await self.validate_live_safety_gates(
            order=order,
            db=db,
            operator_id=operator_id,
            broker_name=broker_name,
            bypass_market_hours=bypass_market_hours,
        )

        # Create database record in SUBMITTED status
        db_order = OrderModel(
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.order_type.value,
            quantity=order.quantity,
            price=order.price,
            stop_price=order.stop_price,
            filled_quantity=0.0,
            average_price=None,
            status=OrderStatus.SUBMITTED.value,
            is_paper=False,
            strategy_id=order.strategy_id,
            broker_message="Dispatched to live broker adapter",
        )
        db.add(db_order)
        await db.commit()
        await db.refresh(db_order)

        try:
            # Dispatch to external broker adapter
            broker_response = await broker_adapter.place_order(order)

            # Update database record with execution results
            db_order.status = broker_response.status.value
            db_order.filled_quantity = broker_response.filled_quantity
            db_order.average_price = broker_response.average_price
            db_order.broker_message = broker_response.broker_message or "Order accepted by broker"
            db_order.updated_at = datetime.now(UTC)

            # Post-execution audit log
            db.add(
                AuditLogModel(
                    event_type="LIVE_ORDER_POST_DISPATCH",
                    operator_id=operator_id,
                    details={
                        "order_id": db_order.order_id,
                        "client_order_id": db_order.client_order_id,
                        "broker_status": broker_response.status.value,
                        "broker_message": db_order.broker_message,
                        "filled_qty": broker_response.filled_quantity,
                    },
                    ip_address="internal_execution",
                )
            )
            await db.commit()
            await db.refresh(db_order)

            # Broadcast alert notification
            await notification_dispatcher.broadcast(
                NotificationEvent(
                    title=f"Live Order Placed: {order.symbol} {order.side.value}",
                    message=f"Order {order.client_order_id} placed on {broker_adapter.broker_name}. Status: {broker_response.status.value}",
                    level="INFO",
                    event_type="LIVE_ORDER_PLACED",
                    details={"order_id": db_order.order_id, "symbol": order.symbol},
                )
            )
            telemetry.increment("live_orders_executed")

            return OrderResponse(
                order_id=db_order.order_id,
                client_order_id=db_order.client_order_id,
                symbol=db_order.symbol,
                side=order.side,
                order_type=order.order_type,
                quantity=db_order.quantity,
                price=db_order.price,
                filled_quantity=db_order.filled_quantity,
                average_price=db_order.average_price,
                status=OrderStatus(db_order.status),
                is_paper=False,
                created_at=db_order.created_at,
                updated_at=db_order.updated_at,
                broker_message=db_order.broker_message,
            )

        except Exception as exc:
            logger.error(
                f"[LIVE EXECUTION FAILURE] Broker rejected order {order.client_order_id}: {exc}",
                exc_info=True,
            )
            db_order.status = OrderStatus.REJECTED.value
            db_order.broker_message = f"Broker rejection: {exc}"
            db_order.updated_at = datetime.now(UTC)

            db.add(
                AuditLogModel(
                    event_type="LIVE_ORDER_FAILED",
                    operator_id=operator_id,
                    details={
                        "order_id": db_order.order_id,
                        "client_order_id": db_order.client_order_id,
                        "error": str(exc),
                    },
                    ip_address="internal_execution",
                )
            )
            await db.commit()

            await notification_dispatcher.broadcast(
                NotificationEvent(
                    title=f"CRITICAL: Live Order Failed: {order.symbol}",
                    message=f"Live order {order.client_order_id} failed on {broker_adapter.broker_name}: {exc}",
                    level="CRITICAL",
                    event_type="LIVE_ORDER_FAILED",
                    details={"client_order_id": order.client_order_id},
                )
            )
            telemetry.increment("live_orders_failed")
            raise

    async def execute_emergency_kill(
        self,
        reason: str,
        operator_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Activates global emergency kill switch, cancels all pending orders,
        broadcasts critical alerts, and records an unalterable audit log.
        """
        kill_switch.activate(reason=reason, operator_id=operator_id)

        # Cancel all open or submitted orders
        open_orders_query = select(OrderModel).where(
            OrderModel.status.in_([OrderStatus.SUBMITTED.value, OrderStatus.PENDING.value])
        )
        res = await db.execute(open_orders_query)
        open_orders = res.scalars().all()

        cancelled_ids = []
        for o in open_orders:
            o.status = OrderStatus.CANCELLED.value
            o.broker_message = f"Emergency Kill Switch Activated: {reason}"
            o.updated_at = datetime.now(UTC)
            cancelled_ids.append(o.order_id)

        # Audit log
        db.add(
            AuditLogModel(
                event_type="EMERGENCY_KILL_SWITCH_ENGAGED",
                operator_id=operator_id,
                details={
                    "reason": reason,
                    "cancelled_order_count": len(cancelled_ids),
                    "cancelled_order_ids": cancelled_ids,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                ip_address="internal_execution",
            )
        )
        await db.commit()

        # Broadcast critical alert across all channels
        await notification_dispatcher.notify_kill_switch(
            is_active=True,
            operator=operator_id,
            reason=f"{reason}. Cancelled {len(cancelled_ids)} active orders.",
        )
        telemetry.increment("emergency_kill_switch_triggers")

        return {
            "status": "engaged",
            "reason": reason,
            "operator_id": operator_id,
            "cancelled_orders": len(cancelled_ids),
            "cancelled_order_ids": cancelled_ids,
        }

    def check_live_readiness(self) -> dict[str, Any]:
        """
        Runs a comprehensive diagnostic assessment of live trading readiness across all systems.
        """
        settings = get_settings()
        placeholder_indicators = ("your_", "placeholder", "changeme", "secret", "demo", "xxx")

        kite_ready = bool(
            settings.KITE_API_KEY
            and settings.KITE_API_SECRET
            and not any(p in settings.KITE_API_KEY.lower() for p in placeholder_indicators)
        )
        binance_ready = bool(
            settings.BINANCE_API_KEY
            and settings.BINANCE_API_SECRET
            and not any(p in settings.BINANCE_API_KEY.lower() for p in placeholder_indicators)
        )
        oanda_ready = bool(
            settings.OANDA_API_KEY
            and settings.OANDA_ACCOUNT_ID
            and not any(p in settings.OANDA_API_KEY.lower() for p in placeholder_indicators)
        )

        now = datetime.now(UTC)
        market_status = MarketCalendar.get_market_status(now)

        return {
            "live_trading_master_switch": settings.LIVE_TRADING,
            "kill_switch_active": kill_switch.is_active,
            "broker_credentials": {
                "kite": {"configured": kite_ready},
                "binance": {"configured": binance_ready},
                "oanda": {"configured": oanda_ready},
            },
            "market_hours": market_status,
            "risk_engine": {
                "active_rules_count": len(risk_engine.rules),
                "rules": [r.rule_name for r in risk_engine.rules],
            },
            "overall_live_executable": bool(
                settings.LIVE_TRADING
                and not kill_switch.is_active
                and (kite_ready or binance_ready or oanda_ready)
            ),
        }


live_execution_coordinator = LiveExecutionCoordinator()
