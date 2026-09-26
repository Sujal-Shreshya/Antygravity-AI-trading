"""
Market Regime Classification and Feature Extraction.
Identifies macroeconomic and microstructural regimes:
BULLISH_TREND, BEARISH_TREND, RANGE_BOUND, HIGH_VOLATILITY, and COMPRESSION.
Crucial rule: The ML layer NEVER executes orders directly — it acts purely as a filter and ranking layer.
"""

from enum import StrEnum

from pydantic import BaseModel

from backend.core.models import OHLCVCandle
from backend.indicators.technical import (
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_rsi,
    compute_sma,
)


class MarketRegime(StrEnum):
    BULLISH_TREND = "BULLISH_TREND"
    BEARISH_TREND = "BEARISH_TREND"
    RANGE_BOUND = "RANGE_BOUND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    COMPRESSION = "COMPRESSION"


class RegimeFeatures(BaseModel):
    """Normalized technical features extracted strictly from historical bars without look-ahead bias."""

    trend_slope: float
    rsi: float
    atr_pct: float
    bb_bandwidth: float
    volume_ratio: float


class MarketRegimeClassifier:
    """
    Statistically calibrated rule-based & ML feature classifier for market regimes.
    Prevents data leakage by strictly scoping features to bars [0 : t].
    """

    @classmethod
    def extract_features(cls, candles: list[OHLCVCandle]) -> RegimeFeatures | None:
        """Computes feature vector from candle window."""
        if len(candles) < 30:
            return None

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]

        # 1. Trend Slope (Normalized 20-period EMA slope)
        ema_20 = compute_ema(closes, 20)
        valid_ema = [v for v in ema_20 if v is not None]
        if len(valid_ema) < 5:
            return None
        slope = (valid_ema[-1] - valid_ema[-5]) / valid_ema[-5]

        # 2. RSI
        rsi_series = compute_rsi(closes, 14)
        current_rsi = rsi_series[-1] or 50.0

        # 3. Normalized ATR (% of close price)
        atr_series = compute_atr(highs, lows, closes, 14)
        current_atr = atr_series[-1] or (closes[-1] * 0.01)
        atr_pct = current_atr / closes[-1]

        # 4. Bollinger Bandwidth (Upper - Lower) / Middle
        upper, mid, lower = compute_bollinger_bands(closes, 20, 2.0)
        u, m, low_b = upper[-1], mid[-1], lower[-1]
        bandwidth = (u - low_b) / m if None not in (u, m, low_b) and m > 0 else 0.04

        # 5. Volume Ratio (Current volume / 20-period average volume)
        vol_sma = compute_sma(volumes, 20)
        avg_vol = vol_sma[-1] or 1.0
        vol_ratio = volumes[-1] / max(avg_vol, 1.0)

        return RegimeFeatures(
            trend_slope=slope,
            rsi=current_rsi,
            atr_pct=atr_pct,
            bb_bandwidth=bandwidth,
            volume_ratio=vol_ratio,
        )

    @classmethod
    def classify_regime(cls, candles: list[OHLCVCandle]) -> tuple[MarketRegime, float]:
        """
        Classifies current market regime and returns (regime, confidence).
        Strictly point-in-time calculation with no forward-looking data.
        """
        features = cls.extract_features(candles)
        if not features:
            return MarketRegime.RANGE_BOUND, 0.50

        # 1. High Volatility detection (ATR > 2.5% of price or extreme Bandwidth)
        if features.atr_pct > 0.025 or features.bb_bandwidth > 0.08:
            return MarketRegime.HIGH_VOLATILITY, min(0.90, 0.60 + features.atr_pct * 10)

        # 2. Volatility Compression / Squeeze (Tight Bollinger Bands)
        if features.bb_bandwidth < 0.02:
            return MarketRegime.COMPRESSION, 0.85

        # 3. Strong Directional Trends
        if features.trend_slope > 0.01 and features.rsi > 55.0:
            return MarketRegime.BULLISH_TREND, min(0.92, 0.65 + features.trend_slope * 20)
        if features.trend_slope < -0.01 and features.rsi < 45.0:
            return MarketRegime.BEARISH_TREND, min(0.92, 0.65 + abs(features.trend_slope) * 20)

        # 4. Default: Range-Bound Mean Reverting
        return MarketRegime.RANGE_BOUND, 0.75
