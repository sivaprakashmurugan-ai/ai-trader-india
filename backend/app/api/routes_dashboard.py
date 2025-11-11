from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from typing import List
import logging
from datetime import datetime, time, timedelta

from app.db.base import get_db
from app.db.models import Position, Trade, PnLSnapshot, Bar
from . import schemas

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/summary", response_model=schemas.DashboardSummarySchema)
def get_summary(db: Session = Depends(get_db)):
    """Provides a high-level summary of the day's trading activity."""
    # Get the latest PnL snapshot for today
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    latest_pnl = db.query(PnLSnapshot).filter(PnLSnapshot.ts >= today_start).order_by(desc(PnLSnapshot.ts)).first()
    
    trade_count = db.query(func.count(Trade.id)).filter(Trade.exit_ts >= today_start).scalar()

    if not latest_pnl:
        return {"daily_realized_pnl": 0.0, "unrealized_pnl": 0.0, "exposure": 0.0, "trade_count": 0, "budget": 100000.00}

    return {
        "daily_realized_pnl": float(latest_pnl.realized_pnl),
        "unrealized_pnl": float(latest_pnl.unrealized_pnl),
        "exposure": float(latest_pnl.exposure),
        "trade_count": trade_count or 0,
        "budget": float(latest_pnl.budget)
    }

@router.get("/positions", response_model=List[schemas.PositionSchema])
def get_positions(db: Session = Depends(get_db)):
    """Returns all current open positions."""
    positions = db.query(Position).all()
    positions_data = []
    for pos in positions:
        latest_bar = db.query(Bar).filter(Bar.symbol == pos.symbol).order_by(desc(Bar.ts)).first()
        pos_data = schemas.PositionSchema.from_orm(pos).model_dump()
        
        if latest_bar:
            pos_data['last_price'] = float(latest_bar.close)
            cost_basis = float(pos.avg_price * pos.quantity)
            market_value = float(latest_bar.close * pos.quantity)
            unrealized_pnl = market_value - cost_basis
            pos_data['pnl_pct'] = (unrealized_pnl / cost_basis) * 100 if cost_basis != 0 else 0
        
        positions_data.append(pos_data)
    return positions_data

@router.get("/trades", response_model=List[schemas.TradeSchema])
def get_trades(db: Session = Depends(get_db)):
    """Returns the last 20 trades of the day."""
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    trades = db.query(Trade).filter(Trade.exit_ts >= today_start).order_by(desc(Trade.exit_ts)).limit(20).all()
    
    trades_data = []
    for trade in trades:
        # Infer the initial 'side' of the trade for display purposes.
        # This is a simplification; a real system might store the entry side explicitly.
        initial_side = "BUY" if trade.pnl > 0 else "SELL"
        trade_dict = schemas.TradeSchema.from_orm(trade).model_dump()
        trade_dict['side'] = initial_side
        trades_data.append(trade_dict)
        
    return trades_data

@router.get("/pnl_timeseries", response_model=List[schemas.PnLSnapshotSchema])
def get_pnl_timeseries(db: Session = Depends(get_db)):
    """Returns all of today's PnL snapshots to draw a chart."""
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    snapshots = db.query(PnLSnapshot).filter(PnLSnapshot.ts >= today_start).order_by(asc(PnLSnapshot.ts)).all()
    return snapshots
