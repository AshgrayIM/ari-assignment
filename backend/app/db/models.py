"""ORM models for market data."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Kline(Base):
    """1분봉 OHLCV 캔들."""

    __tablename__ = "klines"
    __table_args__ = (
        UniqueConstraint("symbol", "open_time", name="uq_kline_symbol_open_time"),
        Index("ix_klines_symbol_open_time", "symbol", "open_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    quote_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Trade(Base):
    """실시간 체결 내역."""

    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("symbol", "trade_id", name="uq_trade_symbol_trade_id"),
        Index("ix_trades_symbol_time", "symbol", "trade_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_id: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    quote_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_buyer_maker: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
