import json
import logging
from datetime import datetime
from typing import Any

from app.core.database import db
from app.core.tenant import context_tenant_id
from app.repositories.base import keys_to_camel
from app.services.alert_levels import stored_risk_level
from app.services.notifications import notify_alert

logger = logging.getLogger(__name__)


def build_prediction(result: dict[str, Any]) -> dict[str, Any]:
    fall_score = float(result.get('fallScore') or 0)
    pain_score = float(result.get('painScore') or 0)
    alert_level = str(result.get('alertLevel') or 'NORMAL').upper()
    fall_info = result.get('fallInfo') or {}
    fall_state = str(fall_info.get('fallState') or fall_info.get('fall_state') or 'normal')
    posture_type = str(fall_info.get('postureType') or fall_info.get('posture_type') or fall_info.get('status') or 'unknown')
    evidence_mode = str(fall_info.get('evidenceMode') or fall_info.get('evidence_mode') or 'unknown')
    reason = str(fall_info.get('reason') or '')
    emotion_alert_level = str(fall_info.get('emotionAlertLevel') or fall_info.get('emotion_alert_level') or 'NORMAL')
    is_fall = fall_state == 'confirmed_fall'
    is_pain = pain_score >= 0.5
    summary = (
        f'证据模式 {evidence_mode}，姿态 {posture_type}/{fall_state}，'
        f'跌倒评分 {fall_score:.2f}，痛苦评分 {pain_score:.2f}，风险 {alert_level}'
    )
    if reason:
        summary = f'{summary}。原因：{reason}'
    if is_fall:
        confidence_score = fall_score
    elif fall_state == 'suspected_fall':
        confidence_score = min(fall_score, 0.75)
    elif fall_state == 'occluded_after_fall':
        confidence_score = max(min(fall_score, 0.9), 0.8)
    elif is_pain:
        confidence_score = pain_score
    else:
        confidence_score = 0
    # Fall-event identity: a fall episode is delimited by confirmed_fall_at
    # (set on confirmation, cleared on recovery). A continuous fall should be
    # ONE alert, not one per 60-second dedup window.
    fall_event_at = None
    confirmed = fall_info.get('confirmedFallAt') or fall_info.get('confirmed_fall_at')
    if confirmed:
        try:
            fall_event_at = datetime.fromtimestamp(float(confirmed))
            # The alerts.fall_event_at column is DATETIME (second precision), so
            # MySQL truncates fractional seconds on write. Without truncating
            # here, the dedup query re-sends the microsecond value and never
            # matches the stored second-precision row -> duplicate alerts for
            # the same fall event. Truncate so insert and dedup compare equal.
            fall_event_at = fall_event_at.replace(microsecond=0)
        except (TypeError, ValueError, OSError):
            fall_event_at = None

    # ── 姿态与表情明细 ────────────────────────────────────────────────
    # 这些值在 result.fallInfo 里本来就有，此前建告警时被丢掉了，只留下
    # "判成了 fall_like" 这种一锤子结论。护理员看到"疑似跌倒"无法判断该不该
    # 跑过去，效果评测也无法回答"哪类几何特征在误报"。全部抽取并落库。
    def _f(*keys):
        for k in keys:
            v = fall_info.get(k)
            if v is not None and v != '':
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
        return None

    def _i(*keys):
        v = _f(*keys)
        return int(v) if v is not None else None

    expressions = result.get('expressions') or []
    top_expr = None
    top_conf = None
    if expressions:
        best = max(expressions, key=lambda e: float(e.get('confidence') or 0))
        top_expr = best.get('className') or best.get('class_name')
        try:
            top_conf = round(float(best.get('confidence') or 0), 3)
        except (TypeError, ValueError):
            top_conf = None

    face_available = bool(result.get('faceAvailable'))
    return {
        'isFall': is_fall,
        'isPain': is_pain,
        'riskLevel': alert_level,
        'confidence': int(round(confidence_score * 100)),
        'emotionAlertLevel': emotion_alert_level,
        'summary': summary,
        'fallEventAt': fall_event_at,
        # Structured detection fields, persisted so the feedback loop can
        # analyse *why* an alert fired (posture / evidence mode / scores)
        # instead of parsing the free-text summary.
        'postureType': posture_type,
        'evidenceMode': evidence_mode,
        'fallScore': round(fall_score, 3),
        'painScore': round(pain_score, 3),
        # ── 姿态细节（几何判据的输入量）──
        'torsoAngle': _f('torsoAngle', 'torso_angle', 'headHipAngle'),
        'kneeHipRatio': _f('kneeHipRatio', 'knee_hip_ratio'),
        'poseQuality': _f('poseQuality', 'pose_quality'),
        'bodyKeypoints': _i('bodyKeypoints', 'body_keypoints'),
        'rapidDescent': 1 if (fall_info.get('rapidDescent') or fall_info.get('rapid_descent')) else 0,
        'fallState': fall_state,
        'trackId': _i('trackId', 'track_id'),
        # ── 表情细节（情绪识别的输出）──
        'expressionTop': top_expr,
        'expressionConfidence': top_conf,
        'exprQuality': _f('exprQuality', 'expr_quality') or 0.0,
        'faceAvailable': 1 if face_available else 0,
        'faceMethod': result.get('faceMethod'),
        # ── 融合与证据质量 ──
        'beliefFall': _f('beliefFall', 'belief_fall'),
        'beliefUnknown': _f('beliefUnknown', 'belief_unknown'),
    }


