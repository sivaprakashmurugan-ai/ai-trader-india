import pandas as pd
import logging
from ta.momentum import RSIIndicator


logger = logging.getLogger(__name__)

def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers features for the ML model.
    - Price-based returns
    - Technical indicators (RSI, MA, VWAP)
    - Volume-based indicators
    """
    logger.info(f"Engineering features for {df['symbol'].iloc[0]} with {len(df)} bars...")
    
    # Ensure dataframe is sorted by time
    df = df.sort_values('ts').reset_index(drop=True)

    # 1. Price-based features
    df['ret_1'] = df['close'].pct_change(1)
    df['ret_3'] = df['close'].pct_change(3)
    df['ret_5'] = df['close'].pct_change(5)

    # 2. Technical Indicators
    # RSI
    rsi_indicator = RSIIndicator(close=df['close'], window=14)
    df['rsi_14'] = rsi_indicator.rsi()

    # Moving Averages
    df['ma_5'] = df['close'].rolling(window=5).mean()
    df['ma_20'] = df['close'].rolling(window=20).mean()

    # Volume Weighted Average Price (VWAP)
    # The 'ta' library's VWAP needs a cumulative volume, which is not ideal for rolling windows.
    # We will calculate a rolling 20-period VWAP manually.
    df['typical_price_vol'] = ((df['high'] + df['low'] + df['close']) / 3) * df['volume']
    df['cum_typical_price_vol_20'] = df['typical_price_vol'].rolling(window=20).sum()
    df['cum_vol_20'] = df['volume'].rolling(window=20).sum()
    df['vwap_20'] = df['cum_typical_price_vol_20'] / df['cum_vol_20']

    # 3. Volume-based features
    df['vol_ma_20'] = df['volume'].rolling(window=20).mean()

    # Clean up intermediate columns and drop NaNs created by rolling windows
    df.drop(columns=['typical_price_vol', 'cum_typical_price_vol_20', 'cum_vol_20'], inplace=True)
    
    logger.info("Feature engineering complete.")
    return df

def create_target(df: pd.DataFrame, threshold: float, periods: int) -> pd.DataFrame:
    """
    Creates the binary target variable 'y'.
    y = 1 if the future return over 'periods' is >= 'threshold'.
    y = 0 otherwise.
    """
    logger.info(f"Creating target variable with threshold={threshold}, periods={periods}...")
    
    future_price = df['close'].shift(-periods)
    df['future_return'] = (future_price / df['close']) - 1
    
    df['y'] = (df['future_return'] >= threshold).astype(int)
    
    df.drop(columns=['future_return'], inplace=True)
    
    logger.info("Target variable creation complete.")
    return df
