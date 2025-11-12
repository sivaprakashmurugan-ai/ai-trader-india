import time
import logging
import pandas as pd
import pytz
from sqlalchemy import create_engine, text
from datetime import datetime, time as dt_time, timedelta
import joblib

from app.config import settings
from app.db.base import SessionLocal
from app.db.models import Position, Trade
from app.models import features

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load Models ---
try:
    MODEL_BUNDLE = joblib.load("app/models/model.pkl")
    MODELS = MODEL_BUNDLE["models"]
    logger.info(f"Successfully loaded model bundle trained at {MODEL_BUNDLE.get('trained_at')}")
except FileNotFoundError:
    logger.critical("Model file 'app/models/model.pkl' not found! The trainer must be run first. Exiting.")
    exit(1)

# --- Config and State ---
TIMEZONE = pytz.timezone(settings.TIMEZONE)
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
agent_state = {
    "cash": settings.DAILY_BUDGET, "daily_realized_pnl": 0.0,
    "trades_today": 0, "stop_trading_today": False,
    "symbol_cooldowns": {}, "last_prob": {}, "last_entry_time": {}
}

# --- Helper Functions ---
def ist_now(): return datetime.now(TIMEZONE)
def _time_obj(hm: str): return dt_time.fromisoformat(hm)

def in_window():
    now_time = ist_now().time()
    # --- FIX: Use the correct long names from settings ---
    start = _time_obj(settings.TRADE_START_TIME)
    end = _time_obj(settings.TRADE_END_TIME)
    return start <= now_time <= end

def should_square_off():
    # --- FIX: Use the correct long name from settings ---
    return ist_now().time() >= _time_obj(settings.SQUARE_OFF_TIME)

def close_trade(db: Session, pos: Position, exit_price: float, reason: str):
    """Handles the complete lifecycle of closing a trade."""
    now = datetime.utcnow()
    logger.info(f"[{reason}] Closing {pos.quantity} of {pos.symbol} at {exit_price:.2f}")

    entry_value = float(pos.avg_price) * pos.quantity
    exit_value = exit_price * pos.quantity
    commission = (entry_value + exit_value) * (settings.COMMISSION_BPS / 10000.0)
    pnl = exit_value - entry_value
    pnl_net = pnl - commission

    db.add(Trade(
        symbol=pos.symbol, entry_ts=pos.entry_time, exit_ts=now, quantity=pos.quantity,
        entry_price=pos.avg_price, exit_price=exit_price, pnl=pnl, pnl_net=pnl_net
    ))
    agent_state["cash"] += exit_value
    agent_state["daily_realized_pnl"] += pnl_net
    db.delete(pos)
    
    cooldown_end = datetime.now() + timedelta(minutes=settings.COOLDOWN_MINUTES_AFTER_EXIT)
    agent_state["symbol_cooldowns"][pos.symbol] = cooldown_end
    agent_state["last_entry_time"].pop(pos.symbol, None)
    logger.info(f"Cooldown for {pos.symbol} set until {cooldown_end.time()}")

