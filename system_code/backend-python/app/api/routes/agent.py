from typing import Any
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user
from app.core.tenant import tenant_id_of
from app.services.agent_service import get_agent

router = APIRouter(prefix='/agent', tags=['agent'])


@router.get('/tools')
def tools(user: dict[str, Any] = Depends(get_current_user)):
    return {
        'success': True,
        'data': [
            {'name': 'elder_search', 'description': '查询老人档案'},
            {'name': 'alert_summary', 'description': '汇总告警统计'},
            {'name': 'schedule_lookup', 'description': '查询值班安排'},
        ],
    }


@router.post('/chat')
def chat(body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    message = body.get('message') or body.get('content') or ''
    history = body.get('history') or []
    if not isinstance(history, list):
        history = []

    agent = get_agent()
    # 租户**显式**传给 agent，再由它转交给工具函数。
    #
    # 这里曾经用 ContextVar 传递，但那条链路上的上下文极不可靠：
    # 工具是在 SSE 生成器的后续 chunk 里、经 anyio 的 to_thread 执行的，
    # 而每段 chunk 都会拿到一份上下文副本。结果是工具拿不到租户 → 抛 403 →
    # 被 execute_tool 的 except 变成一条 {"error": ...} 当正常结果回给模型，
    # AI 助手的三个查询工具**全部静默失效**。
    #
    # 工具生成的是查询语句，租户决定了它能查到哪些数据 —— 安全相关的取值
    # 不该依赖隐式传播机制。显式传参是唯一不会被上下文边界吃掉的做法。
    # 同时也要挡在入口：没有机构归属的账号不得使用助手。
    tenant_id = tenant_id_of(user)

    def events():
        yield from agent.stream_chat(message, history, tenant_id=tenant_id)

    return StreamingResponse(events(), media_type='text/event-stream')
