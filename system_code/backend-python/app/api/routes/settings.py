from typing import Any
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.database import db
from app.services.audit import record_audit
from app.core.security import get_current_user, require_admin, hash_password
from app.core.tenant import require_same_tenant, tenant_id_of
from app.repositories.base import keys_to_camel

router = APIRouter(prefix='/settings', tags=['settings'])


@router.get('/')
def get_settings(user: dict[str, Any] = Depends(require_admin)):
    rows = db.query('SELECT * FROM settings WHERE tenant_id=%s', [tenant_id_of(user)])
    data: dict[str, Any] = {}
    for row in rows:
        key = row.get('setting_key') or row.get('key') or row.get('name')
        value = row.get('setting_value') or row.get('value')
        if key:
            try:
                data[key] = json.loads(value) if isinstance(value, str) else value
            except Exception:
                data[key] = value
    return {'success': True, 'data': data}


@router.put('/')
def put_settings(body: dict[str, Any], user: dict[str, Any] = Depends(require_admin)):
    tid = tenant_id_of(user)
    for key, value in body.items():
        encoded = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        db.execute('INSERT INTO settings (tenant_id,setting_key,setting_value) VALUES (%s,%s,%s) '
                   'ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)', [tid, key, encoded])

    # Push AI parameters into the running inference pipeline. Without this the
    # admin UI persisted settings that the engine never read, so every control
    # on the AI settings panel was inert until a full restart (and even then
    # the engine only consulted environment variables).
    applied: list[str] = []
    try:
        from app.services.ai_engine import get_ai_engine
        engine = get_ai_engine()
        for key in ('aiConfig', 'ai_config', 'aiSettings', 'ai_settings'):
            if key in body:
                applied = engine.apply_ai_config(body[key])
                break
    except Exception:
        # never fail the save because the model is not loaded yet -- the values
        # are persisted and will be applied on the next engine load
        applied = []

    return {'success': True, 'message': '保存成功', 'appliedAiParams': applied}


@router.get('/users')
def users(page: int = 1, pageSize: int = 100, keyword: str | None = None,
          role: str | None = None,
          user: dict[str, Any] = Depends(get_current_user)):
    # 注意：这里**故意**保持 get_current_user 而非 require_admin。
    # 返回的字段只有 id/username/name/email/role（不含口令散列），而护理员
    # 的「值班排班」页要用它填充"人员"筛选下拉；收紧会让普通护士的排班页
    # 直接空掉。管理动作（增删账号、改角色）仍然全部走 require_admin。
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(pageSize or 100)))
    tid = tenant_id_of(user)
    # 租户条件写在**字面量里**，而不是拼进变量：
    # 一是它不可省略，二是这样静态扫描（audit_tenant_coverage.py）能直接看到，
    # 不必为它开一条白名单例外。可选的附加条件才走拼接。
    # 参数顺序必须与占位符一致：tenant 永远第一。
    params: list[Any] = [tid]
    conds: list[str] = []
    kw = (keyword or '').strip()
    if kw:
        conds.append('(username LIKE %s OR name LIKE %s OR dept_name LIKE %s)')
        params.extend([f'%{kw}%'] * 3)
    if role in ('admin', 'nurse'):
        conds.append('role=%s')
        params.append(role)
    extra = (' AND ' + ' AND '.join(conds)) if conds else ''

    base = ('SELECT id, username, name, email, dept_name, role, created_at, updated_at '
            'FROM users WHERE tenant_id=%s')
    rows = db.query(base + extra + ' ORDER BY id DESC LIMIT %s OFFSET %s',
                    params + [page_size, (page - 1) * page_size])
    total = db.query('SELECT COUNT(*) AS cnt FROM users WHERE tenant_id=%s' + extra, params)
    return {'success': True, 'data': {'data': keys_to_camel(rows), 'total': int(total[0].get('cnt') or 0), 'page': page, 'pageSize': page_size}}


