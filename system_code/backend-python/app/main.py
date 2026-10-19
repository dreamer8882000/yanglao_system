import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.core.config import get_settings
from app.core.metrics import metrics as request_metrics
from app.services.ai_engine import get_ai_engine
from app.services.escalation import start_scheduler, stop_scheduler

settings = get_settings()
settings.validate()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version=settings.app_version)

origins = ['*'] if settings.cors_origins == '*' else [item.strip() for item in settings.cors_origins.split(',') if item.strip()]
allow_credentials = origins != ['*']
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware('http')
async def record_request_metrics(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        request_metrics.record(500, (time.perf_counter() - start) * 1000)
        raise
    request_metrics.record(response.status_code, (time.perf_counter() - start) * 1000)
    return response


@app.on_event('startup')
def warmup_ai_engine():
    status = get_ai_engine().status()
    if status.get('status') == 'healthy':
        logger.info('AI engine warmup completed: pose=%s expr=%s device=%s', status.get('poseModel'), status.get('exprModel'), status.get('device'))
    else:
        logger.warning('AI engine warmup unavailable: %s', status.get('error'))
    # Unhandled alerts must eventually escalate even with no operator online.
    start_scheduler(
        interval_minutes=settings.alert_escalate_interval_minutes,
        after_minutes=settings.alert_escalate_after_minutes,
    )


@app.on_event('shutdown')
def shutdown_scheduler():
    stop_scheduler()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else '请求失败'
    return JSONResponse(status_code=exc.status_code, content={'success': False, 'message': message, 'detail': exc.detail})


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    logging.exception('unhandled error')
    return JSONResponse(status_code=500, content={'success': False, 'message': '服务器内部错误'})


@app.get('/')
def root():
    return {'name': settings.app_name, 'version': settings.app_version, 'api': settings.api_base_path}


app.include_router(api_router, prefix=settings.api_base_path)
