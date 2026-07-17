"""SQLAlchemy engine / session factory.

SQLite와 PostgreSQL 모두 DATABASE_URL로 전환 가능하도록 구성합니다.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _build_engine():
    settings = get_settings()
    url = settings.resolved_database_url
    connect_args = {}
    if url.startswith("sqlite"):
        # FastAPI/수집기가 여러 스레드에서 동일 연결을 쓸 수 있도록 허용
        connect_args["check_same_thread"] = False
        # 잠금 대기 시간(ms). busy_timeout PRAGMA와 함께 동작
        connect_args["timeout"] = 30

    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            """SQLite 동시성/안정성 PRAGMA.

            - WAL: 읽기(프론트 Select)와 쓰기(WS Insert)를 동시에 허용
            - busy_timeout: 일시적 잠금 시 즉시 실패 대신 재시도
            - synchronous=NORMAL: WAL과 함께 쓰기에 적합한 내구성/성능 균형
            - foreign_keys: FK 제약 활성화
            """
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """테이블 생성 (존재하지 않을 때만)."""
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Depends용 세션 제너레이터."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
