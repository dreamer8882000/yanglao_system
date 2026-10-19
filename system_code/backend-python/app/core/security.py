from datetime import datetime, timedelta, timezone
from typing import Any
import base64
import hashlib
import hmac
import json
import secrets
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import get_settings
from .database import db
from .tenant import bind_tenant

bearer = HTTPBearer(auto_error=False)
_pwd_context = None
_DEV_JWT_SECRET = secrets.token_urlsafe(48)


def _jwt_secret() -> str:
    settings = get_settings()
    secret = settings.jwt_secret
    if secret and len(secret) >= 32:
        return secret
    if settings.env.lower() in {'production', 'prod'}:
        raise RuntimeError('JWT_SECRET must be set to at least 32 characters')
    return _DEV_JWT_SECRET


def _get_pwd_context():
    global _pwd_context
    if _pwd_context is None:
        from passlib.context import CryptContext
        _pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
    return _pwd_context


def _is_legacy_sha256(hashed: str) -> bool:
    """识别 bcrypt 不可用时期遗留的 SHA-256 十六进制回退哈希（64 位 hex）。"""
    return len(hashed) == 64 and all(c in '0123456789abcdefABCDEF' for c in hashed)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    # 向后兼容历史 SHA-256 回退哈希（升级锁定 bcrypt==4.0.1 后仍能登录旧账号）
    if _is_legacy_sha256(hashed_password):
        legacy = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
        return hmac.compare_digest(legacy, hashed_password.lower())
    try:
        return _get_pwd_context().verify(plain_password, hashed_password)
    except Exception:
        return hmac.compare_digest(hash_password(plain_password), hashed_password)


def hash_password(password: str) -> str:
    try:
        return _get_pwd_context().hash(password)
    except Exception:
        return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, Any] = {'sub': str(subject), 'exp': int(expires.timestamp())}
    if extra:
        payload.update(extra)
    try:
        import jwt
        return jwt.encode(payload, _jwt_secret(), algorithm=settings.jwt_algorithm)
    except Exception:
        header = {'alg': 'HS256', 'typ': 'JWT'}
        signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
        signature = hmac.new(_jwt_secret().encode(), signing_input.encode(), hashlib.sha256).digest()
        return f'{signing_input}.{_b64url(signature)}'


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        import jwt
        return jwt.decode(token, _jwt_secret(), algorithms=[settings.jwt_algorithm])
    except ImportError:
        try:
            header_b64, payload_b64, signature_b64 = token.split('.')
            signing_input = f'{header_b64}.{payload_b64}'
            expected = _b64url(hmac.new(_jwt_secret().encode(), signing_input.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(expected, signature_b64):
                raise ValueError('bad signature')
            payload = json.loads(_b64url_decode(payload_b64))
            if payload.get('exp') and int(payload['exp']) < int(datetime.now(timezone.utc).timestamp()):
                raise ValueError('expired')
            return payload
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='无效或已过期的登录凭证') from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='无效或已过期的登录凭证') from exc


def _normalize_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': row.get('id'),
        'username': row.get('username'),
        'name': row.get('name') or row.get('username'),
        'role': row.get('role') or 'user',
        'email': row.get('email'),
        # 租户：多租户隔离的依据。取自**数据库当前值**而不是 JWT 里的快照 ——
        # 令牌有效期 24 小时，期间若用户被调岗或换机构，JWT 会携带过期租户，
        # 造成能看到原机构数据、或看不到新机构数据的错乱。
        'tenantId': row.get('tenant_id'),
        # 平台级账号：不属于任何机构，只能访问 /api/platform/* 只读视图。
        # 必须由**数据库当前值**决定，不能放进 JWT —— 与 tenantId 同理，
        # 令牌有效期内的授权变更应当立即生效。
        'isPlatform': bool(row.get('is_platform')),
    }


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict[str, Any]:
    token = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get('token') or request.query_params.get('token')
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='未登录')
    payload = decode_token(token)
    user_id = payload.get('sub') or payload.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='无效的登录凭证')
    try:
        rows = db.query('SELECT id, username, name, email, role, tenant_id, is_platform '
                 'FROM users WHERE id=%s LIMIT 1', [user_id])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='无法验证用户身份') from exc
    if not rows:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='用户不存在或已停用')
    user = _normalize_user(rows[0])
    # 在这里绑定租户上下文，而不是在每个路由里各绑一次：
    # 所有需要登录的接口都直接或间接依赖 get_current_user，
    # 绑在这里意味着**新加的路由自动获得**租户上下文；
    # 而逐个路由绑定的写法迟早会漏掉一处，那一处就是数据泄露点。
    bind_tenant(user.get('tenantId'))
    return user


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """**机构**管理员。

    刻意把平台账号排除在外：平台账号的 role 也是 admin，若不排除，
    它会顺带获得"修改任意机构设置/摄像头/账号"的能力 ——
    而平台视图是只读的，不该有写权限。两者的权限边界必须在这里分开。
    """
    if user.get('isPlatform') or user.get('role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail='权限不足（需要机构管理员）')
    return user


def require_admin_or_platform(
        user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """机构管理员**或**平台账号。

    只用于"基础设施/运行时"这类不属于任何机构的接口（例如宿主机 CPU、
    内存、数据库连接数）—— 那本来就是平台运维要看的东西，
    刻意不放进租户业务接口里。
    """
    if not (user.get('isPlatform') or user.get('role') == 'admin'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='权限不足')
    return user


def require_platform(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """平台级账号（SaaS 运营方）。

    刻意**不**写成"管理员即可"：机构管理员只能看到自己的机构，
    跨机构的视图必须是另一种身份。把两者混在一起，等于任何一家机构的
    管理员都能看到别家在住多少老人、出过多少次告警。
    """
    if not user.get('isPlatform'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail='需要平台级账号')
    return user
