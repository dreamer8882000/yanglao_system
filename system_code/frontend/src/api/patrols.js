import request from './request';

// 创建巡查记录
export const createPatrol = (data) => request.post('/patrols/', data);

// 获取巡查记录列表
export const getPatrolList = (params) => request.get('/patrols/', { params });

// 获取单个巡查记录
export const getPatrol = (id) => request.get(`/patrols/${id}`);

// 获取待巡查房间
export const getPendingRooms = () => request.get('/patrols/pending-rooms');

// 获取巡查统计
export const getPatrolStats = (params) => request.get('/patrols/stats', { params });
