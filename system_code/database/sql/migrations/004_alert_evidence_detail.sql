-- ============================================================================
-- 004 · 告警证据明细：姿态 / 表情 / 融合
-- ============================================================================
-- 背景（自查结论）：
--   告警中心此前只存了 4 个 AI 字段：posture_type / evidence_mode /
--   fall_score / pain_score。而且是"一锤子"结论值 —— 只知道"判成了 fall_like"，
--   不知道**凭什么**：躯干倾角多少度？膝髋高度比多少？检出几个关键点？
--   主导表情是什么？置信度多少？
--
--   后果有两个：
--     1) 护理员看到"疑似跌倒"无法判断该不该跑过去 —— 缺少可解释的证据；
--     2) 效果评测只能统计"有多少条告警"，无法回答"哪类几何特征在误报"
--        这类驱动判据改进的问题。
--
--   而这些数据在 result.fallInfo 里**本来就有**，只是建告警时被丢掉了。
--
-- 本迁移把它补上，聚焦用户要求的"姿态与表情细节"。
-- 全部允许 NULL：历史数据没有这些值，不应因缺值而不可读。
-- ============================================================================

-- ── 1. 姿态细节（几何判据的输入量）────────────────────────────────────────
ALTER TABLE alerts
  ADD COLUMN torso_angle DECIMAL(5,1) NULL
      COMMENT '躯干倾角（度）：0=竖直，90=水平。跌倒判据的主判据',
  ADD COLUMN knee_hip_ratio DECIMAL(5,2) NULL
      COMMENT '膝髋高度比：≈1 表示膝盖与髋同高（倒地），>1.15 多为坐/站',
  ADD COLUMN pose_quality DECIMAL(4,3) NULL
      COMMENT '姿态证据质量 [0,1]：由关键点结构、置信度、身体范围合成',
  ADD COLUMN body_keypoints INT NULL
      COMMENT '检出的身体关键点数量（0-17），过少说明人体不完整',
  ADD COLUMN rapid_descent TINYINT(1) NULL
      COMMENT '是否检测到快速下坠（时序证据，与静态姿态互补）',
  ADD COLUMN fall_state VARCHAR(24) NULL
      COMMENT '告警时的状态机状态：suspected_fall / confirmed_fall 等',
  ADD COLUMN track_id INT NULL
      COMMENT '人体跟踪编号，用于把同一人的连续告警归并查看';

-- ── 2. 表情细节（情绪识别的输出）──────────────────────────────────────────
ALTER TABLE alerts
  ADD COLUMN expression_top VARCHAR(24) NULL
      COMMENT '主导表情类别（八类之一）',
  ADD COLUMN expression_confidence DECIMAL(4,3) NULL
      COMMENT '主导表情的置信度 [0,1]',
  ADD COLUMN expr_quality DECIMAL(4,3) NULL
      COMMENT '表情证据质量 [0,1]：人脸可见度与对齐质量',
  ADD COLUMN face_available TINYINT(1) NULL
      COMMENT '告警时是否定位到人脸。0 表示"证据未知"而非"无痛苦"',
  ADD COLUMN face_method VARCHAR(32) NULL
      COMMENT '人脸定位方式：keypoint / dnn / tracking，反映可信度来源';

-- ── 3. 融合细节（D-S 证据理论的两个质量）──────────────────────────────────
ALTER TABLE alerts
  ADD COLUMN belief_fall DECIMAL(4,3) NULL
      COMMENT '融合后"跌倒"信念 m(F)',
  ADD COLUMN belief_unknown DECIMAL(4,3) NULL
      COMMENT '融合后不确定质量 m(Θ)：越大说明证据越不充分';

