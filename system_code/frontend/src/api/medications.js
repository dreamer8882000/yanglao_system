import request from './request';

// ========== 用药清单 ==========
// 创建用药清单
export const createMedication = (data) => request.post('/medications/', data);

// 获取用药清单列表
export const getMedicationList = (params) => request.get('/medications/', { params });

// 更新用药清单
export const updateMedication = (id, data) => request.put(`/medications/${id}`, data);

// 删除用药清单
export const deleteMedication = (id) => request.delete(`/medications/${id}`);

// 获取老人用药清单
export const getElderMedications = (elderId) => request.get(`/medications/elder/${elderId}`);

// ========== 用药记录 ==========
// 获取待服药列表（当前时间段）
export const getPendingMedications = () => request.get('/medications/records/pending');

// 确认服药
export const confirmMedication = (recordId, data) => request.post(`/medications/records/${recordId}/confirm`, data);

// 获取用药记录
export const getMedicationRecords = (params) => request.get('/medications/records', { params });
