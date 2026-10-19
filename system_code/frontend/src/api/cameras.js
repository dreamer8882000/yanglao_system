import request from './request.js';

export const getCameraList = (params) => request.get('/cameras/', { params });
export const createCamera = (data) => request.post('/cameras/', data);
export const updateCamera = (id, data) => request.put(`/cameras/${id}`, data);
export const deleteCamera = (id) => request.delete(`/cameras/${id}`);
export const heartbeatCamera = (id) => request.post(`/cameras/${id}/heartbeat`);
