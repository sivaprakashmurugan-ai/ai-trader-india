import yfinance as yf
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
import logging
import time
from datetime import datetime, timedelta

from app.db.base import SessionLocal
from app.db.models import Bar
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_latest_bar(symbol: str, interval_minutes: int) -> pd.DataFrame:
    """Fetches the most recent intraday bar from yfinance."""
    logger.info(f"Fetching latest {interval_minutes}-min bar for {symbol}...")
    interval_str = f"{interval_minutes}m"
    # Fetch data for the last 2 days to ensure we get the most recent trading day
    period = "2d"
    
    try:
        data = yf.download(
            tickers=symbol,
            period=period,
            interval=interval_str,
            auto_adjust=True,
            progress=False
        )
        if data.empty:
            logger.warning(f"No data returned for {symbol}.")
            return pd.DataFrame()

        # Get the very last row
        latest = data.iloc[[-1]].reset_index()
        
        latest.rename(columns={"Datetime": "ts", "Open": "open", "High": "high",
                               "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        
        if latest['ts'].dt.tz is None:
            latest['ts'] = latest['ts'].dt.tz_localize('UTC')
        else:
            latest['ts'] = latest['ts'].dt.tz_convert('UTC')
            
        latest['symbol'] = symbol
        return latest[['symbol', 'ts', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        logger.error(f"Error fetching latest bar for {symbol}: {e}")
        return pd.DataFrame()

def upsert_bars(db: Session, bars_df: pd.DataFrame):
    if bars_df.empty: return
    table = Bar.__table__
    stmt = insert(table).values(bars_df.to_dict(orient='records'))
    stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'ts'])
    db.execute(stmt)
    db.commit()
    logger.info(f"Upserted 1 bar for symbol {bars_df['symbol'].iloc[0]} at {bars_df['ts'].iloc[0]}.")

def run_ingest_cycle(db: Session):
    """Main loop for the live ingestor."""
    logger.info("--- Starting new ingestion cycle ---")
    for symbol in settings.TICKER_LIST:
        bars_df = fetch_latest_bar(symbol, settings.BAR_INTERVAL_MINUTES)
        upsert_bars(db, bars_df)
        time.sleep(2) # Brief pause between symbols
    logger.info("--- Ingestion cycle complete ---")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        logger.info("Starting live ingestion loop using yfinance...")
        while True:
            run_ingest_cycle(db)
            logger.info(f"Sleeping for {settings.INGEST_LOOP_SLEEP_SECONDS} seconds.")
            time.sleep(settings.INGEST_LOOP_SLEEP_SECONDS)
    finally:
        db.close()