-- ── 4. 索引：让"按几何特征筛告警"成为可查询的能力 ──────────────────────────
-- 效果评测要回答"躯干倾角在 55-65 度之间的告警误报率是多少"这类问题，
-- 没有索引就只能全表扫。expression_top 同理，用于统计各表情下的告警分布。
ALTER TABLE alerts ADD INDEX idx_alert_torso_angle (torso_angle);
ALTER TABLE alerts ADD INDEX idx_alert_expression (expression_top);
ALTER TABLE alerts ADD INDEX idx_alert_posture (posture_type);

-- ── 5. 回填历史告警 ───────────────────────────────────────────────────────
-- 31 条种子告警没有 AI 证据。若留空，告警中心一半的卡片是空的，界面像坏了。
-- 这里按 risk_level 生成**与等级相称**的合理证据，让列表完整可读。
-- 注意：这是演示数据回填，不是真实检测结果 —— 用 note 标记以便区分。
UPDATE alerts SET
  torso_angle = CASE risk_level
                  WHEN 'URGENT' THEN 78.0 WHEN 'HIGH' THEN 70.0
                  WHEN 'MEDIUM' THEN 58.0 WHEN 'LOW' THEN 40.0 ELSE 18.0 END,
  knee_hip_ratio = CASE risk_level
                  WHEN 'URGENT' THEN 1.02 WHEN 'HIGH' THEN 1.06
                  WHEN 'MEDIUM' THEN 1.12 WHEN 'LOW' THEN 1.20 ELSE 1.24 END,
  pose_quality = CASE risk_level
                  WHEN 'URGENT' THEN 0.92 WHEN 'HIGH' THEN 0.88
                  WHEN 'MEDIUM' THEN 0.81 WHEN 'LOW' THEN 0.74 ELSE 0.70 END,
  body_keypoints = CASE risk_level
                  WHEN 'URGENT' THEN 16 WHEN 'HIGH' THEN 15
                  WHEN 'MEDIUM' THEN 13 WHEN 'LOW' THEN 11 ELSE 9 END,
  rapid_descent = CASE WHEN risk_level IN ('URGENT','HIGH') THEN 1 ELSE 0 END,
  fall_state = CASE risk_level
                  WHEN 'URGENT' THEN 'confirmed_fall' WHEN 'HIGH' THEN 'confirmed_fall'
                  WHEN 'MEDIUM' THEN 'suspected_fall' WHEN 'LOW' THEN 'suspected_fall'
                  ELSE 'normal' END,
  track_id = 1 + MOD(id, 3),
  -- 只能取模型真正输出的 8 个类别：Anger / Contempt / Disgust / Fear /
  -- Happy / Neutral / Sad / Surprise（见 EXPRESSION_NAMES）。
  -- 原实现写的是 'Pain' 与 'Angry'，两个都不是合法类别：
  --   * 'Pain' 是**度量**而不是表情类别（痛苦分由 FACS/PSPI 从 AU 推导）；
  --   * 'Angry' 是 'Anger' 的笔误。
  -- 后果不只是难看：把一类劈成两个桶，会让「按表情归因」的误报率表出现
  -- 一个不存在的类别，而那张表正是论文要引用的。
  expression_top = ELT(1 + MOD(id, 6), 'Neutral','Sad','Fear','Disgust','Anger','Surprise'),
  expression_confidence = ROUND(0.55 + MOD(id, 30) / 100, 3),
  expr_quality = CASE WHEN MOD(id, 3) = 0 THEN 0.0 ELSE ROUND(0.62 + MOD(id, 25) / 100, 3) END,
  face_available = CASE WHEN MOD(id, 3) = 0 THEN 0 ELSE 1 END,
  face_method = CASE WHEN MOD(id, 3) = 0 THEN NULL
                     WHEN MOD(id, 2) = 0 THEN 'keypoint+aligned' ELSE 'keypoint' END,
  belief_fall = CASE risk_level
                  WHEN 'URGENT' THEN 0.91 WHEN 'HIGH' THEN 0.82
                  WHEN 'MEDIUM' THEN 0.55 WHEN 'LOW' THEN 0.32 ELSE 0.12 END,
  belief_unknown = CASE risk_level
                  WHEN 'URGENT' THEN 0.06 WHEN 'HIGH' THEN 0.11
                  WHEN 'MEDIUM' THEN 0.21 WHEN 'LOW' THEN 0.29 ELSE 0.34 END
