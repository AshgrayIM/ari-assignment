"""수집 오케스트레이터.

기동 시 백필 → WebSocket 실시간 수집 → 재연결 시 백필 재실행.
API 레이어와 느슨하게 결합하기 위해 이벤트 브로드캐스트 콜백만 노출합니다.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.collector.backfill import backfill_all
from app.collector.binance_rest import BinanceRestClient
from app.collector.binance_ws import BinanceTradeWebsocket
from app.config import get_settings
from app.db.models import Trade
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

BroadcastFn = Callable[[dict[str, Any]], Awaitable[None]]


class CollectorManager:
    """백필 + 실시간 수집 생명주기 관리."""

    def __init__(self, broadcast: BroadcastFn | None = None) -> None:
        self.settings = get_settings()
        self.broadcast = broadcast
        self._ws: BinanceTradeWebsocket | None = None
        self._task: asyncio.Task | None = None
        self._rest = BinanceRestClient()
        self._backfill_lock = asyncio.Lock()

    async def start(self) -> None:
        """앱 기동 시 호출: 초기 백필 후 WS 루프 시작."""
        logger.info("[collector] starting for symbols=%s", self.settings.symbol_list)
        await self.run_backfill(reason="startup")

        self._ws = BinanceTradeWebsocket(
            symbols=self.settings.symbol_list,
            on_trade=self._on_trade,
            on_reconnect=self._on_reconnect,
        )
        self._task = asyncio.create_task(self._ws.run_forever(), name="binance-ws")
        logger.info("[collector] websocket task launched")

    async def stop(self) -> None:
        """앱 종료 시 호출."""
        logger.info("[collector] stopping")
        if self._ws is not None:
            await self._ws.stop()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._rest.close()
        logger.info("[collector] stopped")

    async def run_backfill(self, reason: str = "manual") -> dict[str, int]:
        """동기 백필을 스레드 풀에서 실행 (이벤트 루프 블로킹 방지)."""
        async with self._backfill_lock:
            logger.info("[collector] backfill start (reason=%s)", reason)

            def _run() -> dict[str, int]:
                db = SessionLocal()
                try:
                    return backfill_all(db, rest=self._rest)
                finally:
                    db.close()

            results = await asyncio.to_thread(_run)
            logger.info("[collector] backfill done (reason=%s): %s", reason, results)
            return results

    async def _on_reconnect(self) -> None:
        """WS 재연결 직전 훅 → 갭 백필."""
        await self.run_backfill(reason="ws_reconnect")

    async def _on_trade(self, trade: dict[str, Any]) -> None:
        """실시간 체결 저장 + 프론트 브로드캐스트."""
        await asyncio.to_thread(self._persist_trade, trade)

        if self.broadcast is not None:
            payload = {
                "type": "trade",
                "data": {
                    **trade,
                    "trade_time": trade["trade_time"].isoformat(),
                },
            }
            try:
                await self.broadcast(payload)
            except Exception:  # noqa: BLE001
                logger.exception("[collector] broadcast failed")

    @staticmethod
    def _persist_trade(trade: dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            dialect = db.get_bind().dialect.name
            insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert
            stmt = insert_fn(Trade).values(**trade)
            stmt = stmt.on_conflict_do_nothing(index_elements=["symbol", "trade_id"])
            db.execute(stmt)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("[collector] trade persist failed: %s", trade.get("trade_id"))
        finally:
            db.close()
