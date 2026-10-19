<template>
  <div class="barchart" :style="{ height: height + 'px' }">
    <div class="bc-grid">
      <div v-for="g in gridLines" :key="g.v" class="bc-gridline" :style="{ bottom: g.pct + '%' }">
        <span class="bc-gridlabel">{{ g.v }}</span>
      </div>
    </div>

    <div class="bc-bars">
      <div v-for="(bar, i) in bars" :key="i" class="bc-col">
        <div class="bc-stack" :title="tip(bar)">
          <div
            v-for="seg in bar.segments"
            :key="seg.key"
            class="bc-seg"
            :style="{ height: seg.pct + '%', background: seg.color }"
          >
            <span v-if="seg.pct >= 14" class="bc-segval">{{ seg.value }}</span>
          </div>
        </div>
        <div class="bc-label">{{ bar.label }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

/**
 * 堆叠柱状图（纯 CSS，不引图表库）。
 *
 * 为什么不用 echarts/chart.js：本项目只需要"按天/按类目的数量对比"这一种图，
 * 引入一个数百 KB 的图表库会明显拖慢首屏，且样式还要再适配一遍浅色体系。
 * 纯 CSS 柱子足够表达，且配色直接复用设计令牌。
 */
const props = defineProps({
  // [{ label, segments: [{ key, label, value, color }] }]
  data: { type: Array, default: () => [] },
  height: { type: Number, default: 180 },
});

const rawMax = computed(() => {
  let m = 0;
  for (const bar of props.data) {
    const sum = (bar.segments || []).reduce((a, s) => a + (Number(s.value) || 0), 0);
    if (sum > m) m = sum;
  }
  return m;
});

// 纵轴上限取"好看的整数"，避免出现 7、13 这类刻度
const axisMax = computed(() => {
  const m = rawMax.value;
  if (m <= 0) return 4;
  const step = m <= 4 ? 1 : m <= 10 ? 2 : m <= 40 ? 5 : m <= 100 ? 20 : 50;
  return Math.ceil(m / step) * step;
});

const gridLines = computed(() => {
  const out = [];
  for (let i = 4; i >= 1; i--) out.push({ v: Math.round(axisMax.value * i / 4), pct: i * 25 });
  return out;
});

const bars = computed(() => props.data.map((bar) => {
  const segs = (bar.segments || []).map((s) => ({
    ...s,
    value: Number(s.value) || 0,
    // 用百分比高度让柱子自适应容器；0 值也给一个极小高度以便 hover
    pct: axisMax.value ? Math.max((Number(s.value) || 0) / axisMax.value * 100, 0) : 0,
  }));
  return { label: bar.label, segments: segs };
}));

function tip(bar) {
  const lines = (bar.segments || [])
    .filter((s) => Number(s.value) > 0)
    .map((s) => `${s.label || s.key}: ${s.value}`);
  const total = (bar.segments || []).reduce((a, s) => a + (Number(s.value) || 0), 0);
  return `${bar.label}　合计 ${total}\n${lines.join('\n') || '无数据'}`;
}
</script>

<style scoped>
.barchart { position: relative; width: 100%; padding-left: 30px; box-sizing: border-box; }
.bc-grid { position: absolute; inset: 0 0 22px 30px; pointer-events: none; }
.bc-gridline {
  position: absolute; left: 0; right: 0;
  border-top: 1px dashed var(--border-subtle);
}
.bc-gridlabel {
  position: absolute; left: -30px; top: -8px; width: 24px;
  text-align: right; font-size: 10px; color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.bc-bars {
  position: absolute; inset: 0 0 0 30px;
  display: flex; align-items: flex-end; gap: 6px;
  padding-bottom: 22px; box-sizing: border-box;
}
.bc-col { flex: 1; display: flex; flex-direction: column; height: 100%; min-width: 0; }
.bc-stack {
  flex: 1; display: flex; flex-direction: column-reverse;
  align-items: stretch; justify-content: flex-start;
  border-radius: 4px 4px 0 0; overflow: hidden;
  transition: opacity .15s;
}
.bc-stack:hover { opacity: .82; }
.bc-seg {
  display: flex; align-items: center; justify-content: center;
  min-height: 2px; transition: height .3s ease;
}
.bc-segval {
  font-size: 10px; font-weight: 700; color: var(--text-on-color);
  text-shadow: 0 1px 2px color-mix(in srgb, var(--shadow-color) 35%, transparent); line-height: 1;
}
.bc-label {
  height: 22px; display: flex; align-items: center; justify-content: center;
  font-size: 11px; color: var(--text-tertiary); white-space: nowrap; text-align: center;
}
</style>
