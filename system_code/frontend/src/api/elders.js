import request from './request.js';

export const getElderList = (params) => request.get('/elders/', { params });
export const getElderDetail = (id) => request.get(`/elders/${id}`);
export const getElderHealthTrend = (id, days = 7) => request.get(`/elders/${id}/health-trend`, { params: { days } });
export const createElder = (data) => request.post('/elders/', data);
export const updateElder = (id, data) => request.put(`/elders/${id}`, data);
export const archiveElder = (id) => request.post(`/elders/${id}/archive`);
export const uploadElderAvatar = (id, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return request.post(`/elders/${id}/avatar`, fd);
};
