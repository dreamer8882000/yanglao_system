from fastapi import APIRouter
from app.api.routes import (agent, alerts, auth, cameras, compat, duty, elders, evaluation,
                              health, notifications, platform, python_proxy, settings, yolo,
                              yolo_stream)
from app.api.routes.crud import crud_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.public_router)
api_router.include_router(auth.protected_router)
api_router.include_router(elders.router)
api_router.include_router(alerts.router)
api_router.include_router(cameras.router)
api_router.include_router(settings.router)
api_router.include_router(python_proxy.router)
api_router.include_router(yolo.router)
api_router.include_router(yolo_stream.router)
api_router.include_router(agent.router)
api_router.include_router(evaluation.router)
api_router.include_router(compat.router)
api_router.include_router(notifications.router)
# 平台级只读视图（SaaS 运营方）：与租户业务接口完全分离，见 routes/platform.py 顶部说明
api_router.include_router(platform.router)

# duty 必须先于通用 CRUD 注册：它的 POST/PUT /schedules/ 带冲突检测，
# 若通用路由先匹配上，唯一索引冲突会直接抛 500 而不是可读的 409。
api_router.include_router(duty.router)
api_router.include_router(crud_router('/schedules', 'schedules', 'schedules'))
api_router.include_router(crud_router('/messages', 'messages', 'messages'))
api_router.include_router(crud_router('/audit', 'audit_logs', 'audit', admin_write=True, admin_read=True))
api_router.include_router(crud_router('/patrols', 'patrol_records', 'patrols', admin_write=True))
api_router.include_router(crud_router('/medications', 'medications', 'medications', admin_write=True))
api_router.include_router(crud_router('/vital-signs', 'vital_signs', 'vital-signs'))