def run_agent_cycle():
    """Main loop for the trading agent."""
    logger.info("--- Starting new agent cycle ---")
    db = SessionLocal()
    try:
        now_utc = datetime.utcnow()
        now_ist = ist_now()

        # --- Handle Square Off ---
        if should_square_off():
            open_positions = db.query(Position).all()
            if not open_positions:
                logger.info("Square off time reached. No open positions.")
                agent_state["stop_trading_today"] = True
                return
            logger.warning("SQUARE OFF time reached! Closing all open positions.")
            for pos in open_positions:
                latest_bar = pd.read_sql_query(text("SELECT close FROM bars WHERE symbol=:s ORDER BY ts DESC LIMIT 1"), db.bind, params={'s': pos.symbol}).iloc[0]
                close_trade(db, pos, float(latest_bar['close']), "SQUARE OFF")
            db.commit()
            agent_state["stop_trading_today"] = True
            return

        # --- Handle Trading Window ---
        if not in_window():
            logger.info(f"Outside trading hours ({settings.TRADE_START_TIME} - {settings.TRADE_END_TIME}). Skipping cycle.")
            return
            
        # ... (Full trading logic continues here) ...
        # (This is the complete, correct logic as developed previously)
        
        all_symbols_state, open_positions = [], {p.symbol: p for p in db.query(Position).all()}
        for symbol_ns in settings.TICKER_LIST:
            symbol = symbol_ns.replace('.NS', '')
            model_bundle = MODELS.get(symbol)
            if not model_bundle: continue

            df = pd.read_sql_query(text("SELECT * FROM bars WHERE symbol = :s ORDER BY ts DESC LIMIT 200"), db.bind, params={"s": symbol_ns})
            if len(df) < 25: continue
            
            X = features.make_features(df.sort_values('ts'))
            if X.empty: continue

            latest_row = X.iloc[-1]
            prob_long = model_bundle['model'].predict_proba(latest_row.values.reshape(1, -1))[0, 1]
            
            all_symbols_state.append({
                "symbol": symbol, "prob": prob_long, "price": float(df['close'].iloc[-1]),
                "position": open_positions.get(symbol),
            })
        
        # --- Exit Logic ---
        for state in all_symbols_state:
            pos = state["position"]
            if not pos: continue

            entry_time = agent_state["last_entry_time"].get(pos.symbol)
            if entry_time and (now_utc - entry_time) < timedelta(minutes=settings.MIN_HOLD_MINUTES):
                continue # Skip exit checks if within min-hold period

            price = state["price"]; avg_price = float(pos.avg_price)
            if price >= avg_price * (1 + settings.TAKE_PROFIT_PCT):
                close_trade(db, pos, price, "TAKE PROFIT")
            elif price <= avg_price * (1 - settings.STOP_LOSS_PCT):
                close_trade(db, pos, price, "STOP LOSS")
            elif state["prob"] <= settings.PROB_THRESHOLD_SELL:
                close_trade(db, pos, price, "MODEL EXIT")
        db.commit()
        
        # --- Entry Logic ---
        candidates = []
        for state in all_symbols_state:
            cooldown_time = agent_state["symbol_cooldowns"].get(state["symbol"])
            if cooldown_time and datetime.now() < cooldown_time: continue
            if state["prob"] >= settings.PROB_THRESHOLD_BUY and not state["position"]:
                candidates.append(state)
        
        if not candidates:
            logger.info("No valid entry candidates found.")
            return

        p_max = max(c['prob'] for c in candidates)
        total_score = 0
        for c in candidates:
            edge = c['prob'] - settings.PROB_THRESHOLD_BUY
            rel = max(0, c['prob'] - (p_max - settings.DOMINANCE_GAP))
            c['score'] = edge * rel
            total_score += c['score']

        if total_score > 0:
            capital_to_deploy = agent_state["cash"] * settings.POSITION_ENTRY_PCT
            for c in candidates:
                if c['score'] <= 0: continue
                alloc = capital_to_deploy * (c['score'] / total_score)
                alloc = max(settings.MIN_TRADE_VALUE, min(alloc, settings.MAX_TRADE_VALUE_PER_SYMBOL))
                qty = int(alloc / c['price'])
                cost = qty * c['price']

                if qty > 0 and agent_state["cash"] >= cost:
                    logger.info(f"[ENTRY] BUY {qty} x {c['symbol']} @ {c['price']:.2f}")
                    db.add(Position(symbol=c['symbol'], quantity=qty, avg_price=c['price'], entry_time=now_utc))
                    agent_state["cash"] -= cost
                    agent_state["trades_today"] += 1
                    agent_state["last_entry_time"][c['symbol']] = now_utc
        db.commit()

    except Exception as e:
        logger.error(f"Error in agent cycle: {e}", exc_info=True)
    finally:
        db.close()
    
    logger.info(f"--- Cycle complete. Cash: {agent_state['cash']:.2f} ---")

if __name__ == "__main__":
    logger.info("--- AI Trading Agent Starting ---")
    time.sleep(15) # Initial delay
    while True:
        run_agent_cycle()
        time.sleep(settings.AGENT_LOOP_SLEEP_SECONDS)