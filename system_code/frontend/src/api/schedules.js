import request from './request.js';

export const getOnDuty = () => request.get('/schedules/on-duty');
export const getWeekSchedules = (weekOffset = 0) => request.get('/schedules/', { params: { weekOffset } });
export const createSchedule = (data) => request.post('/schedules/', data);
export const updateSchedule = (id, data) => request.put(`/schedules/${id}`, data);
export const deleteSchedule = (id) => request.delete(`/schedules/${id}`);

// ── 排班值守（duty 模块）────────────────────────────────────────────────
// 排班总览：一次取回本周网格 + 护理员 + 负载 + 巡查任务
export const getDutyOverview = (weekStart) =>
  request.get('/duty/overview', { params: weekStart ? { weekStart } : {} });

// 班次字典（时间定义的单一来源，前端不再硬编码 8:00/20:00）
export const getShiftDict = () => request.get('/duty/shifts');

// 拖拽调班：改日期 / 班次 / 人员，冲突时后端返回 409 并带可读原因
export const moveSchedule = (id, data) => request.put(`/schedules/${id}`, data);

// 巡查任务：生成 / 完成 / 指派
export const getPatrolTasks = (params) => request.get('/patrols/tasks', { params });
export const generatePatrolTasks = (data) => request.post('/patrols/tasks/generate', data || {});
export const completePatrolTask = (id, data) => request.post(`/patrols/tasks/${id}/complete`, data || {});
export const assignPatrolTask = (id, data) => request.post(`/patrols/tasks/${id}/assign`, data);

// 告警派单：不传 assignedTo 时后端自动选当班护理员
export const assignAlert = (id, data) => request.post(`/alerts/${id}/assign`, data || {});