def attach_prediction(result: dict[str, Any]) -> dict[str, Any]:
    result['prediction'] = build_prediction(result)
    return result


def camera_tenant_id(camera_id: int | None) -> int | None:
    """由摄像头反查所属机构 —— AI 主链路的租户来源。

    告警是**引擎自动产生**的，没有登录用户可依据，所以租户只能从摄像头推。
    摄像头本身就是分机构的资产（cameras.tenant_id），这条推导链是可信的。
    """
    if camera_id is None:
        return None
    row = db.query_one('SELECT tenant_id FROM cameras WHERE id=%s', [camera_id])
    return int(row['tenant_id']) if row and row.get('tenant_id') is not None else None


def resolve_identity_by_camera(camera_id: int | None,
                               tenant_id: int | None = None) -> dict[str, Any]:
    """由摄像头推导老人身份，并**明确区分"确定"和"不确定"**。

    此前建告警时**完全没有设置 elder_id** —— 告警只说明"某摄像头报警了"，
    却不说"是哪位老人"，护理员拿到后还得自己去查房间对应关系。

    **多租户修正**：租户化之后 room_no 只在机构内唯一（两家机构都有"101 房"），
    所以 `e.room_no = c.room_no` 这个 join 会跨机构匹配到**另一家机构**的老人。
    必须同时约束 tenant_id，否则第二家机构的告警会被挂到第一家机构的老人名下。

    **多人同房的修正（本次）**：原实现是 `ORDER BY e.id LIMIT 1` —— 一个房间住
    两位老人时，它会**永远**挑 id 较小的那位，不报错、不告警、界面上也看不出，
    只是每次告警都可能挂在错误的人名下。中国养老院的双人间/三人间很普遍。
    现在改为：房间只有一位在册老人时才给出 elder_id；多人时返回
    ``method='ambiguous'`` 且 **elder_id 为 None**，把候选名单交给护士确认。
    「不知道」是一个合法的答案，而"猜一个"不是。

    返回::

        {'elderId': int|None, 'method': str, 'confidence': float,
         'candidates': [{'id','name','bedNo'}], 'roomNo': str|None}
    """
    if camera_id is None:
        # 浏览器/手动检测没有摄像头，无从推导
        return {'elderId': None, 'method': 'no_camera', 'confidence': 0.0,
                'candidates': [], 'roomNo': None}

    tid = tenant_id if tenant_id is not None else camera_tenant_id(camera_id)
    if tid is None:
        return {'elderId': None, 'method': 'unmatched', 'confidence': 0.0,
                'candidates': [], 'roomNo': None}

    room = db.query_one('SELECT room_no FROM cameras WHERE id=%s', [camera_id])
    room_no = room['room_no'] if room else None

    rows = db.query(
        '''SELECT e.id, e.name, e.bed_no FROM cameras c
           JOIN elders e ON e.room_no = c.room_no AND e.tenant_id = c.tenant_id
           WHERE c.id = %s AND e.tenant_id = %s AND e.status = 1
           ORDER BY e.bed_no, e.id''',
        [camera_id, tid],
    )

    if len(rows) == 1:
        return {'elderId': int(rows[0]['id']), 'method': 'room_single',
                'confidence': 1.0, 'candidates': [], 'roomNo': room_no}

    if not rows:
        # 房间没登记老人（空房、老人已出院）。仍然建档，但身份标记为未匹配 ——
        # 这类告警很可能指向"房间里有人但不是在册老人"，不该被静默忽略。
        return {'elderId': None, 'method': 'unmatched', 'confidence': 0.0,
                'candidates': [], 'roomNo': room_no}

    candidates = [{'id': int(r['id']), 'name': r.get('name'),
                   'bedNo': r.get('bed_no')} for r in rows]
    return {'elderId': None, 'method': 'ambiguous', 'confidence': 0.0,
            'candidates': candidates, 'roomNo': room_no}


