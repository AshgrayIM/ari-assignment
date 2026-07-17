"""Binance WebSocket 실시간 체결 수집 + 자동 재연결.

장애 복구 흐름:
  연결 끊김 → 지수 백오프 대기 → 백필(갭 채우기) → WebSocket 재연결
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from app.config import get_settings

logger = logging.getLogger(__name__)

# 공개 Spot 스트림 엔드포인트
_BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream"

TradeHandler = Callable[[dict[str, Any]], Awaitable[None]]
ReconnectHook = Callable[[], Awaitable[None]]


class BinanceTradeWebsocket:
    """다중 심볼 trade 스트림 구독 + 자동 재연결 클라이언트.

    ------------------------------------------------------------------
    [웹소켓 재연결(장애 복구) 로직 — 상세]

    1) run_forever()
       - 외부에서 cancel 되기 전까지 무한 루프를 돌며 연결을 유지한다.
       - 한 번의 연결 수명(= _connect_and_consume)이 끝나거나 예외가 나면
         재연결 절차로 진입한다.

    2) 재연결 절차 (_reconnect_with_backoff)
       a. 끊김 원인 로깅
       b. 지수 백오프(exponential backoff)로 대기
          delay = min(base * 2^attempt, max_delay)
          → 일시적 네트워크 장애 시 서버에 과도한 재접속을 막는다.
       c. on_reconnect 훅 호출 ★핵심★
          → 이 훅에서 backfill이 실행되어
            "마지막 저장 시각 ~ 현재" 구간의 REST 갭을 먼저 메운다.
          → 실시간 스트림만 재개하면 다운타임 데이터가 영구 누락되므로
            반드시 백필을 선행한다.
       d. attempt 카운터 증가 후 다음 연결 시도

    3) 정상 수신 시
       - 메시지를 성공적으로 처리하면 attempt를 0으로 리셋한다.
         (연속 장애가 해소되었으므로 다음 장애 시 짧은 delay부터 다시 시작)

    4) 정상 종료
       - stop() 호출 또는 CancelledError 시 _running=False 후 루프 탈출
    ------------------------------------------------------------------
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        on_trade: TradeHandler | None = None,
        on_reconnect: ReconnectHook | None = None,
    ) -> None:
        settings = get_settings()
        self.symbols = [s.lower() for s in (symbols or settings.symbol_list)]
        self.on_trade = on_trade
        self.on_reconnect = on_reconnect
        self._base_delay = settings.ws_reconnect_base_delay
        self._max_delay = settings.ws_reconnect_max_delay
        self._running = False
        self._ws: Any = None

    def _build_url(self) -> str:
        # combined stream: btcusdt@trade / ethusdt@trade
        streams = "/".join(f"{s}@trade" for s in self.symbols)
        return f"{_BINANCE_WS_BASE}?streams={streams}"

    async def run_forever(self) -> None:
        """연결을 유지하며 끊기면 자동 재연결한다."""
        self._running = True
        attempt = 0

        logger.info("[ws] starting trade stream for %s", self.symbols)

        while self._running:
            try:
                # --- 정상 연결 / 수신 루프 ---
                await self._connect_and_consume()
                # 한 세션이 성공적으로 열렸다가 종료된 경우 attempt 리셋
                # (다음 장애 시 짧은 delay부터 다시 시작)
                attempt = 0
                if not self._running:
                    break
                logger.warning("[ws] connection ended unexpectedly — will reconnect")

            except asyncio.CancelledError:
                # 앱 종료(lifespan shutdown) 시 정상 취소
                logger.info("[ws] cancelled — shutting down")
                self._running = False
                raise

            except Exception as exc:  # noqa: BLE001
                # 네트워크 오류, JSON 파싱 오류 등 예기치 못한 장애
                logger.exception("[ws] connection error: %s", exc)

            if not self._running:
                break

            # --- 재연결 + 백필 훅 ---
            attempt = await self._reconnect_with_backoff(attempt)

    async def _reconnect_with_backoff(self, attempt: int) -> int:
        """지수 백오프 대기 후 백필 훅을 실행하고, 다음 attempt를 반환한다.

        재연결 직전에 백필을 수행하는 이유:
          WebSocket이 끊긴 동안의 체결/캔들은 스트림으로 복구되지 않는다.
          따라서 REST 백필로 갭을 채운 뒤 스트림을 재개해야
          DB 시계열이 끊기지 않는다.
        """
        # 지수 백오프: 1s, 2s, 4s, ... max_delay 까지
        delay = min(self._base_delay * (2**attempt), self._max_delay)
        logger.info(
            "[ws] reconnect scheduled in %.1fs (attempt=%s)",
            delay,
            attempt + 1,
        )
        await asyncio.sleep(delay)

        # ★ 재연결 직전 백필 트리거 (CollectorManager가 주입)
        if self.on_reconnect is not None:
            try:
                logger.info("[ws] triggering backfill before reconnect")
                await self.on_reconnect()
            except Exception:  # noqa: BLE001
                # 백필 실패해도 스트림 재개 자체는 시도한다.
                # (다음 재연결 때 다시 백필이 돌며 결국 수렴)
                logger.exception("[ws] backfill on reconnect failed — continuing")

        return attempt + 1

    async def _connect_and_consume(self) -> None:
        """단일 WebSocket 세션: 연결 → 메시지 수신 → 핸들러 호출."""
        url = self._build_url()
        logger.info("[ws] connecting to %s", url)

        # ping_interval/timeout으로 유휴 연결 끊김을 조기에 감지
        async with websockets.connect(
            url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_queue=1024,
        ) as ws:
            self._ws = ws
            logger.info("[ws] connected")

            async for raw in ws:
                if not self._running:
                    break
                await self._handle_message(raw)

    async def _handle_message(self, raw: str | bytes) -> None:
        """Binance combined stream 메시지를 파싱해 on_trade 콜백으로 전달."""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[ws] invalid JSON skipped: %s", raw[:200])
            return

        # combined stream 형식: {"stream":"btcusdt@trade","data":{...}}
        data = payload.get("data", payload)
        if data.get("e") != "trade":
            return

        trade = {
            "symbol": str(data["s"]).upper(),
            "trade_id": int(data["t"]),
            "price": float(data["p"]),
            "quantity": float(data["q"]),
            "quote_qty": float(data["p"]) * float(data["q"]),
            "trade_time": datetime.fromtimestamp(int(data["T"]) / 1000, tz=timezone.utc),
            "is_buyer_maker": 1 if data.get("m") else 0,
        }

        if self.on_trade is not None:
            await self.on_trade(trade)

    async def stop(self) -> None:
        """우아한 종료: 루프 중단 + 소켓 close."""
        self._running = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except ConnectionClosed:
                pass
            except Exception:  # noqa: BLE001
                logger.debug("[ws] close error ignored", exc_info=True)
            finally:
                self._ws = None
