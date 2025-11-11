from pydantic import BaseModel
from typing import List
from datetime import datetime
from app.db.models import OrderSide # Import the enum

class PositionSchema(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    last_price: float | None = None
    pnl_pct: float | None = None

    class Config:
        from_attributes = True

class DashboardSummarySchema(BaseModel):
    daily_realized_pnl: float
    unrealized_pnl: float
    exposure: float
    trade_count: int
    budget: float

class TradeSchema(BaseModel):
    symbol: str
    exit_ts: datetime
    quantity: int
    exit_price: float
    pnl_net: float
    # We will determine side based on PnL for simplicity, or you could join with Orders
    side: str # Will be 'BUY' or 'SELL' representation

    class Config:
        from_attributes = True

class PnLSnapshotSchema(BaseModel):
    ts: datetime
    realized_pnl: float
    unrealized_pnl: float

    class Config:
        from_attributes = True
