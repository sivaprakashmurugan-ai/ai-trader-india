import pandas as pd
from pynse import NSE
import logging
import time
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.base import SessionLocal
from app.db.models import Bar
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    nse = NSE()
    logger.info("pynse NSE session initialized for backfill.")
except Exception as e:
    logger.critical(f"Failed to initialize pynse: {e}")
    nse = None

def fetch_historical_data(symbol: str, days: int) -> pd.DataFrame:
    if not nse: return pd.DataFrame()
    logger.info(f"--- Fetching {days} days of historical data for: {symbol} ---")
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        df = nse.get_hist(symbol, from_date=start_date, to_date=end_date)
        
        if df.empty:
            logger.warning(f"No historical data returned for {symbol}.")
            return pd.DataFrame()
        df.reset_index(inplace=True)
        df.rename(columns={'Date': 'ts', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
        df['symbol'] = f"{symbol}.NS"
        df['ts'] = pd.to_datetime(df['ts']).dt.tz_localize('UTC')
        return df[['symbol', 'ts', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {e}")
        return pd.DataFrame()

def upsert_bars(db: Session, bars_df: pd.DataFrame):
    if bars_df.empty: return
    table = Bar.__table__
    stmt = insert(table).values(bars_df.to_dict(orient='records'))
    stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'ts'])
    db.execute(stmt)
    db.commit()
    logger.info(f"Upserted {len(bars_df)} historical bars for symbol {bars_df['symbol'].iloc[0]}.")

def main():
    if not nse: exit(1)
    db = SessionLocal()
    try:
        logger.info("--- Starting historical data backfill process with pynse ---")
        for symbol in settings.TICKER_LIST:
            bars_df = fetch_historical_data(symbol, settings.HISTORICAL_DAYS_TO_FETCH)
            if not bars_df.empty:
                upsert_bars(db, bars_df)
            time.sleep(2)
        logger.info("--- Historical data backfill process complete ---")
    finally:
        db.close()

if __name__ == "__main__":
    main()