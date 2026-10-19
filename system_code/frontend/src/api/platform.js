import request from './request.js';

/**
 * 平台级只读接口（SaaS 运营方视角）。
 *
 * 与其它 api/*.js 的区别：这些接口**不按机构过滤**，只有平台级账号能调
 * （后端 require_platform）。机构管理员调用会得到 403 —— 这是刻意的：
 * 跨机构视图必须是另一种身份，不能顺带把业务数据也打开。
 *
 * 边界也在这里写清楚：平台视图不返回任何老人个人信息（姓名/房间/健康数据），
 * 只有机构级的规模数字与安全事件。
 */

export const getPlatformOverview = () => request.get('/platform/overview');

export const getPlatformTenants = () => request.get('/platform/tenants');

export const getPlatformSecurity = (hours = 24) =>
  request.get('/platform/security', { params: { hours } });

export const getPlatformAudit = (params) => request.get('/platform/audit', { params });
