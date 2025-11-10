# backend/app/agent/core.py
import time
import logging
from app.config import settings
from app.db.base import SessionLocal
from app.models import model_store

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_agent_cycle():
    logger.info("Starting new agent cycle...")
    db = SessionLocal()
    try:
        # --- 1. Collect State ---
        # TODO: Check if within trading hours
        # TODO: Check hard risk limits (daily max loss)

        all_symbols_state = []
        for symbol in settings.TICKER_LIST:
            model_bundle = model_store.load_model(symbol)
            if not model_bundle: continue

            # TODO: Get last N bars, build features
            # TODO: Predict probability: prob = model.predict_proba(...)
            # TODO: Apply EMA smoothing
            # TODO: Read existing position
            
            logger.info(f"[State] Symbol: {symbol}, Placeholder Prob: 0.55, Position: 0")

        # --- 2. Exit Rules ---
        # TODO: Loop through open positions and check for TP/SL/Model exits

        # --- 3. Entry Rules ---
        # TODO: Build candidate list from symbols with prob > THRESH_BUY
        # TODO: Compute scores (edge * rel)
        # TODO: Determine capital to deploy and allocate to best candidates
        # TODO: Place paper-trade BUY orders

        logger.info("[Decision] No actions taken in this placeholder cycle.")

    except Exception as e:
        logger.error(f"An error occurred in agent cycle: {e}", exc_info=True)
    finally:
        db.close()
    logger.info("Agent cycle complete.")

def main():
    logger.info("Trading agent service starting.")
    time.sleep(10) # Wait for other services to be ready
    while True:
        run_agent_cycle()
        time.sleep(settings.AGENT_LOOP_SLEEP_SECONDS)

if __name__ == "__main__":
    main()