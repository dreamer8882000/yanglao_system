"""后端健壮性回归：导出注入、告警终态、私信隔离、排班跨租户。"""
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes import alerts as alerts_mod
from app.api.routes import crud as crud_mod
from app.api.routes import duty as duty_mod


def test_csv_escape_blocks_formula_injection():
    assert alerts_mod._csv_escape('=1+1') == '"\'=1+1"'
    assert alerts_mod._csv_escape('+cmd') == '"\'+cmd"'
    assert alerts_mod._csv_escape('@cmd') == '"\'@cmd"'
    assert alerts_mod._csv_escape('-cmd') == '"\'-cmd"'
    assert alerts_mod._csv_escape('a"b') == '"a""b"'


def test_alert_terminal_state_cannot_be_changed_again():
    alerts_mod._ensure_pending({'status': 0})
    for status in (1, 2):
        with pytest.raises(HTTPException) as exc:
            alerts_mod._ensure_pending({'status': status})
        assert exc.value.status_code == 409


def test_message_scope_hides_other_users_for_nurse():
    where, params = crud_mod._message_scope(
        'messages', {'id': 7, 'role': 'nurse', 'tenantId': 1}, 'tenant_id=%s', [1])
    assert where.endswith(' AND user_id=%s')
    assert params == [1, 7]


def test_message_scope_keeps_admin_tenant_wide():
    where, params = crud_mod._message_scope(
        'messages', {'id': 8, 'role': 'admin', 'tenantId': 1}, 'tenant_id=%s', [1])
    assert 'user_id' not in where
    assert params == [1]


def test_message_visibility_understands_camel_and_snake_rows():
    user = {'id': 7, 'role': 'nurse', 'tenantId': 1}
    assert crud_mod._message_visible('messages', {'user_id': 7}, user)
    assert crud_mod._message_visible('messages', {'userId': 7}, user)
    assert not crud_mod._message_visible('messages', {'userId': 9}, user)
    assert crud_mod._message_visible('messages', {'userId': 9}, {'id': 8, 'role': 'admin'})


def test_duty_rejects_cross_tenant_user(monkeypatch):
    monkeypatch.setattr(duty_mod.db, 'query_one',
                        lambda *a, **k: {'id': 9, 'tenant_id': 2})
    with pytest.raises(HTTPException) as exc:
        duty_mod._require_tenant_user(9, {'id': 1, 'tenantId': 1})
    assert exc.value.status_code == 404


def test_duty_accepts_same_tenant_user(monkeypatch):
    monkeypatch.setattr(duty_mod.db, 'query_one',
                        lambda *a, **k: {'id': 9, 'tenant_id': 1})
    assert duty_mod._require_tenant_user('9', {'id': 1, 'tenantId': 1}) == 9


def test_alert_and_duty_joins_are_tenant_scoped():
    alerts_src = Path('app/api/routes/alerts.py').read_text()
    duty_src = Path('app/api/routes/duty.py').read_text()
    assert 'e.tenant_id=a.tenant_id' in alerts_src
    assert 'c.tenant_id=a.tenant_id' in alerts_src
    assert 'u.tenant_id = s.tenant_id' in duty_src
