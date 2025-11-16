import pandas as pd
import logging, time, os, sys
from sqlalchemy import create_engine, text
import lightgbm as lgb
import joblib
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

from app.config import settings
from . import features

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Standalone Setup ---
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

# --- DEFINITIVE FEATURE LIST ---
FEAT_COLS = [
    "ret_1", "ret_5", "rsi_14", "macd_signal", "ma_20", "vwap_20",
    "bb_width_20", "bb_pband_20", "atr_14_pct", "adx_14"
]

def train_symbol(symbol: str):
    logger.info(f"--- Training for {symbol} ---")
    with engine.connect() as conn:
        df = pd.read_sql_query(text("SELECT * FROM bars WHERE symbol = :symbol ORDER BY ts ASC"), conn, params={"symbol": symbol})

    if len(df) < 200:
        logger.warning(f"Not enough bars ({len(df)}) for {symbol}. Skipping.")
        return None

    X = features.make_features(df)
    # --- USE THE TRIPLE BARRIER METHOD ---
    y = features.make_labels(df, X, pt_pct=0.015, sl_pct=0.006, time_limit_bars=10)

    if X.empty or y.empty or len(X) != len(y):
        logger.warning(f"Feature/label mismatch or insufficient data for {symbol}. Skipping.")
        return None
    
    X = X.reindex(columns=FEAT_COLS) # Ensure order is always correct

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    if len(X_train) < 100:
        logger.warning(f"Not enough training data after split for {symbol}. Skipping.")
        return None
        
    pos = int((y_train == 1).sum()); neg = int((y_train == 0).sum())
    if pos == 0 or neg == 0:
        logger.warning(f"Only one class found in training data for {symbol}. Skipping.")
        return None
    
    pos_wt = neg / pos
    logger.info(f"Training LGBM for {symbol} ({len(X_train)} rows, pos_wt={pos_wt:.1f})")
    
    model = lgb.LGBMClassifier(n_estimators=300, num_leaves=64, learning_rate=0.05,
                               scale_pos_weight=pos_wt, n_jobs=-1, random_state=42)
    model.fit(X_train.values, y_train.values)
    
    y_pred_prob = model.predict_proba(X_test.values)[:, 1]
    auc = roc_auc_score(y_test, y_pred_prob)

    logger.info(f"--- EVALUATION for {symbol}: Test Set AUC Score: {auc:.4f} ---")
    if auc < 0.52: # Use a slightly higher threshold for this more advanced model
        logger.warning(f"Model for {symbol} has AUC < 0.52. Skipping save.")
        return None

    plain_symbol = symbol.replace('.NS', '')
    return {plain_symbol: {"model": model, "features": FEAT_COLS, "auc": auc}}

def main():
    logger.info("--- Trainer service started ---")
    models = {}
    for symbol in settings.TICKER_LIST:
        try:
            model_bundle = train_symbol(symbol)
            if model_bundle: models.update(model_bundle)
        except Exception as e:
            logger.error(f"Error training {symbol}: {e}", exc_info=True)
            
    if not models:
        logger.critical("No models were trained successfully. Exiting.")
        sys.exit(1)

    out_path = "app/models/model.pkl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    joblib.dump({"models": models, "trained_at": datetime.utcnow().isoformat()}, out_path)
    logger.info(f"Successfully trained and saved {len(models)} models to {out_path}")

if __name__ == "__main__":
    main()