import request from './request';

// ========== 生命体征记录 ==========
// 创建生命体征记录
export const createVitalSign = (data) => request.post('/vital-signs/', data);

// 获取生命体征列表
export const getVitalSignList = (params) => request.get('/vital-signs/', { params });

// 获取趋势数据
export const getVitalTrend = (params) => request.get('/vital-signs/trend', { params });

// 获取异常预警
export const getVitalAlerts = (params) => request.get('/vital-signs/alerts', { params });

// ========== 预警规则 ==========
// 获取老人预警规则
export const getElderRules = (elderId) => request.get(`/vital-signs/rules/${elderId}`);

// 更新预警规则
export const updateVitalRule = (elderId, data) => request.put(`/vital-signs/rules/${elderId}`, data);
