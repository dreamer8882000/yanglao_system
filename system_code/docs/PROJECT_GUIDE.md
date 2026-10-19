# 智慧养老监护系统 - 完整项目指南

## 📖 目录

- [项目概述](#项目概述)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [核心模块详解](#核心模块详解)
- [数据库设计](#数据库设计)
- [API 接口](#api-接口)
- [安装部署](#安装部署)
- [开发指南](#开发指南)
- [运维管理](#运维管理)
- [常见问题](#常见问题)

---

## 📝 项目概述

### 系统简介

**智慧养老监护系统**是一套基于 AI 视觉技术的智能养老院监护解决方案，通过整合摄像头监控、YOLO 目标检测、实时告警、数据统计等功能，为养老机构提供 7×24 小时智能监护服务。

### 核心功能

| 功能模块 | 功能描述 | 技术实现 |
|---------|---------|---------|
| 🏥 **老人档案** | 老人基本信息、健康档案、紧急联系人管理 | CRUD + 搜索过滤 |
| 📹 **实时监控** | 多路视频流监控、摄像头状态管理 | WebSocket + SSE |
| ⚠️ **智能告警** | AI 行为检测、风险分级、实时推送 | YOLO + 规则引擎 |
| 📊 **数据统计** | 告警趋势、处理效率、房间分布分析 | ECharts 可视化 |
| 📅 **值班排班** | 值班人员排班、审批流程 | 日历组件 + 状态机 |
| 🤖 **Agent AI** | 智能问答、数据查询、辅助决策 | LLM 集成 |
| ⚙️ **系统设置** | AI 参数、通知配置、摄像头管理 | 动态配置 |
| 📋 **审计日志** | 操作记录、敏感操作追溯 | AOP 拦截 |
| 📈 **性能监控** | 系统健康检查、资源使用率、告警监控 | Cron 定时任务 |
| 💾 **数据备份** | 自动/手动备份、备份管理 | MySQL dump |
| 💬 **实时通信** | WebSocket 双向通信、SSE 事件推送 | ws + EventSource |

### 应用场景

- **养老院**：24 小时智能监护、跌倒检测、异常行为告警
- **医疗机构**：病房监控、患者行为分析
- **康养中心**：健康管理、安全预警

---

## 🏗️ 系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                              │
│                    (Vue 3 + Vite)                            │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/WebSocket/SSE
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     Node.js 网关层                            │
│                (Express 5 + Auth 中间件)                      │
├─────────────────────────────────────────────────────────────┤
│  路由层         服务层           数据层          中间件        │
│  Routes  →   Services   →     DAO/Models  →  Middlewares   │
│  (RESTful)   (业务逻辑)      (数据访问)       (鉴权/限流)      │
└────────┬────────────┬───────────┬────────────────────────────┘
         │            │           │
         ▼            ▼           ▼
┌─────────────┐ ┌──────────┐ ┌────────────────┐
│ MySQL 8.0   │ │ Python AI│ │ 企业集成服务    │
│ (数据存储)   │ │ (可选)   │ │ (UUAP/消息)    │
└─────────────┘ └──────────┘ └────────────────┘
```

### 技术架构分层

#### 1. **前端层（Frontend）**
```
frontend/
├── views/          # 页面组件（10+ 页面）
├── components/     # 公共组件（表格、卡片、对话框等）
├── api/            # API 请求封装
├── router/         # 路由配置
├── utils/          # 工具函数
└── composables/    # 组合式函数（状态管理、业务逻辑）
```

**核心技术**：
- **Vue 3 Composition API**：响应式状态管理
- **Vue Router 4**：SPA 路由
- **Axios**：HTTP 请求拦截器
- **ECharts 5**：数据可视化
- **WebSocket/SSE**：实时通信

#### 2. **后端层（Backend）**
```
backend/
├── app.js          # 应用入口（路由注册）
├── server.js       # 基础服务器类（中间件配置）
├── routes/         # 路由层（14 个路由模块）
├── services/       # 业务逻辑层（核心服务）
├── dao/            # 数据访问层（BaseDAO + 业务 DAO）
├── models/         # 数据模型层（ORM 映射）
├── middlewares/    # 中间件（鉴权、限流、错误处理）
├── utils/          # 工具模块（日志、缓存、性能监控）
├── config/         # 配置管理（环境变量加载）
├── db/             # 数据库连接池
└── sql/            # Flyway 数据库迁移脚本
```

**核心技术**：
- **Node.js 22+**：运行时环境
- **Express 5**：Web 框架
- **MySQL2**：数据库驱动（Promise API）
- **WebSocket (ws)**：双向通信
- **SSE (Server-Sent Events)**：单向推送
- **PM2**：进程管理（生产环境）
- **Node Cron**：定时任务调度

#### 3. **数据层（Database）**
```
MySQL 8.0.26
├── users           # 用户表（登录鉴权）
├── elders          # 老人档案表
├── cameras         # 摄像头表
├── alerts          # 告警记录表
├── schedules       # 值班排班表
├── schedules_audit_logs  # 排班审批日志
├── messages        # 系统消息表
└── settings        # 系统配置表（动态配置）
```

**数据库版本管理**：
- 使用 **Flyway** 命名规范（`V1__init.sql`, `V2__add_xxx.sql`）
- 迁移文件只增不删，确保数据完整性
- 当前最新版本：**V11**

#### 4. **内置 AI 推理层（backend-python）**
```
backend-python/app/services/
├── ai_engine.py       # 本地姿态估计、表情识别、D-S 融合适配
└── image_loader.py    # 图片输入加载与安全边界
```

**核心技术**：
- **FastAPI**：高性能 API 框架
- **YOLO**：姿态估计与表情识别
- **OpenCV**：图像处理

---

## 💻 技术栈

### 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.5.13 | 渐进式框架 |
| Vue Router | 4.5.0 | 路由管理 |
| Axios | 1.9.0+ | HTTP 客户端 |
| ECharts | 5.6.0 | 数据可视化 |
| Vite | 6.3.5 | 构建工具 |
| Day.js | 1.11.13 | 时间处理 |
| Lodash-ES | 4.17.21 | 工具函数 |

### 后端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Node.js | 22+ | 运行环境 |
| Express | 5.2.1+ | Web 框架 |
| MySQL | 8.0.26 | 关系型数据库 |
| mysql2 | 3.15.3+ | 数据库驱动 |
| ws | 8.18.0 | WebSocket |
| PM2 | 最新 | 进程管理 |
| node-cron | 3.0.3 | 定时任务 |
| archiver | 7.0.1 | 文件压缩 |

### 开发工具

| 工具 | 用途 |
|------|------|
| Docker Compose | 容器编排 |
| Git | 版本控制 |
| VSCode | IDE |
| Postman | API 测试 |

---

## 📂 项目结构

### 完整目录树

```
智慧养老监护系统/
├── backend/                    # 后端服务
│   ├── app.js                  # 应用入口（路由注册）
│   ├── server.js               # 基础服务器类（中间件配置）
│   ├── ecosystem.config.js     # PM2 配置
│   ├── package.json
│   ├── .env.development        # 开发环境配置
│   ├── .env.production         # 生产环境配置
│   ├── Dockerfile              # Docker 镜像构建
│   │
│   ├── config/                 # 配置管理
│   │   └── index.js            # 统一配置加载器
│   │
│   ├── db/                     # 数据库
│   │   └── mysql.js            # MySQL 连接池
│   │
│   ├── sql/                    # 数据库迁移脚本（Flyway）
│   │   ├── V1__init.sql        # 初始化数据库
│   │   ├── V2__add_schedules_and_audit.sql
│   │   ├── V3__ensure_schedules_audit_cameras.sql
│   │   ├── V4__add_auth_fields.sql
│   │   ├── V5__camera_source_type.sql
│   │   ├── V6__add_constraints.sql
│   │   ├── V7__add_user_auth_columns.sql
│   │   ├── V8__add_camera_yolo_model.sql
│   │   ├── V9__create_schedules_audit_logs.sql
│   │   ├── V10__create_messages_table.sql
│   │   └── V11__enhance_yolo_model_config.sql
│   │
│   ├── dao/                    # 数据访问层（DAO）
│   │   ├── baseDao.js          # 基础 DAO 类（CRUD + 驼峰转换）
│   │   ├── userDao.js          # 用户数据访问
│   │   ├── elderDao.js         # 老人数据访问
│   │   ├── alertDao.js         # 告警数据访问
│   │   ├── cameraDao.js        # 摄像头数据访问
│   │   ├── scheduleDao.js      # 排班数据访问
│   │   ├── auditDao.js         # 审计日志数据访问
│   │   ├── settingDao.js       # 系统配置数据访问
│   │   └── messageDao.js       # 消息数据访问
│   │
│   ├── models/                 # 数据模型层
│   │   ├── user.js
│   │   ├── elder.js
│   │   ├── alert.js
│   │   ├── camera.js
│   │   ├── schedule.js
│   │   ├── auditLog.js
│   │   ├── setting.js
│   │   └── message.js
│   │
│   ├── services/               # 业务逻辑层（核心）
│   │   ├── authService.js      # 认证服务（登录、Token）
│   │   ├── elderService.js     # 老人档案服务
│   │   ├── alertService.js     # 告警管理服务
│   │   ├── cameraService.js    # 摄像头管理服务
│   │   ├── cameraYoloService.js # 摄像头 YOLO 配置服务
│   │   ├── notifyService.js    # 通知服务（短信、邮件）
│   │   ├── auditService.js     # 审计日志服务
│   │   ├── integrationService.js # 企业集成服务
│   │   ├── healthCheckService.js # 健康检查服务
│   │   ├── schedulerService.js # 任务调度服务（Cron）
│   │   ├── pythonProxyService.js # Python AI 代理服务
│   │   ├── sseService.js       # SSE 推送服务
│   │   ├── websocketService.js # WebSocket 服务
│   │   └── backupService.js    # 数据备份服务
│   │
│   ├── routes/                 # 路由层（API 端点）
│   │   ├── health.js           # 健康检查
│   │   ├── auth.js             # 登录鉴权
│   │   ├── elders.js           # 老人档案 CRUD
│   │   ├── alerts.js           # 告警管理（含 AI 推送）
│   │   ├── cameras.js          # 摄像头管理
│   │   ├── schedules.js        # 值班排班
│   │   ├── settings.js         # 系统配置
│   │   ├── audit.js            # 审计日志
│   │   ├── messages.js         # 系统消息
│   │   ├── agent.js            # Agent AI 对话
│   │   ├── python-proxy.js     # Python 服务代理
│   │   ├── monitor.js          # 性能监控
│   │   ├── backup.js           # 数据备份
│   │   └── yolo.js             # YOLO 配置管理
│   │
│   ├── middlewares/            # 中间件
│   │   ├── authMiddleware.js   # JWT 鉴权中间件
│   │   ├── rateLimiter.js      # API 限流中间件
│   │   ├── errorHandler.js     # 全局错误处理
│   │   └── performanceMiddleware.js # 性能监控中间件
│   │
│   ├── utils/                  # 工具模块
│   │   ├── logger.js           # 日志服务（文件日志）
│   │   ├── envValidator.js     # 环境变量验证
│   │   ├── cache.js            # 内存缓存
│   │   ├── performanceMonitor.js # 性能监控
│   │   ├── jwt.js              # JWT 工具
│   │   ├── password.js         # 密码加密
│   │   ├── sanitize.js         # 输入清理
│   │   └── captcha.js          # 验证码生成
│   │
│   ├── docs/                   # 后端文档
│   ├── test-health-check.js    # 健康检查测试脚本
│   └── verify-fix.js           # 修复验证脚本
│
├── frontend/                   # 前端应用
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js          # Vite 配置
│   ├── .env.development        # 开发环境配置
│   ├── Dockerfile              # Docker 镜像构建
│   │
│   └── src/
│       ├── main.js             # 应用入口
│       ├── App.vue             # 根组件
│       │
│       ├── router/             # 路由配置
│       │   └── index.js
│       │
│       ├── views/              # 页面组件（10+ 页面）
│       │   ├── Layout.vue      # 主布局（侧边栏 + 顶栏）
│       │   ├── Login.vue       # 登录页
│       │   ├── Dashboard.vue   # 数据看板
│       │   ├── Monitor.vue     # 实时监控（视频流）
│       │   ├── Elders.vue      # 老人档案管理
│       │   ├── Alerts.vue      # 告警管理
│       │   ├── Statistics.vue  # 数据统计
│       │   ├── Schedule.vue    # 值班排班
│       │   ├── Audit.vue       # 审计日志
│       │   ├── Settings.vue    # 系统设置
│       │   ├── Agent.vue       # Agent AI 对话
│       │   └── SystemMonitor.vue # 系统监控
│       │
│       ├── components/         # 公共组件
│       │   ├── AlertCard.vue   # 告警卡片
│       │   ├── CameraCard.vue  # 摄像头卡片
│       │   ├── DataTable.vue   # 数据表格
│       │   └── ...
│       │
│       ├── api/                # API 请求封装
│       │   ├── request.js      # Axios 实例配置
│       │   ├── auth.js
│       │   ├── elders.js
│       │   ├── alerts.js
│       │   ├── cameras.js
│       │   └── ...
│       │
│       ├── composables/        # 组合式函数
│       │   ├── useWebSocket.js # WebSocket 连接管理
│       │   ├── useSSE.js       # SSE 事件监听
│       │   └── useAlertSound.js # 告警音效
│       │
│       ├── utils/              # 工具函数
│       │   ├── format.js       # 格式化工具
│       │   ├── validate.js     # 表单验证
│       │   └── storage.js      # 本地存储
│       │
│       ├── config/             # 前端配置
│       │   └── index.js
│       │
│       └── constants/          # 常量定义
│           └── index.js
│
├── backend-python/             # FastAPI 主后台与内置 AI 推理
│   ├── app/
│   │   ├── api/                # 业务接口与 AI 检测入口
│   │   └── services/           # AI 引擎、图片加载等服务
│   ├── requirements.txt        # Python 依赖
│   └── Dockerfile
│
├── docker-compose.yml          # Docker Compose 编排
├── .gitignore
│
├── 文档/                       # 项目文档
│   ├── README.md               # 项目主文档
│   ├── QUICKSTART.md           # 快速启动指南
│   ├── DEPLOYMENT.md           # 部署文档
│   ├── API.md                  # API 接口文档
│   ├── ARCHITECTURE.md         # 系统架构文档
│   ├── CHANGELOG.md            # 更新日志
│   ├── TROUBLESHOOTING.md      # 故障排除
│   ├── HEALTH_CHECK_FIX.md     # 健康检查修复文档
│   ├── PYTHON_SERVICE.md       # 本地 AI 推理迁移说明
│   ├── FIX_SUMMARY.md          # 修复总结
│   ├── CHECKLIST.md            # 检查清单
│   └── PROJECT_GUIDE.md        # 本文档
│
└── 脚本/                       # 运维脚本
    ├── init.sh                 # 项目初始化
    ├── init-db.sh              # 数据库初始化
    ├── start-all.sh            # 启动所有服务
    ├── stop-all.sh             # 停止所有服务
    ├── status.sh               # 查看服务状态
    ├── health-check-full.sh    # 完整健康检查
    ├── backup-db.sh            # 数据库备份
    ├── cleanup-logs.sh         # 清理日志
    ├── benchmark.sh            # 性能基准测试
    └── check-env.sh            # 环境检查
```

---

## 🔧 核心模块详解

### 1. 后端核心模块

#### 1.1 应用启动流程（`app.js` + `server.js`）

**app.js** - 应用入口
```javascript
async function startApplication() {
  // 1. 验证环境变量（数据库配置、JWT Secret 等）
  const isValid = envValidator.validate();
  
  // 2. 创建服务器实例
  const server = new BaseServer();
  
  // 3. 注册业务路由（14 个模块）
  server.addBusinessRoutes(new ElderRoutes().getRouter(), 'elders');
  server.addBusinessRoutes(new AlertRoutes().getRouter(), 'alerts');
  // ... 其他路由
  
  // 4. 启动服务器（数据库连接、中间件、错误处理）
  await server.start();
  
  // 5. 启动附加服务
  CameraService.startHeartbeatMonitor();  // 摄像头心跳监控
  SchedulerService.start();               // 定时任务调度
}
```

**server.js** - 基础服务器类
```javascript
class BaseServer {
  constructor() {
    this.app = express();
    this.setupMiddleware();      // 配置中间件
    this.setupAuthMiddleware();  // 配置鉴权
    this.setupUserRoutes();      // 配置用户路由
  }
  
  setupMiddleware() {
    // CORS、Cookie Parser、Body Parser
    this.app.use(cors());
    this.app.use(cookieParser());
    this.app.use(express.json());
  }
  
  setupAuthMiddleware() {
    // UUAP + JWT 双模式认证
    this.app.use(auth({
      hostname: config.get('uuap.hostname'),
      appKey: config.get('uuap.appKey'),
      secretKey: config.get('uuap.secretKey'),
      secret: config.get('jwt.secret'),
    }).unless({ path: publicPaths }));  // 公开路径白名单
    
    // 用户认证中间件（从 auth 中提取用户信息）
    this.app.use(authenticateUser.unless({ path: publicPaths }));
  }
  
  async start() {
    await this.initializeDatabase();  // 初始化数据库连接池
    this.setupErrorHandler();         // 配置错误处理中间件
    this.server = this.app.listen(this.PORT, this.HOST);
    this.setupGracefulShutdown();     // 优雅关闭
  }
}
```

**关键特性**：
- ✅ **环境变量验证**：启动前检查必需配置
- ✅ **UUAP + JWT 双模式认证**：支持企业单点登录和 JWT Token
- ✅ **统一错误处理**：404、500、业务异常统一处理
- ✅ **优雅关闭**：SIGTERM/SIGINT 信号处理，确保连接正常关闭

---

#### 1.2 数据访问层（DAO）

**BaseDAO** - 基础数据访问类
```javascript
class BaseDAO {
  constructor(tableName) {
    this.tableName = tableName;
    this.pool = mysqlPool;
  }
  
  // 🔄 自动转换：数据库下划线 ↔ JS 驼峰命名
  _keysToCamel(data) {
    // created_at → createdAt
    // elder_id → elderId
  }
  
  _keysToSnake(data) {
    // createdAt → created_at
    // elderId → elder_id
  }
  
  async query(sql, params = []) {
    const rows = await this.pool.query(sql, params);
    return this._keysToCamel(rows);  // 自动转换
  }
  
  // 通用 CRUD 方法（子类可覆盖）
  async findById(id) { /* ... */ }
  async findAll() { /* ... */ }
  async insert(data) { /* ... */ }
  async update(id, data) { /* ... */ }
  async delete(id) { /* ... */ }
}
```

**ElderDAO** - 老人档案数据访问（继承 BaseDAO）
```javascript
class ElderDAO extends BaseDAO {
  constructor() {
    super('elders');  // 指定表名
  }
  
  async findByRoomNo(roomNo) {
    const sql = 'SELECT * FROM elders WHERE room_no = ? AND status = 1';
    return await this.query(sql, [roomNo]);
  }
  
  async searchElders(keyword, page, pageSize) {
    const offset = (page - 1) * pageSize;
    const sql = `
      SELECT * FROM elders 
      WHERE status = 1 AND (name LIKE ? OR room_no LIKE ?)
      ORDER BY created_at DESC
      LIMIT ${parseInt(pageSize)} OFFSET ${offset}
    `;
    return await this.query(sql, [`%${keyword}%`, `%${keyword}%`]);
  }
}
```

**关键设计**：
- ✅ **继承复用**：所有 DAO 继承 BaseDAO，复用通用方法
- ✅ **自动转换**：数据库字段名（snake_case）与 JS 对象（camelCase）自动转换
- ✅ **SQL 注入防护**：使用参数化查询（`?` 占位符）
- ⚠️ **LIMIT/OFFSET 特殊处理**：使用模板字符串（MySQL 限制）

---

#### 1.3 业务逻辑层（Services）

**AlertService** - 告警管理服务
```javascript
class AlertService {
  // 📥 接收 AI 推送的告警（来自 Python 服务）
  static async ingestAlert(alertData) {
    // 1. 数据验证
    this.validateAlertData(alertData);
    
    // 2. 查询关联信息（老人、摄像头）
    const elder = await ElderModel.findById(alertData.elderId);
    const camera = await CameraModel.findById(alertData.cameraId);
    
    // 3. 风险分级（根据置信度）
    const riskLevel = this.calculateRiskLevel(alertData.confidence);
    
    // 4. 入库
    const alert = await AlertModel.create({
      elderId: alertData.elderId,
      cameraId: alertData.cameraId,
      riskLevel,
      confidence: alertData.confidence,
      alertTime: new Date()
    });
    
    // 5. 实时推送（WebSocket + SSE）
    websocketService.broadcast('new-alert', alert);
    sseService.broadcast('alert', alert);
    
    // 6. 通知相关人员（短信/邮件）
    if (riskLevel === 'HIGH') {
      await NotifyService.sendAlertNotification(alert, elder);
    }
    
    return alert;
  }
  
  // 📊 告警统计
  static async getStatistics(startDate, endDate) {
    const dao = new AlertDAO();
    
    // 按风险等级统计
    const byRiskLevel = await dao.countByRiskLevel(startDate, endDate);
    
    // 按处理状态统计
    const byStatus = await dao.countByStatus(startDate, endDate);
    
    // 趋势分析（按天/小时）
    const trend = await dao.getTrend(startDate, endDate, 'day');
    
    return { byRiskLevel, byStatus, trend };
  }
}
```

**HealthCheckService** - 健康检查服务
```javascript
class HealthCheckService {
  static async checkAll() {
    const components = {};
    
    // 检查数据库（核心服务）
    components.database = await this.checkDatabase();
    
    // 检查 Python AI 服务（可选服务）
    components.pythonService = await this.checkPythonService();
    
    // 检查 Agent 服务（可选服务）
    components.agentService = await this.checkAgentService();
    
    // 计算整体状态
    const status = this.calculateOverallStatus(components);
    
    return { status, components, timestamp: new Date() };
  }
  
  static calculateOverallStatus(components) {
    // 核心服务 unhealthy → 系统 degraded
    if (components.database?.status === 'unhealthy') {
      return 'degraded';
    }
    
    // 过滤可选服务的 disabled/degraded 状态
    const optionalIssues = Object.values(components).filter(c =>
      c.status === 'disabled' || c.status === 'degraded'
    );
    
    // 所有核心服务正常 → 系统 healthy（可选服务状态不影响）
    return optionalIssues.length === Object.keys(components).length
      ? 'healthy'
      : 'healthy';
  }
}
```

**SchedulerService** - 任务调度服务
```javascript
class SchedulerService {
  start() {
    // 每天凌晨 2 点执行数据库备份
    this.scheduleTask('database-backup', '0 2 * * *', async () => {
      await BackupService.createBackup();
    });
    
    // 每小时执行一次系统健康检查
    this.scheduleTask('health-check', '0 * * * *', async () => {
      const health = await HealthCheckService.checkAll();
      
      // 只在核心服务异常时记录 ERROR
      if (health.components.database?.status === 'unhealthy') {
        logger.error('核心服务异常:', health);
      } 
      // 可选服务降级记录 INFO
      else if (health.status === 'degraded') {
        logger.info('部分可选服务降级:', health);
      }
      // 系统正常时静默运行 ✅
    });
    
    // 每天凌晨 3 点清理旧日志（保留 30 天）
    this.scheduleTask('log-cleanup', '0 3 * * *', async () => {
      await this.cleanupOldLogs();
    });
  }
}
```

**关键设计**：
- ✅ **服务分级**：核心服务（数据库）异常记 ERROR，可选服务降级记 INFO
- ✅ **实时推送**：WebSocket（双向通信）+ SSE（单向推送）双通道
- ✅ **自动通知**：高风险告警自动触发短信/邮件通知
- ✅ **定时任务**：健康检查、数据备份、日志清理自动化

---

#### 1.4 实时通信

**WebSocket 服务**
```javascript
class WebSocketService {
  constructor(server) {
    this.wss = new WebSocket.Server({ server });
    this.clients = new Set();
    
    this.wss.on('connection', (ws, req) => {
      // 从 JWT Token 中提取用户信息
      const user = this.authenticateClient(req);
      
      ws.user = user;
      this.clients.add(ws);
      
      // 心跳检测
      ws.isAlive = true;
      ws.on('pong', () => { ws.isAlive = true; });
      
      ws.on('message', (data) => {
        const message = JSON.parse(data);
        this.handleMessage(ws, message);
      });
      
      ws.on('close', () => {
        this.clients.delete(ws);
      });
    });
    
    // 每 30 秒发送心跳
    setInterval(() => {
      this.wss.clients.forEach(client => {
        if (client.isAlive === false) return client.terminate();
        client.isAlive = false;
        client.ping();
      });
    }, 30000);
  }
  
  // 广播消息给所有在线客户端
  broadcast(event, data) {
    const message = JSON.stringify({ event, data });
    this.clients.forEach(client => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    });
  }
  
  // 发送消息给特定用户
  sendToUser(username, event, data) {
    const message = JSON.stringify({ event, data });
    this.clients.forEach(client => {
      if (client.user?.username === username && 
          client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    });
  }
}
```

**SSE 服务**
```javascript
class SSEService {
  constructor() {
    this.clients = new Map();
  }
  
  addClient(userId, res) {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    
    this.clients.set(userId, res);
    
    // 发送初始连接事件
    this.sendToClient(userId, 'connected', { message: 'SSE 连接成功' });
    
    // 客户端断开时清理
    res.on('close', () => {
      this.clients.delete(userId);
    });
  }
  
  sendToClient(userId, event, data) {
    const client = this.clients.get(userId);
    if (client) {
      client.write(`event: ${event}\n`);
      client.write(`data: ${JSON.stringify(data)}\n\n`);
    }
  }
  
  broadcast(event, data) {
    this.clients.forEach((client, userId) => {
      this.sendToClient(userId, event, data);
    });
  }
}
```

**前端连接示例**
```javascript
// WebSocket 连接
const useWebSocket = () => {
  const ws = ref(null);
  
  const connect = () => {
    const token = sessionStorage.getItem('api_token');
    ws.value = new WebSocket(`ws://localhost:8090/ws?token=${token}`);
    
    ws.value.onmessage = (event) => {
      const { event: eventType, data } = JSON.parse(event.data);
      
      if (eventType === 'new-alert') {
        // 处理新告警
        handleNewAlert(data);
      }
    };
  };
  
  return { ws, connect };
};

// SSE 连接
const useSSE = () => {
  const eventSource = ref(null);
  
  const connect = () => {
    eventSource.value = new EventSource('/api/sse');
    
    eventSource.value.addEventListener('alert', (event) => {
      const alert = JSON.parse(event.data);
      handleNewAlert(alert);
    });
  };
  
  return { eventSource, connect };
};
```

---

### 2. 前端核心模块

#### 2.1 路由配置（`router/index.js`）

```javascript
const routes = [
  {
    path: '/login',
    component: () => import('../views/Login.vue'),
    meta: { public: true }  // 公开路由
  },
  {
    path: '/',
    component: Layout,  // 主布局
    meta: { requiresAuth: true },  // 需要登录
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'monitor', component: () => import('../views/Monitor.vue') },
      { path: 'elders', component: () => import('../views/Elders.vue') },
      { path: 'alerts', component: () => import('../views/Alerts.vue') },
      { path: 'statistics', component: () => import('../views/Statistics.vue') },
      { path: 'schedule', component: () => import('../views/Schedule.vue') },
      { path: 'audit', component: () => import('../views/Audit.vue') },
      { path: 'settings', component: () => import('../views/Settings.vue') },
      { path: 'agent', component: () => import('../views/Agent.vue') },
      { path: 'system-monitor', component: () => import('../views/SystemMonitor.vue') }
    ]
  }
];

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = sessionStorage.getItem('api_token');
  
  if (to.meta.requiresAuth && !token) {
    next('/login');  // 未登录跳转登录页
  } else {
    next();
  }
});
```

---

#### 2.2 API 请求封装（`api/request.js`）

```javascript
import axios from 'axios';

// Token 持久化处理（应用启动时执行）
const urlToken = new URLSearchParams(window.location.search).get('token');
if (urlToken) {
  sessionStorage.setItem('api_token', urlToken);
}

// 创建 Axios 实例
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL + '/api',
  timeout: 120000,  // 2 分钟超时
  headers: {
    'Content-Type': 'application/json',
    'original-url': window.location.href
  }
});

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = sessionStorage.getItem('api_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    // 401 未授权 → 跳转登录
    if (error.response?.status === 401) {
      const redirectUrl = error.response.data?.redirectUrl || '';
      if (redirectUrl) {
        window.location.href = redirectUrl;
      } else {
        window.location.href = '/login';
      }
    }
    
    // 403 禁止访问
    if (error.response?.status === 403) {
      showToast('无权限访问', 'error');
    }
    
    // 500 服务器错误
    if (error.response?.status === 500) {
      showToast('服务器错误，请稍后重试', 'error');
    }
    
    return Promise.reject(error);
  }
);

