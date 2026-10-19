# Python AI 服务迁移说明

旧的独立 Python AI 微服务已经从当前主链路迁移到 `backend-python` 进程内推理。

## 当前架构

- 主后台：`system_code/backend-python`
- AI Pipeline：复用仓库根目录 `expression_recognition.system.SmartElderlyCareSystem`
- 姿态模型默认路径：`thesis_assets/pose/weights/pose_bifpn_best.pt`
- 表情模型默认路径：`thesis_assets/expr/weights/expr_lka_best.pt`
- 检测入口：`/api/python/detect`、`/api/python/yolo/detect`、`/api/yolo/cameras/{id}/test`
- 健康检查：`/api/health/detailed` 的 `components.aiEngine`

## 行为

backend-python 直接执行完整级联流程：姿态估计 → 跌倒几何评分 → 跌倒阈值触发表情识别 → 痛苦分数 → D-S 融合风险等级。

模型缺失或初始化失败时，业务后台仍可导入和启动；检测接口返回 AI 不可用错误，健康检查返回原因，不使用模拟检测替代真实推理。

## 配置

```bash
AI_POSE_MODEL_PATH=/path/to/pose.pt
AI_EXPR_MODEL_PATH=/path/to/expression.pt
AI_DEVICE=cpu
AI_FALL_THRESHOLD=0.3
AI_EXPR_CONF=0.25
AI_ALLOW_REMOTE_IMAGE=false
AI_ALLOWED_IMAGE_ROOT=/path/to/uploads
```

旧的独立服务目录已删除，不再作为当前 AI 主链路部署。

## 反向代理与密钥

- 只有可信反向代理会覆盖 `X-Forwarded-For` 时才设置 `TRUST_PROXY_HEADERS=true`；否则审计/登录限流使用 socket peer IP，避免伪造 header 绕过限流。
- 生产环境必须设置 `JWT_SECRET`（≥32 位）与 `DB_PASSWORD`；开发环境未设置时使用进程内临时密钥（重启后旧 token 失效）。
