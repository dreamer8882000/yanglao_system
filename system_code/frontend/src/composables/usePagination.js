/**
 * 分页组合式函数
 */

import { ref, computed, reactive } from 'vue';

export function usePagination(options = {}) {
  const {
    defaultPageSize = 20,
    pageSizes = [10, 20, 50, 100],
    onPageChange = null
  } = options;

  const pagination = reactive({
    page: 1,
    pageSize: defaultPageSize,
    total: 0,
    totalPages: 0
  });

  const updatePagination = (data) => {
    if (data?.pagination) {
      Object.assign(pagination, data.pagination);
    }
  };

  const handlePageChange = (page) => {
    pagination.page = page;
    onPageChange?.(pagination);
  };

  const handleSizeChange = (size) => {
    pagination.pageSize = size;
    pagination.page = 1;
    onPageChange?.(pagination);
  };

  const reset = () => {
    pagination.page = 1;
    pagination.pageSize = defaultPageSize;
    pagination.total = 0;
    pagination.totalPages = 0;
  };

  return {
    pagination,
    pageSizes,
    updatePagination,
    handlePageChange,
    handleSizeChange,
    reset
  };
}
