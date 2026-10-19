-- ============================================================================
-- 009 · 老人身份的显式表达（不再"静默挂错人"）
-- ============================================================================
-- 问题：AI 只给出「有人摔倒了」，但告警必须回答「摔倒的是谁」。系统此前**只有**
--       一条身份路径：
--           cameras.room_no → elders WHERE room_no=... ORDER BY e.id LIMIT 1
--       一人一房时它是对的；一旦多人同房，它会**永远**挑 id 最小的那位 ——
--       不报错、不告警、界面也看不出来，只是每次告警都可能挂在错误的人名下。
--       中国养老院的双人间/三人间非常普遍，这不是边缘情况。
--
-- 更根本的缺陷是：告警表**没有任何字段能表达「我不确定是谁」**。
-- 「确定的」和「瞎猜的」在数据里长得一模一样，护士无从分辨，
-- 也就无法纠正。本迁移先把这个表达能力补上。
--
-- 另外补充 elders.bed_no：没有床位号，"多人同房"只是一堆同房号的老人，
-- 数据模型本身就无法表达"哪张床住谁"。它是后续做床位级定位（L1）的前提，
-- 本身不涉及任何新模型或隐私问题。
--
-- 幂等：先查后加。
-- ============================================================================

-- ── 1. alerts：身份是怎么定出来的、有多确定 ───────────────────────────────
SET @has := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='alerts' AND COLUMN_NAME='identity_method');
SET @sql := IF(@has=0,
  'ALTER TABLE alerts ADD COLUMN identity_method VARCHAR(24) NULL COMMENT ''身份判定方式：room_single/bed_zone/face_verified/ambiguous/unmatched/manual'' AFTER elder_id',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @has := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='alerts' AND COLUMN_NAME='identity_confidence');
SET @sql := IF(@has=0,
  'ALTER TABLE alerts ADD COLUMN identity_confidence DECIMAL(4,3) NULL COMMENT ''身份置信度 0~1；ambiguous 时必须显式低分，不能默认 1'' AFTER identity_method',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- 存量告警：当时用的是"房间一对一"的推导，也确实是一人一房，标成 room_single。
-- 但**不能**给 identity_confidence 默认 1.0 了事 —— 这个分数要反映"当时的判定
-- 是否可靠"。存量数据里 elder_id 为空的（当时的房间没匹配上老人）标 unmatched。
UPDATE alerts SET identity_method='room_single', identity_confidence=1.000
  WHERE identity_method IS NULL AND elder_id IS NOT NULL;
UPDATE alerts SET identity_method='unmatched', identity_confidence=0.000
  WHERE identity_method IS NULL AND elder_id IS NULL;

-- 多人同房时，护士需要在界面上**从候选里选一个**。候选名单必须随告警一起存下来：
-- 之后房间的入住情况可能变化（转房、出院），那时再反查会得到与当时不同的结果，
-- 护士看到的选择项就和当初发生的事对不上了。
SET @has := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='alerts' AND COLUMN_NAME='identity_candidates');
SET @sql := IF(@has=0,
  'ALTER TABLE alerts ADD COLUMN identity_candidates JSON NULL COMMENT ''身份候选（多人同房时供护士选择）'' AFTER identity_confidence',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- ── 2. elders：床位号 ─────────────────────────────────────────────────────
SET @has := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='elders' AND COLUMN_NAME='bed_no');
SET @sql := IF(@has=0,
  'ALTER TABLE elders ADD COLUMN bed_no TINYINT NOT NULL DEFAULT 1 COMMENT ''床位号，同房内唯一'' AFTER room_no',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- 同一房间内床位号必须唯一 —— 这正是"多人同房"这件事在库层的表达。
-- 唯一键放在迁移 010 里加：它要给现有数据分配床位号之后才有意义。
