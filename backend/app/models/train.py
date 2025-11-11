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
    
    # 1. Load data from the database
    logger.info("Loading historical data...")
    query = text(f"""
        SELECT ts, open, high, low, close, volume, symbol
        FROM bars
        WHERE symbol = :symbol
        ORDER BY ts ASC
        LIMIT :limit
    """)
    # Note: Using yfinance symbols with .NS for loading data
    df = pd.read_sql(query, db.bind, params={"symbol": f"{symbol}.NS", "limit": settings.TRAIN_MAX_BARS})

    if df.empty or len(df) < 500: # Need enough data for feature creation and training
        logger.warning(f"Not enough data to train model for {symbol}. Found {len(df)} bars. Skipping.")
        return

    # 2. Engineer features and create target variable
    df_features = features.create_features(df)
    df_final = features.create_target(df_features, threshold=settings.TARGET_RETURN_THRESHOLD, periods=3)

    # 3. Prepare data for training
    # Drop rows with NaN values (from rolling windows and target creation)
    df_final.dropna(inplace=True)

    feature_columns = [
        'ret_1', 'ret_3', 'ret_5', 'rsi_14', 'ma_5', 'ma_20', 'vwap_20', 'vol_ma_20'
    ]
    target_column = 'y'
    
    X = df_final[feature_columns]
    y = df_final[target_column]

    if len(X) < 100:
        logger.warning(f"Not enough clean data points ({len(X)}) to train after feature engineering. Skipping.")
        return

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

    logger.info(f"Training data shape: {X_train.shape}, Test data shape: {X_test.shape}")

    # 4. Train LightGBM classifier
    logger.info("Training LightGBM model...")
    lgbm = lgb.LGBMClassifier(
        objective='binary',
        n_estimators=100,
        n_jobs=-1,
        random_state=42
    )
    lgbm.fit(X_train, y_train)

    # (Optional) Evaluate model
    accuracy = lgbm.score(X_test, y_test)
    logger.info(f"Model accuracy on test set for {symbol}: {accuracy:.2f}")

    # 5. Save model bundle
    model_bundle = {
        "model": lgbm,
        "feature_columns": feature_columns,
        "training_date": pd.Timestamp.now().isoformat()
    }
    # Save using the plain symbol name, which the agent uses
    model_store.save_model(model_bundle, symbol)
    logger.info(f"--- Training pipeline for {symbol} complete. Model saved. ---")

def main():
    logger.info("Trainer service starting. Waiting for data services...")
    time.sleep(10) # Give ingestor/backfill a moment to start
    db = SessionLocal()
    try:
        # Use the plain symbols from the config, the training function adds the .NS suffix
        for symbol in settings.TICKER_LIST:
            train_model_for_symbol(db, symbol)
            time.sleep(2) # Small delay between training runs
    finally:
        db.close()
    logger.info("Trainer service finished all training jobs.")

if __name__ == "__main__":
    main()
