# Python FastAPI 后端

这是由原 Node.js/Express 后端迁移而来的 Python FastAPI 主后端。默认监听 `8090`，并保持 `/api` 接口前缀，便于原 Vue 前端继续使用。

## 启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```

## 关键环境变量

- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `JWT_SECRET`
- `AI_POSE_MODEL_PATH`：姿态估计权重路径，默认使用仓库根目录 `thesis_assets/pose/weights/pose_bifpn_best.pt`
- `AI_EXPR_MODEL_PATH`：表情识别权重路径，默认使用仓库根目录 `thesis_assets/expr/weights/expr_lka_best.pt`
- `AI_DEVICE`：推理设备，默认 `cpu`
- `AI_FALL_THRESHOLD`：触发表情识别的跌倒阈值，默认 `0.3`
- `AI_EXPR_CONF`：表情检测置信度，默认 `0.25`
- `AI_ALLOW_REMOTE_IMAGE`：是否允许拉取远程 HTTP(S) 图片，默认 `false`
- `AI_ALLOWED_IMAGE_ROOT`：允许读取的本地图片目录，默认 `backend-python/uploads`

## AI 推理说明

backend-python 现在内置本地 AI 推理主链路，不再依赖独立 Python AI 微服务。检测入口 `/api/python/detect`、`/api/python/yolo/detect` 和 `/api/yolo/cameras/{id}/test` 会调用 `expression_recognition.system.SmartElderlyCareSystem`，执行姿态估计、条件触发表情识别、痛苦分数计算和 D-S 风险融合。

当模型文件缺失或加载失败时，后台仍可启动，`/api/health/detailed` 会在 `components.aiEngine` 中返回不可用原因，检测接口会返回明确错误，不会返回模拟检测结果。
