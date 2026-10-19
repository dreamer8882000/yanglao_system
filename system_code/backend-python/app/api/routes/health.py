from app.core.timeutil import local_now
from typing import Any
import platform
import time
from fastapi import APIRouter, Depends, Response
from app.core.config import get_settings
from app.core.database import db
from app.core.metrics import PROCESS_START, metrics as request_metrics
from app.core.security import get_current_user, require_admin_or_platform
from app.services.ai_engine import get_ai_engine

router = APIRouter(tags=['health'])


@router.get('/health')
def health(response: Response):
    ok = db.health()
    if not ok:
        response.status_code = 503
    return {'status': 'healthy' if ok else 'degraded', 'timestamp': local_now().isoformat()}


@router.get('/health/detailed')
def detailed_health(response: Response, user: dict[str, Any] = Depends(get_current_user)):
    database_ok = db.health()
    ai_status = get_ai_engine().status()
    ai_nonfatal = ai_status['status'] in {'healthy', 'unavailable'}
    status = 'healthy' if database_ok and ai_nonfatal else 'degraded'
    if status != 'healthy':
        response.status_code = 503
    return {
        'status': status,
        'timestamp': local_now().isoformat(),
        'components': {
            'database': {'status': 'healthy' if database_ok else 'unhealthy'},
            'aiEngine': ai_status,
            'pythonService': {'status': 'removed', 'message': 'AI 主链路已迁移到 backend-python 本地引擎'},
        },
    }


@router.get('/monitor/performance')
def performance(user: dict[str, Any] = Depends(require_admin_or_platform)):
    """Runtime performance metrics for the SystemMonitor dashboard.

    Returns the raw metrics object (not wrapped in {success, data}) because the
    frontend assigns ``res.data`` straight to its ``metrics`` ref.

    它会把宿主机的操作系统版本、运行环境名与数据库连接数一起吐出来，
    属于**基础设施信息而非租户数据**：
      · 护理员不该看到（与处置告警无关）；
      · 机构管理员够用；
      · 平台运维**同样需要** —— 所以用 require_admin_or_platform，
        而不是 require_admin（后者已刻意排除平台账号）。
    """
    settings = get_settings()

    cpu_usage = 0.0
    mem_used = mem_total = 0
    try:
        import psutil
        cpu_usage = psutil.cpu_percent(interval=0.0)
        vm = psutil.virtual_memory()
        mem_used, mem_total = int(vm.used), int(vm.total)
    except Exception:
        pass

    db_active = db_max = 0
    try:
        rows = db.query("SHOW STATUS LIKE 'Threads_connected'")
        db_active = int(rows[0].get('Value') or 0) if rows else 0
        rows2 = db.query('SELECT @@max_connections AS m')
        db_max = int(rows2[0]['m']) if rows2 else 0
    except Exception:
        pass

    snap = request_metrics.snapshot()
    return {
        'cpu': {'usage': round(float(cpu_usage), 1)},
        'memory': {'used': mem_used, 'total': mem_total},
        'database': {
            'activeConnections': db_active,
            'maxConnections': db_max,
            'status': 'healthy' if db.health() else 'unhealthy',
        },
        'performance': {
            'avgResponseTime': snap['avgResponseTime'],
            'sampleSize': snap['sampleSize'],
        },
        'requests': {
            'total': snap['total'],
            'success': snap['success'],
            'error': snap['error'],
        },
        'system': {
            'platform': platform.platform(),
            'runtimeVersion': f'Python {platform.python_version()}',
            'uptime': int(time.time() - PROCESS_START),
            'env': settings.env,
        },
    }
