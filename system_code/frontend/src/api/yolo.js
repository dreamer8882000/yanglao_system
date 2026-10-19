import request from './request';

/**
 * YOLO 模型管理 API
 */

// 获取可用模型列表
export const getAvailableModels = () => {
  return request.get('/yolo/models');
};

// 获取指定模型信息
export const getModelInfo = (modelId) => {
  return request.get(`/yolo/models/${modelId}`);
};

// 获取摄像头 YOLO 配置
export const getCameraYoloConfig = (cameraId) => {
  return request.get(`/yolo/cameras/${cameraId}/config`);
};

// 更新摄像头 YOLO 配置
export const updateCameraYoloConfig = (cameraId, config) => {
  return request.put(`/yolo/cameras/${cameraId}/config`, config);
};

// 批量配置摄像头 YOLO
export const batchUpdateYoloConfigs = (configs) => {
  return request.post('/yolo/cameras/batch-config', { configs });
};

// 测试摄像头推理：可传 imageUrl/imageBase64；不传时后端按摄像头 streamUrl 抽帧
export const testCameraInference = (cameraId, payload = {}) => {
  const body = typeof payload === 'string' ? { imageUrl: payload } : payload;
  return request.post(`/yolo/cameras/${cameraId}/test`, body || {});
};

// 获取模型使用统计
export const getModelStats = () => {
  return request.get('/yolo/stats');
};
