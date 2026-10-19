from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from app.core.security import get_current_user, require_admin
from app.services.evaluation import (
    get_report,
    job_status,
    list_reports,
    start_run,
)

router = APIRouter(prefix='/eval', tags=['eval'])


@router.get('/reports')
def reports(user: dict[str, Any] = Depends(require_admin)):
    return {'success': True, 'data': list_reports()}


@router.get('/report/{name}')
def report(name: str, user: dict[str, Any] = Depends(require_admin)):
    data = get_report(name)
    if data is None:
        raise HTTPException(status_code=404, detail='评测报告不存在')
    return {'success': True, 'data': data}


@router.post('/run')
def run(body: dict[str, Any] | None = None, user: dict[str, Any] = Depends(require_admin)):
    payload = body or {}
    try:
        every = max(1, min(int(payload.get('every') or 5), 60))
    except (TypeError, ValueError):
        every = 5
    try:
        videos = max(0, int(payload.get('videos') or 0))
    except (TypeError, ValueError):
        videos = 0
    return {'success': True, 'data': start_run(every=every, videos=videos),
            'message': '评测任务已启动'}


@router.get('/status/{job_id}')
def status(job_id: str, user: dict[str, Any] = Depends(require_admin)):
    job = job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='任务不存在')
    return {'success': True, 'data': job}
