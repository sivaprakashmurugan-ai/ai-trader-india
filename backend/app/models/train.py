import pandas as pd
import logging, time, os, sys
from sqlalchemy import text
import lightgbm as lgb
import joblib

from app.db.base import SessionLocal
from app.config import settings
from . import features

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FEAT_COLS = ["ret_1", "rsi_14", "ma_5", "ma_20", "vwap"]

def train_symbol(db, symbol: str):
    logger.info(f"--- Training for {symbol} ---")
    query = text("SELECT * FROM bars WHERE symbol = :symbol ORDER BY ts ASC")
    df = pd.read_sql(query, db.bind, params={"symbol": symbol})

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
    return {"model": model, "features": FEAT_COLS}

def main():
    db = SessionLocal()
    models = {}
    try:
        for symbol in settings.TICKER_LIST:
            model_bundle = train_symbol(db, symbol)
            if model_bundle:
                models[symbol] = model_bundle
    finally:
        db.close()

    if not models:
        logger.critical("No models were trained. Exiting.")
        sys.exit(1)

    out_path = "app/models/model.pkl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    joblib.dump({"models": models, "trained_at": datetime.utcnow().isoformat()}, out_path)
    logger.info(f"Successfully trained and saved {len(models)} models to {out_path}")

if __name__ == "__main__":
    main()