# backend/app/models/train.py
import pandas as pd
import logging
import time
from sqlalchemy import text
from app.db.base import SessionLocal
from app.config import settings
from . import features, model_store
# TODO: from sklearn.model_selection import train_test_split
# TODO: import lightgbm as lgb

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def train_model_for_symbol(db, symbol: str):
    logger.info(f"Starting training pipeline for {symbol}...")
    # 1. Load data
    query = text(f"""
        SELECT ts, open, high, low, close, volume
        FROM bars
        WHERE symbol = :symbol
        ORDER BY ts DESC
        LIMIT :limit
    """)
    df = pd.read_sql(query, db.bind, params={"symbol": symbol, "limit": settings.TRAIN_MAX_BARS})
    df = df.sort_values('ts').reset_index(drop=True)

    if df.empty or len(df) < 100:
        logger.warning(f"Not enough data to train model for {symbol}. Found {len(df)} bars.")
        return

    # 2. Build features & target
    df = features.create_features(df)
    df = features.create_target(df, settings.TARGET_RETURN_THRESHOLD)
    df.dropna(inplace=True)

    # 3. TODO: Train LightGBM classifier
    logger.info("Placeholder: SKIPPING ACTUAL MODEL TRAINING.")
    # X = df[['feature_1', 'feature_2']]
    # y = df['target']
    # X_train, X_test, y_train, y_test = train_test_split(...)
    # model = lgb.LGBMClassifier(...)
    # model.fit(X_train, y_train)

    # 4. Save model bundle
    model_bundle = {
        "model": "dummy_model_object", # Replace with actual trained model
        "feature_columns": ['feature_1', 'feature_2'],
        "training_date": pd.Timestamp.now().isoformat()
    }
    model_store.save_model(model_bundle, symbol)
    logger.info(f"Training pipeline for {symbol} complete.")

def main():
    logger.info("Trainer service starting.")
    db = SessionLocal()
    try:
        for symbol in settings.TICKER_LIST:
            train_model_for_symbol(db, symbol)
            time.sleep(1)
    finally:
        db.close()
    logger.info("Trainer service finished.")

if __name__ == "__main__":
    main()