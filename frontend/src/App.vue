<script setup lang="ts">
import PriceChart from "./components/PriceChart.vue";
import TickerCards from "./components/TickerCards.vue";
import TradeTable from "./components/TradeTable.vue";
import { useMarketData } from "./composables/useMarketData";

const {
  tickers,
  klines,
  trades,
  selectedSymbol,
  connected,
  loading,
  error,
  changeSymbol,
  loadInitial,
} = useMarketData();
</script>

<template>
  <div class="min-h-screen px-4 py-6 md:px-8 md:py-8 max-w-6xl mx-auto">
    <header class="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <p class="text-[var(--accent)] text-sm font-medium tracking-[0.18em] uppercase mb-2">
          Market Ops
        </p>
        <h1 class="text-3xl md:text-4xl font-semibold tracking-tight">
          Binance 실시간 운영 대시보드
        </h1>
        <p class="mt-2 text-[var(--muted)] max-w-xl">
          BTCUSDT / ETHUSDT 수집 현황 · 1분봉 백필 + WebSocket 체결 스트림
        </p>
      </div>

      <div class="flex items-center gap-3 text-sm">
        <span
          class="inline-flex items-center gap-2 rounded-full border border-[var(--line)] px-3 py-1.5 bg-[var(--card)]"
        >
          <span
            class="h-2 w-2 rounded-full"
            :class="connected ? 'bg-[var(--accent)] animate-pulse' : 'bg-[var(--warn)]'"
          />
          {{ connected ? "Live" : "Connecting" }}
        </span>
        <button
          type="button"
          class="rounded-full border border-[var(--line)] px-3 py-1.5 bg-[var(--card)] hover:border-[var(--accent-dim)] transition"
          @click="loadInitial"
        >
          새로고침
        </button>
      </div>
    </header>

    <p v-if="error" class="mb-4 text-sm text-[var(--danger)]">
      {{ error }} — 백엔드(http://127.0.0.1:8000) 실행 여부를 확인해 주세요.
    </p>
    <p v-if="loading" class="mb-4 text-sm text-[var(--muted)]">초기 데이터 로딩 중…</p>

    <div class="space-y-6">
      <TickerCards
        :tickers="tickers"
        :selected-symbol="selectedSymbol"
        @select="(s) => changeSymbol(s as 'BTCUSDT' | 'ETHUSDT')"
      />
      <PriceChart :klines="klines" :symbol="selectedSymbol" />
      <TradeTable :trades="trades" />
    </div>

    <footer class="mt-10 text-xs text-[var(--muted)] border-t border-[var(--line)] pt-4">
      REST(과거 데이터) + WebSocket(실시간) · SQLite 수집 파이프라인
    </footer>
  </div>
</template>
