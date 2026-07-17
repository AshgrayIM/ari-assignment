"""FastAPI entrypoint.

lifespan에서 CollectorManager를 기동/종료하여
데이터 수집과 API 서빙을 한 프로세스에서 운영합니다.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.websocket import hub
from app.collector.manager import CollectorManager
from app.config import get_settings
from app.db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

collector: CollectorManager | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global collector

    settings = get_settings()
    logger.info("DATABASE_URL=%s", settings.resolved_database_url)
    init_db()

    collector = CollectorManager(broadcast=hub.broadcast)
    await collector.start()
    logger.info("application started")

    try:
        yield
    finally:
        if collector is not None:
            await collector.stop()
        logger.info("application stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Binance Market Dashboard API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    @app.websocket("/ws/market")
    async def market_ws(websocket: WebSocket) -> None:
        await hub.connect(websocket)
        try:
            # 클라이언트가 보내는 ping/제어 메시지를 수신하며 연결 유지
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await hub.disconnect(websocket)
        except Exception:  # noqa: BLE001
            await hub.disconnect(websocket)

    return app


app = create_app()
