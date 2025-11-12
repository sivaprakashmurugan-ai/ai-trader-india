import pandas as pd

def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build the 5 numeric features the agent will also compute."""
    if df is None or len(df) < 25: return pd.DataFrame()
    close = df["close"].astype(float)
    vol = df["volume"].astype(float).fillna(0)
    ret_1 = close.pct_change()
    r = close.pct_change()
    gain = r.clip(lower=0).rolling(14).mean()
    loss = -r.clip(upper=0).rolling(14).mean().replace(0, 1e-9)
    rsi14 = 100.0 - (100.0 / (1.0 + (gain / loss)))
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    vwap20 = (close * vol).rolling(20).sum() / vol.rolling(20).sum().replace(0, 1)
    X = pd.DataFrame({"ret_1": ret_1, "rsi_14": rsi14, "ma_5": ma5, "ma_20": ma20, "vwap": vwap20})
    return X.dropna().astype("float32")

def make_labels(df: pd.DataFrame, X: pd.DataFrame, periods: int = 3, threshold: float = 0.003) -> pd.Series:
    """y = 1 if future return > threshold, else 0"""
    future_price = df['close'].shift(-periods)
    future_return = (future_price / df['close']) - 1
    y_full = (future_return >= threshold).astype(int)
    if X.empty: return pd.Series(dtype="int8")
    y = y_full.iloc[X.index].reset_index(drop=True)
    return y.astype("int8")