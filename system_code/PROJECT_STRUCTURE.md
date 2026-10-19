# 项目目录说明

```text
converted-python-project/
├── README.md                 # 原项目说明
├── MIGRATION_NOTES.md         # Python 迁移说明、启动方式、注意事项
├── PROJECT_STRUCTURE.md       # 当前目录说明
├── docker-compose.yml         # 一键启动：前端 + Python 主后端（内置 AI）+ MySQL
├── backend-python/            # 新 Python FastAPI 主后端，替代原 Node.js 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 应用入口
│   │   ├── api/               # 路由层，保持 /api 接口前缀
│   │   ├── core/              # 配置、数据库、安全鉴权
│   │   ├── repositories/      # 数据访问基础封装
│   │   ├── services/          # 本地 AI 引擎、图片加载等后台服务
│   │   └── schemas/           # 预留数据模型/校验结构
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── frontend/                  # 原 Vue 前端，已接入本地 AI 推理接口
├── database/
│   └── sql/                   # 原 MySQL schema 和迁移脚本
└── docs/                      # 原项目文档归档
```

## 启动入口

推荐使用：

```bash
docker compose up --build
```

- 前端：`http://localhost:5173`
- Python 主后端：`http://localhost:8090`
- 后端健康检查：`http://localhost:8090/api/health`

## 本次自检查修复摘要（第四轮，2026-06-23）

**CRITICAL 修复**
- 修复 `repositories/base.py` 中 `snake_to_camel` 函数定义被意外删除导致所有 API 响应崩溃的 NameError
- 修复 `alerts.py` 仪表盘统计中 `highRisk` 计数始终为 0 的 key mismatch（camelCase 与 raw SQL key 混用）

**安全修复**
- `auth.py` 登录接口改用显式列名查询，避免 `SELECT *` 将 `password_hash` 泄露到响应体
- `yolo.py` YOLO 摄像头配置写接口（PUT/POST）改为 `require_admin`，防止护士级别用户篡改模型参数
- `yolo.py` `model_weights` 路径增加正则白名单验证（仅接受 `*.pt` 文件名），防止路径遍历
- `health.py` `/health/detailed` 加登录认证，防止内部服务状态泄露
- `auth.py` `reset-password` 改用 `require_admin` 依赖，移除手动角色字符串比较
- `alerts.py` `/statistics` 接口修复 `range` 参数被忽略的问题，实际查询区间按参数变化

**权限修复**
- `router.py` 审计日志、巡查记录、用药清单的写/删操作改为 `admin_write=True`，防止护士误删临床数据

**数据一致性修复**
- `compat.py` `vital_alert_rules` 批量替换改用事务（`db.transaction()`），防止中途失败导致规则部分删除
- `database.py` 新增 `transaction()` 上下文管理器方法

**前几轮的修复（保留记录）**
- 为通用 Repository 增加表名和字段白名单，避免任意请求字段被拼接为 SQL 标识符
- `order_by` 参数增加正则白名单过滤，防止 SQL 注入
- 修复 `verify_password` fallback 明文比对安全漏洞
- `require_admin` 移除 `'administrator'` 非法角色
- `_normalize_user` 移除不存在的 `phone` 字段引用
- YOLO API 路径修正（`/api/yolo` → `/yolo`）
- 补齐所有前端兼容接口
- Docker Compose 健康检查全覆盖，前端 build arg 正确传入
