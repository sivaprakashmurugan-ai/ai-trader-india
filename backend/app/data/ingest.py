import os, time, pandas as pd, yfinance as yf
from sqlalchemy import create_engine, text
import logging

from app.config import settings # Use our project's config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use settings from our config object
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
UNIVERSE = settings.TICKER_LIST
INTERVAL = f"{settings.BAR_INTERVAL_MINUTES}m"
LOOP_SECONDS = settings.INGEST_LOOP_SLEEP_SECONDS

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    df = df.reset_index()
    ts_col = next((c for c in ("Datetime","Date","index") if c in df.columns), df.columns[0])
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join([str(x) for x in t if x and str(x)!='nan']) for t in df.columns]
    out = pd.DataFrame()
    out["ts"] = pd.to_datetime(df[ts_col], errors="coerce")
    def pick(prefixes, default=None):
        cands = [c for c in df.columns if any(c.lower().startswith(p) for p in prefixes)]
        return pd.to_numeric(df[cands[0]], errors="coerce") if cands else default
    close = pick(["close","adj close","adj_close"])
    if close is None: return pd.DataFrame()
    out["close"]  = close
    out["open"]   = pick(["open"], default=out["close"])
    out["high"]   = pick(["high"], default=out["close"])
    out["low"]    = pick(["low"],  default=out["close"])
    vol = pick(["volume"], default=0)
    out["volume"] = vol if vol is not None else 0
    return out.dropna(subset=["ts","close"])

def upsert_all_once():
    for sym in UNIVERSE:
        try:
            # Using the successful parameter combination from your friend's script
            data = yf.download(
                tickers=sym, period="30d", interval=INTERVAL,
                progress=False, auto_adjust=False, actions=False,
                threads=False, group_by="column"
            )
            norm = normalize_df(data)
            if norm.empty:
                logger.warning(f"[Ingestor] No usable data for {sym}")
                continue
            with engine.begin() as conn:
                # Use a more efficient bulk insert
                insert_data = []
                for _, r in norm.iterrows():
                    insert_data.append({
                        "s": sym, "ts": pd.to_datetime(r["ts"]).to_pydatetime(),
                        "o": float(r["open"]), "h": float(r["high"]),
                        "l": float(r["low"]),  "c": float(r["close"]),
                        "v": int(r.get("volume", 0) or 0),
                    })
                
                if insert_data:
                    conn.execute(text("""
                        INSERT INTO bars(symbol, ts, open, high, low, close, volume)
                        VALUES (:s, :ts, :o, :h, :l, :c, :v)
                        ON CONFLICT (symbol, ts) DO NOTHING
                    """), insert_data)
            logger.info(f"[Ingestor] {sym} upsert ok ({len(norm)} rows)")
        except Exception as e:
            logger.error(f"[Ingestor] Error processing {sym}: {e}")

# This snapshot logic is brilliant, let's keep it.
def snapshot_pnl_tick():
    # ... (Your friend's snapshot code can be pasted here directly if needed)
    pass # For now, we focus on ingestion.

def main():
    logger.info("--- Starting yfinance live ingestor ---")
    while True:
        upsert_all_once()
        # snapshot_pnl_tick()
        logger.info(f"Ingestion cycle complete. Sleeping for {LOOP_SECONDS} seconds.")
        time.sleep(LOOP_SECONDS)

if __name__ == "__main__":
    main()