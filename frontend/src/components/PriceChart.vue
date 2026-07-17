<script setup lang="ts">
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { computed } from "vue";
import { Line } from "vue-chartjs";
import type { Kline } from "../types/market";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
);

const props = defineProps<{
  klines: Kline[];
  symbol: string;
}>();

const chartData = computed<ChartData<"line">>(() => {
  const labels = props.klines.map((k) => {
    const d = new Date(k.open_time);
    return d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
  });
  const closes = props.klines.map((k) => k.close);

  return {
    labels,
    datasets: [
      {
        label: `${props.symbol} Close`,
        data: closes,
        borderColor: "#3dba8a",
        backgroundColor: "rgba(61, 186, 138, 0.14)",
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 3,
        tension: 0.2,
        fill: true,
      },
    ],
  };
});

const options: ChartOptions<"line"> = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 250 },
  interaction: { mode: "index", intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: "#15201c",
      borderColor: "#2a3d35",
      borderWidth: 1,
      titleColor: "#8aa397",
      bodyColor: "#e8f0ec",
      displayColors: false,
    },
  },
  scales: {
    x: {
      ticks: { color: "#8aa397", maxTicksLimit: 8 },
      grid: { color: "rgba(42, 61, 53, 0.5)" },
      border: { color: "#2a3d35" },
    },
    y: {
      ticks: { color: "#8aa397" },
      grid: { color: "rgba(42, 61, 53, 0.5)" },
      border: { color: "#2a3d35" },
    },
  },
};
</script>

<template>
  <section class="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4 md:p-5">
    <div class="flex items-end justify-between mb-4">
      <div>
        <h3 class="text-lg font-semibold">가격 흐름</h3>
        <p class="text-sm text-[var(--muted)]">{{ symbol }} · 1분봉 종가 (최근 6시간)</p>
      </div>
    </div>
    <div class="h-[340px]">
      <Line v-if="klines.length" :data="chartData" :options="options" />
      <div
        v-else
        class="h-full flex items-center justify-center text-[var(--muted)] text-sm"
      >
        차트 데이터 로딩 중…
      </div>
    </div>
  </section>
</template>
