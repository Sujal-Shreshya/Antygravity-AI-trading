"""
Global Emergency Kill Switch.
Provides thread-safe and asyncio-safe emergency halt functionality.
When engaged, all new order submissions are immediately rejected.
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from backend.core.exceptions import KillSwitchActiveError

logger = logging.getLogger("trading.kill_switch")


class EmergencyKillSwitch:
    """Thread-safe singleton emergency kill switch."""

    _instance: "EmergencyKillSwitch | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "EmergencyKillSwitch":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._is_active: bool = False
        self._reason: str | None = None
        self._activated_at: datetime | None = None
        self._operator_id: str | None = None
        self._activation_count: int = 0
        self._listeners: list[Callable[[str], None]] = []
        self._initialized = True

    def register_listener(self, callback: Callable[[str], None]) -> None:
        """Register a callback triggered whenever the kill switch is activated."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def activate(self, reason: str, operator_id: str | None = None) -> None:
        """
        Immediately engages the emergency kill switch.
        Notifies all listeners to cancel open orders and stop consumers.
        """
        with self._lock:
            self._is_active = True
            self._reason = reason
            self._activated_at = datetime.now(UTC)
            self._operator_id = operator_id or "SYSTEM"
            self._activation_count += 1
            logger.critical(
                f"[EMERGENCY KILL SWITCH ACTIVATED] Reason: {reason} | Operator: {self._operator_id}"
            )
            listeners_to_notify = list(self._listeners)

        for listener in listeners_to_notify:
            try:
                listener(reason)
            except Exception as e:
                logger.error(f"Error in kill switch activation listener: {e}", exc_info=True)

    def deactivate(self, operator_id: str | None = None) -> None:
        """Disengages the kill switch after explicit operator intervention."""
        with self._lock:
            prev_reason = self._reason
            self._is_active = False
            self._reason = None
            self._activated_at = None
            self._operator_id = operator_id or "SYSTEM"
            logger.warning(
                f"[EMERGENCY KILL SWITCH DEACTIVATED] Operator: {self._operator_id} (Prior reason: {prev_reason})"
            )

    @property
    def is_active(self) -> bool:
        """Check if the kill switch is currently engaged."""
        return self._is_active

    def verify_inactive(self) -> None:
        """
        Convenience method to verify system is operational.
        Raises KillSwitchActiveError if engaged.
        """
        if self._is_active:
            raise KillSwitchActiveError(
                message=f"Operation rejected: Emergency kill switch is engaged. Reason: {self._reason}",
                details={
                    "activated_at": self._activated_at.isoformat() if self._activated_at else None,
                    "operator_id": self._operator_id,
                    "reason": self._reason,
                },
            )

    def get_status(self) -> dict[str, Any]:
        """Returns the current state and audit details."""
        with self._lock:
            return {
                "is_active": self._is_active,
                "reason": self._reason,
                "activated_at": self._activated_at.isoformat() if self._activated_at else None,
                "operator_id": self._operator_id,
                "total_activations": self._activation_count,
            }


# Global singleton instance
kill_switch = EmergencyKillSwitch()
