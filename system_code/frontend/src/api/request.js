import axios from 'axios';

const basePath = import.meta.env.VITE_BASE_PATH || '/';

const urlToken = new URLSearchParams(window.location.search).get('token');
if (urlToken) {
  sessionStorage.setItem('api_token', urlToken);
  // Do not leave bearer credentials in the address bar/history/referrer.
  const cleanUrl = new URL(window.location.href);
  cleanUrl.searchParams.delete('token');
  window.history.replaceState({}, '', cleanUrl.pathname + cleanUrl.search + cleanUrl.hash);
}

const request = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || '') + '/api',
  timeout: 120000,
  headers: { 'original-url': window.location.origin + window.location.pathname }
});

/**
 * 去掉查询参数里的空值。
 *
 * 为什么必须在这一层做：所有列表页的筛选条件初始值都是空字符串，直接发出去会变成
 * `?status=&keyword=&startDate=`。而后端的 `status: int | None` 拿到空字符串会
 * **校验失败返回 422**（空字符串不是合法的 int），请求整体失败。
 *
 * 更糟的是失败是**静默**的：各列表页都写成 `try { ... } catch {}`，422 被吞掉，
 * 列表保持上一次的数据不变。表现出来就是「点重置没反应」「筛选没效果」，
 * 而控制台里连一条报错都没有 —— 极难定位。
 *
 * 统一在这里剔除空值，比让十几处调用点各自记得不传空串可靠得多。
 */
function stripEmptyParams(params) {
  if (!params || typeof params !== 'object') return params;
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)
  );
}

request.interceptors.request.use(config => {
  const token = sessionStorage.getItem('api_token');
  if (token) config.headers['Authorization'] = `Bearer ${token}`;
  if (config.params) config.params = stripEmptyParams(config.params);
  return config;
});

request.interceptors.response.use(
  res => res,
  err => {
    const status = err.response?.status;
    if (status === 401 && window.location.pathname !== basePath.replace(/\/$/, '') + '/login') {
      sessionStorage.removeItem('api_token');
      sessionStorage.removeItem('current_user');
      window.location.href = basePath.replace(/\/$/, '') + '/login';
    } else if (status === 403) {
      console.warn('权限不足', err.config?.url);
    } else if (status === 422) {
      // 请求参数校验失败：通常是筛选条件格式不对（例如日期格式、数值字段传了空串）。
      // 必须报出来 —— 各列表页的 catch 会把它吞掉，不在这里留痕就完全查不到。
      console.error('请求参数校验失败', err.config?.url, err.response?.data?.detail);
    } else if (status >= 500) {
      console.error('服务器错误', status, err.config?.url, err.response?.data?.message);
    } else if (status === undefined) {
      // 网络错误 / 超时 / 请求被中断：**没有 response**，上面四个分支一个都不命中，
      // 原来这里一行日志都不留。于是"后端挂了"和"这条数据本来就是空的"在控制台
      // 里长得一模一样 —— 这是排查时最容易走弯路的一类问题。
      const kind = err.code === 'ECONNABORTED' ? '请求超时'
        : err.code === 'ERR_CANCELED' ? '请求已取消'
          : '网络不可达';
      console.error(`${kind}: ${err.config?.method?.toUpperCase() || ''} ${err.config?.url || ''}`,
                    err.message);
    }
    // 统一挂一个人话错误文案，供页面直接展示；页面不必再去猜 err.response 的层级。
    err.friendlyMessage = err.response?.data?.detail
      || err.response?.data?.message
      || (status === 403 ? '权限不足'
        : status === undefined ? '网络异常，请检查服务是否在运行'
          : `请求失败（${status}）`);
    return Promise.reject(err);
  }
);

export default request;
