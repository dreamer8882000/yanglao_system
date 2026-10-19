import request from './request.js';

export const listReports = () => request.get('/eval/reports');
export const getReport = (name) => request.get(`/eval/report/${encodeURIComponent(name)}`);
export const runEvaluation = (data = {}) => request.post('/eval/run', data);
export const evalStatus = (id) => request.get(`/eval/status/${encodeURIComponent(id)}`);
