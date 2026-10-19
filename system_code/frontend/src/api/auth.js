import request from './request.js';

export const getCaptcha = () => request.get('/public/auth/captcha');
export const login = (data) => request.post('/public/auth/login', data);
export const logout = () => request.post('/public/auth/logout');
export const changePassword = (data) => request.post('/auth/change-password', data);
export const resetPassword = (data) => request.post('/auth/reset-password', data);
export const initPassword = (data) => request.post('/public/auth/init-password', data);
export const register = (data) => request.post('/public/auth/register', data);
