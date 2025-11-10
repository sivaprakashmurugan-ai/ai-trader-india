# backend/app/models/model_store.py
import pickle
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
MODEL_DIR = Path("./model_store")
MODEL_DIR.mkdir(exist_ok=True)

def save_model(model_bundle: dict, symbol: str):
    """Saves a model bundle to disk."""
    model_path = MODEL_DIR / f"model_{symbol}.pkl"
    logger.info(f"Saving model for {symbol} to {model_path}...")
    with open(model_path, 'wb') as f:
        pickle.dump(model_bundle, f)

def load_model(symbol: str) -> dict:
    """Loads a model bundle from disk."""
    model_path = MODEL_DIR / f"model_{symbol}.pkl"
    if not model_path.exists():
        logger.warning(f"Model for {symbol} not found at {model_path}.")
        return None
    logger.info(f"Loading model for {symbol} from {model_path}...")
    with open(model_path, 'rb') as f:
        return pickle.load(f)