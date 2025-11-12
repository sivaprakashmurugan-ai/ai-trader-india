import pandas as pd
import logging, time, os, sys
from sqlalchemy import create_engine, text
import lightgbm as lgb
import joblib
from datetime import datetime

from app.config import settings

# --- Standalone Setup for Robustness ---
# This script is a self-contained job. It will manage its own DB connection.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load features functions from the same module
from . import features

# Use the DATABASE_URL passed into the container environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.critical("DATABASE_URL environment variable not set! Exiting.")
    sys.exit(1)

try:
    engine = create_engine(DATABASE_URL)
    logger.info("Database engine created successfully.")
except Exception as e:
    logger.critical(f"Failed to create database engine: {e}")
    sys.exit(1)


FEAT_COLS = ["ret_1", "rsi_14", "ma_5", "ma_20", "vwap"]

def train_symbol(symbol: str):
    logger.info(f"--- Training for {symbol} ---")
    
    with engine.connect() as conn:
        df = pd.read_sql_query(text("SELECT * FROM bars WHERE symbol = :symbol ORDER BY ts ASC"), conn, params={"symbol": symbol})

    if len(df) < 200:
        logger.warning(f"Not enough bars ({len(df)}) for {symbol}. Skipping.")
        return None

    X = features.make_features(df)
    y = features.make_labels(df, X)

    if len(X) != len(y) or len(X) < 100:
        logger.warning(f"Feature/label mismatch or insufficient data for {symbol}. Skipping.")
        return None

    pos = int((y == 1).sum()); neg = int((y == 0).sum())
    if pos == 0 or neg == 0:
        logger.warning(f"Only one class found for {symbol}. Skipping.")
        return None
    
    pos_wt = neg / pos
    logger.info(f"Training LGBM for {symbol} ({len(X)} rows, pos_wt={pos_wt:.1f})")
    
    model = lgb.LGBMClassifier(
        n_estimators=300, num_leaves=64, learning_rate=0.05,
        scale_pos_weight=pos_wt, n_jobs=-1, random_state=42
    )
    model.fit(X.values, y.values)
    
    # Save the model using the plain symbol name for the agent
    plain_symbol = symbol.replace('.NS', '')
    return {plain_symbol: {"model": model, "features": FEAT_COLS}}

def main():
    logger.info("--- Trainer service started ---")
    models = {}
    
    # Use the TICKER_LIST from our main project settings
    for symbol in settings.TICKER_LIST:
        try:
            model_bundle = train_symbol(symbol)
            if model_bundle:
                models.update(model_bundle)
        except Exception as e:
            logger.error(f"An unexpected error occurred while training {symbol}: {e}", exc_info=True)
            
    if not models:
        logger.critical("No models were trained. Check data availability and script logic. Exiting.")
        sys.exit(1)

    out_path = "app/models/model.pkl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    joblib.dump({"models": models, "trained_at": datetime.utcnow().isoformat()}, out_path)
    logger.info(f"Successfully trained and saved {len(models)} models to {out_path}")
    logger.info("--- Trainer service finished all jobs successfully ---")

if __name__ == "__main__":
    main()