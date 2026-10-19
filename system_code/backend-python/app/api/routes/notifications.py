"""通知渠道管理 + 投递记录。

为什么必须提供「测试发送」接口：
配置一个 webhook 是否填对、SMTP 是否能连上，光看配置项无法判断 ——
唯一的办法是真发一条。没有测试按钮，用户只能等真实的跌倒告警发生才知道没配对，
而那时已经太晚了。所以测试发送不是"锦上添花"，它是让这套东西可用的前提。
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.database import db
from app.core.security import get_current_user, require_admin
from app.core.tenant import require_same_tenant, tenant_id_of
from app.repositories.base import keys_to_camel
from app.services.audit import record_audit
from app.services.notify_channels import (CHANNEL_TYPES, LEVEL_LABEL, LEVEL_ORDER,
                                          build_message, dispatch, log_delivery)

router = APIRouter(prefix='/notifications', tags=['notifications'])

LEVELS = ('LOW', 'MEDIUM', 'HIGH', 'URGENT')


@router.get('/types')
def channel_types(user: dict[str, Any] = Depends(get_current_user)):
    """可用渠道类型及其需要的配置项 —— 前端据此渲染表单，避免两边各写一份字段清单。"""
    return {'success': True, 'data': [
        {'type': 'wecom', 'label': '企业微信群机器人',
         'hint': '在群设置 → 群机器人 → 添加，复制 Webhook 地址',
         'fields': [{'key': 'webhook', 'label': 'Webhook 地址', 'required': True}]},
        {'type': 'dingtalk', 'label': '钉钉群机器人',
         'hint': '在群设置 → 智能群助手 → 添加机器人 → 自定义，复制 Webhook',
         'fields': [{'key': 'webhook', 'label': 'Webhook 地址', 'required': True},
                    {'key': 'secret', 'label': '加签密钥（可选）', 'required': False}]},
        {'type': 'email', 'label': '邮件（SMTP）',
         'hint': '收件人有三种来源，可叠加：指定邮箱、按角色取账号里的邮箱、'
                 '以及当班护理员兜底（三者都空时无法发送，会明确记为「未发送」）',
         'fields': [{'key': 'host', 'label': 'SMTP 服务器', 'required': True},
                    {'key': 'port', 'label': '端口（SSL 默认 465，否则 25）',
                     'required': False},
                    {'key': 'user', 'label': '账号', 'required': False},
                    {'key': 'password', 'label': '密码/授权码', 'required': False, 'secret': True},
                    {'key': 'from', 'label': '发件人', 'required': False},
                    {'key': 'to', 'label': '指定收件人（逗号分隔，可留空）',
                     'required': False},
                    # 按角色取 users.email：人员变动时自动跟随，不会静默发不到人
                    {'key': 'toRoles', 'label': '按角色接收', 'required': False,
                     'type': 'roles', 'options': [
                         {'value': 'admin', 'label': '机构管理员'},
                         {'value': 'nurse', 'label': '护理员'}]},
                    {'key': 'onlyOnDuty', 'label': '仅发给当班护理员（夜间推荐）',
                     'required': False, 'type': 'bool'},
                    {'key': 'use_tls', 'label': 'STARTTLS', 'required': False, 'type': 'bool'},
                    {'key': 'use_ssl', 'label': 'SSL', 'required': False, 'type': 'bool'}]},
    ], 'levels': [{'value': k, 'label': LEVEL_LABEL[k]} for k in LEVELS]}


@router.get('/channels')
def list_channels(user: dict[str, Any] = Depends(get_current_user)):
    rows = db.query('SELECT * FROM notification_channels WHERE tenant_id=%s ORDER BY id',
                    [tenant_id_of(user)])
    from app.services.notify_channels import _mask_config
    out = []
    for r in rows:
        item = keys_to_camel(r)
        cfg = r.get('config')
        if isinstance(cfg, str):
            import json
            try:
                cfg = json.loads(cfg)
            except json.JSONDecodeError:
                cfg = {}
        item['config'] = _mask_config(cfg)
        out.append(item)
    return {'success': True, 'data': out}


def _clean_config(type_: str, config: Any) -> dict[str, Any]:
    """只保留该渠道类型认识的键，并做基本校验。"""
    cls = CHANNEL_TYPES.get(type_)
    if cls is None:
        raise HTTPException(status_code=400, detail=f'未知渠道类型：{type_}')
    if not isinstance(config, dict):
        config = {}
    allowed = {
        'wecom': {'webhook'},
        'dingtalk': {'webhook', 'secret'},
        # 白名单必须与上面的 fields 清单一致：漏掉任何一个键，前端保存成功、
        # 值却被静默丢掉（表现为"填了角色但收件人还是空的"）。
        'email': {'host', 'port', 'user', 'password', 'from', 'to', 'toRoles',
                  'onlyOnDuty', 'use_tls', 'use_ssl'},
    }[type_]
    return {k: v for k, v in config.items() if k in allowed}


@router.post('/channels')
def create_channel(body: dict[str, Any], request: Request = None,
                   user: dict[str, Any] = Depends(require_admin)):
    type_ = str(body.get('type') or '').strip()
    name = str(body.get('name') or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='渠道名称必填')
    min_level = str(body.get('minLevel') or body.get('min_level') or 'HIGH').upper()
    if min_level not in LEVELS:
        raise HTTPException(status_code=400, detail=f'minLevel 必须是 {LEVELS} 之一')
    cfg = _clean_config(type_, body.get('config'))
    new_id = db.insert(
        'INSERT INTO notification_channels (tenant_id, type, name, config, min_level, enabled) '
        'VALUES (%s,%s,%s,%s,%s,%s)',
        [tenant_id_of(user), type_, name, __import__('json').dumps(cfg, ensure_ascii=False),
         min_level, 1 if body.get('enabled', True) else 0])
    record_audit('新增通知渠道', user=user, resource_type='notification_channel',
                 resource_id=new_id, detail={'type': type_, 'name': name,
                                             'minLevel': min_level}, request=request)
    return {'success': True, 'data': {'id': new_id}, 'message': '渠道已创建'}


@router.put('/channels/{channel_id}')
def update_channel(channel_id: int, body: dict[str, Any], request: Request = None,
                   user: dict[str, Any] = Depends(require_admin)):
    row = require_same_tenant(
        db.query_one('SELECT * FROM notification_channels WHERE id=%s', [channel_id]), user)
    sets, params = [], []
    if body.get('name') is not None:
        sets.append('name=%s'); params.append(str(body['name']).strip())
    if body.get('minLevel') is not None or body.get('min_level') is not None:
        lvl = str(body.get('minLevel') or body.get('min_level')).upper()
        if lvl not in LEVELS:
            raise HTTPException(status_code=400, detail=f'minLevel 必须是 {LEVELS} 之一')
        sets.append('min_level=%s'); params.append(lvl)
    if body.get('enabled') is not None:
        sets.append('enabled=%s'); params.append(1 if body['enabled'] else 0)
    if body.get('config') is not None:
        import json
        cfg = _clean_config(str(row['type']), body['config'])
        # 脱敏回传的 '******' 不能被写回库：那会把真实密码覆盖成星号
        old = row.get('config')
        if isinstance(old, str):
            try:
                old = json.loads(old)
            except json.JSONDecodeError:
                old = {}
        for k, v in list(cfg.items()):
            if v == '******' and (old or {}).get(k):
                cfg[k] = old[k]
        sets.append('config=%s'); params.append(json.dumps(cfg, ensure_ascii=False))
    if not sets:
        return {'success': True, 'message': '没有需要更新的字段'}
    params += [channel_id, tenant_id_of(user)]
    db.execute(f'UPDATE notification_channels SET {", ".join(sets)} '
               'WHERE id=%s AND tenant_id=%s', params)
    record_audit('修改通知渠道', user=user, resource_type='notification_channel',
                 resource_id=channel_id, detail={k: v for k, v in body.items()
                                                 if k != 'config'}, request=request)
    return {'success': True, 'message': '渠道已更新'}


@router.delete('/channels/{channel_id}')
def delete_channel(channel_id: int, request: Request = None,
                   user: dict[str, Any] = Depends(require_admin)):
    require_same_tenant(
        db.query_one('SELECT id, tenant_id FROM notification_channels WHERE id=%s', [channel_id]), user)
    db.execute('DELETE FROM notification_channels WHERE id=%s AND tenant_id=%s',
               [channel_id, tenant_id_of(user)])
    record_audit('删除通知渠道', user=user, resource_type='notification_channel',
                 resource_id=channel_id, request=request)
    return {'success': True, 'message': '渠道已删除'}


@router.post('/channels/{channel_id}/test')
def test_channel(channel_id: int, user: dict[str, Any] = Depends(require_admin)):
    """真发一条测试消息。返回**真实结果**，失败时把原因原样给出。

    刻意不做"测试通过"的假象：如果 webhook 填错、SMTP 连不上，这里必须
    如实返回失败原因 —— 否则用户会以为配好了，直到某天真的有人摔倒。
    """
    row = require_same_tenant(
        db.query_one('SELECT * FROM notification_channels WHERE id=%s', [channel_id]), user)
    tid = tenant_id_of(user)
    cls = CHANNEL_TYPES.get(str(row['type']))
    if cls is None:
        raise HTTPException(status_code=400, detail=f'未知渠道类型 {row["type"]}')

    ch = cls(row)
    if ch.type_name == 'email' and not ch.config.get('to'):
        from app.services.notify_channels import on_duty_emails
        ch.config['_fallback_to'] = on_duty_emails(tid)

    sample = {'id': None, 'riskLevel': 'HIGH', 'roomNo': '101', 'elderName': '测试老人',
              'postureType': 'fall_like', 'expressionTop': 'Disgust', 'confidence': 88,
              'alertTime': '（测试消息，非真实告警）'}
    problem = ch.validate()
    if problem:
        log_delivery(tenant_id=tid, alert_id=None, channel=ch, channel_type=ch.type_name,
                     channel_name=ch.name, target=ch.target, status='skipped',
                     reason='test', alert_level='HIGH', error=problem, duration_ms=0)
        return {'success': False, 'data': {'status': 'skipped', 'error': problem},
                'message': f'未发送：{problem}'}

    ok, err, ms = ch.send(build_message(sample, 'test'))
    log_delivery(tenant_id=tid, alert_id=None, channel=ch, channel_type=ch.type_name,
                 channel_name=ch.name, target=ch.target,
                 status='success' if ok else 'failed', reason='test',
                 alert_level='HIGH', error=(None if ok else err), duration_ms=ms)
    return {'success': ok,
            'data': {'status': 'success' if ok else 'failed', 'error': err, 'durationMs': ms},
            'message': f'已发送（{ms}ms）' if ok else f'发送失败：{err}'}


@router.get('/logs')
def list_logs(page: int = 1, pageSize: int = 20, status: str | None = None,
              channelType: str | None = None, alertId: int | None = None,
              user: dict[str, Any] = Depends(get_current_user)):
    """投递记录。**这是排查"我没收到告警"的唯一依据。**"""
    tid = tenant_id_of(user)
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(pageSize or 20)))
    conds, params = ['tenant_id=%s'], [tid]
    if status:
        conds.append('status=%s'); params.append(status)
    if channelType:
        conds.append('channel_type=%s'); params.append(channelType)
    if alertId:
        conds.append('alert_id=%s'); params.append(alertId)
    clause = ' AND '.join(conds)
    rows = db.query(f'SELECT * FROM notification_logs WHERE {clause} '
                    'ORDER BY id DESC LIMIT %s OFFSET %s',
                    params + [page_size, (page - 1) * page_size])
    total = db.query(f'SELECT COUNT(*) AS c FROM notification_logs WHERE {clause}', params)
    stats = db.query(
        'SELECT status, COUNT(*) AS c FROM notification_logs WHERE tenant_id=%s '
        'GROUP BY status', [tid])
    return {'success': True, 'data': {
        'data': keys_to_camel(rows),
        'total': int(total[0]['c'] or 0), 'page': page, 'pageSize': page_size,
        'byStatus': {r['status']: int(r['c']) for r in stats},
    }}


@router.post('/dispatch/{alert_id}')
def redispatch(alert_id: int, user: dict[str, Any] = Depends(require_admin)):
    """把某条告警重新推送一遍（用于渠道修好之后补发）。"""
    alert = require_same_tenant(db.query_one('SELECT * FROM alerts WHERE id=%s', [alert_id]), user)
    results = dispatch(keys_to_camel(alert), reason='new')
    ok = [r for r in results if r['status'] == 'success']
    return {'success': True, 'data': results,
            'message': f'{len(ok)}/{len(results)} 个渠道发送成功' if results else '没有匹配的渠道'}
