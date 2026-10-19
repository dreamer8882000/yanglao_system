import request from './request.js';

export const getCurrentUser = () => request.get('/user');
export const getSettings = () => request.get('/settings/');
export const saveSettings = (data) => request.put('/settings/', data);
// 支持分页参数：/settings/users 是分页接口，返回 { data, total, page, pageSize }
export const getUserList = (params) => request.get('/settings/users', { params });
export const updateUserRole = (id, role) => request.put(`/settings/users/${id}/role`, { role });
export const createUser = (data) => request.post('/settings/users', data);
export const deleteUser = (id) => request.delete(`/settings/users/${id}`);
export const setGlobalYoloModel = (models) => request.put('/settings/yolo-model', { models });

// ── 告警通知渠道 ────────────────────────────────────────────────────────
export const getNotifyTypes = () => request.get('/notifications/types');
export const getNotifyChannels = () => request.get('/notifications/channels');
export const createNotifyChannel = (data) => request.post('/notifications/channels', data);
export const updateNotifyChannel = (id, data) => request.put(`/notifications/channels/${id}`, data);
export const deleteNotifyChannel = (id) => request.delete(`/notifications/channels/${id}`);
// 真发一条测试消息；返回的是真实结果，失败会带出原因
export const testNotifyChannel = (id) => request.post(`/notifications/channels/${id}/test`);
export const getNotifyLogs = (params) => request.get('/notifications/logs', { params });
