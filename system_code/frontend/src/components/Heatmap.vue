<template>
  <div class="heat">
    <div class="heat-grid">
      <!-- 左上角留空，其余列为小时刻度 -->
      <div class="heat-corner"></div>
      <div v-for="h in hours" :key="'h' + h" class="heat-hour">{{ h }}</div>

      <!-- 每周一行：左侧星期标签 + 24 个格子 -->
      <template v-for="(day, di) in days" :key="'d' + di">
        <div class="heat-day">{{ day }}</div>
        <div
          v-for="(h, hi) in hours"
          :key="`${di}-${hi}`"
          class="heat-cell"
          :style="{ background: cellColor(valueAt(di, hi)) }"
          :title="`${day} ${h}:00 — ${valueAt(di, hi)} 条告警`"
        ></div>
      </template>
    </div>

    <div class="heat-legend">
      <span class="hl-text">少</span>
      <span v-for="s in legendSteps" :key="s" class="hl-swatch" :style="{ background: cellColor(s) }"></span>
      <span class="hl-text">多（峰值 {{ max }} 条）</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

/**
 * 星期 × 小时 热力图（纯 CSS 网格）。
 *
 * 为什么这张图值得单独做：**跌倒高发时段直接决定夜班巡查怎么排**。
 * 原来的「数据统计」页用 echarts 画它，但一是接口根本没返回 hourlyHeat
 * （字段不匹配，图上全是零），二是为一个热力图引入 ~1MB 的图表库不划算。
 *
 * 配色用主色的透明度梯度，而不是从深蓝到红的彩虹色 —— 后者在浅色体系里
 * 对比失控，且彩虹色本身对"量级"的表达并不直观。
 */
const props = defineProps({
  // { '0-19': 3, '1-2': 1, ... }  键为「星期索引-小时」
  data: { type: Object, default: () => ({}) },
  hours: { type: Array, default: () => Array.from({ length: 24 }, (_, i) => i) },
  days: { type: Array, default: () => ['周一', '周二', '周三', '周四', '周五', '周六', '周日'] },
});

const max = computed(() => {
  const vals = Object.values(props.data || {}).map(Number).filter((n) => !Number.isNaN(n));
  return Math.max(1, ...vals);
});

function valueAt(di, hi) {
  return Number(props.data?.[`${di}-${hi}`] || 0);
}

// 5 档：0 值用最浅的中性底，避免"没有数据"和"有一点数据"分不清
const legendSteps = [0, 1, 2, 3, 4];
function cellColor(v) {
  const n = Number(v) || 0;
  if (n <= 0) return 'var(--tint-1)';
  const ratio = Math.min(1, n / max.value);
  const step = Math.min(4, Math.max(1, Math.ceil(ratio * 4)));
  // 5 档透明度取 --tint 系列，跟随主题（原来写死的是亮色主色的 rgba）
  return `var(--tint-${step + 1})`;
}
</script>

<style scoped>
.heat { width: 100%; }
.heat-grid {
  display: grid;
  grid-template-columns: 34px repeat(24, minmax(0, 1fr));
  gap: 2px;
  align-items: center;
}
.heat-corner { height: 14px; }
.heat-hour {
  font-size: 9px; color: var(--text-muted); text-align: center;
  line-height: 1; height: 14px; display: flex; align-items: center; justify-content: center;
}
.heat-day {
  font-size: 10px; color: var(--text-tertiary); text-align: right;
  padding-right: 6px; white-space: nowrap;
}
.heat-cell {
  height: 18px; border-radius: 3px;
  transition: outline .12s;
}
.heat-cell:hover { outline: 2px solid var(--primary); outline-offset: -1px; }

.heat-legend {
  display: flex; align-items: center; justify-content: center;
  gap: 4px; margin-top: 10px;
}
.hl-text { font-size: 10px; color: var(--text-muted); }
.hl-swatch { width: 14px; height: 10px; border-radius: 2px; }
</style>
