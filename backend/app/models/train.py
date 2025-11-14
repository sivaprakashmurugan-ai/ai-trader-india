import pandas as pd
import logging, time, os, sys
from sqlalchemy import text
import lightgbm as lgb
import joblib
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score # Import evaluation metrics

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
    
    # --- NEW: Proper Train/Test Split ---
    # We use shuffle=False because this is time-series data. The test set must come after the train set.
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False, random_state=42)

    if len(X_train) < 100 or len(X_test) < 20:
        logger.warning(f"Not enough data after splitting for {symbol}. Skipping.")
        return None

    pos = int((y_train == 1).sum()); neg = int((y_train == 0).sum())
    if pos == 0 or neg == 0:
        logger.warning(f"Only one class found in training data for {symbol}. Skipping.")
        return None
    
    pos_wt = neg / pos
    logger.info(f"Training LGBM for {symbol} ({len(X_train)} rows, pos_wt={pos_wt:.1f})")
    
    model = lgb.LGBMClassifier(
        n_estimators=300, num_leaves=64, learning_rate=0.05,
        scale_pos_weight=pos_wt, n_jobs=-1, random_state=42
    )
    model.fit(X_train.values, y_train.values)
    
    # --- NEW: Evaluate the Model on Unseen Test Data ---
    y_pred_prob = model.predict_proba(X_test.values)[:, 1]
    y_pred_class = model.predict(X_test.values)

    accuracy = accuracy_score(y_test, y_pred_class)
    auc = roc_auc_score(y_test, y_pred_prob)

    logger.info(f"--- EVALUATION for {symbol} ---")
    logger.info(f"Test Set Accuracy: {accuracy:.4f}")
    logger.info(f"Test Set AUC Score: {auc:.4f}")
    logger.info("-----------------------------")

    # Only save the model if it has at least some predictive power (better than random)
    if auc < 0.51:
        logger.warning(f"Model for {symbol} has an AUC of {auc:.4f}, which is too low. Skipping save.")
        return None

    # Save the model using the plain symbol name for the agent
    plain_symbol = symbol.replace('.NS', '')
    return {plain_symbol: {"model": model, "features": FEAT_COLS, "auc": auc}}

def main():
    db = SessionLocal()
    models = {}
    try:
        for symbol in settings.TICKER_LIST:
            model_bundle = train_symbol(db, symbol)
            if model_bundle:
                models.update(model_bundle)
    finally:
        db.close()

    if not models:
        logger.critical("No models were trained successfully. Exiting.")
        sys.exit(1)

    out_path = "app/models/model.pkl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    joblib.dump({"models": models, "trained_at": datetime.utcnow().isoformat()}, out_path)
    logger.info(f"Successfully trained and saved {len(models)} models to {out_path}")

if __name__ == "__main__":
    main()