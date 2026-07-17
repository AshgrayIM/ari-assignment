"""API response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KlineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    trade_id: int
    price: float
    quantity: float
    quote_qty: float
    trade_time: datetime
    is_buyer_maker: int


class TickerOut(BaseModel):
    symbol: str
    last: float = Field(description="현재가")
    percentage: float = Field(description="24시간 변동률(%)")
    quote_volume: float = Field(description="24시간 거래대금(USDT)")
    base_volume: float = Field(description="24시간 거래량(코인)")
    high: float
    low: float


class HealthOut(BaseModel):
    status: str
    symbols: list[str]
