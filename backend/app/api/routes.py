"""REST endpoints for historical data and ticker summaries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collector.binance_rest import BinanceRestClient
from app.config import get_settings
from app.db.models import Kline, Trade
from app.db.session import get_db
from app.schemas.market import HealthOut, KlineOut, TickerOut, TradeOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()
    return HealthOut(status="ok", symbols=settings.symbol_list)


@router.get("/tickers", response_model=list[TickerOut])
def get_tickers() -> list[TickerOut]:
    """BTC/ETH 현재가·24h 변동률·거래량 카드용."""
    settings = get_settings()
    rest = BinanceRestClient()
    try:
        return [TickerOut(**rest.fetch_ticker(s)) for s in settings.symbol_list]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"ticker fetch failed: {exc}") from exc
    finally:
        rest.close()


@router.get("/klines", response_model=list[KlineOut])
def get_klines(
    symbol: str = Query(..., description="예: BTCUSDT"),
    limit: int = Query(500, ge=1, le=2000),
    hours: int | None = Query(None, ge=1, le=168, description="최근 N시간"),
    db: Session = Depends(get_db),
) -> list[KlineOut]:
    """차트용 과거 1분봉 조회."""
    symbol = symbol.upper()
    stmt = select(Kline).where(Kline.symbol == symbol)

    if hours is not None:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        stmt = stmt.where(Kline.open_time >= since)

    stmt = stmt.order_by(Kline.open_time.desc()).limit(limit)
    rows = list(db.execute(stmt).scalars().all())
    rows.reverse()  # 시간 오름차순
    return [KlineOut.model_validate(r) for r in rows]


@router.get("/trades", response_model=list[TradeOut])
def get_trades(
    symbol: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[TradeOut]:
    """최근 체결 테이블용."""
    stmt = select(Trade)
    if symbol:
        stmt = stmt.where(Trade.symbol == symbol.upper())
    stmt = stmt.order_by(Trade.trade_time.desc()).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [TradeOut.model_validate(r) for r in rows]
