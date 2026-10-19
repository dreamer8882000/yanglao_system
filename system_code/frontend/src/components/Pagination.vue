<template>
  <div v-if="total > 0" class="pager">
    <!-- 三栏：左留空、中间页码、右侧统计。
         页码与"跳至"居中，统计（共 N 条 / 每页 M 条）钉在最右，
         两侧各有一份等宽空白，所以中间那组是真的在视觉中线上。 -->
    <div class="pager-side" aria-hidden="true"></div>

    <div class="pager-center">
      <button class="pg-btn" :disabled="page <= 1" @click="go(1)" title="首页">«</button>
      <button class="pg-btn" :disabled="page <= 1" @click="go(page - 1)" title="上一页">‹</button>

      <button
        v-for="(p, i) in pageItems"
        :key="i"
        class="pg-btn"
        :class="{ active: p === page, dots: p === '...' }"
        :disabled="p === '...'"
        @click="p !== '...' && go(p)"
      >{{ p }}</button>

      <button class="pg-btn" :disabled="page >= totalPages" @click="go(page + 1)" title="下一页">›</button>
      <button class="pg-btn" :disabled="page >= totalPages" @click="go(totalPages)" title="末页">»</button>

      <span class="pager-jump">
        跳至
        <input
          type="number" min="1" :max="totalPages"
          :value="page" @keyup.enter="go($event.target.value)"
          aria-label="跳转到指定页码"
        />
        页
      </span>
    </div>

    <div class="pager-side pager-stats">
      <span class="pager-total">共 <b>{{ total }}</b> 条</span>
      <label class="pager-size">
        每页
        <select :value="pageSize" @change="onSizeChange($event.target.value)" aria-label="每页条数">
          <option v-for="s in sizeOptions" :key="s" :value="s">{{ s }}</option>
        </select>
        条
      </label>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

/**
 * 共享分页组件。
 *
 * 为什么做成组件而不是每页各写一份：此前「老人档案 / 告警 / 审计」三页各写了
 * 一套只有"上一页/下一页"的分页，且都**没有每页条数选择**；其余列表页则完全
 * 没有分页。各写各的必然继续走样，因此收敛到这一个组件。
 *
 * 两种用法都支持：
 *   - 服务端分页：父组件把 page / pageSize / total 传进来，监听 change 重新取数；
 *   - 客户端分页：total 传数组长度，父组件用 slice 展示。
 *
 * ⚠ 用法前提：**一个列表只能渲染一个分页条**，而且必须放在列表容器**外面**。
 * 把 <Pagination> 写进 v-for 里会每个条目渲染一条分页
 * （视频检测页曾经就是这样：12 帧历史渲染出 12 条分页），
 * scripts/eval/test_pager_and_panel.py 会专门把这类写法测出来。
 *
 * 另外：**实时流不要分页**。持续追加的帧/记录用分页没有意义
 * （每来一帧页码就失效），应当只展示最新 N 条。
 */
const props = defineProps({
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  total: { type: Number, default: 0 },
  // 可选每页条数，默认 10/20/30/50/100
  sizes: { type: Array, default: () => [10, 20, 30, 50, 100] },
});
const emit = defineEmits(['update:page', 'update:pageSize', 'change']);

const sizeOptions = computed(() => {
  const list = [...props.sizes];
  // 父组件若用了非标准值（如老人档案的 12），也要能显示出来
  if (!list.includes(props.pageSize)) list.push(props.pageSize);
  return list.sort((a, b) => a - b);
});

const totalPages = computed(() =>
  Math.max(1, Math.ceil((props.total || 0) / Math.max(1, props.pageSize))));

// 页码序列：首尾常驻，当前页附近展开，其余折叠为省略号
const pageItems = computed(() => {
  const last = totalPages.value;
  const cur = Math.min(Math.max(1, props.page), last);
  if (last <= 7) return Array.from({ length: last }, (_, i) => i + 1);

  const items = [1];
  const start = Math.max(2, cur - 1);
  const end = Math.min(last - 1, cur + 1);
  if (start > 2) items.push('...');
  for (let p = start; p <= end; p++) items.push(p);
  if (end < last - 1) items.push('...');
  items.push(last);
  return items;
});

function go(p) {
  const target = Math.min(Math.max(1, Number(p) || 1), totalPages.value);
  if (target === props.page) return;
  emit('update:page', target);
  emit('change', { page: target, pageSize: props.pageSize });
}

function onSizeChange(value) {
  const size = Number(value) || props.pageSize;
  emit('update:pageSize', size);
  // 换每页条数后回到第 1 页：否则当前页可能已越界，出现空白列表
  emit('update:page', 1);
  emit('change', { page: 1, pageSize: size });
}
</script>

<style scoped>
/* 布局契约：中间页码居中、右侧统计靠右、两侧内边距不让内容贴到边框。
   三栏等宽（1fr auto 1fr）是关键 —— 用 justify-content: space-between
   做不到"页码真正居中"：右侧统计比左侧宽时，中间那组会被推偏。 */
.pager {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-subtle);
  font-size: 13px;
  color: var(--text-tertiary);
  min-width: 0;
}
.pager-center {
  display: flex; align-items: center; justify-content: center;
  gap: 6px; flex-wrap: wrap; min-width: 0;
}
.pager-side { min-width: 0; }
.pager-stats {
  display: flex; align-items: center; justify-content: flex-end;
  gap: var(--space-3); flex-wrap: wrap;
}
.pager-total { white-space: nowrap; }
.pager-total b { color: var(--text-primary); }
.pager-size { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.pager-size select {
  padding: 3px 6px; border-radius: 6px;
  border: 1px solid var(--border-default); background: var(--bg-surface);
  color: var(--text-secondary); font-size: 13px; cursor: pointer;
}
.pg-btn {
  min-width: 30px; height: 30px; padding: 0 8px;
  border-radius: 7px; border: 1px solid var(--border-default);
  background: var(--bg-surface); color: var(--text-secondary);
  font-size: 13px; cursor: pointer; transition: all .15s;
}
.pg-btn:hover:not(:disabled):not(.active) { background: var(--bg-hover); color: var(--primary); }
.pg-btn.active {
  background: var(--primary-soft, color-mix(in srgb, var(--primary) 12%, transparent));
  border-color: var(--primary); color: var(--primary); font-weight: 700;
}
.pg-btn:disabled { opacity: .4; cursor: not-allowed; }
.pg-btn.dots { border: none; background: transparent; cursor: default; }
.pager-jump { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.pager-jump input {
  width: 48px; padding: 3px 6px; text-align: center;
  border-radius: 6px; border: 1px solid var(--border-default);
  background: var(--bg-surface); color: var(--text-secondary); font-size: 13px;
}

/* 窄屏：三栏改成一列，全部居中；否则 1fr auto 1fr 会把页码压成一列字 */
@media (max-width: 860px) {
  .pager { grid-template-columns: 1fr; justify-items: center; }
  .pager-stats { justify-content: center; }
  .pager-side[aria-hidden='true'] { display: none; }
}
</style>
