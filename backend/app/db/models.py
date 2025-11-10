# backend/app/db/models.py
import enum
from sqlalchemy import (Column, Integer, String, DateTime, Numeric,
                        ForeignKey, UniqueConstraint, Enum as pgEnum, func)
from .base import Base

class Bar(Base):
    __tablename__ = "bars"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Numeric(10, 2), nullable=False)
    high = Column(Numeric(10, 2), nullable=False)
    low = Column(Numeric(10, 2), nullable=False)
    close = Column(Numeric(10, 2), nullable=False)
    volume = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('symbol', 'ts', name='_symbol_ts_uc'),)

class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime(timezone=True), server_default=func.now())
    symbol = Column(String, nullable=False, index=True)
    side = Column(pgEnum(OrderSide), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(pgEnum(OrderStatus), nullable=False, default=OrderStatus.ACTIVE)

class Fill(Base):
    __tablename__ = "fills"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    ts = Column(DateTime(timezone=True), server_default=func.now())
    price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    commission = Column(Numeric(10, 2), nullable=False)

class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    avg_price = Column(Numeric(10, 2), nullable=False)
    entry_time = Column(DateTime(timezone=True), server_default=func.now())

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    entry_ts = Column(DateTime(timezone=True), nullable=False)
    exit_ts = Column(DateTime(timezone=True), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Numeric(10, 2), nullable=False)
    exit_price = Column(Numeric(10, 2), nullable=False)
    pnl = Column(Numeric(10, 2), nullable=False)
    pnl_net = Column(Numeric(10, 2), nullable=False)

class PnLSnapshot(Base):
    __tablename__ = "pnl_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    realized_pnl = Column(Numeric(10, 2), nullable=False)
    unrealized_pnl = Column(Numeric(10, 2), nullable=False)
    exposure = Column(Numeric(12, 2), nullable=False)
    budget = Column(Numeric(12, 2), nullable=False)