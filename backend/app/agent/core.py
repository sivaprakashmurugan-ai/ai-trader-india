import time
import logging
import pandas as pd
from sqlalchemy import text, func, desc
from datetime import datetime, time as dt_time

from app.config import settings
from app.db.base import SessionLocal
from app.db.models import Position, Trade, PnLSnapshot, Bar, Order
from app.models import model_store, features

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Global State (in-memory for simplicity) ---
# In a production system, this would be stored more robustly (e.g., in Redis or the DB)
agent_state = {
    "cash": settings.DAILY_BUDGET,
    "daily_realized_pnl": 0.0,
    "trades_today": 0,
    "stop_trading_today": False,
    "symbol_cooldowns": {}, # e.g., {'INFY': datetime_object}
    "last_prob": {} # For EMA smoothing
}

def run_agent_cycle():
    """Main loop for the trading agent, runs once per minute."""
    logger.info("--- Starting new agent cycle ---")
    db = SessionLocal()
    try:
        now = datetime.now()
        
        # --- 1. Check System State & Risk Limits ---
        if agent_state["stop_trading_today"]:
            logger.warning("Daily max loss hit. No new trades will be placed.")
            return

        # --- 2. Collect State for All Symbols ---
        all_symbols_state = []
        open_positions = {pos.symbol: pos for pos in db.query(Position).all()}
        
        for symbol in settings.TICKER_LIST:
            model_bundle = model_store.load_model(symbol)
            if not model_bundle:
                continue

            # Load latest bars to build features
            query = text("SELECT * FROM bars WHERE symbol = :symbol ORDER BY ts DESC LIMIT 200")
            latest_bars_df = pd.read_sql(query, db.bind, params={"symbol": f"{symbol}.NS"})
            if latest_bars_df.empty:
                continue
            
            latest_bars_df = latest_bars_df.sort_values('ts').reset_index(drop=True)
            
            # Feature engineering
            df_features = features.create_features(latest_bars_df)
            latest_row = df_features.iloc[-1]
            X = latest_row[model_bundle['feature_columns']].values.reshape(1, -1)
            
            # Predict probability and apply EMA smoothing
            prob_long = model_bundle['model'].predict_proba(X)[0, 1]
            last_prob = agent_state["last_prob"].get(symbol, prob_long)
            prob_smooth = (settings.PROB_EMA_ALPHA * prob_long) + (1 - settings.PROB_EMA_ALPHA) * last_prob
            agent_state["last_prob"][symbol] = prob_smooth
            
            # Get current position info
            pos = open_positions.get(symbol)
            
            all_symbols_state.append({
                "symbol": symbol,
                "prob": prob_smooth,
                "price": float(latest_row['close']),
                "position": pos,
            })

        # --- 3. Apply Exit Rules to Open Positions ---
        for state in all_symbols_state:
            pos = state["position"]
            if not pos:
                continue

            price = state["price"]
            avg_price = float(pos.avg_price)
            
            # Rule: Take-Profit
            if price >= avg_price * (1 + settings.TAKE_PROFIT_PCT):
                logger.info(f"[EXIT] TAKE PROFIT for {pos.symbol} at {price:.2f}")
                # TODO: Implement trade closing logic (create Trade, delete Position)
                db.delete(pos)

            # Rule: Stop-Loss
            elif price <= avg_price * (1 - settings.STOP_LOSS_PCT):
                logger.info(f"[EXIT] STOP LOSS for {pos.symbol} at {price:.2f}")
                db.delete(pos)

            # Rule: Model-based Exit
            elif state["prob"] <= settings.PROB_THRESHOLD_SELL:
                logger.info(f"[EXIT] MODEL EXIT for {pos.symbol} at {price:.2f} (prob={state['prob']:.2f})")
                db.delete(pos)
        
        db.commit() # Commit any exits

        # --- 4. Apply Entry Rules for New Positions ---
        candidates = []
        for state in all_symbols_state:
            # Entry condition: High probability and no current position
            if state["prob"] >= settings.PROB_THRESHOLD_BUY and not state["position"]:
                candidates.append(state)
        
        if not candidates:
            logger.info("No entry candidates found in this cycle.")
            return

        # Calculate scores for all candidates
        p_max = max(c['prob'] for c in candidates)
        total_score = 0
        for c in candidates:
            edge = c['prob'] - settings.PROB_THRESHOLD_BUY
            rel = max(0, c['prob'] - (p_max - settings.DOMINANCE_GAP))
            c['score'] = edge * rel
            total_score += c['score']

        # Allocate capital and place paper trades
        if total_score > 0:
            total_capital_to_deploy = agent_state["cash"] * settings.POSITION_ENTRY_PCT
            
            for c in candidates:
                if c['score'] <= 0: continue
                
                alloc = total_capital_to_deploy * (c['score'] / total_score)
                alloc = max(settings.MIN_TRADE_VALUE, min(alloc, settings.MAX_TRADE_VALUE_PER_SYMBOL))
                
                qty = int(alloc / c['price'])

                if qty > 0 and agent_state["cash"] >= qty * c['price']:
                    logger.info(f"[ENTRY] BUY {qty} x {c['symbol']} @ {c['price']:.2f} (prob={c['prob']:.2f}, score={c['score']:.2f})")
                    
                    # Create a new position in the database
                    new_pos = Position(
                        symbol=c['symbol'],
                        quantity=qty,
                        avg_price=c['price'],
                        entry_time=now
                    )
                    db.add(new_pos)
                    agent_state["cash"] -= qty * c['price']
                    agent_state["trades_today"] += 1
        
        db.commit() # Commit any new entries

    except Exception as e:
        logger.error(f"An error occurred in agent cycle: {e}", exc_info=True)
    finally:
        db.close()
    
    logger.info("--- Agent cycle complete ---")


if __name__ == "__main__":
    logger.info("Trading agent service starting. Waiting for services...")
    time.sleep(15) # Wait for models to be built and data to be available
    
    while True:
        # TODO: Add logic to only trade between TRADE_START and TRADE_END times
        run_agent_cycle()
        time.sleep(settings.AGENT_LOOP_SLEEP_SECONDS)