def resolve_elder_by_camera(camera_id: int | None,
                            tenant_id: int | None = None) -> int | None:
    """兼容包装：只要 elder_id。多人同房时返回 None（**不再瞎猜**）。

    调用方若需要区分"没人"和"人太多"，请直接用 ``resolve_identity_by_camera``。
    """
    return resolve_identity_by_camera(camera_id, tenant_id)['elderId']


def _dedup_query(camera_id: int | None, fall_event_at=None,
                 tenant_id: int | None = None) -> tuple[str, list]:
    """Build the unresolved-alert dedup lookup.

    Two modes:

    * ``fall_event_at`` given (a confirmed fall episode): dedup on the SAME
      fall event (same camera + same event identity), so one continuous fall
      produces exactly one alert regardless of duration.
    * otherwise: rate-limit to a 60-second window (pain-only / suspected
      alerts).

    Handles ``camera_id=None`` (browser/manual detections) with a NULL-safe
    comparison; ``camera_id = NULL`` never matches in SQL, so it must be
    ``camera_id IS NULL``.
    """
    where = "camera_id=%s" if camera_id is not None else "camera_id IS NULL"
    args = [camera_id] if camera_id is not None else []
    if tenant_id is not None:
        where += " AND tenant_id=%s"
        args.append(tenant_id)
    # SELECT the columns needed to decide whether to escalate an existing alert.
    if fall_event_at is not None:
        where += " AND fall_event_at=%s"
        args.append(fall_event_at)
        sql = (f"SELECT id, risk_level, confidence FROM alerts WHERE {where} AND status=0 "
               "ORDER BY alert_time DESC LIMIT 1")
    else:
        sql = (
            f"SELECT id, risk_level, confidence FROM alerts WHERE {where} AND status=0 "
            "AND alert_time >= DATE_SUB(NOW(), INTERVAL 60 SECOND) "
            "ORDER BY alert_time DESC LIMIT 1"
        )
    return sql, args


_RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "URGENT": 4}


def _should_escalate(existing_level, existing_conf, new_level, new_conf) -> bool:
    """Whether a new detection is more severe than an already-stored alert.

    A continuous fall that starts HIGH and later escalates to URGENT (e.g. a
    stable pain face is finally detected) must update the existing row rather
    than leave the original level in the alert history.
    """
    new_order = _RISK_ORDER.get(str(new_level or "").upper(), 0)
    existing_order = _RISK_ORDER.get(str(existing_level or "").upper(), 0)
    if new_order > existing_order:
        return True
    if new_order == existing_order and int(new_conf or 0) > int(existing_conf or 0):
        return True
    return False


