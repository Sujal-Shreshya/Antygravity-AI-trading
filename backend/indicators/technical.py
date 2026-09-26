"""
Vectorized and numerical technical indicators.
Implements core mathematical formulas using NumPy and pure algorithms:
EMA, SMA, RSI (Wilder's), MACD, Bollinger Bands, ATR, VWAP, Breakout channels, and Momentum.
"""

import math

from backend.core.models import OHLCVCandle


def compute_sma(prices: list[float], period: int) -> list[float | None]:
    """Calculates Simple Moving Average."""
    if len(prices) < period:
        return [None] * len(prices)

    sma: list[float | None] = [None] * (period - 1)
    current_sum = sum(prices[:period])
    sma.append(current_sum / period)

    for i in range(period, len(prices)):
        current_sum += prices[i] - prices[i - period]
        sma.append(current_sum / period)

    return sma


def compute_ema(prices: list[float], period: int) -> list[float | None]:
    """Calculates Exponential Moving Average."""
    if len(prices) < period:
        return [None] * len(prices)

    ema: list[float | None] = [None] * (period - 1)
    # Seed with SMA of the first period
    initial_sma = sum(prices[:period]) / period
    ema.append(initial_sma)

    multiplier = 2.0 / (period + 1.0)
    current_ema = initial_sma

    for i in range(period, len(prices)):
        current_ema = (prices[i] - current_ema) * multiplier + current_ema
        ema.append(current_ema)

    return ema


def compute_rsi(prices: list[float], period: int = 14) -> list[float | None]:
    """
    Calculates Relative Strength Index using Wilder's smoothing method.
    Returns values between 0.0 and 100.0.
    """
    if len(prices) <= period:
        return [None] * len(prices)

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    rsi: list[float | None] = [None] * period  # 1 for delta offset + (period - 1)

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0.0:
        rsi.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi.append(100.0 - (100.0 / (1.0 + rs)))

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0.0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100.0 - (100.0 / (1.0 + rs)))

    return rsi


def compute_macd(
    prices: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """
    Calculates MACD Line, Signal Line, and MACD Histogram.
    Returns (macd_line, signal_line, histogram).
    """
    fast_ema = compute_ema(prices, fast_period)
    slow_ema = compute_ema(prices, slow_period)

    macd_line: list[float | None] = []
    for f, s in zip(fast_ema, slow_ema, strict=True):
        if f is not None and s is not None:
            macd_line.append(f - s)
        else:
            macd_line.append(None)

    # Extract valid values for signal EMA calculation
    valid_macd = [val for val in macd_line if val is not None]
    if len(valid_macd) < signal_period:
        return macd_line, [None] * len(prices), [None] * len(prices)

    valid_signal = compute_ema(valid_macd, signal_period)
    leading_nones = len(prices) - len(valid_macd)
    signal_line: list[float | None] = [None] * leading_nones + valid_signal

    histogram: list[float | None] = []
    for m, sig in zip(macd_line, signal_line, strict=True):
        if m is not None and sig is not None:
            histogram.append(m - sig)
        else:
            histogram.append(None)

    return macd_line, signal_line, histogram


def compute_bollinger_bands(
    prices: list[float],
    period: int = 20,
    num_std_dev: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """
    Calculates Upper, Middle (SMA), and Lower Bollinger Bands.
    Returns (upper_band, middle_band, lower_band).
    """
    middle = compute_sma(prices, period)
    upper: list[float | None] = []
    lower: list[float | None] = []

    for i in range(len(prices)):
        mid = middle[i]
        if mid is None or i < period - 1:
            upper.append(None)
            lower.append(None)
        else:
            window = prices[i - period + 1 : i + 1]
            variance = sum((p - mid) ** 2 for p in window) / period
            std_dev = math.sqrt(variance)
            upper.append(mid + num_std_dev * std_dev)
            lower.append(mid - num_std_dev * std_dev)

    return upper, middle, lower


def compute_atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float | None]:
    """
    Calculates Average True Range (ATR) using Wilder's smoothing.
    Critical for volatility measurement and dynamic stop loss placement.
    """
    n = len(closes)
    if n <= period or len(highs) != n or len(lows) != n:
        return [None] * n

    true_ranges: list[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    atr: list[float | None] = [None] * (period - 1)
    current_atr = sum(true_ranges[:period]) / period
    atr.append(current_atr)

    for i in range(period, n):
        current_atr = (current_atr * (period - 1) + true_ranges[i]) / period
        atr.append(current_atr)

    return atr


def compute_vwap(candles: list[OHLCVCandle]) -> list[float | None]:
    """Calculates Volume Weighted Average Price (VWAP) across a series of candles."""
    if not candles:
        return []

    vwap_series: list[float | None] = []
    cumulative_pv = 0.0
    cumulative_vol = 0.0

    for c in candles:
        typical_price = (c.high + c.low + c.close) / 3.0
        vol = max(c.volume, 1e-9)
        cumulative_pv += typical_price * vol
        cumulative_vol += vol
        vwap_series.append(cumulative_pv / cumulative_vol)

    return vwap_series


def compute_donchian_breakout(
    highs: list[float],
    lows: list[float],
    period: int = 20,
) -> tuple[list[float | None], list[float | None]]:
    """Calculates upper and lower Donchian channel breakout levels."""
    n = len(highs)
    upper: list[float | None] = [None] * period
    lower: list[float | None] = [None] * period

    for i in range(period, n):
        # Lookback excluding current bar to detect breakout
        window_highs = highs[i - period : i]
        window_lows = lows[i - period : i]
        upper.append(max(window_highs))
        lower.append(min(window_lows))

    return upper, lower


def compute_momentum(prices: list[float], period: int = 10) -> list[float | None]:
    """Calculates Price Momentum (Price_t - Price_{t-period})."""
    if len(prices) <= period:
        return [None] * len(prices)

    mom: list[float | None] = [None] * period
    for i in range(period, len(prices)):
        mom.append(prices[i] - prices[i - period])
    return mom