export default request;
```

---

#### 2.3 核心页面组件

**Dashboard.vue** - 数据看板
```vue
<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <div class="stats-grid">
      <StatCard title="在档老人" :value="stats.totalElders" icon="👴" />
      <StatCard title="今日告警" :value="stats.todayAlerts" icon="⚠️" />
      <StatCard title="待处理" :value="stats.pendingAlerts" icon="⏰" />
      <StatCard title="在线摄像头" :value="stats.onlineCameras" icon="📹" />
    </div>
    
    <!-- 告警趋势图 -->
    <EChartComponent :option="alertTrendOption" height="400px" />
    
    <!-- 最新告警列表 -->
    <RecentAlertsList :alerts="recentAlerts" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { getStatistics } from '@/api/statistics';

const stats = ref({});
const recentAlerts = ref([]);

onMounted(async () => {
  stats.value = await getStatistics();
  // 建立 SSE 连接监听实时告警
  connectSSE();
});
</script>
```

**Monitor.vue** - 实时监控
```vue
<template>
  <div class="monitor">
    <!-- 摄像头网格 -->
    <div class="camera-grid">
      <CameraCard
        v-for="camera in cameras"
        :key="camera.id"
        :camera="camera"
        @alert="handleAlert"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useWebSocket } from '@/composables/useWebSocket';
