# backend/app/config.py
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    TICKER_UNIVERSE: str
    BAR_INTERVAL_MINUTES: int = 5
    HISTORICAL_DAYS_TO_FETCH: int = 90
    INGEST_LOOP_SLEEP_SECONDS: int = 300
    TRAIN_MAX_BARS: int = 50000
    TARGET_RETURN_THRESHOLD: float = 0.003
    MODEL_TYPE: str = "lightgbm"
    TRADE_START_TIME: str = "09:15"
    TRADE_END_TIME: str = "15:00"
    SQUARE_OFF_TIME: str = "15:15"
    TIMEZONE: str = "Asia/Kolkata"
    AGENT_LOOP_SLEEP_SECONDS: int = 60
    DAILY_BUDGET: float = 100000.00
    DAILY_MAX_LOSS_PCT: float = 0.015
    MAX_ACTIVE_POSITIONS: int = 3
    POSITION_ENTRY_PCT: float = 0.25
    MIN_TRADE_VALUE: float = 5000.00
    MAX_TRADE_VALUE_PER_SYMBOL: float = 50000.00
    PROB_THRESHOLD_BUY: float = 0.65
    PROB_THRESHOLD_SELL: float = 0.45
    PROB_EMA_ALPHA: float = 0.5
    DOMINANCE_GAP: float = 0.1
    TAKE_PROFIT_PCT: float = 0.012
    STOP_LOSS_PCT: float = 0.006
    TRAILING_STOP_ACTIVATION_PCT: float = 0.01
    TRAILING_STOP_TRAIL_PCT: float = 0.005
    MIN_HOLD_MINUTES: int = 10
    COOLDOWN_MINUTES_AFTER_EXIT: int = 15
    MAX_TRADES_PER_DAY: int = 25
    MAX_TRADES_PER_SYMBOL_PER_DAY: int = 5
    COMMISSION_BPS: int = 4
    #ALPHA_VANTAGE_API_KEY: str

    @property
    def TICKER_LIST(self) -> List[str]:
        return [ticker.strip() for ticker in self.TICKER_UNIVERSE.split(',')]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
