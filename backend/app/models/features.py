import pandas as pd
import logging
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.trend import MACD, ADXIndicator

logger = logging.getLogger(__name__)

def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build the final, comprehensive feature set."""
    if df is None or len(df) < 30:
        return pd.DataFrame()

    close = df["close"].astype(float); high = df["high"].astype(float)
    low = df["low"].astype(float); vol = df["volume"].astype(float).fillna(0)

    # 1. Price-based features
    ret_1 = close.pct_change()
    ret_5 = close.pct_change(5)

    # 2. Momentum
    rsi_14 = RSIIndicator(close=close, window=14).rsi()
    macd_signal = MACD(close=close, window_slow=26, window_fast=12, window_sign=9).macd_signal()

    # 3. Trend & Volume
    ma_20 = close.rolling(20).mean()
    vwap_20 = (close * vol).rolling(20).sum() / vol.rolling(20).sum().replace(0, 1)

    # 4. Volatility
    bb_indicator = BollingerBands(close=close, window=20, window_dev=2)
    bb_width = bb_indicator.bollinger_wband()
    bb_pband = bb_indicator.bollinger_pband()
    atr_14_pct = (AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range() / close) * 100

    # 5. Trend Strength
    adx_14 = ADXIndicator(high=high, low=low, close=close, window=14).adx()

    X = pd.DataFrame({
        "ret_1": ret_1, "ret_5": ret_5,
        "rsi_14": rsi_14, "macd_signal": macd_signal,
        "ma_20": ma_20, "vwap_20": vwap_20,
        "bb_width_20": bb_width, "bb_pband_20": bb_pband,
        "atr_14_pct": atr_14_pct,
        "adx_14": adx_14,
    })
    
    # Use reindex to guarantee column order
    final_cols = [
        "ret_1", "ret_5", "rsi_14", "macd_signal", "ma_20", "vwap_20",
        "bb_width_20", "bb_pband_20", "atr_14_pct", "adx_14"
    ]
    return X.dropna().astype("float32").reindex(columns=final_cols)

# Using the superior Triple Barrier Labeling
def make_labels(df: pd.DataFrame, X: pd.DataFrame, pt_pct: float = 0.015, sl_pct: float = 0.006, time_limit_bars: int = 10) -> pd.Series:
    """Creates labels using the Triple Barrier Method."""
    logger.info("Creating labels with Triple Barrier Method...")
    close = df['close']
    labels = pd.Series(index=X.index, dtype=float)
    for i in X.index:
        entry_price = close[i]
        profit_target = entry_price * (1 + pt_pct)
        stop_loss = entry_price * (1 - sl_pct)
        outcome = 0
        for j in range(1, time_limit_bars + 1):
            if i + j >= len(close): break
            future_high = df['high'].iloc[i+j]
            future_low = df['low'].iloc[i+j]
            if future_high >= profit_target:
                outcome = 1
                break
            if future_low <= stop_loss:
                outcome = 0
                break
        labels.loc[i] = outcome
    return labels.dropna().astype("int8")