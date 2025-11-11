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

def fetch_historical_data_yfinance(symbol: str, days: int, interval_minutes: int) -> pd.DataFrame:
    """Fetches historical intraday data from yfinance."""
    logger.info(f"Fetching last {days} days of {interval_minutes}-min data for {symbol} from yfinance...")
    interval_str = f"{interval_minutes}m"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        data = yf.download(
            tickers=symbol,
            start=start_date,
            end=end_date,
            interval=interval_str,
            auto_adjust=True,
            progress=False
        )
        if data.empty:
            logger.warning(f"No data returned for {symbol} from yfinance.")
            return pd.DataFrame()

        data.reset_index(inplace=True)
        # Standardize column names
        data.rename(columns={"Datetime": "ts", "Open": "open", "High": "high",
                             "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        
        # Ensure 'ts' is timezone-aware and standardized to UTC
        if data['ts'].dt.tz is None:
            data['ts'] = data['ts'].dt.tz_localize('UTC')
        else:
            data['ts'] = data['ts'].dt.tz_convert('UTC')
            
        data['symbol'] = symbol
        return data[['symbol', 'ts', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        logger.error(f"Error fetching data for {symbol} from yfinance: {e}")
        return pd.DataFrame()

def upsert_bars(db: Session, bars_df: pd.DataFrame):
    if bars_df.empty: return
    table = Bar.__table__
    stmt = insert(table).values(bars_df.to_dict(orient='records'))
    stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'ts'])
    db.execute(stmt)
    db.commit()
    logger.info(f"Upserted {len(bars_df)} historical bars for symbol {bars_df['symbol'].iloc[0]}.")

def run_backfill():
    """Runs the historical data backfill for all symbols in the universe."""
    db = SessionLocal()
    try:
        # Note: yfinance requires .NS suffix for NSE stocks
        symbols_with_suffix = [f"{ticker}.NS" for ticker in settings.TICKER_LIST]
        
        for symbol in symbols_with_suffix:
            # yfinance can sometimes fail due to IP blocks. We will be persistent.
            bars_df = fetch_historical_data_yfinance(
                symbol,
                days=settings.HISTORICAL_DAYS_TO_FETCH,
                interval_minutes=settings.BAR_INTERVAL_MINUTES
            )
            upsert_bars(db, bars_df)
            time.sleep(5) # Sleep to be polite to the yfinance servers
            
        logger.info("Historical data backfill process complete.")
    finally:
        db.close()

if __name__ == "__main__":
    run_backfill()
