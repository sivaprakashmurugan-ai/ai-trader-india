import pandas as pd
import logging
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.trend import ADXIndicator

logger = logging.getLogger(__name__)

def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build a richer set of features including volatility and trend strength."""
    if df is None or len(df) < 30: # Need more data for new indicators
        return pd.DataFrame()

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["volume"].astype(float).fillna(0)

    # 1. Price-based features
    ret_1 = close.pct_change()
    ret_5 = close.pct_change(5)

    # 2. Momentum
    rsi_14 = RSIIndicator(close=close, window=14).rsi()

    # 3. Trend & Volume
    ma_5 = close.rolling(5).mean()
    ma_20 = close.rolling(20).mean()
    vwap_20 = (close * vol).rolling(20).sum() / vol.rolling(20).sum().replace(0, 1)

    # 4. Volatility
    # Bollinger Bands (20-period)
    bb_indicator = BollingerBands(close=close, window=20, window_dev=2)
    bb_width = bb_indicator.bollinger_wband() # Bandwidth
    bb_pband = bb_indicator.bollinger_pband() # %B Position
    # Average True Range (ATR) normalized by price
    atr_14 = (AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range() / close) * 100

    # 5. Trend Strength
    adx_14 = ADXIndicator(high=high, low=low, close=close, window=14).adx()

    X = pd.DataFrame({
        "ret_1": ret_1, "ret_5": ret_5,
        "rsi_14": rsi_14,
        "ma_5": ma_5, "ma_20": ma_20, "vwap": vwap_20,
        "bb_width_20": bb_width,
        "bb_pband_20": bb_pband,
        "atr_14_pct": atr_14,
        "adx_14": adx_14,
    })
    
    return X.dropna().astype("float32")

def make_labels(df: pd.DataFrame, X: pd.DataFrame, periods: int = 3, threshold: float = 0.003) -> pd.Series:
    """Creates the binary target variable 'y'."""
    future_price = df['close'].shift(-periods)
    future_return = (future_price / df['close']) - 1
    y_full = (future_return >= threshold).astype(int)
    if X.empty: return pd.Series(dtype="int8")
    # Align labels with the features that were not dropped
    y = y_full.loc[X.index].reset_index(drop=True)
    return y.astype("int8")