<template>
  <div class="barlist">
    <div v-for="row in rows" :key="row.key" class="bl-row">
      <span class="bl-name" :title="row.label">{{ row.label }}</span>
      <div class="bl-track">
        <div class="bl-fill" :style="{ width: row.pct + '%', background: row.color }"></div>
      </div>
      <span class="bl-value">{{ row.value }}</span>
      <span v-if="showShare" class="bl-share">{{ row.share }}%</span>
    </div>
    <div v-if="!rows.length" class="bl-empty">暂无数据</div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

/**
 * 横向条形分布图（纯 CSS）。
 * 用于"风险等级占比""处置状态"这类类目数量对比 —— 比柱状图更适合
 * 类目名较长的情况（名字放左侧，不用旋转标签）。
 */
const props = defineProps({
  // [{ key, label, value, color }]
  items: { type: Array, default: () => [] },
  showShare: { type: Boolean, default: true },
  // 排序：'none' 保持传入顺序（如等级由高到低），'desc' 按数量降序
  sort: { type: String, default: 'none' },
});

const total = computed(() =>
  props.items.reduce((a, i) => a + (Number(i.value) || 0), 0));

const rows = computed(() => {
  let list = props.items.map((i) => ({ ...i, value: Number(i.value) || 0 }));
  if (props.sort === 'desc') list = [...list].sort((a, b) => b.value - a.value);
  const max = Math.max(1, ...list.map((i) => i.value));
  return list.map((i) => ({
    ...i,
    pct: (i.value / max) * 100,
    share: total.value ? Math.round(i.value / total.value * 100) : 0,
  }));
});
</script>

<style scoped>
.barlist { display: flex; flex-direction: column; gap: 9px; }
.bl-row { display: grid; grid-template-columns: 74px 1fr 40px 42px; align-items: center; gap: 8px; }
.bl-name {
  font-size: 12px; color: var(--text-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.bl-track { height: 9px; border-radius: 5px; background: var(--tint-2); overflow: hidden; }
.bl-fill { height: 100%; border-radius: 5px; transition: width .35s ease; min-width: 2px; }
.bl-value {
  font-size: 13px; font-weight: 700; color: var(--text-primary);
  text-align: right; font-variant-numeric: tabular-nums;
}
.bl-share { font-size: 11px; color: var(--text-muted); text-align: right; }
.bl-empty { font-size: 12px; color: var(--text-muted); padding: 12px 0; text-align: center; }
</style>
