"""
Notification Dispatcher Orchestrator.
Broadcasts critical trading events across all registered channels concurrently.
Safeguards engine stability: notification errors are isolated and never crash the trading engine.
"""

import asyncio
import logging
from typing import Any

from backend.notifications.channels import (
    BaseNotificationChannel,
    EmailChannel,
    NotificationEvent,
    TelegramChannel,
    WebhookChannel,
)

logger = logging.getLogger("trading.notifications.dispatcher")


class NotificationDispatcher:
    """Coordinates multi-channel broadcasting with fail-safe isolation."""

    def __init__(self) -> None:
        self.channels: dict[str, BaseNotificationChannel] = {
            "telegram": TelegramChannel(),
            "webhook": WebhookChannel(),
            "email": EmailChannel(),
        }

    def register_channel(self, name: str, channel: BaseNotificationChannel) -> None:
        self.channels[name] = channel

    async def broadcast(self, event: NotificationEvent) -> dict[str, bool]:
        """Broadcasts event across all registered notification channels concurrently."""
        results: dict[str, bool] = {}

        tasks = []
        names = []
        for name, channel in self.channels.items():
            tasks.append(channel.send(event))
            names.append(name)

        if not tasks:
            return results

        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        for name, outcome in zip(names, outcomes, strict=True):
            if isinstance(outcome, Exception):
                logger.error(f"Channel {name} raised unexpected error: {outcome}")
                results[name] = False
            else:
                results[name] = bool(outcome)

        return results

    async def notify_trade_fill(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_id: str,
        is_paper: bool = True,
    ) -> dict[str, bool]:
        """Convenience method to notify on trade execution fills."""
        mode = "PAPER" if is_paper else "LIVE"
        event = NotificationEvent(
            title=f"Trade Executed [{mode}]: {side} {quantity} {symbol}",
            message=f"Order {order_id[:8]} filled @ ₹{price:,.2f}. Total notional: ₹{(quantity * price):,.2f}",
            level="INFO",
            event_type="TRADE_FILL",
            details={"symbol": symbol, "side": side, "quantity": quantity, "price": price, "order_id": order_id},
        )
        return await self.broadcast(event)

    async def notify_circuit_breaker(
        self,
        breaker_name: str,
        reason: str,
        metrics: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """Convenience method to notify on circuit breaker halts."""
        event = NotificationEvent(
            title=f"CIRCUIT BREAKER TRIGGERED: {breaker_name}",
            message=f"Trading halted by risk rule '{breaker_name}'. Reason: {reason}",
            level="CRITICAL",
            event_type="CIRCUIT_BREAKER",
            details=metrics or {},
        )
        return await self.broadcast(event)

    async def notify_kill_switch(
        self,
        is_active: bool,
        operator: str,
        reason: str | None = None,
    ) -> dict[str, bool]:
        """Convenience method to notify on kill switch state changes."""
        action = "ENGAGED - TRADING HALTED" if is_active else "DISENGAGED - NORMAL OPERATION"
        event = NotificationEvent(
            title=f"EMERGENCY KILL SWITCH {action}",
            message=f"Operator: {operator}. Justification: {reason or 'Manual operator action'}",
            level="CRITICAL" if is_active else "WARNING",
            event_type="KILL_SWITCH",
            details={"is_active": is_active, "operator": operator, "reason": reason},
        )
        return await self.broadcast(event)


notification_dispatcher = NotificationDispatcher()
