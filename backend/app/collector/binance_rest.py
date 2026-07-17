"""Binance REST client (ccxt) for historical klines and tickers.

수집기 모듈이 API 서버와 독립적으로 REST 호출을 수행할 수 있도록
얇은 래퍼로 분리합니다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import ccxt

logger = logging.getLogger(__name__)

# ccxt 심볼 형식: BTC/USDT
def to_ccxt_symbol(symbol: str) -> str:
    s = symbol.upper().replace("/", "")
    if s.endswith("USDT"):
        return f"{s[:-4]}/USDT"
    return symbol


def to_db_symbol(symbol: str) -> str:
    return symbol.upper().replace("/", "")


class BinanceRestClient:
    """ccxt 기반 Binance Spot REST 클라이언트."""

    def __init__(self) -> None:
        self._exchange = ccxt.binance(
            {
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )

    def fetch_klines(
        self,
        symbol: str,
        timeframe: str = "1m",
        since_ms: int | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """OHLCV 캔들 조회 후 정규화된 dict 리스트로 반환.

        Returns:
            open_time(ms), open, high, low, close, volume, close_time(ms), ...
        """
        ccxt_symbol = to_ccxt_symbol(symbol)
        raw = self._exchange.fetch_ohlcv(
            ccxt_symbol,
            timeframe=timeframe,
            since=since_ms,
            limit=limit,
        )
        # fetch_ohlcv: [timestamp, open, high, low, close, volume]
        interval_ms = self._timeframe_to_ms(timeframe)
        rows: list[dict[str, Any]] = []
        for candle in raw:
            open_ms = int(candle[0])
            rows.append(
                {
                    "symbol": to_db_symbol(symbol),
                    "open_time": datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc),
                    "close_time": datetime.fromtimestamp(
                        (open_ms + interval_ms - 1) / 1000, tz=timezone.utc
                    ),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                    "quote_volume": 0.0,
                    "trade_count": 0,
                }
            )
        return rows

    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """24h ticker 요약 정보."""
        ccxt_symbol = to_ccxt_symbol(symbol)
        t = self._exchange.fetch_ticker(ccxt_symbol)
        return {
            "symbol": to_db_symbol(symbol),
            "last": float(t.get("last") or 0),
            "percentage": float(t.get("percentage") or 0),
            "quote_volume": float(t.get("quoteVolume") or 0),
            "base_volume": float(t.get("baseVolume") or 0),
            "high": float(t.get("high") or 0),
            "low": float(t.get("low") or 0),
            "timestamp": t.get("timestamp"),
        }

    @staticmethod
    def _timeframe_to_ms(timeframe: str) -> int:
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        multipliers = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}
        if unit not in multipliers:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return value * multipliers[unit]

    def close(self) -> None:
        try:
            self._exchange.close()
        except Exception:  # noqa: BLE001
            logger.debug("exchange close ignored", exc_info=True)
