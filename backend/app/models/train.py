import pandas as pd
import logging
import time
from sqlalchemy import text
from sklearn.model_selection import train_test_split
import lightgbm as lgb

from app.db.base import SessionLocal
from app.config import settings
from . import features, model_store

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def train_model_for_symbol(db, symbol: str):
    """Full pipeline to train and save a model for a single symbol."""
    logger.info(f"--- Starting training pipeline for {symbol} ---")
    
    logger.info("Loading historical data...")
    query = text(f"""
        SELECT ts, open, high, low, close, volume, symbol
        FROM bars WHERE symbol = :symbol ORDER BY ts ASC LIMIT :limit
    """)
    # --- FIX: Pass the symbol directly without modification ---
    df = pd.read_sql(query, db.bind, params={"symbol": symbol, "limit": settings.TRAIN_MAX_BARS})

    if df.empty or len(df) < 500:
        logger.warning(f"Not enough data to train model for {symbol}. Found {len(df)} bars. Skipping.")
        return

    df_features = features.create_features(df)
    df_final = features.create_target(df_features, threshold=settings.TARGET_RETURN_THRESHOLD, periods=3)
    df_final.dropna(inplace=True)

    feature_columns = [
        'ret_1', 'ret_3', 'ret_5', 'rsi_14', 'ma_5', 'ma_20', 'vwap_20', 'vol_ma_20'
    ]
    target_column = 'y'
    
    X = df_final[feature_columns]
    y = df_final[target_column]

    if len(X) < 100:
        logger.warning(f"Not enough clean data points ({len(X)}) to train. Skipping.")
        return

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
    logger.info(f"Training data shape: {X_train.shape}, Test data shape: {X_test.shape}")

    logger.info("Training LightGBM model...")
    lgbm = lgb.LGBMClassifier(objective='binary', n_estimators=100, n_jobs=-1, random_state=42)
    lgbm.fit(X_train, y_train)

    accuracy = lgbm.score(X_test, y_test)
    logger.info(f"Model accuracy on test set for {symbol}: {accuracy:.2f}")

    model_bundle = {
        "model": lgbm,
        "feature_columns": feature_columns,
        "training_date": pd.Timestamp.now().isoformat()
    }
    # Save using the plain symbol name (without .NS) for the agent
    plain_symbol = symbol.replace('.NS', '')
    model_store.save_model(model_bundle, plain_symbol)
    logger.info(f"--- Training pipeline for {symbol} complete. Model saved as {plain_symbol}.pkl ---")

def main():
    logger.info("Trainer service starting...")
    time.sleep(5)
    db = SessionLocal()
    try:
        # --- FIX: Use the symbols directly from the config, which are already in .NS format ---
        for symbol in settings.TICKER_LIST:
            train_model_for_symbol(db, symbol)
            time.sleep(1)
    finally:
        db.close()
    logger.info("Trainer service finished all training jobs.")

if __name__ == "__main__":
    main()