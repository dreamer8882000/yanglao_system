# Node.js 后端迁移到 Python FastAPI 说明

## 已完成的迁移内容

本项目已将原 `backend/` Node.js/Express 主后端迁移为 `backend-python/` FastAPI 主后端，并保留：

- `frontend/`：原 Vue 前端
- `database/sql/`：原 MySQL 建表与迁移脚本

原 `python-service/` 独立 AI 微服务已删除，AI 主链路迁移到 `backend-python` 进程内执行。

FastAPI 主后端保持：

- 端口：`8090`
- API 前缀：`/api`
- 登录 Token：`Authorization: Bearer <token>`
- 前端兼容：已修正 YOLO API 重复 `/api` 前缀问题，统一由请求封装追加 `/api`

## 已迁移/兼容的主要接口

- `GET /api/health`（公开）
- `GET /api/health/detailed`（需登录）
- `GET /api/public/auth/captcha`
- `POST /api/public/auth/login`
- `POST /api/public/auth/register`
- `POST /api/public/auth/init-password`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/auth/change-password`
- `POST /api/auth/reset-password`（需 admin）
- `/api/elders/*`
- `/api/cameras/*`
- `/api/alerts/*`
- `/api/settings/*`
- `/api/yolo/*`（配置写接口需 admin）
- `/api/python/*`
- `/api/agent/*`
- `/api/schedules/*`
- `/api/messages/*`
- `/api/audit/*`（写接口需 admin）
- `/api/patrols/*`（写接口需 admin）
- `/api/medications/*`（写接口需 admin）
- `/api/vital-signs/*`

## 技术栈

- FastAPI
- Uvicorn
- PyMySQL
- PyJWT
- passlib[bcrypt]
- httpx
- numpy / opencv-python / torch / ultralytics
- FastAPI StreamingResponse（SSE）

## 启动方式

### Docker Compose

**首次启动前必须设置环境变量：**

```bash
export MYSQL_ROOT_PASSWORD=your-strong-db-password
export JWT_SECRET=your-random-32char-secret
docker compose up --build
```

访问：

- 前端：`http://localhost:5173`
- Python 主后端：`http://localhost:8090`
- 健康检查：`http://localhost:8090/api/health`

### 本地启动主后端

```bash
cd backend-python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```

## 权限体系

| 角色 | 权限说明 |
|------|---------|
| `admin` | 全部接口，包括用户管理、角色分配、YOLO 配置、审计日志写入、医疗/巡查记录管理 |
| `nurse` | 读取大部分数据，创建生命体征记录、确认服药，不可删除临床记录 |

## 安全注意事项

1. **生产环境必须**设置 `MYSQL_ROOT_PASSWORD` 和 `JWT_SECRET`（不少于 32 位），Docker Compose 会强制要求。
2. `/api/health/detailed` 需要登录，防止内部服务状态外泄。
3. YOLO 摄像头配置写接口（`PUT /yolo/cameras/:id/config`、`POST /yolo/cameras/batch-config`）仅 admin 可操作。
4. 审计日志、巡查记录、用药清单的删改接口仅 admin 可操作，防止护士级别误删临床数据。
5. 密码使用 bcrypt 存储；若 passlib 未安装则 fallback 到 SHA-256 哈希。
6. `model_weights`（YOLO 权重路径）仅接受 `*.pt` 格式文件名，防止路径遍历。
7. `vital_alert_rules` 的批量写操作使用事务，保证数据一致性。

## 重要注意事项

1. 原 Node 企业鉴权依赖无法直接在 Python 中复用，当前 Python 版优先实现本地账号 + JWT 登录。
2. AI 主链路已迁移到 `backend-python` 本地引擎，直接复用 `SmartElderlyCareSystem` 执行姿态估计、表情识别和 D-S 融合。
3. 数据库字段以原 `database/sql/full_database_schema.sql` 为准，API 层做 camelCase/snake_case 兼容。
4. 部分复杂模块（如备份、Agent 深度逻辑、完整通知调度）当前提供基础兼容接口，后续可按业务细节继续补齐。
