import request from './request.js';

export const getAuditList = (params) => request.get('/audit/', { params });
