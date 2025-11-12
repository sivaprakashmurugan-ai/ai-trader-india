import pandas as pd
import yfinance as yf
import logging
import time
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.base import SessionLocal
from app.db.models import Bar
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """A robust function to clean yfinance data, inspired by the review code."""
    if df is None or df.empty: return pd.DataFrame()
    df = df.reset_index()
    ts_col = next((c for c in ("Datetime","Date","index") if c in df.columns), df.columns[0])
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join([str(x) for x in t if x]) for t in df.columns]
    out = pd.DataFrame()
    out["ts"] = pd.to_datetime(df[ts_col], errors="coerce").dt.tz_localize('UTC')
    def pick(prefixes, default=None):
        cands = [c for c in df.columns if any(c.lower().startswith(p) for p in prefixes)]
        return pd.to_numeric(df[cands[0]], errors="coerce") if cands else default
    close = pick(["close","adj close"])
    if close is None: return pd.DataFrame()
    out["close"]  = close
    out["open"]   = pick(["open"], default=out["close"])
    out["high"]   = pick(["high"], default=out["close"])
    out["low"]    = pick(["low"],  default=out["close"])
    out["volume"] = pick(["volume"], default=0)
    return out.dropna(subset=["ts","close"])

def fetch_latest_bars(symbol: str) -> pd.DataFrame:
    """Fetches the last 30 days of data and normalizes it."""
    logger.info(f"Fetching data for {symbol}...")
    try:
        data = yf.download(
            tickers=symbol, period="30d", interval=f"{settings.BAR_INTERVAL_MINUTES}m",
            progress=False, auto_adjust=False, actions=False
        )
        norm = normalize_df(data)
        if norm.empty:
            logger.warning(f"[Ingestor] No usable data for {symbol}")
            return pd.DataFrame()
        norm['symbol'] = symbol
        return norm
    except Exception as e:
        logger.error(f"[Ingestor] Error processing {symbol}: {e}")
        return pd.DataFrame()

def upsert_bars(db: Session, bars_df: pd.DataFrame):
    if bars_df.empty: return
    table = Bar.__table__
    stmt = insert(table).values(bars_df.to_dict(orient='records'))
    stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'ts'])
    db.execute(stmt)
    db.commit()
    logger.info(f"Upserted {len(bars_df)} bars for {bars_df['symbol'].iloc[0]}.")

def main():
    logger.info("--- Starting robust yfinance live ingestor ---")
    db = SessionLocal()
    try:
        while True:
            for symbol in settings.TICKER_LIST:
                bars_df = fetch_latest_bars(symbol)
                upsert_bars(db, bars_df)
                time.sleep(2)
            logger.info(f"Ingestion cycle complete. Sleeping for {settings.INGEST_LOOP_SLEEP_SECONDS} seconds.")
            time.sleep(settings.INGEST_LOOP_SLEEP_SECONDS)
    finally:
        db.close()

if __name__ == "__main__":
    main()