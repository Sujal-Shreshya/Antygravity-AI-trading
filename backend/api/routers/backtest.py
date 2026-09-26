"""
Backtesting API Router.
Provides endpoints for executing backtests, calculating risk-adjusted metrics,
and querying historical backtest runs and equity curves.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_role
from backend.backtesting.engine import BacktestConfig, BacktestingEngine, BacktestRunResult
from backend.data.mock_provider import MockDataProvider
from backend.database.models import BacktestResultModel, UserModel
from backend.database.session import get_db

router = APIRouter(prefix="/backtest", tags=["Backtesting & Simulation"])


class BacktestRunRequest(BaseModel):
    strategy_name: str
    symbol: str = "RELIANCE"
    timeframe: str = "15m"
    initial_capital: float = Field(default=100_000.0, gt=0)
    commission_rate: float = Field(default=0.0003, ge=0)
    slippage_rate: float = Field(default=0.0005, ge=0)
    risk_per_trade_pct: float = Field(default=0.01, gt=0, le=0.05)
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    bars_count: int = Field(default=120, ge=30, le=1000)


@router.post("/run", response_model=BacktestRunResult, summary="Execute strategy backtest")
async def run_backtest(
    payload: BacktestRunRequest,
    current_user: UserModel = Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"])),
    db: AsyncSession = Depends(get_db),
) -> BacktestRunResult:
    """Executes a backtest using historical OHLCV data bars and records results in database."""
    # Obtain historical candle dataset via deterministic provider
    provider = MockDataProvider()
    candles = await provider.fetch_historical_candles(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        limit=payload.bars_count,
    )

    if len(candles) < 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient candle data: received {len(candles)}, minimum 30 required.",
        )

    config = BacktestConfig(
        strategy_name=payload.strategy_name,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        initial_capital=payload.initial_capital,
        commission_rate=payload.commission_rate,
        slippage_rate=payload.slippage_rate,
        risk_per_trade_pct=payload.risk_per_trade_pct,
        strategy_params=payload.strategy_params,
    )

    try:
        engine = BacktestingEngine(config)
        result = engine.run(candles)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    # Persist in database
    db_result = BacktestResultModel(
        id=result.backtest_id,
        strategy_name=payload.strategy_name,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        start_date=candles[0].timestamp,
        end_date=candles[-1].timestamp,
        initial_capital=result.metrics.initial_capital,
        final_equity=result.metrics.final_equity,
        total_trades=result.metrics.total_trades,
        win_rate=result.metrics.win_rate_pct,
        profit_factor=result.metrics.profit_factor,
        max_drawdown=result.metrics.max_drawdown_pct,
        sharpe_ratio=result.metrics.sharpe_ratio,
        metrics_json=result.metrics.model_dump(),
    )
    db.add(db_result)
    await db.commit()

    return result


@router.get("/results", summary="List historical backtest results")
async def list_backtest_results(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Returns historical backtest runs and performance summaries."""
    query = select(BacktestResultModel).order_by(desc(BacktestResultModel.created_at)).limit(limit)
    res = await db.execute(query)
    records = res.scalars().all()

    return [
        {
            "id": r.id,
            "strategy_name": r.strategy_name,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "initial_capital": r.initial_capital,
            "final_equity": r.final_equity,
            "total_trades": r.total_trades,
            "win_rate": r.win_rate,
            "profit_factor": r.profit_factor,
            "max_drawdown": r.max_drawdown,
            "sharpe_ratio": r.sharpe_ratio,
            "metrics": r.metrics_json,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@router.get("/results/{backtest_id}", summary="Get backtest details by ID")
async def get_backtest_by_id(
    backtest_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves full metrics and parameters for a specific backtest run."""
    record = await db.get(BacktestResultModel, backtest_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")

    return {
        "id": record.id,
        "strategy_name": record.strategy_name,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "start_date": record.start_date.isoformat(),
        "end_date": record.end_date.isoformat(),
        "initial_capital": record.initial_capital,
        "final_equity": record.final_equity,
        "total_trades": record.total_trades,
        "win_rate": record.win_rate,
        "profit_factor": record.profit_factor,
        "max_drawdown": record.max_drawdown,
        "sharpe_ratio": record.sharpe_ratio,
        "metrics": record.metrics_json,
        "created_at": record.created_at.isoformat(),
    }
