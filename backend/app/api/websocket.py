"""프론트엔드 실시간 브로드캐스트용 ConnectionManager."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """대시보드 클라이언트 WebSocket 연결 관리."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        logger.info("[hub] client connected (%s total)", len(self._clients))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
        logger.info("[hub] client disconnected (%s total)", len(self._clients))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """모든 구독 클라이언트에 JSON 메시지 전송."""
        if not self._clients:
            return

        data = json.dumps(message, default=str)
        async with self._lock:
            clients = list(self._clients)

        stale: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001
                stale.append(ws)

        for ws in stale:
            await self.disconnect(ws)


hub = ConnectionManager()
