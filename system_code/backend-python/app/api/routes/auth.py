from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any
import base64
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from app.core.database import db
from app.core.security import create_access_token, get_current_user, hash_password, require_admin, verify_password
from app.core.tenant import require_same_tenant, tenant_id_of
from app.repositories.base import keys_to_camel
from app.services.audit import client_ip, record_audit, tenant_of_username
from app.services.captcha import generate_captcha
from app.services.login_guard import LoginGuard
from app.core.config import get_settings

public_router = APIRouter(prefix='/public/auth', tags=['auth'])
protected_router = APIRouter(prefix='/auth', tags=['auth'])

_settings = get_settings()
login_guard = LoginGuard(
    max_attempts=_settings.login_max_attempts,
    window_seconds=_settings.login_window_minutes * 60,
    lockout_seconds=_settings.login_lockout_minutes * 60,
)

_captchas: dict[str, tuple[str, datetime]] = {}
_CAPTCHA_TTL = timedelta(minutes=5)


class LoginBody(BaseModel):
    username: str
    password: str
    captchaId: str | None = None
    captchaCode: str | None = None


class RegisterBody(BaseModel):
    username: str
    name: str
    email: str
    password: str


def _cleanup_captchas(now: datetime) -> None:
    expired = [captcha_id for captcha_id, (_, expires_at) in _captchas.items() if expires_at <= now]
    for captcha_id in expired:
        _captchas.pop(captcha_id, None)


def _verify_captcha(captcha_id: str | None, captcha_code: str | None) -> None:
    now = datetime.now(timezone.utc)
    _cleanup_captchas(now)
    if not captcha_id or not captcha_code:
        raise HTTPException(status_code=400, detail='请输入验证码')
    stored = _captchas.pop(captcha_id, None)
    if not stored:
        raise HTTPException(status_code=400, detail='验证码已过期，请刷新后重试')
    code, expires_at = stored
    if expires_at <= now or code.lower() != captcha_code.strip().lower():
        raise HTTPException(status_code=400, detail='验证码错误')


@public_router.get('/captcha')
def captcha():
    now = datetime.now(timezone.utc)
    _cleanup_captchas(now)
    code, png = generate_captcha()
    captcha_id = token_urlsafe(16)
    _captchas[captcha_id] = (code, now + _CAPTCHA_TTL)
    # NOTE: the code itself is never returned. It used to be embedded verbatim in
    # an SVG <text> node, which made the challenge trivially machine-readable.
    image = 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')
    return {'success': True, 'data': {'id': captcha_id, 'image': image}}


_SAFE_USER_COLS = 'id, username, name, email, role, dept_name, avatar, created_at, updated_at, tenant_id, is_platform'


@public_router.post('/login')
def login(body: LoginBody, request: Request = None):
    ip = client_ip(request)

    remaining = login_guard.remaining_lockout(body.username, ip)
    if remaining > 0:
        record_audit('登录被限流', username=body.username, resource_type='auth',
                     tenant_id=tenant_of_username(body.username),
                     detail={'remainingSeconds': int(remaining)}, request=request)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f'登录失败次数过多，请 {int(remaining // 60) + 1} 分钟后重试')

    _verify_captcha(body.captchaId, body.captchaCode)
    rows = db.query(f'SELECT {_SAFE_USER_COLS}, password_hash FROM users WHERE username=%s LIMIT 1', [body.username])
    if not rows:
        login_guard.record_failure(body.username, ip)
        record_audit('登录失败', username=body.username, resource_type='auth',
                     tenant_id=tenant_of_username(body.username),
                     detail={'reason': '账号不存在'}, request=request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='账号或密码错误')
    user = rows[0]
    if not verify_password(body.password, user.get('password_hash') or ''):
        locked_for = login_guard.record_failure(body.username, ip)
        record_audit('登录失败', username=body.username, resource_type='auth',
                     tenant_id=tenant_of_username(body.username),
                     detail={'reason': '密码错误', 'lockedSeconds': int(locked_for)}, request=request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='账号或密码错误')
    login_guard.reset(body.username, ip)
    token = create_access_token(user['id'], {'username': user.get('username'), 'role': user.get('role')})
    safe_user = keys_to_camel({k: v for k, v in user.items() if k != 'password_hash'})
    try:
        db.execute('UPDATE users SET last_login_at=NOW() WHERE id=%s', [user['id']])
    except Exception:
        pass
    record_audit('登录成功', user=user, resource_type='auth',
                 detail={'role': user.get('role')}, request=request)
    return {'success': True, 'data': {'token': token, 'user': safe_user}, 'message': '登录成功'}