import { getCameras } from '@/api/cameras';

const cameras = ref([]);
const { ws, connect, disconnect } = useWebSocket();

onMounted(async () => {
  cameras.value = await getCameras();
  
  // 建立 WebSocket 连接
  connect();
  
  // 监听告警事件
  ws.value.on('new-alert', (alert) => {
    handleAlert(alert);
    playAlertSound();  // 播放告警音效
  });
});

onUnmounted(() => {
  disconnect();
});

const handleAlert = (alert) => {
  // 高亮告警摄像头
  const camera = cameras.value.find(c => c.id === alert.cameraId);
  if (camera) {
    camera.hasAlert = true;
  }
};
</script>
```

**Alerts.vue** - 告警管理
```vue
<template>
  <div class="alerts">
    <!-- 筛选器 -->
    <AlertFilter
      v-model:riskLevel="filter.riskLevel"
      v-model:status="filter.status"
      v-model:dateRange="filter.dateRange"
      @search="loadAlerts"
    />
    
    <!-- 告警列表 -->
    <DataTable
      :data="alerts"
      :columns="columns"
      :pagination="pagination"
      @page-change="handlePageChange"
    >
      <template #actions="{ row }">
        <button @click="handleAlert(row)">处理</button>
        <button @click="viewDetails(row)">详情</button>
      </template>
    </DataTable>
    
    <!-- 处理对话框 -->
    <HandleAlertDialog
      v-model="showDialog"
      :alert="currentAlert"
      @confirm="confirmHandle"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { getAlerts, handleAlert as handleAlertAPI } from '@/api/alerts';

