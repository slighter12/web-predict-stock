<script lang="ts">
  import { onMount } from "svelte";
  import * as echarts from "echarts";

  import type { EquityPoint } from "../types";

  export let points: EquityPoint[] = [];

  let chartElement: HTMLDivElement;
  let chart: echarts.ECharts | null = null;
  let observer: ResizeObserver | null = null;

  function renderChart() {
    if (!chart) {
      return;
    }

    if (!points.length) {
      chart.clear();
      return;
    }

    chart.setOption({
      animationDuration: 500,
      grid: { left: 14, right: 14, top: 24, bottom: 24, containLabel: true },
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: points.map((point) => point.date),
        axisLabel: { color: "#94a3b8" },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: "#94a3b8",
          formatter: (value: number) => value.toFixed(2),
        },
        splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.12)" } },
      },
      series: [
        {
          name: "Equity",
          type: "line",
          smooth: true,
          symbol: "none",
          data: points.map((point) => point.equity),
          lineStyle: { width: 3, color: "#f59e0b" },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(245, 158, 11, 0.35)" },
              { offset: 1, color: "rgba(245, 158, 11, 0.02)" },
            ]),
          },
        },
      ],
      backgroundColor: "transparent",
    });
  }

  onMount(() => {
    chart = echarts.init(chartElement);
    observer = new ResizeObserver(() => chart?.resize());
    observer.observe(chartElement);
    renderChart();

    return () => {
      observer?.disconnect();
      chart?.dispose();
    };
  });

  $: renderChart();
</script>

<div bind:this={chartElement} class="chart" aria-label="Equity curve chart"></div>

<style>
  .chart {
    width: 100%;
    height: 320px;
  }
</style>
