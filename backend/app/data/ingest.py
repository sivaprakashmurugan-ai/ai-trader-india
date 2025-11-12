import pandas as pd
import requests
import logging
import time
from datetime import datetime
from urllib.parse import quote

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.base import SessionLocal
from app.db.models import Bar
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- NSE Live Data Configuration ---
NSE_BASE_URL = "https://www.nseindia.com/"
NSE_CHART_API_URL = "https://www.nseindia.com/api/chart-databyindex?index={identifier}"

# These headers are critical to mimic a real browser session
HEADERS = {
    'Host': 'www.nseindia.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
}

def get_nse_session() -> requests.Session:
    """Initializes a persistent session with the necessary NSE cookies."""
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        logger.info("Acquiring new NSE session cookies...")
        session.get(NSE_BASE_URL, timeout=15) # Visit the main page to set cookies
        logger.info("NSE session is active and cookies are set.")
        return session
    except requests.RequestException as e:
        logger.error(f"Fatal error: Failed to initialize NSE session: {e}")
        return None

def fetch_live_data_nse(session: requests.Session, symbol: str) -> pd.DataFrame:
    """Fetches the latest intraday data from the NSE's public chart API."""
    logger.info(f"--- Processing symbol: {symbol} ---")
    try:
        # For standard equities, the identifier is the symbol + "EQN"
        identifier = f"{quote(symbol)}EQN"
        url = NSE_CHART_API_URL.format(identifier=identifier)

        # Make the API call
        response = session.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        graph_data = data.get("grapthData", [])
        if not graph_data:
            logger.warning(f"No graph data found for {symbol} in NSE response.")
            return pd.DataFrame()

        df = pd.DataFrame(graph_data, columns=["timestamp", "price"])
        
        # This endpoint only provides the close price. We will use it for all OHLC values.
        df['open'] = df['price']
        df['high'] = df['price']
        df['low'] = df['price']
        df['close'] = df['price']
        df['volume'] = 0 # Volume is not available from this endpoint
        df['symbol'] = f"{symbol}.NS" # Store with .NS to match historical data
        df['ts'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC')

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
    session = get_nse_session()
    if not session:
        exit(1)
        
    db = SessionLocal()
    try:
        logger.info("Starting live ingestion loop with NSE data source...")
        while True:
            logger.info("--- Starting new ingestion cycle ---")
            for symbol in settings.TICKER_LIST:
                bars_df = fetch_live_data_nse(session, symbol)
                if not bars_df.empty:
                    upsert_bars(db, bars_df)
                time.sleep(5) # Be polite to the NSE servers
            
            logger.info(f"--- Ingestion cycle complete. Sleeping for {settings.INGEST_LOOP_SLEEP_SECONDS} seconds. ---")
            time.sleep(settings.INGEST_LOOP_SLEEP_SECONDS)
    finally:
        db.close()

if __name__ == "__main__":
    main()