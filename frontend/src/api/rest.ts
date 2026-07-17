import type { Kline, Ticker, Trade } from "../types/market";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

export function fetchTickers(): Promise<Ticker[]> {
  return getJson<Ticker[]>("/api/tickers");
}

export function fetchKlines(symbol: string, hours = 6, limit = 500): Promise<Kline[]> {
  const q = new URLSearchParams({
    symbol,
    hours: String(hours),
    limit: String(limit),
  });
  return getJson<Kline[]>(`/api/klines?${q}`);
}

export function fetchTrades(symbol?: string, limit = 40): Promise<Trade[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (symbol) q.set("symbol", symbol);
  return getJson<Trade[]>(`/api/trades?${q}`);
}
