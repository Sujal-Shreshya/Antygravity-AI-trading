"""
Market Hours and Trading Calendar.
Validates session timing and holidays for Indian Equities/FNO, Crypto (24/7), and Forex (24/5).
"""

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.core.models import MarketType

# Timezones: IST is UTC+05:30
try:
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))


class MarketCalendar:
    """Validates whether a target market is open for active trading."""

    @staticmethod
    def is_market_open(market: MarketType, at_time: datetime | None = None) -> bool:
        """Determines whether the market is open at the specified UTC datetime."""
        dt_utc = at_time or datetime.now(UTC)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=UTC)

        if market in (MarketType.CRYPTO_SPOT, MarketType.CRYPTO_FUTURES):
            # Crypto markets operate continuously 24 hours a day, 7 days a week
            return True

        if market in (MarketType.INDIAN_EQUITY, MarketType.INDIAN_FNO):
            # Indian markets operate Monday to Friday, 09:15 to 15:30 IST
            dt_ist = dt_utc.astimezone(IST)
            weekday = dt_ist.weekday()  # 0=Monday, 6=Sunday
            if weekday >= 5:  # Saturday or Sunday
                return False

            market_open = dt_ist.replace(hour=9, minute=15, second=0, microsecond=0)
            market_close = dt_ist.replace(hour=15, minute=30, second=0, microsecond=0)
            return market_open <= dt_ist <= market_close

        if market == MarketType.FOREX:
            # Forex operates globally 24 hours from Sunday 21:00 UTC to Friday 21:00 UTC
            weekday = dt_utc.weekday()
            hour = dt_utc.hour

            if weekday == 5:  # Saturday -> Always closed
                return False
            if weekday == 6:  # Sunday -> Opens at 21:00 UTC
                return hour >= 21
            if weekday == 4:  # Friday -> Closes at 21:00 UTC
                return hour < 21
            # Monday through Thursday -> Always open
            return True

        return False

    @staticmethod
    def get_market_status(at_time: datetime | None = None) -> dict[str, bool]:
        """Returns the open/closed status across all supported markets."""
        t = at_time or datetime.now(UTC)
        return {m.value: MarketCalendar.is_market_open(m, t) for m in MarketType}