def maybe_create_alert(result: dict[str, Any], camera_id: int | None,
                       tenant_id: int | None = None) -> dict[str, Any] | None:
    prediction = build_prediction(result)
    stored_level = stored_risk_level(prediction['riskLevel'])
    if stored_level is None:
        return None

    # ── 租户归属与「越权写入」防护 ────────────────────────────────────────
    # 旧实现是 `camera_tenant_id(camera_id) or tenant_id or context_tenant_id()`：
    # **摄像头所属机构优先于调用者机构**，且全程不校验这个摄像头是不是调用者的。
    # 于是一个已登录用户只要在请求体里写别人的 cameraId，就能把告警写进**别的机构**：
    # 实测（调用者=租户1）POST /api/python/detect 带 cameraId=102（租户2 的摄像头）
    # → 落库告警 tenant_id=2、camera_id=102、elder_id=102（租户2 的真实老人），
    # 并推送给租户2 的 SSE 订阅者。即任意登录用户可向他机构注入临床告警记录。
    #
    # 现在把显式传入的 tenant_id 当作**授权约束**而不是"兜底取值"：
    # 摄像头所属机构与调用者机构不一致时直接拒绝，绝不落库。
    # 引擎自动路径（无调用者）不受影响，仍按摄像头推导。
    camera_tid = camera_tenant_id(camera_id)
    caller_tid = tenant_id if tenant_id is not None else context_tenant_id(required=False)
    if camera_tid is not None and caller_tid is not None and camera_tid != caller_tid:
        logger.warning('refuse cross-tenant alert: camera=%s belongs to tenant %s, '
                       'but caller is tenant %s', camera_id, camera_tid, caller_tid)
        return None
    tenant_id = camera_tid or caller_tid
    if tenant_id is None:
        # 拿不到机构就不落库：alerts.tenant_id 是 NOT NULL，且一条无归属的告警
        # 之后谁也看不到（任何机构的列表都查不到它），等于静默丢数据。
        logger.warning('drop alert: cannot resolve tenant (camera_id=%s)', camera_id)
        return None

    fall_event_at = prediction.get('fallEventAt')
    confidence = prediction['confidence']
    dedup_sql, dedup_args = _dedup_query(camera_id, fall_event_at, tenant_id)
    rows = db.query(dedup_sql, dedup_args)
    if rows:
        existing = rows[0]
        if _should_escalate(existing.get('risk_level'), existing.get('confidence'),
                            stored_level, confidence):
            db.execute(
                'UPDATE alerts SET risk_level=%s, confidence=%s WHERE id=%s',
                [stored_level, confidence, existing['id']],
            )
            updated = db.query('SELECT * FROM alerts WHERE id=%s LIMIT 1', [existing['id']])
            alert = keys_to_camel(updated[0]) if updated else keys_to_camel(existing)
            notify_alert(alert, reason='escalated')
            return alert
        return keys_to_camel(existing)

    # 身份：确定才写 elder_id，不确定就把候选交给护士
    identity = resolve_identity_by_camera(camera_id, tenant_id)
    if identity['method'] == 'ambiguous':
        logger.info('alert identity ambiguous: camera=%s room=%s candidates=%d',
                    camera_id, identity['roomNo'], len(identity['candidates']))

    alert_id = db.insert(
        '''INSERT INTO alerts (tenant_id, camera_id, elder_id, identity_method, identity_confidence,
                               identity_candidates, risk_level, confidence, status, handler_notes, fall_event_at,
                               posture_type, evidence_mode, fall_score, pain_score,
                               torso_angle, knee_hip_ratio, pose_quality, body_keypoints,
                               rapid_descent, fall_state, track_id,
                               expression_top, expression_confidence, expr_quality,
                               face_available, face_method,
                               belief_fall, belief_unknown)
           VALUES (
             %s, %s, %s, %s, %s, %s,          -- tenant_id, camera_id, elder_id ×3
             %s, %s, 0, %s, %s,               -- risk_level, confidence, status=0, notes, fall_event_at
             %s, %s, %s, %s,                  -- posture_type, evidence_mode, fall_score, pain_score
             %s, %s, %s, %s,                  -- torso_angle, knee_hip_ratio, pose_quality, body_keypoints
             %s, %s, %s,                      -- rapid_descent, fall_state, track_id
             %s, %s, %s,                      -- expression_top, expression_confidence, expr_quality
             %s, %s,                          -- face_available, face_method
             %s, %s)                          -- belief_fall, belief_unknown
           ''',
        [tenant_id, camera_id, identity['elderId'],
         identity['method'], identity['confidence'],
         json.dumps(identity['candidates'], ensure_ascii=False) if identity['candidates'] else None,
         stored_level, prediction['confidence'], prediction['summary'], fall_event_at,
         prediction.get('postureType'), prediction.get('evidenceMode'),
         prediction.get('fallScore'), prediction.get('painScore'),
         prediction.get('torsoAngle'), prediction.get('kneeHipRatio'),
         prediction.get('poseQuality'), prediction.get('bodyKeypoints'),
         prediction.get('rapidDescent'), prediction.get('fallState'),
         prediction.get('trackId'),
         prediction.get('expressionTop'), prediction.get('expressionConfidence'),
         prediction.get('exprQuality'), prediction.get('faceAvailable'),
         prediction.get('faceMethod'),
         prediction.get('beliefFall'), prediction.get('beliefUnknown')],
    )
    alert = db.query('SELECT * FROM alerts WHERE id=%s LIMIT 1', [alert_id])
    if alert:
        payload = keys_to_camel(alert[0])
        notify_alert(payload, reason='new')
        return payload
    return None
