<script setup lang="ts">
import type { Ticker } from "../types/market";

defineProps<{
  tickers: Ticker[];
  selectedSymbol: string;
}>();

const emit = defineEmits<{
  select: [symbol: string];
}>();

function formatPrice(n: number): string {
  if (n >= 1000) return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (n >= 1) return n.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return n.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function formatVolume(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(2)}K`;
  return n.toFixed(2);
}

function baseAsset(symbol: string): string {
  return symbol.replace("USDT", "");
}
</script>

<template>
  <section class="grid gap-4 md:grid-cols-2">
    <button
      v-for="t in tickers"
      :key="t.symbol"
      type="button"
      class="text-left rounded-xl border px-5 py-4 transition duration-300"
      :class="
        selectedSymbol === t.symbol
          ? 'border-[var(--accent)] bg-[var(--card)] shadow-[0_0_0_1px_rgba(61,186,138,0.25)]'
          : 'border-[var(--line)] bg-[var(--card)] hover:border-[var(--accent-dim)]'
      "
      @click="emit('select', t.symbol)"
    >
      <div class="flex items-center justify-between mb-3">
        <div>
          <p class="text-sm text-[var(--muted)]">{{ t.symbol }}</p>
          <h2 class="text-xl font-semibold tracking-wide">{{ baseAsset(t.symbol) }}</h2>
        </div>
        <span
          class="mono text-sm px-2 py-1 rounded"
          :class="t.percentage >= 0 ? 'text-[var(--accent)] bg-[rgba(61,186,138,0.12)]' : 'text-[var(--danger)] bg-[rgba(224,112,112,0.12)]'"
        >
          {{ t.percentage >= 0 ? "+" : "" }}{{ t.percentage.toFixed(2) }}%
        </span>
      </div>

      <p class="mono text-3xl font-medium mb-4 tracking-tight">
        {{ formatPrice(t.last) }}
        <span class="text-sm text-[var(--muted)] font-normal">USDT</span>
      </p>

      <div class="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p class="text-[var(--muted)] mb-1">24h 변동률</p>
          <p class="mono" :class="t.percentage >= 0 ? 'text-[var(--accent)]' : 'text-[var(--danger)]'">
            {{ t.percentage >= 0 ? "+" : "" }}{{ t.percentage.toFixed(2) }}%
          </p>
        </div>
        <div>
          <p class="text-[var(--muted)] mb-1">24h 거래대금</p>
          <p class="mono">{{ formatVolume(t.quote_volume) }} USDT</p>
        </div>
      </div>
    </button>
  </section>
</template>
