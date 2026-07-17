"""K-line 백필(Backfill) 로직.

동작 요약:
1) DB에 데이터가 없으면 최근 N일(기본 7일) 1분봉을 REST로 채워 넣는다.
2) 마지막 저장 시각과 현재 시각 사이에 갭이 있으면 해당 구간만 보충한다.
3) WebSocket 재연결 시에도 동일 로직이 호출되어 장애 구간의 누락을 복구한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.collector.binance_rest import BinanceRestClient
from app.config import get_settings
from app.db.models import Kline

logger = logging.getLogger(__name__)

_MAX_LIMIT = 1000
_ONE_MINUTE_MS = 60_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_latest_open_time(db: Session, symbol: str) -> datetime | None:
    """심볼별 가장 최근 K-line open_time 조회. 없으면 None."""
    stmt = select(func.max(Kline.open_time)).where(Kline.symbol == symbol)
    return db.execute(stmt).scalar_one_or_none()


def upsert_klines(db: Session, rows: list[dict]) -> int:
    """(symbol, open_time) 기준 upsert.

    DB 방언(dialect)에 따라 SQLite / PostgreSQL insert를 선택합니다.
    DATABASE_URL만 바꿔도 동일 코드로 동작하도록 설계했습니다.
    """
    if not rows:
        return 0

    dialect = db.get_bind().dialect.name
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert

    inserted = 0
    for row in rows:
        stmt = insert_fn(Kline).values(**row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "open_time"],
            set_={
                "close_time": stmt.excluded.close_time,
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "quote_volume": stmt.excluded.quote_volume,
                "trade_count": stmt.excluded.trade_count,
            },
        )
        db.execute(stmt)
        inserted += 1
    db.commit()
    return inserted


def backfill_symbol(
    db: Session,
    rest: BinanceRestClient,
    symbol: str,
    *,
    days: int | None = None,
    interval: str | None = None,
) -> int:
    """단일 심볼에 대한 갭 채우기 백필.

    ------------------------------------------------------------------
    [누락 구간 데이터 채우기 로직 — 상세]

    Step A. 기준 시작점(start) 결정
      - DB에 해당 심볼의 K-line이 전혀 없으면:
          start = 현재시각 - backfill_days (기본 7일)
          → "초기 적재" 모드
      - 이미 데이터가 있으면:
          start = (마지막 open_time + 1분)
          → "갭 보충" 모드
          ※ 마지막 캔들 다음 분부터 가져와 중복 호출을 최소화한다.

    Step B. 종료점(end) 결정
      - end = 현재 UTC 시각
      - start >= end 이면 갭이 없으므로 즉시 종료 (0건)

    Step C. 페이지네이션 루프
      - Binance/ccxt는 한 번에 최대 1000개만 반환하므로
        since_ms 를 앞으로 옮기며 반복 호출한다.
      - 각 배치를 upsert로 저장 (재실행해도 안전)
      - 반환 건수가 0이거나, 마지막 캔들이 end에 도달하면 종료

    Step D. 장애 복구 연계
      - WebSocket이 끊겼다가 다시 붙을 때 이 함수가 재호출된다.
      - 다운타임 동안 쌓인 갭(마지막 저장 ~ 현재)만 REST로 메운 뒤
        실시간 스트림을 재개하므로 데이터 연속성이 보장된다.
    ------------------------------------------------------------------
    """
    settings = get_settings()
    days = days if days is not None else settings.backfill_days
    interval = interval or settings.kline_interval

    now = _utcnow()
    latest = get_latest_open_time(db, symbol)

    # --- Step A: 시작점 결정 ---
    if latest is None:
        # 데이터가 전혀 없음 → 최근 N일 초기 백필
        start = now - timedelta(days=days)
        logger.info(
            "[backfill] %s: DB empty → initial backfill from %s (%s days)",
            symbol,
            start.isoformat(),
            days,
        )
    else:
        # 마지막 캔들 다음 1분부터 갭 보충
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        start = latest + timedelta(minutes=1)
        logger.info(
            "[backfill] %s: gap fill from %s (last stored=%s)",
            symbol,
            start.isoformat(),
            latest.isoformat(),
        )

    # --- Step B: 갭 존재 여부 ---
    if start >= now:
        logger.info("[backfill] %s: no gap (start=%s >= now=%s)", symbol, start, now)
        return 0

    # --- Step C: 페이지 단위로 REST 호출 ---
    since_ms = int(start.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)
    total = 0

    while since_ms < end_ms:
        try:
            batch = rest.fetch_klines(
                symbol,
                timeframe=interval,
                since_ms=since_ms,
                limit=_MAX_LIMIT,
            )
        except Exception:
            logger.exception("[backfill] %s: REST fetch failed at since_ms=%s", symbol, since_ms)
            raise

        if not batch:
            break

        filtered = [
            row
            for row in batch
            if int(row["open_time"].timestamp() * 1000) <= end_ms
        ]
        if not filtered:
            break

        count = upsert_klines(db, filtered)
        total += count

        last_open_ms = int(filtered[-1]["open_time"].timestamp() * 1000)
        next_since = last_open_ms + _ONE_MINUTE_MS
        if next_since <= since_ms:
            logger.warning("[backfill] %s: pagination stalled at %s", symbol, since_ms)
            break
        since_ms = next_since

        logger.debug(
            "[backfill] %s: upserted %s rows (cursor=%s)",
            symbol,
            count,
            datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc).isoformat(),
        )

    logger.info("[backfill] %s: done, total upserted=%s", symbol, total)
    return total


def backfill_all(
    db: Session,
    rest: BinanceRestClient | None = None,
    symbols: list[str] | None = None,
) -> dict[str, int]:
    """설정된 전 심볼에 대해 백필 실행.

    Returns:
        {symbol: upserted_count}
    """
    settings = get_settings()
    symbols = symbols or settings.symbol_list
    owns_client = rest is None
    rest = rest or BinanceRestClient()
    results: dict[str, int] = {}

    try:
        for symbol in symbols:
            try:
                results[symbol] = backfill_symbol(db, rest, symbol)
            except Exception:
                logger.exception("[backfill] failed for %s — continuing others", symbol)
                results[symbol] = -1
    finally:
        if owns_client:
            rest.close()

    return results
