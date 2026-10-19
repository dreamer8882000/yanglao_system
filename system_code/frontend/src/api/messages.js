import request from './request.js';

export const getMessages = (params) => request.get('/messages/', { params });
export const getUnreadCount = () => request.get('/messages/unread');
export const markRead = (id) => request.put(`/messages/${id}/read`);
export const markAllRead = () => request.post('/messages/read-all');
