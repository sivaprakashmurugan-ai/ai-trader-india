import pandas as pd
from pynse import NSE
import logging
import time
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.base import SessionLocal
from app.db.models import Bar
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    nse = NSE()
    logger.info("pynse NSE session initialized successfully.")
except Exception as e:
    logger.critical(f"Failed to initialize pynse NSE session: {e}")
    nse = None

def fetch_live_data(symbol: str, interval: str) -> pd.DataFrame:
    if not nse: return pd.DataFrame()
    logger.info(f"--- Fetching live data for: {symbol} ---")
    try:
        df = nse.get_intraday(symbol=symbol, interval=interval)
        if df.empty:
            logger.warning(f"No live data returned for {symbol}.")
            return pd.DataFrame()
        df.reset_index(inplace=True)
        df.rename(columns={'timestamp': 'ts'}, inplace=True)
        df['symbol'] = f"{symbol}.NS"
        df['ts'] = df['ts'].dt.tz_convert('UTC')
        return df[['symbol', 'ts', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        logger.error(f"Error fetching live data for {symbol}: {e}")
        return pd.DataFrame()

def upsert_bars(db: Session, bars_df: pd.DataFrame):
    if bars_df.empty: return
    table = Bar.__table__
    stmt = insert(table).values(bars_df.to_dict(orient='records'))
    stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'ts'])
    db.execute(stmt)
    db.commit()
    logger.info(f"Upserted {len(bars_df)} live bars for symbol {bars_df['symbol'].iloc[0]}.")

def main():
    if not nse: exit(1)
    db = SessionLocal()
    try:
        logger.info("Starting live ingestion loop with pynse...")
        while True:
            interval = f"{settings.BAR_INTERVAL_MINUTES}minute"
            for symbol in settings.TICKER_LIST:
                bars_df = fetch_live_data(symbol, interval)
                if not bars_df.empty:
                    upsert_bars(db, bars_df)
                time.sleep(2)
            logger.info(f"Ingestion cycle complete. Sleeping for {settings.INGEST_LOOP_SLEEP_SECONDS}s.")
            time.sleep(settings.INGEST_LOOP_SLEEP_SECONDS)
    finally:
        db.close()

if __name__ == "__main__":
    main()