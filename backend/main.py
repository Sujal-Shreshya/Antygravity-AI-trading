"""
AI Trading Engine - FastAPI Gateway & Core Application.
Configures CORS, structured correlation logging, lifecycle hooks, and API routes.
"""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routers.auth import router as auth_router
from backend.api.routers.backtest import router as backtest_router
from backend.api.routers.health import router as health_router
from backend.api.routers.instruments import router as instruments_router
from backend.api.routers.market_data import router as market_data_router
from backend.api.routers.orders import router as orders_router
from backend.api.routers.paper import router as paper_router
from backend.api.routers.portfolio import router as portfolio_router
from backend.api.routers.positions import router as positions_router
from backend.api.routers.risk import router as risk_router
from backend.api.routers.signals import router as signals_router
from backend.api.routers.strategies import router as strategies_router
from backend.core.config import get_settings
from backend.core.exceptions import (
    DuplicateOrderError,
    KillSwitchActiveError,
    LiveTradingBlockedError,
    RiskLimitExceededError,
    TradingEngineError,
)
from backend.core.kill_switch import kill_switch
from backend.core.logging import configure_logging, correlation_id_ctx, get_logger
from backend.database.session import close_db, init_db

logger = get_logger("trading.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: initialize database tables, log startup, and cleanup on exit."""
    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL)
    logger.info("Initializing AI Trading Engine...")
    logger.info(f"Environment: {settings.ENVIRONMENT} | LIVE_TRADING={settings.LIVE_TRADING}")

    # Synchronize tables
    await init_db()

    # If kill switch flag was preset in environment, engage it
    if settings.EMERGENCY_KILL_SWITCH:
        kill_switch.activate("Engaged via environment startup flag")

    yield

    logger.info("Shutting down AI Trading Engine...")
    await close_db()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="AI Trading Engine",
    description="Production-oriented Multi-Market Algorithmic Trading Platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ------------------------------------------------------------------------------
# Middlewares
# ------------------------------------------------------------------------------

# CORS
settings = get_settings()
allowed_origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next) -> Response:
    """Attaches a unique correlation ID to every incoming HTTP request for end-to-end tracing."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = correlation_id_ctx.set(request_id)
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        return response
    finally:
        correlation_id_ctx.reset(token)


# ------------------------------------------------------------------------------
# Exception Handlers
# ------------------------------------------------------------------------------


@app.exception_handler(LiveTradingBlockedError)
async def live_trading_blocked_handler(request: Request, exc: LiveTradingBlockedError):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"error": "LiveTradingBlocked", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(KillSwitchActiveError)
async def kill_switch_active_handler(request: Request, exc: KillSwitchActiveError):
    return JSONResponse(
        status_code=status.HTTP_423_LOCKED,
        content={"error": "KillSwitchActive", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(RiskLimitExceededError)
async def risk_limit_handler(request: Request, exc: RiskLimitExceededError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "RiskLimitExceeded",
            "rule": exc.rule_name,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(DuplicateOrderError)
async def duplicate_order_handler(request: Request, exc: DuplicateOrderError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": "DuplicateOrder", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(TradingEngineError)
async def general_trading_error_handler(request: Request, exc: TradingEngineError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "TradingEngineError", "message": exc.message, "details": exc.details},
    )


# ------------------------------------------------------------------------------
# Routers Registration
# ------------------------------------------------------------------------------

# Health probe at root level
app.include_router(health_router)

# Versioned API routes under /api/v1
api_v1_prefix = "/api/v1"
app.include_router(health_router, prefix=api_v1_prefix)
app.include_router(auth_router, prefix=api_v1_prefix)
app.include_router(instruments_router, prefix=api_v1_prefix)
app.include_router(market_data_router, prefix=api_v1_prefix)
app.include_router(orders_router, prefix=api_v1_prefix)
app.include_router(paper_router, prefix=api_v1_prefix)
app.include_router(positions_router, prefix=api_v1_prefix)
app.include_router(portfolio_router, prefix=api_v1_prefix)
app.include_router(risk_router, prefix=api_v1_prefix)
app.include_router(signals_router, prefix=api_v1_prefix)
app.include_router(strategies_router, prefix=api_v1_prefix)
app.include_router(backtest_router, prefix=api_v1_prefix)


@app.get("/", tags=["Root"])
async def root():
    return {
        "engine": "AI Trading Engine",
        "status": "operational",
        "docs": "/docs",
        "live_trading": False,
    }
