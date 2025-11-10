# backend/app/data/ingest.py
import yfinance as yf
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
import logging
import time
from datetime import datetime, timedelta
from app.db.base import SessionLocal, engine
from app.db.models import Bar, Base
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_data(symbol: str, start_date: datetime, end_date: datetime, interval_minutes: int) -> pd.DataFrame:
    interval_str = f"{interval_minutes}m"
    try:
        data = yf.download(
            tickers=symbol, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'),
            interval=interval_str, auto_adjust=True, progress=False
        )
        if data.empty:
            logger.warning(f"No data for {symbol} from {start_date} to {end_date}")
            return pd.DataFrame()
        data.reset_index(inplace=True)
        data.rename(columns={"Datetime": "ts", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        data['symbol'] = symbol
        data['ts'] = data['ts'].dt.tz_convert('UTC') # Standardize to UTC
        return data[['symbol', 'ts', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()

def upsert_bars(db: Session, bars_df: pd.DataFrame):
    if bars_df.empty: return
    table = Bar.__table__
    stmt = insert(table).values(bars_df.to_dict(orient='records'))
    stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'ts'])
    db.execute(stmt)
    db.commit()

def run_historical_backfill(db: Session):
    logger.info("Starting historical data backfill...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=settings.HISTORICAL_DAYS_TO_FETCH)
    for symbol in settings.TICKER_LIST:
        logger.info(f"Fetching historical data for {symbol}...")
        bars_df = fetch_data(symbol, start_date, end_date, settings.BAR_INTERVAL_MINUTES)
        upsert_bars(db, bars_df)
        time.sleep(1) # Be nice to the API
    logger.info("Historical data backfill complete.")

def run_live_ingest(db: Session):
    logger.info("Fetching latest bar for live ingestion...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=2)
    for symbol in settings.TICKER_LIST:
        bars_df = fetch_data(symbol, start_date, end_date, settings.BAR_INTERVAL_MINUTES)
        if not bars_df.empty:
            upsert_bars(db, bars_df.tail(5)) # Upsert last few to be safe
        time.sleep(1)

def main():
    logger.info("Ingestor service starting.")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_historical_backfill(db)
        logger.info("Starting live ingestion loop...")
        while True:
            run_live_ingest(db)
            logger.info(f"Ingestion cycle complete. Sleeping for {settings.INGEST_LOOP_SLEEP_SECONDS} seconds.")
            time.sleep(settings.INGEST_LOOP_SLEEP_SECONDS)
    except KeyboardInterrupt:
        logger.info("Ingestor service stopped.")
    finally:
        db.close()

if __name__ == "__main__":
    main()