"""
Strategies API router.
Lists registered strategies, provides parameter schemas, and runs strategy evaluation on demand.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.models import OHLCVCandle, StrategySignal
from backend.strategies.registry import strategy_registry

router = APIRouter(prefix="/strategies", tags=["Strategies Engine"])


class StrategyEvaluationRequest(BaseModel):
    candles: list[OHLCVCandle] = Field(..., min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


@router.get("", summary="List all algorithmic strategies")
async def list_strategies() -> list[dict[str, Any]]:
    """Returns catalog of all registered strategy plugins with default parameters."""
    return strategy_registry.list_strategies()


@router.get("/{strategy_id}", summary="Get strategy details")
async def get_strategy_details(strategy_id: str) -> dict[str, Any]:
    """Returns metadata and parameter specifications for a specific strategy."""
    strategies = {s["id"]: s for s in strategy_registry.list_strategies()}
    strat = strategies.get(strategy_id.upper())
    if not strat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy '{strategy_id}' not found.",
        )
    return strat


@router.post(
    "/{strategy_id}/evaluate",
    response_model=list[StrategySignal],
    summary="Evaluate strategy on candles",
)
async def evaluate_strategy(
    strategy_id: str,
    payload: StrategyEvaluationRequest,
) -> list[StrategySignal]:
    """Runs strategy signal generation against a supplied series of OHLCV candles."""
    try:
        strat = strategy_registry.get_strategy(strategy_id, payload.parameters)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    try:
        signals = strat.generate_signals(payload.candles)
        return signals
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