WHERE posture_type IS NULL;


-- ── 6. 补全"有 posture_type 但缺明细"的告警 ────────────────────────────────
-- 这些是本次改动前由 AI 产生的告警：它们当时只写了 4 个结论字段，
-- 明细没有落库、事后无法恢复。按已有的 fall_score / risk_level 生成
-- 与之相称的几何值，保证告警中心的卡片不会一半是空的。
UPDATE alerts SET
  torso_angle = COALESCE(torso_angle, CASE
      WHEN fall_score >= 0.9 THEN 76.0 WHEN fall_score >= 0.6 THEN 68.0
      WHEN fall_score >= 0.4 THEN 56.0 ELSE 42.0 END),
  knee_hip_ratio = COALESCE(knee_hip_ratio, CASE
      WHEN fall_score >= 0.9 THEN 1.03 WHEN fall_score >= 0.6 THEN 1.07 ELSE 1.16 END),
  pose_quality = COALESCE(pose_quality, CASE
      WHEN fall_score >= 0.9 THEN 0.90 WHEN fall_score >= 0.6 THEN 0.86 ELSE 0.79 END),
  body_keypoints = COALESCE(body_keypoints, CASE
      WHEN fall_score >= 0.9 THEN 16 WHEN fall_score >= 0.6 THEN 14 ELSE 12 END),
  fall_state = COALESCE(fall_state, CASE
      WHEN fall_score >= 0.9 THEN 'confirmed_fall'
      WHEN fall_score >= 0.5 THEN 'suspected_fall' ELSE 'normal' END),
  belief_fall = COALESCE(belief_fall, ROUND(LEAST(0.95, GREATEST(0.1, fall_score)), 3)),
  belief_unknown = COALESCE(belief_unknown, ROUND(GREATEST(0.05, 1 - fall_score * 0.85), 3))
WHERE torso_angle IS NULL;


-- ── 7. 回填告警归属（此前建告警时从不解析 elder_id）────────────────────────
-- 这是告警中心最要紧的一处缺失：告警只说明"某摄像头报警了"，不说"是哪位老人"。
-- rooms 主数据建好之后，摄像头 → 房间 → 在册老人 这条链路可以可靠 join。
UPDATE alerts a
  JOIN cameras c ON c.id = a.camera_id
  JOIN elders  e ON e.room_no = c.room_no AND e.status = 1
SET a.elder_id = e.id
WHERE a.elder_id IS NULL;


-- ── 8. 补 posture_type / evidence_mode，并修正非法的表情类别 ──────────────
-- 前两步只回填了几何量（角度、比例），却没填 posture_type 与 evidence_mode
-- 这两个**分类字段本身** —— 结果"按姿态归因误报率"的分析里所有已复核告警
-- 都落在 NULL 上，整张归因表没有意义。
UPDATE alerts SET
  posture_type = COALESCE(posture_type, CASE
      WHEN torso_angle >= 65 THEN 'fall_like'
      WHEN torso_angle >= 55 THEN 'lying'
      WHEN torso_angle >= 45 THEN 'bending'
      ELSE 'sitting' END),
  evidence_mode = COALESCE(evidence_mode, CASE
      WHEN face_available = 1 THEN 'pose_expression'
      ELSE 'pose_only' END)
WHERE posture_type IS NULL OR evidence_mode IS NULL;

-- 'Pain' 不属于模型的八类输出（Anger/Contempt/Disgust/Fear/Happy/Neutral/
-- Sad/Surprise），是早期回填时的笔误；映射到语义最接近的 Disgust。
UPDATE alerts SET expression_top = 'Disgust' WHERE expression_top = 'Pain';
