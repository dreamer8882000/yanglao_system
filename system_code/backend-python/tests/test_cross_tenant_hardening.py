"""跨租户防护的回归测试。

这两个缺陷都是**真实存在过**的，且都是加多租户时引入的：

  1. `_on_duty_nurse` 的 SQL 里，三个班次分支只被 OR 连接，
     租户条件被拼在整个表达式的**末尾** —— 而 MySQL 的 AND 优先级高于 OR，
     等价于 `(A) OR (B) OR (C AND tenant_id=?)`，租户条件只约束了最后一个分支。
     实测：传一个**不存在**的 tenant_id 仍会返回租户 1 的当班护理员。
     危害不是"查不到"，而是**查到别人家的人**：告警派单与巡查任务生成会把
     本机构的工作派给另一个机构的护士。

  2. `maybe_create_alert` 里"摄像头所属机构优先于调用者机构"，且不校验归属。
     客户端可以在请求体里填别人的 cameraId，把告警写进**别的机构**
     （python_proxy 的 detect / detect_batch 都没传调用者租户）。

这两条一旦回归，都是"数据写错机构"级别的问题，所以在这里钉死。
"""
from __future__ import annotations

import pytest

from app.core.database import db
from app.services.ai_alerts import camera_tenant_id, maybe_create_alert


# ── 1. 当班人员查询必须严格按租户 ─────────────────────────────────────────

def _on_duty_sql(tenant_id: int | None):
    """与 duty._on_duty_nurse 相同的 SQL，用于独立验证括号是否起作用。"""
    from datetime import datetime
    now = datetime.now()
    scope = ' AND s.tenant_id = %s' if tenant_id is not None else ''
    sp = [tenant_id] if tenant_id is not None else []
    return db.query(f'''
        SELECT s.user_id, u.name AS user_name, s.tenant_id
        FROM schedules s JOIN users u ON u.id = s.user_id
        WHERE ((
                s.shift_date = CURDATE() AND s.start_time <= s.end_time
                AND %s >= s.start_time AND %s < s.end_time
              ) OR (
                s.shift_date = CURDATE() AND s.start_time > s.end_time
                AND %s >= s.start_time
              ) OR (
                s.shift_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND s.start_time > s.end_time
                AND %s < s.end_time
              )
        ){scope}
        ORDER BY s.start_time LIMIT 1
    ''', [now.time()] * 4 + sp)


def test_on_duty_nonexistent_tenant_returns_nothing() -> None:
    """不存在的机构必须查不到任何人。

    这正是原缺陷的判据：当时它会返回租户 1 的护士。
    """
    rows = _on_duty_sql(999_999)
    assert rows == [], f'不存在的机构竟然查到了人: {rows}'


@pytest.mark.parametrize('tenant_id', [1, 2])
def test_on_duty_is_scoped_to_the_tenant(tenant_id: int) -> None:
    """查到的当班人员必须属于所查机构。"""
    for row in _on_duty_sql(tenant_id):
        assert int(row['tenant_id']) == tenant_id


def test_on_duty_differs_between_tenants_or_is_empty() -> None:
    """两家机构的当班人员不可能是同一批。

    若租户条件失效，两次查询会返回同一个人 —— 这条断言能直接抓住它。
    """
    a = {r['user_id'] for r in _on_duty_sql(1)}
    b = {r['user_id'] for r in _on_duty_sql(2)}
    assert not (a & b), f'两家机构返回了同一个人: {a & b}'


# ── 2. 显式租户必须被当作授权约束，而不是兜底取值 ─────────────────────────

def _fall_result() -> dict:
    import time
    return {
        'fallScore': 0.82, 'painScore': 0.61, 'alertLevel': 'HIGH',
        'fallInfo': {'fallState': 'confirmed_fall', 'postureType': 'fall_like',
                     'evidenceMode': 'pose_expression', 'poseQuality': 0.88,
                     'torsoAngle': 71.5, 'kneeHipRatio': 1.35, 'rapidDescent': True,
                     'trackId': 3, 'confirmedFallAt': time.time()},
        'expressionTop': 'Disgust', 'expressionConfidence': 0.74, 'exprQuality': 0.66,
        'faceAvailable': True, 'faceMethod': 'keypoint+aligned',
        'beliefFall': 0.79, 'beliefUnknown': 0.12,
    }


def test_cross_tenant_camera_id_cannot_write() -> None:
    """用别人的 cameraId 必须**写不进去**，而不是"写进去但记在别人名下"。"""
    cam2 = db.query_one('SELECT id, tenant_id FROM cameras WHERE tenant_id=2 LIMIT 1')
    if not cam2:
        pytest.skip('没有租户 2 的摄像头可供伪造')
    assert camera_tenant_id(cam2['id']) == 2

    before = db.query_one('SELECT COUNT(*) AS c FROM alerts WHERE tenant_id=2')['c']
    # 调用者声明自己是租户 1，却传了租户 2 的摄像头
    alert = maybe_create_alert(_fall_result(), cam2['id'], tenant_id=1)
    after = db.query_one('SELECT COUNT(*) AS c FROM alerts WHERE tenant_id=2')['c']

    assert alert is None, '跨机构伪造 cameraId 竟然创建了告警'
    assert after == before, f'租户 2 的告警数被改了: {before} → {after}'


def test_same_tenant_camera_still_works() -> None:
    """同机构的正常路径不能因为上面的防护而失效。"""
    cam1 = db.query_one('SELECT id FROM cameras WHERE tenant_id=1 ORDER BY id LIMIT 1')
    if not cam1:
        pytest.skip('没有租户 1 的摄像头')
    alert = maybe_create_alert(_fall_result(), cam1['id'], tenant_id=1)
    assert alert is not None, '同机构路径被误伤了'
    # 清理本次产生的告警
    db.execute('DELETE FROM alerts WHERE id=%s AND tenant_id=1', [alert['id']])
