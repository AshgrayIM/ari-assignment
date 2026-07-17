import { computed, onMounted, onUnmounted, ref } from "vue";
import { fetchKlines, fetchTickers, fetchTrades } from "../api/rest";
import { MarketSocket } from "../api/ws";
import type { Kline, Ticker, Trade } from "../types/market";

const SYMBOLS = ["BTCUSDT", "ETHUSDT"] as const;

export function useMarketData() {
  const selectedSymbol = ref<(typeof SYMBOLS)[number]>("BTCUSDT");
  const tickers = ref<Ticker[]>([]);
  const klines = ref<Kline[]>([]);
  const trades = ref<Trade[]>([]);
  const connected = ref(false);
  const loading = ref(true);
  const error = ref<string | null>(null);

  let socket: MarketSocket | null = null;
  let tickerTimer: number | null = null;

  const selectedTicker = computed(() =>
    tickers.value.find((t) => t.symbol === selectedSymbol.value) ?? null,
  );

  async function loadInitial(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const [t, k, tr] = await Promise.all([
        fetchTickers(),
        fetchKlines(selectedSymbol.value, 6, 500),
        fetchTrades(undefined, 40),
      ]);
      tickers.value = t;
      klines.value = k;
      trades.value = tr;
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
    } finally {
      loading.value = false;
    }
  }

  async function refreshTickers(): Promise<void> {
    try {
      tickers.value = await fetchTickers();
    } catch {
      // keep last known values
    }
  }

  async function changeSymbol(symbol: (typeof SYMBOLS)[number]): Promise<void> {
    selectedSymbol.value = symbol;
    try {
      klines.value = await fetchKlines(symbol, 6, 500);
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
    }
  }

  function applyTrade(trade: Trade): void {
    // 테이블: 최신 체결을 앞에 추가
    trades.value = [trade, ...trades.value].slice(0, 50);

    // 티커 현재가 즉시 반영
    const idx = tickers.value.findIndex((t) => t.symbol === trade.symbol);
    if (idx >= 0) {
      const copy = [...tickers.value];
      copy[idx] = { ...copy[idx], last: trade.price };
      tickers.value = copy;
    }

    // 선택 심볼 차트: 마지막 캔들 close 갱신 또는 새 분봉 추가
    if (trade.symbol !== selectedSymbol.value) return;

    const ts = new Date(trade.trade_time).getTime();
    const minute = Math.floor(ts / 60_000) * 60_000;
    const last = klines.value[klines.value.length - 1];

    if (!last) {
      klines.value = [
        {
          symbol: trade.symbol,
          open_time: new Date(minute).toISOString(),
          close_time: new Date(minute + 59_999).toISOString(),
          open: trade.price,
          high: trade.price,
          low: trade.price,
          close: trade.price,
          volume: trade.quantity,
          quote_volume: trade.quote_qty,
          trade_count: 1,
        },
      ];
      return;
    }

    const lastMinute = Math.floor(new Date(last.open_time).getTime() / 60_000) * 60_000;
    if (minute === lastMinute) {
      const updated = {
        ...last,
        high: Math.max(last.high, trade.price),
        low: Math.min(last.low, trade.price),
        close: trade.price,
        volume: last.volume + trade.quantity,
        quote_volume: last.quote_volume + trade.quote_qty,
        trade_count: last.trade_count + 1,
      };
      klines.value = [...klines.value.slice(0, -1), updated];
    } else if (minute > lastMinute) {
      klines.value = [
        ...klines.value,
        {
          symbol: trade.symbol,
          open_time: new Date(minute).toISOString(),
          close_time: new Date(minute + 59_999).toISOString(),
          open: trade.price,
          high: trade.price,
          low: trade.price,
          close: trade.price,
          volume: trade.quantity,
          quote_volume: trade.quote_qty,
          trade_count: 1,
        },
      ].slice(-500);
    }
  }

  onMounted(async () => {
    await loadInitial();

    socket = new MarketSocket();
    socket.connect((msg) => {
      connected.value = true;
      applyTrade(msg.data);
    });

    // 24h 변동률/거래량은 REST 주기 갱신
    tickerTimer = window.setInterval(() => {
      void refreshTickers();
    }, 15_000);
  });

  onUnmounted(() => {
    socket?.close();
    if (tickerTimer !== null) window.clearInterval(tickerTimer);
  });

  return {
    SYMBOLS,
    selectedSymbol,
    tickers,
    klines,
    trades,
    connected,
    loading,
    error,
    selectedTicker,
    changeSymbol,
    loadInitial,
  };
}
