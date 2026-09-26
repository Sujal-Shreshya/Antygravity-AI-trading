"""
Instruments API router.
Provides endpoints to list tradable assets across Indian Equities, Crypto, and Forex.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_role
from backend.database.models import InstrumentModel, UserModel
from backend.database.session import get_db

router = APIRouter(prefix="/instruments", tags=["Instruments & Markets"])


class InstrumentCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    market: str = Field(..., description="INDIAN_EQUITY, INDIAN_FNO, CRYPTO_SPOT, FOREX")
    exchange: str = Field(..., description="NSE, BSE, BINANCE, OANDA")
    tick_size: float = Field(default=0.05, gt=0)
    lot_size: int = Field(default=1, ge=1)
    is_active: bool = Field(default=True)


class InstrumentResponse(BaseModel):
    symbol: str
    name: str
    market: str
    exchange: str
    tick_size: float
    lot_size: int
    is_active: bool


@router.get("", response_model=list[InstrumentResponse], summary="List all instruments")
async def list_instruments(
    market: str | None = None,
    exchange: str | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Lists tradable instruments, optionally filtered by market, exchange, and active state."""
    query = select(InstrumentModel)
    if market:
        query = query.where(InstrumentModel.market == market)
    if exchange:
        query = query.where(InstrumentModel.exchange == exchange)
    if active_only:
        query = query.where(InstrumentModel.is_active.is_(True))

    result = await db.execute(query)
    instruments = result.scalars().all()
    return instruments


@router.post(
    "",
    response_model=InstrumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create instrument",
)
async def create_instrument(
    instrument_in: InstrumentCreate,
    current_user: UserModel = Depends(require_role(["ADMIN", "OPERATOR"])),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Creates a new tradable instrument contract (requires ADMIN or OPERATOR role)."""
    existing = await db.get(InstrumentModel, instrument_in.symbol)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Instrument {instrument_in.symbol} already exists",
        )

    instrument = InstrumentModel(**instrument_in.model_dump())
    db.add(instrument)
    await db.commit()
    await db.refresh(instrument)
    return instrument