const alerts = ref([]);
const pagination = ref({ page: 1, pageSize: 20, total: 0 });

const loadAlerts = async () => {
  const { data, total } = await getAlerts({
    ...filter.value,
    page: pagination.value.page,
    pageSize: pagination.value.pageSize
  });
  
  alerts.value = data;
  pagination.value.total = total;
};

const confirmHandle = async (handlerNotes) => {
  await handleAlertAPI(currentAlert.value.id, {
    status: 1,
    handlerNotes
  });
  
  showToast('处理成功', 'success');
  loadAlerts();
};

onMounted(() => {
  loadAlerts();
});
</script>
```

---

## 🗄️ 数据库设计

### 核心表结构

#### 1. **users** - 用户表
```sql
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(100) NOT NULL UNIQUE COMMENT '登录账号',
  name VARCHAR(100) NOT NULL COMMENT '姓名',
  email VARCHAR(200) NOT NULL DEFAULT '' COMMENT '邮箱',
  dept_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT '部门名称',
  avatar VARCHAR(500) NULL COMMENT '头像URL',
  role VARCHAR(20) NOT NULL DEFAULT 'nurse' COMMENT '角色: admin-机构管理员, nurse-护理管理员',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_username (username)
);
```

#### 2. **elders** - 老人档案表
```sql
CREATE TABLE elders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL COMMENT '姓名',
  gender TINYINT NOT NULL DEFAULT 1 COMMENT '性别: 1-男, 2-女',
  age INT NOT NULL COMMENT '年龄',
  room_no VARCHAR(20) NOT NULL COMMENT '房间号',
  admission_date DATE NOT NULL COMMENT '入院日期',
  health_notes TEXT NULL COMMENT '健康状况备注',
  contact_name VARCHAR(100) NOT NULL DEFAULT '' COMMENT '紧急联系人姓名',
  contact_phone VARCHAR(20) NOT NULL DEFAULT '' COMMENT '紧急联系人电话',
  avatar VARCHAR(500) NULL COMMENT '照片URL',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1-在档, 0-已离院',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_status (status),
  INDEX idx_room_no (room_no)
);
```

#### 3. **cameras** - 摄像头表
```sql
CREATE TABLE cameras (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL COMMENT '摄像头名称',
  room_no VARCHAR(20) NOT NULL COMMENT '绑定房间号',
  stream_url VARCHAR(500) NULL COMMENT '视频流地址',
  source_type VARCHAR(20) NOT NULL DEFAULT 'rtsp' COMMENT '视频源类型: rtsp/http/file',
  yolo_model VARCHAR(50) NULL COMMENT 'YOLO模型配置',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1-正常, 0-禁用',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_room_no (room_no),
  INDEX idx_status (status)
);
```

#### 4. **alerts** - 告警记录表
```sql
CREATE TABLE alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  elder_id INT NULL COMMENT '关联老人ID',
  camera_id INT NULL COMMENT '触发摄像头ID',
  risk_level VARCHAR(10) NOT NULL COMMENT '风险等级: LOW/MEDIUM/HIGH',
  confidence INT NOT NULL COMMENT '置信度百分比',
  alert_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '告警时间',
  status TINYINT NOT NULL DEFAULT 0 COMMENT '处理状态: 0-待处理, 1-已处理',
  handler_id INT NULL COMMENT '处理人ID',
  handler_notes VARCHAR(200) NULL COMMENT '处置备注',
  handled_at TIMESTAMP NULL COMMENT '处理时间',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_elder_id (elder_id),
  INDEX idx_camera_id (camera_id),
  INDEX idx_risk_level (risk_level),
  INDEX idx_status (status),
  INDEX idx_alert_time (alert_time)
);
```

#### 5. **schedules** - 值班排班表
```sql
CREATE TABLE schedules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL COMMENT '值班人员ID',
  schedule_date DATE NOT NULL COMMENT '值班日期',
  shift_type VARCHAR(20) NOT NULL COMMENT '班次: morning/afternoon/night',
  status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态: pending/approved/rejected',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_user_id (user_id),
  INDEX idx_schedule_date (schedule_date),
  INDEX idx_status (status)
);
```

#### 6. **settings** - 系统配置表
```sql
CREATE TABLE settings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  setting_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
  setting_value TEXT NULL COMMENT '配置值(JSON)',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_key (setting_key)
);

