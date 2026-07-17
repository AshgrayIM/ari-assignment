<script setup lang="ts">
import type { Trade } from "../types/market";

defineProps<{
  trades: Trade[];
}>();

function formatPrice(n: number): string {
  if (n >= 1000) return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (n >= 1) return n.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return n.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function sideLabel(t: Trade): string {
  // is_buyer_maker=1 → 매수자가 maker → 시장가 매도(sell)
  return t.is_buyer_maker ? "SELL" : "BUY";
}
</script>

<template>
  <section class="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4 md:p-5">
    <div class="mb-4">
      <h3 class="text-lg font-semibold">최근 체결</h3>
      <p class="text-sm text-[var(--muted)]">WebSocket 실시간 업데이트</p>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-[var(--muted)] border-b border-[var(--line)]">
            <th class="py-2 pr-3 font-medium">시간</th>
            <th class="py-2 pr-3 font-medium">심볼</th>
            <th class="py-2 pr-3 font-medium">방향</th>
            <th class="py-2 pr-3 font-medium text-right">가격</th>
            <th class="py-2 font-medium text-right">수량</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="t in trades"
            :key="`${t.symbol}-${t.trade_id}`"
            class="border-b border-[rgba(42,61,53,0.45)] hover:bg-[rgba(61,186,138,0.05)] transition-colors"
          >
            <td class="py-2 pr-3 mono text-[var(--muted)]">{{ formatTime(t.trade_time) }}</td>
            <td class="py-2 pr-3">{{ t.symbol }}</td>
            <td
              class="py-2 pr-3 mono font-medium"
              :class="sideLabel(t) === 'BUY' ? 'text-[var(--accent)]' : 'text-[var(--danger)]'"
            >
              {{ sideLabel(t) }}
            </td>
            <td class="py-2 pr-3 mono text-right">{{ formatPrice(t.price) }}</td>
            <td class="py-2 mono text-right">{{ t.quantity.toFixed(5) }}</td>
          </tr>
          <tr v-if="!trades.length">
            <td colspan="5" class="py-8 text-center text-[var(--muted)]">
              체결 데이터 대기 중…
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