@public_router.post('/init-password')
def init_password(body: LoginBody):
    if not body.username or len(body.password) < 6:
        raise HTTPException(status_code=400, detail='账号不能为空且密码至少 6 位')
    rows = db.query(f'SELECT {_SAFE_USER_COLS}, password_hash FROM users WHERE username=%s LIMIT 1', [body.username])
    if not rows:
        raise HTTPException(status_code=400, detail='账号不存在，请联系管理员创建账号')
    user = rows[0]
    if user.get('is_platform') or user.get('tenant_id') is None:
        raise HTTPException(status_code=403, detail='平台账号或未归属机构的账号不允许自助初始化，请联系管理员')
    if user.get('password_hash'):
        raise HTTPException(status_code=400, detail='该账号已设置密码，请直接登录或使用修改密码功能')
    db.execute('UPDATE users SET password_hash=%s WHERE id=%s', [hash_password(body.password), user['id']])
    return {'success': True, 'message': '密码初始化成功，请登录'}


@public_router.post('/register')
def register(body: RegisterBody):
    if len(body.username.strip()) < 3 or len(body.password) < 6:
        raise HTTPException(status_code=400, detail='账号长度需至少 3 位，密码至少 6 位')
    if db.query('SELECT id FROM users WHERE username=%s LIMIT 1', [body.username.strip()]):
        raise HTTPException(status_code=400, detail='该账号已存在')
    if db.query('SELECT id FROM users WHERE email=%s LIMIT 1', [body.email.strip()]):
        raise HTTPException(status_code=400, detail='该邮箱已被注册')
    db.insert(
        'INSERT INTO users (username,name,email,password_hash,role) VALUES (%s,%s,%s,%s,%s)',
        [body.username.strip(), body.name.strip(), body.email.strip(), hash_password(body.password), 'nurse'],
    )
    return {'success': True, 'message': '注册成功，请登录'}


@protected_router.get('/me')
def me(user: dict[str, Any] = Depends(get_current_user)):
    return {'success': True, 'data': user}


@protected_router.post('/logout')
def logout(user: dict[str, Any] = Depends(get_current_user)):
    return {'success': True, 'message': '已退出'}


@public_router.post('/logout')
def public_logout():
    return {'success': True, 'message': '已退出'}


@protected_router.post('/change-password')
def change_password(body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    old_password = body.get('oldPassword')
    new_password = body.get('newPassword')
    confirm_password = body.get('confirmPassword')
    if not isinstance(new_password, str) or len(new_password) < 6:
        raise HTTPException(status_code=400, detail='新密码至少 6 位')
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail='两次密码输入不一致')
    rows = db.query('SELECT id, password_hash FROM users WHERE id=%s LIMIT 1', [user['id']])
    if not rows or not verify_password(old_password or '', rows[0].get('password_hash') or ''):
        raise HTTPException(status_code=400, detail='原密码错误')
    db.execute('UPDATE users SET password_hash=%s WHERE id=%s', [hash_password(new_password), user['id']])
    return {'success': True, 'message': '密码修改成功，请重新登录'}


@protected_router.post('/reset-password')
def reset_password(body: dict[str, Any], user: dict[str, Any] = Depends(require_admin)):
    user_id = body.get('userId')
    new_password = body.get('newPassword')
    if not user_id or not isinstance(new_password, str) or len(new_password) < 6:
        raise HTTPException(status_code=400, detail='参数不完整，且新密码至少 6 位')
    # 越权面：不校验归属的话，任一机构的管理员只要猜到 id 就能重置**其它机构**
    # 任何账号的密码，进而直接登录对方系统。
    require_same_tenant(db.query_one('SELECT id, tenant_id FROM users WHERE id=%s', [user_id]), user)
    db.execute('UPDATE users SET password_hash=%s WHERE id=%s AND tenant_id=%s',
               [hash_password(new_password), user_id, tenant_id_of(user)])
    return {'success': True, 'message': '密码已重置'}