-- 默认配置
INSERT INTO settings (setting_key, setting_value) VALUES
('aiConfig', '{"minConfidence":20,"lowMin":20,"lowMax":50,"mediumMin":50,"mediumMax":80,"highMin":80}'),
('notifyConfig', '{"hiEnabled":true,"smsEnabled":true,"receivers":""}');
```

### 数据库迁移版本历史

| 版本 | 文件名 | 描述 | 影响表 |
|------|--------|------|--------|
| V1 | `V1__init.sql` | 初始化数据库 | users, elders, cameras, alerts, settings |
| V2 | `V2__add_schedules_and_audit.sql` | 添加排班和审批功能 | schedules |
| V3 | `V3__ensure_schedules_audit_cameras.sql` | 确保表结构完整 | - |
| V4 | `V4__add_auth_fields.sql` | 添加鉴权字段 | users |
| V5 | `V5__camera_source_type.sql` | 添加摄像头视频源类型 | cameras |
| V6 | `V6__add_constraints.sql` | 添加数据约束 | 多表 |
| V7 | `V7__add_user_auth_columns.sql` | 添加用户认证列 | users |
| V8 | `V8__add_camera_yolo_model.sql` | 添加 YOLO 模型字段 | cameras |
| V9 | `V9__create_schedules_audit_logs.sql` | 创建排班审批日志表 | schedules_audit_logs |
| V10 | `V10__create_messages_table.sql` | 创建系统消息表 | messages |
| V11 | `V11__enhance_yolo_model_config.sql` | 增强 YOLO 模型配置 | cameras |

---

## 🌐 API 接口

### 认证接口

#### POST `/api/public/auth/login`
**功能**：用户登录

**请求体**：
```json
{
  "username": "admin",
  "password": "123456",
  "captcha": "ABCD"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": 1,
      "username": "admin",
      "name": "管理员",
      "role": "admin"
    }
  },
  "message": "登录成功"
}
```

---

### 老人档案接口

#### GET `/api/elders`
**功能**：获取老人列表（分页 + 搜索）

**查询参数**：
- `page` (number): 页码，默认 1
- `pageSize` (number): 每页数量，默认 20
- `keyword` (string): 搜索关键词（姓名/房间号）

**响应**：
```json
{
  "success": true,
  "data": {
    "list": [
      {
        "id": 1,
        "name": "张三",
        "gender": 1,
        "age": 75,
        "roomNo": "101",
        "admissionDate": "2024-01-15",
        "healthNotes": "高血压",
        "contactName": "张小明",
        "contactPhone": "13800138000",
        "avatar": "https://...",
        "status": 1,
        "createdAt": "2024-01-15T08:00:00.000Z"
      }
    ],
    "total": 100
  }
}
```

#### POST `/api/elders`
**功能**：新增老人档案

**请求体**：
```json
{
  "name": "李四",
  "gender": 2,
  "age": 80,
  "roomNo": "102",
  "admissionDate": "2024-06-20",
  "healthNotes": "糖尿病",
  "contactName": "李小红",
  "contactPhone": "13900139000"
}
```

#### PUT `/api/elders/:id`
**功能**：更新老人档案

#### DELETE `/api/elders/:id`
**功能**：删除老人档案（软删除）

---

### 告警接口

#### POST `/api/alerts/ingest`
**功能**：接收 AI 推送的告警（来自 Python 服务）

**请求头**：
- `X-Service-Secret`: Python 服务密钥

**请求体**：
```json
{
  "elderId": 1,
  "cameraId": 2,
  "riskLevel": "HIGH",
  "confidence": 85,
  "alertTime": "2024-06-22T10:30:00Z"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "id": 123,
    "elderId": 1,
    "cameraId": 2,
    "riskLevel": "HIGH",
    "confidence": 85,
    "status": 0,
    "alertTime": "2024-06-22T10:30:00.000Z"
  },
  "message": "告警已记录"
}
```

#### GET `/api/alerts`
**功能**：获取告警列表（分页 + 筛选）

**查询参数**：
- `page`, `pageSize`
- `riskLevel` (string): LOW/MEDIUM/HIGH
- `status` (number): 0-待处理, 1-已处理
- `startDate`, `endDate` (string): 日期范围

#### PUT `/api/alerts/:id/handle`
**功能**：处理告警

**请求体**：
```json
{
  "status": 1,
  "handlerNotes": "已处理，老人状况正常"
}
```

---

### 摄像头接口

#### GET `/api/cameras`
**功能**：获取摄像头列表

**响应**：
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "1号楼101房间",
      "roomNo": "101",
      "streamUrl": "rtsp://...",
      "sourceType": "rtsp",
      "yoloModel": "yolov8n",
      "status": 1,
      "isOnline": true
    }
  ]
}
```

