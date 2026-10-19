import { computed, ref, watch } from 'vue';

/**
 * 客户端分页。
 *
 * 用于数据已经一次性全部拿到手的列表（摄像头列表、检测历史等）——
 * 这类列表没有服务端分页接口，但同样需要"翻页 + 选每页条数"。
 *
 * 用法：
 *   const { page, pageSize, total, paged } = usePaging(history);
 *   <div v-for="x in paged"> ... </div>
 *   <Pagination v-model:page="page" v-model:pageSize="pageSize" :total="total" />
 */
export function usePaging(source, initialSize = 10) {
  const page = ref(1);
  const pageSize = ref(initialSize);

  const total = computed(() => (Array.isArray(source.value) ? source.value.length : 0));
  const totalPages = computed(() =>
    Math.max(1, Math.ceil(total.value / Math.max(1, pageSize.value))));

  const paged = computed(() => {
    const list = Array.isArray(source.value) ? source.value : [];
    const size = Math.max(1, pageSize.value);
    const start = (Math.max(1, page.value) - 1) * size;
    return list.slice(start, start + size);
  });

  // 数据变少时（筛选、删除、换每页条数）当前页可能越界，会出现空白列表，
  // 这里自动收回到最后一页。
  watch([totalPages, pageSize], () => {
    if (page.value > totalPages.value) page.value = totalPages.value;
    if (page.value < 1) page.value = 1;
  });

  return { page, pageSize, total, totalPages, paged };
}
