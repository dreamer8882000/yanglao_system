import request from './request.js';

// ==================== YOLO 检测服务 ====================

/**
 * YOLO 目标检测
 * @param {Object} data - { imageUrl, elderId }
 * @returns {Promise}
 */
export const detectYOLO = (data) => request.post('/python/yolo/detect', data);

/**
 * 批量图像检测
 * @param {Array} imageUrls - 图像URL列表
 * @returns {Promise}
 */
export const batchDetectYOLO = (imageUrls) => 
  request.post('/python/yolo/batch', { imageUrls });

/**
 * 切换 YOLO 模型
 * @param {String} modelName - yolov5/yolov8/yolov10
 * @returns {Promise}
 */
export const switchYOLOModel = (modelName) => 
  request.post('/python/yolo/switch-model', { modelName });

// ==================== 统计分析服务 ====================

/**
 * 趋势分析
 * @param {Array} data - [{ date, value }, ...]
 * @returns {Promise} { trend, slope, confidence }
 */
export const analyzeTrend = (data) => 
  request.post('/python/statistics/trend', { data });

/**
 * 异常检测
 * @param {Array} data - 数据列表
 * @param {Number} threshold - Z-score 阈值
 * @returns {Promise} { anomalies: [] }
 */
export const detectAnomaly = (data, threshold = 2.0) => 
  request.post('/python/statistics/anomaly', { data, threshold });

/**
 * 预测未来趋势
 * @param {Array} data - 历史数据
 * @param {Number} periods - 预测周期数
 * @returns {Promise} { predictions: [] }
 */
export const predictTrend = (data, periods = 7) => 
  request.post('/python/statistics/predict', { data, periods });

/**
 * 老人风险评分
 * @param {Number} elderId - 老人ID
 * @returns {Promise} { score, level, factors }
 */
export const calculateRiskScore = (elderId) => 
  request.post('/python/statistics/risk-score', { elderId });

// ==================== 服务健康检查 ====================

/**
 * Python 服务健康检查
 * @returns {Promise}
 */
export const checkPythonHealth = () => request.get('/python/health');
// 近 N 天告警趋势（GET，返回 items: [{date, riskLevel, count}]），用于总览页柱状图
export const getAlertTrends = (days = 7) =>
  request.get('/python/statistics/trends', { params: { days } });