#### POST `/api/cameras`
**功能**：添加摄像头

#### PUT `/api/cameras/:id`
**功能**：更新摄像头配置

#### POST `/api/cameras/:id/heartbeat`
**功能**：摄像头心跳上报（由 Python 服务调用）

---

### 实时通信接口

#### GET `/api/sse`
**功能**：建立 SSE 连接（单向推送）

**事件类型**：
- `connected`: 连接成功
- `alert`: 新告警推送
- `camera-status`: 摄像头状态变更
- `system-notification`: 系统通知

#### WebSocket `/ws?token=xxx`
**功能**：建立 WebSocket 连接（双向通信）

**事件类型**：
- `new-alert`: 新告警
- `alert-handled`: 告警已处理
- `camera-online`: 摄像头上线
- `camera-offline`: 摄像头离线

---

### 健康检查接口

#### GET `/api/health`
**功能**：简单健康检查（用于负载均衡器）

**响应**：
```json
{
  "status": "healthy",
  "timestamp": "2024-06-22T10:00:00.000Z"
}
```

#### GET `/api/health/detailed`
**功能**：详细健康检查（包含所有组件状态）

**响应**：
```json
{
  "status": "healthy",
  "components": {
    "database": { "status": "healthy" },
    "pythonService": { "status": "disabled" },
    "agentService": { "status": "disabled" }
  },
  "timestamp": "2024-06-22T10:00:00.000Z"
}
```

---

## 🚀 安装部署

### 环境要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Node.js | 22.x+ | 后端运行环境 |
| MySQL | 8.0.26 | 数据库 |
| PM2 | 最新 | 进程管理（生产环境） |
| Docker | 20.10+ | 容器运行时（可选） |
| Docker Compose | 2.0+ | 容器编排（可选） |

---

### 快速启动（本地开发）

#### 1. 克隆项目
```bash
git clone <repository-url>
cd elderly-care-system
```

#### 2. 安装依赖
```bash
# 后端依赖
cd backend
npm install

# 前端依赖
cd ../frontend
npm install
```

#### 3. 配置环境变量

**backend/.env.development**
```bash
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=elderly_care_sbbr0v5jespt

# JWT 配置
JWT_SECRET=your-jwt-secret-key

# 服务配置
PORT=8090
HOST=0.0.0.0
NODE_ENV=development

# 内置 AI 推理配置
AI_POSE_MODEL_PATH=../thesis_assets/pose/weights/pose_bifpn_best.pt
AI_EXPR_MODEL_PATH=../thesis_assets/expr/weights/expr_lka_best.pt
AI_DEVICE=cpu
AI_FALL_THRESHOLD=0.3
AI_EXPR_CONF=0.25
AI_ALLOW_REMOTE_IMAGE=false
```

**frontend/.env.development**
```bash
# 后端 API 地址
VITE_API_BASE_URL=http://localhost:8090

# 基础路径
VITE_BASE_PATH=/

# 允许的主机
VITE_ALLOWED_HOSTS=localhost,127.0.0.1
```

#### 4. 初始化数据库
```bash
# 方式 1：自动初始化脚本
chmod +x init-db.sh
./init-db.sh

# 方式 2：手动执行 SQL
mysql -u root -p < backend/sql/V1__init.sql
mysql -u root -p elderly_care_sbbr0v5jespt < backend/sql/V2__add_schedules_and_audit.sql
# ... 依次执行 V1 到 V11
```

#### 5. 启动服务
```bash
# 启动后端（开发模式，热重载）
cd backend
npm run dev

# 启动前端（另一个终端）
cd frontend
npm run dev
```

#### 6. 访问应用
- **前端**：http://localhost:8070
- **后端 API**：http://localhost:8090/api
- **健康检查**：http://localhost:8090/api/health

---

### Docker 部署（推荐）

#### 1. 配置环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
nano .env
```

**.env**
```bash
# 数据库密码
DB_PASSWORD=your_secure_password

# JWT 密钥
JWT_SECRET=your_secure_jwt_secret

# 内置 AI 推理
AI_DEVICE=cpu
AI_FALL_THRESHOLD=0.3
AI_EXPR_CONF=0.25

# UUAP 配置（可选）
UUAP_HOSTNAME=
UUAP_APP_KEY=
UUAP_SECRET_KEY=
UUAP_TARGET_APP_KEY=
```

#### 2. 启动所有服务
```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看服务状态
docker-compose ps
```

#### 3. 验证部署
```bash
# 健康检查
curl http://localhost:8090/api/health/detailed

# 前端访问
open http://localhost:8070
```

#### 4. 停止服务
```bash
docker-compose down

# 删除数据卷（谨慎！会删除数据库数据）
docker-compose down -v
```

---

### 生产环境部署

#### 1. 环境准备
```bash
# 安装 Node.js
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# 安装 PM2
npm install -g pm2

# 安装 MySQL
sudo apt-get install -y mysql-server
```

#### 2. 部署后端
```bash
cd backend

# 安装依赖（生产模式）
npm install --production

# 配置生产环境变量
cp .env.production.example .env.production
nano .env.production

# 使用 PM2 启动
npm start

# 查看进程状态
pm2 status

# 查看日志
pm2 logs elderly-care-backend
```

#### 3. 部署前端
```bash
cd frontend

# 构建生产版本
npm run build

