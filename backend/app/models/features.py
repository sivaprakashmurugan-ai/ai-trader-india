import pandas as pd
import logging
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange # <-- NEW: Import ATR
from ta.trend import ADXIndicator        # <-- NEW: Import ADX

logger = logging.getLogger(__name__)

def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build a richer set of features including volatility and trend strength."""
    if df is None or len(df) < 30: # Need more data for new indicators
        return pd.DataFrame()

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["volume"].astype(float).fillna(0)

    # 1. Price-based features (Returns)
    ret_1 = close.pct_change()
    ret_5 = close.pct_change(5)

    # 2. Momentum Indicators
    rsi14 = RSIIndicator(close=close, window=14).rsi()

    # 3. Trend Indicators
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    vwap20 = (close * vol).rolling(20).sum() / vol.rolling(20).sum().replace(0, 1)

    # 4. --- NEW: Volatility Indicator ---
    # Average True Range (ATR) normalized by price
    atr14 = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
    atr14_pct = (atr14 / close) * 100 # Express volatility as a percentage of price

    # 5. --- NEW: Trend Strength Indicator ---
    # Average Directional Index (ADX)
    adx14 = ADXIndicator(high=high, low=low, close=close, window=14).adx()

    X = pd.DataFrame({
        "ret_1": ret_1, "ret_5": ret_5,
        "rsi_14": rsi14,
        "ma_5": ma5, "ma_20": ma20, "vwap": vwap20,
        "atr14_pct": atr14_pct, # New volatility feature
        "adx14": adx14,         # New trend strength feature
    })
    
    return X.dropna().astype("float32")

# The 'make_labels' function does not need to be changed.
def make_labels(df: pd.DataFrame, X: pd.DataFrame, periods: int = 3, threshold: float = 0.003) -> pd.Series:
    future_price = df['close'].shift(-periods)
    future_return = (future_price / df['close']) - 1
    y_full = (future_return >= threshold).astype(int)
    if X.empty: return pd.Series(dtype="int8")
    y = y_full.iloc[X.index].reset_index(drop=True)
    return y.astype("int8")