@router.post('/users')
def create_user(body: dict[str, Any], request: Request = None, user: dict[str, Any] = Depends(require_admin)):
    username = (body.get('username') or '').strip()
    name = (body.get('name') or '').strip()
    password = body.get('password') or ''
    if not username or not name or len(password) < 6:
        raise HTTPException(status_code=400, detail='账号、姓名必填，密码至少 6 位')
    tid = tenant_id_of(user)
    # 账号在**机构内**唯一即可 —— 不同机构各有自己的 admin/nurse 账号是常态，
    # 若按全局唯一校验，第二家机构就无法创建与第一家同名的账号。
    if db.query('SELECT id FROM users WHERE tenant_id=%s AND username=%s LIMIT 1', [tid, username]):
        raise HTTPException(status_code=400, detail='账号已存在')
    new_id = db.insert('INSERT INTO users (tenant_id,username,name,email,dept_name,role,password_hash) '
                       'VALUES (%s,%s,%s,%s,%s,%s,%s)',
                       [tid, username, name, body.get('email') or '', body.get('deptName') or '',
                        body.get('role') or 'nurse', hash_password(password)])
    row = db.query('SELECT id, username, name, email, dept_name, role FROM users WHERE id=%s AND tenant_id=%s',
                   [new_id, tid])[0]
    record_audit('新增用户', user=user, resource_type='user', resource_id=new_id,
                 detail={'username': username, 'role': body.get('role') or 'nurse'}, request=request)
    return {'success': True, 'data': keys_to_camel(row), 'message': '账号创建成功'}


@router.put('/users/{user_id}/role')
def update_role(user_id: int, body: dict[str, Any], request: Request = None, user: dict[str, Any] = Depends(require_admin)):
    role = body.get('role')
    if role not in {'admin', 'nurse'}:
        raise HTTPException(status_code=400, detail='无效角色')
    require_same_tenant(db.query_one('SELECT id, tenant_id FROM users WHERE id=%s', [user_id]), user)
    db.execute('UPDATE users SET role=%s WHERE id=%s AND tenant_id=%s',
               [role, user_id, tenant_id_of(user)])
    record_audit('修改用户角色', user=user, resource_type='user', resource_id=user_id,
                 detail={'role': role}, request=request)
    return {'success': True, 'message': '角色更新成功'}


@router.delete('/users/{user_id}')
def delete_user(user_id: int, request: Request = None, user: dict[str, Any] = Depends(require_admin)):
    if str(user_id) == str(user.get('id')):
        raise HTTPException(status_code=400, detail='不能删除自己的账号')
    require_same_tenant(db.query_one('SELECT id, tenant_id FROM users WHERE id=%s', [user_id]), user)
    db.execute('DELETE FROM users WHERE id=%s AND tenant_id=%s', [user_id, tenant_id_of(user)])
    record_audit('删除用户', user=user, resource_type='user', resource_id=user_id, request=request)
    return {'success': True, 'message': '账号已删除'}


@router.put('/yolo-model')
def yolo_model(body: dict[str, Any], request: Request = None, user: dict[str, Any] = Depends(require_admin)):
    models = body.get('models') or body.get('model') or body.get('yoloModels')
    if isinstance(models, str):
        models = [models]
    if not isinstance(models, list) or not models:
        raise HTTPException(status_code=400, detail='models 不能为空')
    # 原实现是无条件 UPDATE：任一机构的管理员点一下，**所有机构**的摄像头
    # 推理模型都会被换掉，是多租户下最直接的越权写入。加 tenant_id 约束。
    db.execute('UPDATE cameras SET yolo_model=%s, yolo_models=%s WHERE tenant_id=%s',
               [models[0], json.dumps(models, ensure_ascii=False), tenant_id_of(user)])
    record_audit('批量修改推理模型', user=user, resource_type='camera',
                 detail={'models': models}, request=request)
    return {'success': True, 'message': '已应用到所有摄像头'}
