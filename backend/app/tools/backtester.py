import pandas as pd
import logging
import time
import argparse
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import joblib

# Set up imports to use our existing project structure
from app.config import settings
from app.models import features

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Backtester Configuration ---
engine = create_engine(settings.DATABASE_URL)
try:
    MODEL_BUNDLE = joblib.load("app/models/model.pkl")
    MODELS = MODEL_BUNDLE["models"]
    logger.info(f"Loaded model bundle trained at {MODEL_BUNDLE.get('trained_at')}")
except FileNotFoundError:
    logger.critical("Model file 'app/models/model.pkl' not found! The trainer must be run first.")
    exit(1)

def run_backtest(start_date: str, end_date: str):
    """
    Runs a simulation of the agent's logic over a historical date range.
    """
    logger.info(f"--- Starting Backtest from {start_date} to {end_date} ---")
    
    # 1. Load Data (No changes here)
    logger.info("Loading all historical bars for the backtest period...")
    query = text("SELECT * FROM bars WHERE ts >= :start AND ts < :end ORDER BY ts ASC")
    all_bars = pd.read_sql_query(query, engine, params={'start': start_date, 'end': end_date})
    if all_bars.empty:
        logger.error("No historical data found for the specified date range. Exiting.")
        return
    data_by_symbol = {symbol: df.copy() for symbol, df in all_bars.groupby('symbol')}
    all_timestamps = sorted(all_bars['ts'].unique())
    logger.info(f"Loaded {len(all_bars)} bars across {len(data_by_symbol)} symbols, with {len(all_timestamps)} unique timestamps.")

    # 2. Initialize State
    cash = settings.DAILY_BUDGET
    # --- UPGRADE: Add new fields to the position dictionary for trailing stops ---
    positions = {} # { 'symbol': {'qty': 10, 'avg_price': 1500.0, 'high_water_mark': 1510.0, 'ts_active': False} }
    completed_trades = []
    pnl_history = []

    # 3. Main Simulation Loop
    logger.info("Starting simulation loop...")
    for i, ts in enumerate(all_timestamps):
        if i % 100 == 0:
            logger.info(f"Simulating timestamp {i+1}/{len(all_timestamps)}: {pd.to_datetime(ts).strftime('%Y-%m-%d %H:%M')}")

        all_symbol_states = [] # This needs to be inside the loop to reset each timestamp

        for symbol_ns, symbol_df in data_by_symbol.items():
            current_data = symbol_df[symbol_df['ts'] <= ts]
            if len(current_data) < 200: continue
            
            current_bar = current_data.iloc[-1]
            price = float(current_bar['close'])
            plain_symbol = symbol_ns.replace('.NS', '')

            # --- UPGRADE: Implement Trailing Stop Logic ---
            if plain_symbol in positions:
                pos = positions[plain_symbol]
                avg_price = pos['avg_price']
                
                # Update the highest price seen since entry
                pos['high_water_mark'] = max(pos.get('high_water_mark', price), price)

                # Activate the trailing stop if profit target is hit
                if not pos.get('ts_active', False) and price >= avg_price * (1 + settings.TRAILING_STOP_ACTIVATION_PCT):
                    pos['ts_active'] = True
                    logger.info(f"[{pd.to_datetime(ts).strftime('%H:%M')}] Trailing Stop ACTIVATED for {plain_symbol} at {price:.2f}")

                # Check for exit via Trailing Stop
                if pos.get('ts_active', False):
                    trailing_stop_price = pos['high_water_mark'] * (1 - settings.TRAILING_STOP_TRAIL_PCT)
                    if price <= trailing_stop_price:
                        pnl = (price - avg_price) * pos['qty']
                        completed_trades.append({'symbol': plain_symbol, 'pnl': pnl, 'reason': 'Trailing Stop'})
                        cash += price * pos['qty']
                        del positions[plain_symbol]
                        logger.info(f"[{pd.to_datetime(ts).strftime('%H:%M')}] EXIT {plain_symbol} via TRAILING STOP at {price:.2f}, PnL: {pnl:.2f}")
                        continue # Skip to the next symbol as we have closed this one

                # Check for exit via Hard Stop-Loss (only if trailing stop is not active)
                if not pos.get('ts_active', False) and price <= avg_price * (1 - settings.STOP_LOSS_PCT):
                    pnl = (price - avg_price) * pos['qty']
                    completed_trades.append({'symbol': plain_symbol, 'pnl': pnl, 'reason': 'Hard Stop'})
                    cash += price * pos['qty']
                    del positions[plain_symbol]
                    logger.info(f"[{pd.to_datetime(ts).strftime('%H:%M')}] EXIT {plain_symbol} via HARD STOP at {price:.2f}, PnL: {pnl:.2f}")
                    continue

            # This part of your logic for generating signals is unchanged
            model_bundle = MODELS.get(plain_symbol)
            if not model_bundle: continue
            feature_df = features.make_features(current_data)
            if feature_df.empty: continue
            latest_features = feature_df.iloc[-1]
            prob_long = model_bundle['model'].predict_proba(latest_features.values.reshape(1, -1))[0, 1]
            all_symbol_states.append({
                "symbol": plain_symbol, "prob": prob_long,
                "price": price, "has_position": plain_symbol in positions
            })

        # Entry Logic (Unchanged)
        candidates = [s for s in all_symbol_states if s['prob'] >= settings.PROB_THRESHOLD_BUY and not s['has_position']]
        if candidates:
            best_candidate = max(candidates, key=lambda c: c['prob'])
            symbol_to_buy = best_candidate['symbol']
            price = best_candidate['price']
            alloc = cash * settings.POSITION_ENTRY_PCT
            qty = int(alloc / price)
            if qty > 0 and cash >= qty * price:
                # --- UPGRADE: Add trailing stop fields to new position ---
                positions[symbol_to_buy] = {'qty': qty, 'avg_price': price, 'high_water_mark': price, 'ts_active': False}
                cash -= qty * price
                logger.info(f"[{pd.to_datetime(ts).strftime('%H:%M')}] ENTRY {symbol_to_buy} x{qty} at {price:.2f} (prob={best_candidate['prob']:.2f})")

        # PnL Recording (Unchanged)
        realized_pnl = sum(t['pnl'] for t in completed_trades)
        unrealized_pnl = 0
        for symbol, pos in positions.items():
            latest_price = data_by_symbol[f"{symbol}.NS"][data_by_symbol[f"{symbol}.NS"]['ts'] == ts]['close'].iloc[0]
            unrealized_pnl += (latest_price - pos['avg_price']) * pos['qty']
        pnl_history.append(realized_pnl + unrealized_pnl)

    logger.info("Simulation loop finished.")

    # 4. Final Report (with upgrades)
    total_pnl = pnl_history[-1] if pnl_history else 0
    num_trades = len(completed_trades)
    wins = [t for t in completed_trades if t['pnl'] > 0]
    win_rate = (len(wins) / num_trades) * 100 if num_trades > 0 else 0
    peak, max_drawdown = 0, 0
    for pnl in pnl_history:
        if pnl > peak: peak = pnl
        drawdown = peak - pnl
        if drawdown > max_drawdown: max_drawdown = drawdown

    # --- UPGRADE: Add the individual trade log to the report ---
    print("\n--- INDIVIDUAL TRADE LOG ---")
    if not completed_trades:
        print("No trades were executed.")
    else:
        # Create a DataFrame for easy viewing and sorting
        trade_log_df = pd.DataFrame(completed_trades)
        trade_log_df = trade_log_df.sort_values(by='pnl', ascending=False)
        for _, trade in trade_log_df.iterrows():
            print(f"  - Symbol: {trade['symbol']:<12} | PnL: ₹{trade['pnl']:>8.2f} | Exit Reason: {trade['reason']}")

    print("\n--- BACKTEST PERFORMANCE REPORT ---")
    print(f"Period:                     {start_date} to {end_date}")
    print(f"Final Portfolio Value:      ₹{settings.DAILY_BUDGET + total_pnl:,.2f}")
    print(f"Total Net PnL:              ₹{total_pnl:,.2f}")
    print("---")
    print(f"Total Trades:               {num_trades}")
    print(f"Win Rate:                   {win_rate:.2f}%")
    print(f"Max Drawdown:               ₹{max_drawdown:,.2f}")
    print("----------------------------------\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a backtest of the trading agent.")
    parser.add_argument("--start-date", default="2025-11-03", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", default="2025-11-08", help="End date in YYYY-MM-DD format.")
    args = parser.parse_args()
    run_backtest(args.start_date, args.end_date)