-- ============================================================================
-- 011 · 身份不确定的告警样例（让"不确定"在界面上看得见）
-- ============================================================================
-- 010 铺了多人同房与对应的摄像头，但「告警中心」里一条 ambiguous 告警都没有 ——
-- 那条分支界面上永远走不到，护士也就永远看不到"这条告警不知道是谁"的提示，
-- 更没法确认当事人。功能做了却看不到，等于没做。
--
-- 这些样例的**证据明细与其它种子告警保持一致**（体态/证据模式/姿态质量/
-- 表情/融合信念都填全），因为界面要展示的正是"在证据齐全、跌倒判据明确的情况下，
-- 仍然只是不知道是谁"——这才是身份问题独立的证明。
--
-- identity_candidates 由**房间里的在册老人实时聚合**出来，而不是手写死数据：
-- 这样候选结构与真实代码路径产出的完全一致，前端的渲染逻辑才算真的被验证过。
--
-- 幂等：以「该摄像头是否已有 ambiguous 告警」为准。
-- ============================================================================

INSERT INTO alerts (tenant_id, camera_id, elder_id, identity_method, identity_confidence,
                    identity_candidates, risk_level, confidence, status, alert_time,
                    fall_event_at, posture_type, evidence_mode, fall_score, pain_score,
                    torso_angle, knee_hip_ratio, pose_quality, body_keypoints,
                    rapid_descent, fall_state, track_id,
                    expression_top, expression_confidence, expr_quality,
                    face_available, face_method, belief_fall, belief_unknown, handler_notes)
SELECT c.tenant_id, c.id, NULL, 'ambiguous', 0.000,
       (SELECT JSON_ARRAYAGG(JSON_OBJECT('id', e.id, 'name', e.name, 'bedNo', e.bed_no))
          FROM elders e
         WHERE e.tenant_id = c.tenant_id AND e.room_no = c.room_no AND e.status = 1),
       m.level, m.conf, m.st, m.at,
       m.at, 'fall_like', 'pose_expression', m.fs, m.ps, m.ta, m.khr, m.pq, 15, 1,
       'confirmed_fall', 7,
       m.expr, m.ec, m.eq, 1, 'keypoint+aligned', m.bf, m.bu,
       CONCAT('该房间住 ', m.occ, ' 位老人，未能确定是哪一位，请确认当事人')
FROM cameras c
JOIN (SELECT room_no, COUNT(*) occ FROM elders WHERE tenant_id=1 AND status=1
      GROUP BY room_no HAVING COUNT(*) > 1) r ON r.room_no = c.room_no
JOIN (
  SELECT '301' AS room_no, 'HIGH' AS level, 82 AS conf, 1 AS st,
         DATE_SUB(NOW(), INTERVAL 5 HOUR) AS at, 0.84 AS fs, 0.66 AS ps,
         72.0 AS ta, 1.42 AS khr, 0.880 AS pq, 'Disgust' AS expr, 0.71 AS ec,
         0.690 AS eq, 0.840 AS bf, 0.090 AS bu, 2 AS occ
  UNION ALL SELECT '303', 'HIGH', 79, 0, DATE_SUB(NOW(), INTERVAL 20 HOUR),
         0.81, 0.58, 68.0, 1.31, 0.860, 'Sad', 0.660, 0.650, 0.810, 0.110, 2
  UNION ALL SELECT '401', 'URGENT', 91, 0, DATE_SUB(NOW(), INTERVAL 2 HOUR),
         0.93, 0.88, 84.0, 1.61, 0.910, 'Fear', 0.820, 0.780, 0.910, 0.040, 3
  UNION ALL SELECT '402', 'MEDIUM', 58, 2, DATE_SUB(NOW(), INTERVAL 40 HOUR),
         0.44, 0.52, 52.0, 1.12, 0.830, 'Anger', 0.610, 0.670, 0.520, 0.230, 3
  UNION ALL SELECT '105', 'HIGH', 76, 1, DATE_SUB(NOW(), INTERVAL 30 HOUR),
         0.78, 0.71, 66.0, 1.24, 0.870, 'Sad', 0.690, 0.700, 0.780, 0.130, 2
) m ON m.room_no = c.room_no
WHERE c.tenant_id = 1
  AND NOT EXISTS (SELECT 1 FROM alerts a
                  WHERE a.camera_id = c.id AND a.identity_method = 'ambiguous');

-- ── 租户 2 的样例：只放一条，用来验证跨机构下"不确定"同样成立 ─────────────
INSERT INTO alerts (tenant_id, camera_id, elder_id, identity_method, identity_confidence,
                    identity_candidates, risk_level, confidence, status, alert_time,
                    fall_event_at, posture_type, evidence_mode, fall_score, pain_score,
                    torso_angle, knee_hip_ratio, pose_quality, body_keypoints,
                    rapid_descent, fall_state, track_id,
                    expression_top, expression_confidence, expr_quality,
                    face_available, face_method, belief_fall, belief_unknown, handler_notes)
SELECT 2, c.id, NULL, 'ambiguous', 0.000,
       (SELECT JSON_ARRAYAGG(JSON_OBJECT('id', e.id, 'name', e.name, 'bedNo', e.bed_no))
          FROM elders e
         WHERE e.tenant_id = 2 AND e.room_no = c.room_no AND e.status = 1),
       'HIGH', 74, 0, DATE_SUB(NOW(), INTERVAL 8 HOUR),
       DATE_SUB(NOW(), INTERVAL 8 HOUR), 'fall_like', 'pose_expression', 0.79, 0.63,
       69.0, 1.28, 0.850, 15, 1, 'confirmed_fall', 4,
       'Sad', 0.680, 0.660, 1, 'keypoint+aligned', 0.800, 0.120,
       '该房间住 2 位老人，未能确定是哪一位，请确认当事人'
FROM cameras c
WHERE c.tenant_id = 2 AND c.room_no = '105'
  AND NOT EXISTS (SELECT 1 FROM alerts a
                  WHERE a.camera_id = c.id AND a.identity_method = 'ambiguous');
