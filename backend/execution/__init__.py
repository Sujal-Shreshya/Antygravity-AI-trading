"""
Live execution package.
Provides the fail-closed LiveExecutionCoordinator and multi-market routing utilities.
"""

from backend.execution.coordinator import (
    LiveExecutionCoordinator,
    live_execution_coordinator,
    resolve_broker_for_symbol,
    resolve_market_type_for_symbol,
)

__all__ = [
    "LiveExecutionCoordinator",
    "live_execution_coordinator",
    "resolve_market_type_for_symbol",
    "resolve_broker_for_symbol",
]
