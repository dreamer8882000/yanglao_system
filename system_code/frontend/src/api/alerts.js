import request from './request.js';

export const getDashboard = () => request.get('/alerts/dashboard');
export const getRecentAlerts = (limit = 10) => request.get('/alerts/recent', { params: { limit } });
export const getAlertList = (params) => request.get('/alerts/', { params });
export const confirmAlert = (id, notes) => request.post(`/alerts/${id}/confirm`, { notes });
// 多人同房时系统不给答案（identityMethod='ambiguous'），由护士从候选床位里指定当事人。
export const confirmAlertIdentity = (id, elderId) => request.post(`/alerts/${id}/identity`, { elderId });
export const markAlertFalseAlarm = (id, notes) => request.post(`/alerts/${id}/false-alarm`, { notes });
export const getFeedbackStats = (days = 30) => request.get('/alerts/feedback-stats', { params: { days } });
export const batchConfirmAlerts = (ids, notes) => request.post('/alerts/batch-confirm', { ids, notes });
export const getStatistics = (params) => request.get('/alerts/statistics', { params });
export const exportAlerts = (params) => request.get('/alerts/export', { params, responseType: 'blob' });
