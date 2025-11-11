import pandas as pd
from nsetools import Nse
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

# Initialize the Nse session handler
try:
    nse = Nse()
    logger.info("nsetools Nse session initialized successfully.")
except Exception as e:
    logger.critical(f"Failed to initialize nsetools Nse session: {e}")
    nse = None

def fetch_data_nsetools(symbol: str) -> pd.DataFrame:
    """Fetches a live quote using the nsetools library."""
    if not nse:
        logger.error("nsetools session is not available. Skipping fetch.")
        return pd.DataFrame()

    logger.info(f"--- Processing symbol: {symbol} ---")
    try:
        # get_quote returns a dictionary with the latest trade information
        quote = nse.get_quote(symbol)

        if not quote or 'lastPrice' not in quote:
            logger.warning(f"No valid quote returned for {symbol} from nsetools.")
            return pd.DataFrame()

        # Create a single-row DataFrame representing the latest bar
        price = float(quote['lastPrice'])
        volume = int(quote.get('totalTradedVolume', 0)) # Use total traded volume for the bar
        
        # We create a bar for the current time
        ts = datetime.utcnow()

        bar_data = {
            'ts': [ts],
            'open': [price],
            'high': [price],
            'low': [price],
            'close': [price],
            'volume': [volume],
            'symbol': [symbol]
        }
        
        df = pd.DataFrame(bar_data)
        
        # Ensure the timestamp is timezone-aware and in UTC
        df['ts'] = pd.to_datetime(df['ts']).dt.tz_localize('UTC')

        return df

    except Exception as e:
        logger.error(f"Error fetching data for {symbol} with nsetools: {e}")
        return pd.DataFrame()

def upsert_bars(db: Session, bars_df: pd.DataFrame):
    if bars_df.empty: return
    
    # Since we are creating bars based on live ticks, we need a different upsert strategy.
    # We will round the timestamp to the nearest 5-minute interval.
    
    bars_df['ts'] = bars_df['ts'].dt.round(f"{settings.BAR_INTERVAL_MINUTES}min")

    table = Bar.__table__
    stmt = insert(table).values(bars_df.to_dict(orient='records'))
    
    # On conflict, we update the existing bar with the new price and accumulated volume
    stmt = stmt.on_conflict_do_update(
        index_elements=['symbol', 'ts'],
        set_={
            'high': func.greatest(table.c.high, stmt.excluded.high),
            'low': func.least(table.c.low, stmt.excluded.low),
            'close': stmt.excluded.close,
            'volume': table.c.volume + stmt.excluded.volume
        }
    )
    db.execute(stmt)
    db.commit()
    logger.info(f"Upserted 1 bar for symbol {bars_df['symbol'].iloc[0]}.")

def run_ingest_cycle(db: Session):
    logger.info("Starting new ingestion cycle using nsetools...")
    
    equity_symbols = [s for s in settings.TICKER_LIST if 'BEES' not in s.upper()]

    for symbol in equity_symbols:
        bars_df = fetch_data_nsetools(symbol)
        if not bars_df.empty:
            upsert_bars(db, bars_df)
        time.sleep(2) # Be polite
    logger.info("Ingestion cycle complete.")

if __name__ == "__main__":
    if not nse:
        exit(1)
        
    db = SessionLocal()
    try:
        logger.info("Starting live ingestion loop...")
        while True:
            run_ingest_cycle(db)
            logger.info(f"Sleeping for {settings.INGEST_LOOP_SLEEP_SECONDS} seconds.")
            time.sleep(settings.INGEST_LOOP_SLEEP_SECONDS)
    finally:
        db.close()
