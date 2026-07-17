"""Application settings.

DATABASE_URL alone switches SQLite <-> PostgreSQL via SQLAlchemy URL format.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _default_sqlite_url() -> str:
    db_path = (BACKEND_ROOT / "data" / "market.db").resolve()
    return f"sqlite:///{db_path.as_posix()}"


class Settings(BaseSettings):
    """Settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = _default_sqlite_url()
    symbols: str = "BTCUSDT,ETHUSDT"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    backfill_days: int = 7
    kline_interval: str = "1m"
    ws_reconnect_base_delay: float = 1.0
    ws_reconnect_max_delay: float = 60.0

    @property
    def resolved_database_url(self) -> str:
        """상대경로 SQLite URL을 backend 루트 기준 절대경로로 보정."""
        url = self.database_url
        prefix = "sqlite:///"
        if url.startswith(prefix) and not url.startswith("sqlite:////"):
            raw = url[len(prefix):]
            path = Path(raw)
            if not path.is_absolute():
                path = (BACKEND_ROOT / path).resolve()
            return f"{prefix}{path.as_posix()}"
        return url

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip().upper() for s in self.symbols.split(",") if s.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
