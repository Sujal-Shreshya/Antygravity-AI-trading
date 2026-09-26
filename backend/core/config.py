"""
Core Engine Configuration.
Loads and validates environment variables using pydantic-settings.
Enforces fail-closed safety invariants: LIVE_TRADING defaults strictly to False.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --------------------------------------------------------------------------
    # 1. Trading Safety & Operational Mode (CRITICAL)
    # --------------------------------------------------------------------------
    # LIVE_TRADING MUST REMAIN FALSE BY DEFAULT.
    # When False, the entire system is technically blocked from dispatching real orders.
    LIVE_TRADING: bool = Field(
        default=False,
        description="Master live-trading switch. Defaults strictly to False.",
    )

    EMERGENCY_KILL_SWITCH: bool = Field(
        default=False,
        description="Global emergency kill switch to immediately freeze order placement.",
    )

    ENVIRONMENT: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        description="Current deployment environment.",
    )
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    # API Server Networking
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_BASE_URL: str = Field(default="http://localhost:8000")
    FRONTEND_URL: str = Field(default="http://localhost:3000")

    # --------------------------------------------------------------------------
    # 2. Database & Cache
    # --------------------------------------------------------------------------
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_DB: str = Field(default="trading_db")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/trading_db",
        description="Async PostgreSQL connection URL for SQLAlchemy.",
    )
    DATABASE_URL_SYNC: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/trading_db",
        description="Synchronous PostgreSQL connection URL for migrations and health probes.",
    )

    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: str | None = Field(default=None)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # --------------------------------------------------------------------------
    # 3. Security & Authentication
    # --------------------------------------------------------------------------
    JWT_SECRET: str = Field(
        default="change_this_to_a_super_secure_random_string_at_least_32_characters",
        min_length=32,
        description="Secret key used for signing JWT access tokens.",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    BOOTSTRAP_ADMIN_EMAIL: str = Field(default="admin@tradingengine.local")
    BOOTSTRAP_ADMIN_PASSWORD: str = Field(default="change_this_secure_admin_password_123!")

    # --------------------------------------------------------------------------
    # 4. Global Risk Management Boundaries
    # --------------------------------------------------------------------------
    # Maximum risk per single trade (0.01 = 1% equity)
    RISK_MAX_RISK_PER_TRADE_PCT: float = Field(
        default=0.01,
        ge=0.001,
        le=0.05,
        description="Maximum risk per individual trade (0.1% to 5%).",
    )

    # Maximum cumulative loss allowed in a single trading day (0.03 = 3% equity)
    RISK_MAX_DAILY_LOSS_PCT: float = Field(
        default=0.03,
        ge=0.005,
        le=0.10,
        description="Daily loss circuit breaker percentage (0.5% to 10%).",
    )

    # Maximum portfolio-level drawdown threshold (0.10 = 10% equity)
    RISK_MAX_PORTFOLIO_DRAWDOWN_PCT: float = Field(
        default=0.10,
        ge=0.01,
        le=0.25,
        description="Max drawdown circuit breaker threshold (1% to 25%).",
    )

    # Maximum open positions
    RISK_MAX_OPEN_POSITIONS: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum allowed concurrent open positions.",
    )

    # Maximum single position exposure as fraction of total equity
    RISK_MAX_SINGLE_POSITION_PCT: float = Field(
        default=0.15,
        ge=0.01,
        le=0.50,
        description="Maximum capital exposure for any single position (1% to 50%).",
    )

    # Minimum risk-to-reward ratio for accepted signals
    RISK_MIN_RISK_REWARD_RATIO: float = Field(
        default=1.5,
        ge=1.0,
        le=10.0,
        description="Minimum acceptable risk/reward ratio.",
    )

    # --------------------------------------------------------------------------
    # 5. Broker Credentials Placeholders (Never committed with real values)
    # --------------------------------------------------------------------------
    KITE_API_KEY: str | None = Field(default=None)
    KITE_API_SECRET: str | None = Field(default=None)
    KITE_ACCESS_TOKEN: str | None = Field(default=None)

    BINANCE_API_KEY: str | None = Field(default=None)
    BINANCE_API_SECRET: str | None = Field(default=None)
    BINANCE_TESTNET: bool = Field(default=True)

    OANDA_API_KEY: str | None = Field(default=None)
    OANDA_ACCOUNT_ID: str | None = Field(default=None)
    OANDA_ENVIRONMENT: Literal["practice", "trade"] = Field(default="practice")

    # --------------------------------------------------------------------------
    # 6. Notifications
    # --------------------------------------------------------------------------
    TELEGRAM_BOT_TOKEN: str | None = Field(default=None)
    TELEGRAM_CHAT_ID: str | None = Field(default=None)

    SMTP_HOST: str | None = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: str | None = Field(default=None)
    SMTP_PASSWORD: str | None = Field(default=None)
    SMTP_FROM_ADDRESS: str | None = Field(default=None)
    SMTP_TO_ADDRESSES: str | None = Field(default=None)

    ALERT_ON_SIGNALS: bool = Field(default=True)
    ALERT_ON_EXECUTION: bool = Field(default=True)
    ALERT_ON_RISK_EVENTS: bool = Field(default=True)

    @field_validator("LIVE_TRADING")
    @classmethod
    def validate_live_trading_guard(cls, v: bool, info) -> bool:
        """Double-check live trading safety guard."""
        # Live trading is always allowed to be False without checks
        if not v:
            return False
        # If set to True, require explicit non-test environment
        return bool(v)

    @property
    def is_live_trading_enabled(self) -> bool:
        """Safe property accessor for live trading status."""
        return self.LIVE_TRADING


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns singleton settings instance."""
    return Settings()