# 使用 Nginx 部署
sudo cp -r dist/* /var/www/html/elderly-care/

# Nginx 配置示例
sudo nano /etc/nginx/sites-available/elderly-care
```

**Nginx 配置**
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    root /var/www/html/elderly-care;
    index index.html;
    
    # SPA 路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # 后端 API 代理
    location /api {
        proxy_pass http://localhost:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # SSE 支持
    location /api/sse {
        proxy_pass http://localhost:8090;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 24h;
    }
}
```

#### 4. 配置 PM2 开机自启
```bash
# 保存当前进程列表
pm2 save

# 生成启动脚本
pm2 startup

# 执行输出的命令（根据实际输出）
sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u username --hp /home/username
```

---

## 💡 开发指南

### 开发环境设置

#### 1. IDE 配置（VSCode）

**推荐插件**：
- Vue - Official
- ESLint
- Prettier
- MySQL
- Docker
- GitLens

**settings.json**
```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "vetur.validation.template": false
}
```

#### 2. Git 工作流

**分支策略**：
- `main`: 生产环境分支
- `dev`: 开发分支
- `feature/*`: 功能分支
- `hotfix/*`: 紧急修复分支

**提交规范**：
```bash
# 格式：<type>(<scope>): <subject>

feat(elders): 添加老人档案导出功能
fix(alerts): 修复告警推送延迟问题
docs(api): 更新 API 文档
style(ui): 优化告警卡片样式
refactor(dao): 重构 BaseDAO 类
test(services): 添加 AlertService 单元测试
chore(deps): 升级依赖包版本
```

---

### 代码规范

#### 后端规范（Node.js）

**文件命名**：
- 小驼峰：`alertService.js`, `elderDao.js`
- 类名大驼峰：`AlertService`, `ElderDAO`

**函数命名**：
```javascript
// ✅ 动词开头，语义明确
async getElderById(id)
async createAlert(data)
async updateCamera(id, data)
async deleteSchedule(id)

// ❌ 避免
async elder(id)
async alert(data)
```

**错误处理**：
```javascript
// ✅ 明确的错误信息
throw new Error('老人档案不存在');
throw new Error('告警数据验证失败: elderId 不能为空');

// ❌ 避免泛泛的错误
throw new Error('Error');
throw new Error('操作失败');
```

**日志规范**：
```javascript
// ✅ 使用 logger，包含上下文信息
logger.info('创建老人档案', { name: elder.name, roomNo: elder.roomNo });
logger.error('数据库查询失败', { sql, error: error.message });

// ❌ 避免 console.log
console.log('创建成功');
```

---

#### 前端规范（Vue 3）

**组件命名**：
- PascalCase：`AlertCard.vue`, `DataTable.vue`
- 多词命名：避免单词组件名（如 `Card.vue`）

**Composition API 风格**：
```vue
<script setup>
import { ref, computed, onMounted } from 'vue';

// 响应式状态
const alerts = ref([]);
const filter = ref({ riskLevel: '', status: '' });

// 计算属性
const filteredAlerts = computed(() => {
  return alerts.value.filter(alert => {
    if (filter.value.riskLevel && alert.riskLevel !== filter.value.riskLevel) {
      return false;
    }
    return true;
  });
});

// 方法
const loadAlerts = async () => {
  try {
    alerts.value = await getAlerts(filter.value);
  } catch (error) {
    showToast('加载失败', 'error');
  }
};

// 生命周期
onMounted(() => {
  loadAlerts();
});
</script>
```

**Props 定义**：
```vue
<script setup>
defineProps({
  alert: {
    type: Object,
    required: true
  },
  showActions: {
    type: Boolean,
    default: true
  }
});
</script>
```

**Emit 事件**：
```vue
<script setup>
const emit = defineEmits(['update', 'delete']);

const handleUpdate = () => {
  emit('update', updatedData);
};
</script>
```

---

### 新增功能开发流程

#### 示例：添加"老人健康记录"功能

**1. 数据库迁移**
```bash
# 创建迁移文件
cd backend/sql
touch V12__create_health_records_table.sql
```

```sql
-- V12__create_health_records_table.sql
CREATE TABLE IF NOT EXISTS health_records (
  id INT AUTO_INCREMENT PRIMARY KEY,
  elder_id INT NOT NULL COMMENT '老人ID',
  record_date DATE NOT NULL COMMENT '记录日期',
  blood_pressure VARCHAR(20) NULL COMMENT '血压',
  heart_rate INT NULL COMMENT '心率',
  temperature DECIMAL(3,1) NULL COMMENT '体温',
  notes TEXT NULL COMMENT '备注',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_elder_id (elder_id),
  INDEX idx_record_date (record_date),
  FOREIGN KEY (elder_id) REFERENCES elders(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='健康记录表';
```

**2. 创建 DAO**
```javascript
// backend/dao/healthRecordDao.js
const BaseDAO = require('./baseDao');

class HealthRecordDAO extends BaseDAO {
  constructor() {
    super('health_records');
  }
  
  async findByElderId(elderId, startDate, endDate) {
    const sql = `
      SELECT * FROM health_records 
      WHERE elder_id = ? AND record_date BETWEEN ? AND ?
      ORDER BY record_date DESC
    `;
    return await this.query(sql, [elderId, startDate, endDate]);
  }
}

module.exports = HealthRecordDAO;
```

**3. 创建 Model**
```javascript
// backend/models/healthRecord.js
const HealthRecordDAO = require('../dao/healthRecordDao');

class HealthRecordModel {
  static async create(data) {
    try {
      return await new HealthRecordDAO().insert(data);
    } catch (error) {
      throw error;
    }
  }
  
  static async findByElderId(elderId, startDate, endDate) {
    return await new HealthRecordDAO().findByElderId(elderId, startDate, endDate);
  }
}

module.exports = HealthRecordModel;
```

**4. 创建 Service**
```javascript
// backend/services/healthRecordService.js
const HealthRecordModel = require('../models/healthRecord');

class HealthRecordService {
  static validateData(data) {
    if (!data.elderId) throw new Error('老人ID不能为空');
    if (!data.recordDate) throw new Error('记录日期不能为空');
    
    // 验证血压格式：120/80
    if (data.bloodPressure && !/^\d{2,3}\/\d{2,3}$/.test(data.bloodPressure)) {
      throw new Error('血压格式错误，应为：120/80');
    }
    
    return true;
  }
  
  static async create(data) {
    this.validateData(data);
    return await HealthRecordModel.create(data);
  }
  
  static async getByElderId(elderId, startDate, endDate) {
    return await HealthRecordModel.findByElderId(elderId, startDate, endDate);
  }
}

module.exports = HealthRecordService;
```

**5. 创建路由**
```javascript
// backend/routes/healthRecords.js
const express = require('express');
const router = express.Router();
const HealthRecordService = require('../services/healthRecordService');

class HealthRecordRoutes {
  constructor() { this.setupRoutes(); }
  
  setupRoutes() {
    // 获取老人健康记录
    router.get('/:elderId', async (req, res) => {
      try {
        const { elderId } = req.params;
        const { startDate, endDate } = req.query;
        
        const records = await HealthRecordService.getByElderId(
          parseInt(elderId),
          startDate,
          endDate
        );
        
        res.json({ success: true, data: records });
      } catch (error) {
        res.status(500).json({ success: false, message: error.message });
      }
    });
    
    // 添加健康记录
    router.post('/', async (req, res) => {
      try {
        const record = await HealthRecordService.create(req.body);
        res.json({ success: true, data: record, message: '添加成功' });
      } catch (error) {
        res.status(400).json({ success: false, message: error.message });
      }
    });
  }
  
  getRouter() { return router; }
}

module.exports = HealthRecordRoutes;
```

**6. 注册路由**
```javascript
// backend/app.js
const HealthRecordRoutes = require('./routes/healthRecords');

// 在 startApplication() 中添加
server.addBusinessRoutes(new HealthRecordRoutes().getRouter(), 'health-records');
```

**7. 前端 API 封装**
```javascript
// frontend/src/api/healthRecords.js
import request from './request';

export const getHealthRecords = (elderId, params) => {
  return request({
    url: `/health-records/${elderId}`,
    method: 'get',
    params
  });
};

export const createHealthRecord = (data) => {
  return request({
    url: '/health-records',
    method: 'post',
    data
  });
};
```

**8. 前端页面组件**
```vue
<!-- frontend/src/views/HealthRecords.vue -->
<template>
  <div class="health-records">
    <h2>健康记录 - {{ elder.name }}</h2>
    
    <!-- 日期筛选 -->
    <DateRangePicker v-model="dateRange" @change="loadRecords" />
    
    <!-- 添加记录按钮 -->
    <button @click="showAddDialog = true">添加记录</button>
    
    <!-- 记录列表 -->
    <div class="records-list">
      <HealthRecordCard
        v-for="record in records"
        :key="record.id"
        :record="record"
      />
    </div>
    
    <!-- 添加对话框 -->
    <AddHealthRecordDialog
      v-model="showAddDialog"
      :elder-id="elderId"
      @success="loadRecords"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { getHealthRecords } from '@/api/healthRecords';

const route = useRoute();
const elderId = ref(route.params.id);
const elder = ref({});
const records = ref([]);
const dateRange = ref([]);
const showAddDialog = ref(false);

const loadRecords = async () => {
  try {
    const [startDate, endDate] = dateRange.value;
    records.value = await getHealthRecords(elderId.value, {
      startDate,
      endDate
    });
  } catch (error) {
    showToast('加载失败', 'error');
  }
};

onMounted(() => {
  loadRecords();
});
</script>
```

---

## 🛠️ 运维管理

### 日志管理

#### 日志文件位置
```
backend/logs/
├── INFO-2024-06-22.log      # 信息日志
├── WARN-2024-06-22.log      # 警告日志
├── ERROR-2024-06-22.log     # 错误日志
└── ...
```

#### 日志查看
```bash
# 实时查看错误日志
tail -f backend/logs/ERROR-$(date +%Y-%m-%d).log

# 查询特定关键词
grep "数据库连接" backend/logs/ERROR-*.log

# 统计错误次数
grep -c "Error" backend/logs/ERROR-$(date +%Y-%m-%d).log
```

#### 日志清理
```bash
# 自动清理（定时任务，每天凌晨 3 点）
# 保留 30 天日志

# 手动清理
./cleanup-logs.sh
```

---

### 数据库备份

#### 自动备份
```bash
# 定时任务：每天凌晨 2 点自动备份
# 备份文件：backend/logs/backup-YYYY-MM-DD-HH-mm-ss.sql.gz
```

#### 手动备份
```bash
# 方式 1：使用脚本
./backup-db.sh

# 方式 2：通过 API
curl -X POST http://localhost:8090/api/backup \
  -H "Authorization: Bearer YOUR_TOKEN"

# 方式 3：直接使用 mysqldump
mysqldump -u root -p elderly_care_sbbr0v5jespt > backup.sql
```

#### 恢复数据
```bash
# 解压备份文件
gunzip backup-2024-06-22-02-00-00.sql.gz

# 恢复数据库
mysql -u root -p elderly_care_sbbr0v5jespt < backup-2024-06-22-02-00-00.sql
```

---

### 性能监控

#### 系统健康检查
```bash
# 完整健康检查
./health-check-full.sh

# 输出示例：
# ✅ 数据库: healthy
# ℹ️  Python 服务: disabled（未配置）
# ℹ️  Agent 服务: disabled（未配置）
# 整体状态: healthy
```

#### 性能监控端点
```bash
# 系统性能指标
curl http://localhost:8090/api/monitor/stats

# 响应示例：
{
  "cpu": { "usage": 15.2 },
  "memory": { "used": 512, "total": 2048 },
  "requests": {
    "total": 10234,
    "avgResponseTime": 45.6,
    "errorRate": 0.02
  }
}
```

#### PM2 监控
```bash
# 查看进程状态
pm2 status

# 查看详细监控
pm2 monit

# 查看日志
pm2 logs elderly-care-backend

# 重启服务
pm2 restart elderly-care-backend

# 停止服务
pm2 stop elderly-care-backend

# 删除进程
pm2 delete elderly-care-backend
```

---

### 故障排查

#### 常见问题

**1. 数据库连接失败**
```bash
# 检查 MySQL 服务状态
sudo systemctl status mysql

# 检查连接配置
cat backend/.env.development | grep DB_

# 测试连接
mysql -h localhost -u root -p -e "SELECT 1"
```

**2. 端口被占用**
```bash
# 查找占用端口的进程
lsof -i :8090
lsof -i :8070

# 杀死进程
kill -9 <PID>
```

**3. WebSocket 连接失败**
```bash
# 检查 Nginx 配置是否支持 WebSocket
grep -A 5 "Upgrade" /etc/nginx/sites-available/elderly-care

# 测试 WebSocket 连接
wscat -c ws://localhost:8090/ws?token=YOUR_TOKEN
```

**4. 告警不推送**
```bash
# 检查 WebSocket 服务是否启动
pm2 logs elderly-care-backend | grep WebSocket

# 检查 SSE 连接
curl -N http://localhost:8090/api/sse \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**5. 本地 AI 推理不可用**
```bash
# 检查 backend-python 详细健康状态
curl http://localhost:8090/api/health/detailed \
  -H "Authorization: Bearer YOUR_TOKEN"

# 检查 AI 配置
printenv | grep '^AI_'

# 常见原因：模型权重路径不存在、缺少 torch/ultralytics/opencv 依赖、AI_DEVICE 与运行环境不匹配
```

---

### 安全加固

#### 1. 环境变量保护
```bash
# 设置文件权限
chmod 600 backend/.env.production
chmod 600 frontend/.env.production

# 禁止提交到 Git
echo ".env*" >> .gitignore
```

#### 2. API 限流
```javascript
// 已配置限流中间件
// 告警推送：100 次/分钟
// 登录接口：5 次/分钟
// 其他接口：60 次/分钟
```

#### 3. 数据库安全
```sql
-- 创建专用数据库用户（避免使用 root）
CREATE USER 'elderly_care'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON elderly_care_sbbr0v5jespt.* TO 'elderly_care'@'localhost';
FLUSH PRIVILEGES;
```

#### 4. HTTPS 配置
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # ... 其他配置
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}
```

---

## ❓ 常见问题

### Q1: 如何添加新的管理员用户？
```sql
-- 直接在数据库中添加
INSERT INTO users (username, name, email, dept_name, role) VALUES
('admin2', '管理员2', 'admin2@example.com', '信息部', 'admin');
```

### Q2: 如何修改 AI 告警阈值？
```bash
# 方式 1：通过前端系统设置页面修改

# 方式 2：直接修改数据库
UPDATE settings SET setting_value = 
'{"minConfidence":30,"lowMin":30,"lowMax":60,"mediumMin":60,"mediumMax":85,"highMin":85}'
WHERE setting_key = 'aiConfig';
```

### Q3: 如何启用本地 AI 推理？
参考 `PYTHON_SERVICE.md` 迁移说明，按以下步骤操作：
1. 确认姿态与表情模型权重文件存在
2. 配置 `AI_POSE_MODEL_PATH`、`AI_EXPR_MODEL_PATH`、`AI_DEVICE` 等环境变量
3. 重启 backend-python 后端服务，并在 `/api/health/detailed` 查看 `aiEngine` 状态

### Q4: 如何查看实时告警？
- **前端**：访问"实时监控"页面，自动建立 WebSocket 连接
- **后端**：监听 SSE 端点 `/api/sse`
- **日志**：查看 `INFO-YYYY-MM-DD.log`

### Q5: 数据库迁移出错怎么办？
```bash
# 检查当前数据库版本
mysql -u root -p elderly_care_sbbr0v5jespt -e "SHOW TABLES"

# 手动执行缺失的迁移文件
mysql -u root -p elderly_care_sbbr0v5jespt < backend/sql/VX__xxx.sql
```

### Q6: 如何扩展系统容量？
- **数据库**：主从复制、读写分离
- **后端**：负载均衡（Nginx + 多个 Node.js 实例）
- **前端**：CDN 加速
- **WebSocket**：使用 Redis 作为消息中间件

---

## 📚 相关文档

- **[README.md](README.md)** - 项目主文档
- **[QUICKSTART.md](QUICKSTART.md)** - 5 分钟快速启动
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - 详细部署指南
- **[API.md](API.md)** - 完整 API 接口文档
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 系统架构设计
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - 故障排除手册
- **[HEALTH_CHECK_FIX.md](HEALTH_CHECK_FIX.md)** - 健康检查修复说明
- **[PYTHON_SERVICE.md](PYTHON_SERVICE.md)** - 本地 AI 推理迁移说明

---

## 🎯 总结

本项目是一套**企业级智慧养老监护系统**，具备以下特点：

### ✅ 技术亮点
- **现代化技术栈**：Vue 3 + Node.js 22 + MySQL 8
- **实时通信**：WebSocket + SSE 双通道推送
- **AI 智能分析**：YOLO 目标检测 + 风险分级
- **混合架构**：Node.js 网关 + Python AI 微服务
- **企业级鉴权**：UUAP + JWT 双模式认证
- **高可用设计**：健康检查、优雅关闭、自动重启
- **完整监控**：日志、性能、健康检查全覆盖

### ✅ 功能完备
- 老人档案、摄像头管理、实时监控
- 智能告警、数据统计、值班排班
- Agent AI、审计日志、系统配置
- 性能监控、数据备份、实时通信

### ✅ 代码质量
- **分层架构**：Route → Service → DAO → Model
- **命名规范**：驼峰转换、语义明确
- **错误处理**：统一异常、友好提示
- **文档完整**：代码注释 + 独立文档

### ✅ 运维友好
- **Docker 支持**：一键部署、环境隔离
- **PM2 管理**：进程守护、日志管理
- **自动化脚本**：初始化、备份、健康检查
- **故障排查**：详细日志、监控指标

---

**项目已完成所有核心功能开发，可直接用于生产环境部署！** 🎉

有任何问题请参考相关文档或联系开发团队。