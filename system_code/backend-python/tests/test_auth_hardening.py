import pytest
from fastapi import HTTPException

from app.api.routes import auth as auth_mod
from app.api.routes import alerts as alerts_mod
from app.core.security import _jwt_secret


def test_init_password_rejects_platform_account(monkeypatch):
    row = {
        'id': 1, 'username': 'platform', 'password_hash': None,
        'tenant_id': None, 'is_platform': 1,
    }
    monkeypatch.setattr(auth_mod.db, 'query', lambda *a, **k: [row])
    with pytest.raises(HTTPException) as exc:
        auth_mod.init_password(auth_mod.LoginBody(username='platform', password='123456'))
    assert exc.value.status_code == 403


def test_init_password_rejects_account_without_tenant(monkeypatch):
    row = {
        'id': 2, 'username': 'orphan', 'password_hash': None,
        'tenant_id': None, 'is_platform': 0,
    }
    monkeypatch.setattr(auth_mod.db, 'query', lambda *a, **k: [row])
    with pytest.raises(HTTPException) as exc:
        auth_mod.init_password(auth_mod.LoginBody(username='orphan', password='123456'))
    assert exc.value.status_code == 403


def test_ingest_rejects_cross_tenant_elder(monkeypatch):
    monkeypatch.setattr(alerts_mod.db, 'query_one', lambda *a, **k: None)
    with pytest.raises(HTTPException) as exc:
        alerts_mod.ingest({'elderId': 99}, None, {'id': 1, 'tenantId': 1})
    assert exc.value.status_code == 404


def test_dev_jwt_secret_is_nonempty():
    assert len(_jwt_secret()) >= 32
