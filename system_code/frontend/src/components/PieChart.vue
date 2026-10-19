<template>
  <div class="pie-wrap">
    <svg class="pie-svg" :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`">
      <!-- 底环：无数据时也能看出图表位置与形状 -->
      <circle
        :cx="c" :cy="c" :r="r"
        fill="none" stroke="var(--tint-2)" :stroke-width="thickness"
      />
      <circle
        v-for="a in arcs" :key="a.key"
        :cx="c" :cy="c" :r="r"
        fill="none"
        :stroke="a.color"
        :stroke-width="thickness"
        :stroke-dasharray="`${a.len} ${circumference}`"
        :stroke-dashoffset="a.offset"
        stroke-linecap="butt"
        transform-origin="center"
        transform="rotate(-90)"
      >
        <title>{{ a.label }}：{{ a.value }}（{{ a.share }}%）</title>
      </circle>
      <!-- 圆心数字：文字居中，直接读出总量 -->
      <text :x="c" :y="c - 2" text-anchor="middle" dominant-baseline="middle"
            class="pie-total">{{ total }}</text>
      <text :x="c" :y="c + 16" text-anchor="middle" dominant-baseline="middle"
            class="pie-unit">{{ unit }}</text>
    </svg>

    <ul class="pie-legend">
      <li v-for="a in arcs" :key="a.key" class="pl-item">
        <span class="pl-dot" :style="{ background: a.color }"></span>
        <span class="pl-name">{{ a.label }}</span>
        <span class="pl-val">{{ a.value }}</span>
        <span class="pl-share">{{ a.share }}%</span>
      </li>
      <li v-if="!arcs.length" class="pl-empty">暂无数据</li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue';

/**
 * 环形饼图（纯 SVG，不引图表库）。
 * 中心直接显示总量，右侧图例给出各分类的数值与占比 —— 图例而不是引导线标签，
 * 是考虑到本项目的分类名较短、且布局要求"文字居中、排布均匀"。
 */
const props = defineProps({
  // [{ key, label, value, color }]
  items: { type: Array, default: () => [] },
  size: { type: Number, default: 150 },
  thickness: { type: Number, default: 18 },
  unit: { type: String, default: '总计' },
});

const c = computed(() => props.size / 2);
const r = computed(() => props.size / 2 - props.thickness / 2 - 2);
const circumference = computed(() => 2 * Math.PI * r.value);

const total = computed(() =>
  props.items.reduce((a, i) => a + (Number(i.value) || 0), 0));

const arcs = computed(() => {
  if (!total.value) return [];
  let acc = 0;
  return props.items
    .filter((i) => (Number(i.value) || 0) > 0)
    .map((i) => {
      const value = Number(i.value) || 0;
      const frac = value / total.value;
      const len = frac * circumference.value;
      const arc = {
        key: i.key ?? i.label,
        label: i.label,
        value,
        color: i.color,
        share: Math.round(frac * 100),
        len,
        // dashoffset 从 0 开始递减，形成顺时针排布
        offset: -acc * circumference.value,
      };
      acc += frac;
      return arc;
    });
});
</script>

<style scoped>
.pie-wrap {
  display: flex; align-items: center; justify-content: center;
  gap: 18px; flex-wrap: wrap; width: 100%;
}
.pie-svg { flex-shrink: 0; }
.pie-total {
  font-size: 22px; font-weight: 800; fill: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.pie-unit { font-size: 10px; fill: var(--text-muted); }

.pie-legend {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: 7px; min-width: 132px;
}
.pl-item {
  display: grid; grid-template-columns: 9px 1fr auto auto;
  align-items: center; gap: 7px; font-size: 12px;
}
.pl-dot { width: 9px; height: 9px; border-radius: 2px; }
.pl-name { color: var(--text-secondary); text-align: center; }
.pl-val {
  color: var(--text-primary); font-weight: 700;
  font-variant-numeric: tabular-nums; text-align: right;
}
.pl-share { color: var(--text-muted); font-size: 11px; min-width: 32px; text-align: right; }
.pl-empty { font-size: 12px; color: var(--text-muted); }
</style>
