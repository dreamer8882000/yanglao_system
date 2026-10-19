-- ============================================================================
-- 006 · 系统配置按机构隔离
-- ============================================================================
-- 背景：005 把 15 张业务表加上了 tenant_id，但 settings 表仍是**全局唯一键**，
--       于是留下一个隐蔽的越权面：
--         * 任一机构的管理员改「AI 参数 / 通知配置」，会同时改掉所有机构的配置；
--         * PUT /settings/yolo-model 更直接 —— 它执行的是
--           `UPDATE cameras SET yolo_model=...`（无条件），一次调用把**全部机构
--           的摄像头**推理模型都换掉。
--       settings 表原本用 `UNIQUE KEY setting_key(setting_key)`，在单租户下正确，
--       在多租户下等于强制所有机构共用一份配置。
--
-- 改法：把唯一键从 (setting_key) 改为 (tenant_id, setting_key)，与 rooms 的
--       (tenant_id, room_no) 同一思路 —— 每个机构各自持有同名配置键。
--
-- 幂等：先查后加，可重复执行。
-- ============================================================================

-- ── 1. 加列 ────────────────────────────────────────────────────────────────
SET @has_tenant := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'settings' AND COLUMN_NAME = 'tenant_id'
);
SET @sql := IF(@has_tenant = 0,
  'ALTER TABLE settings ADD COLUMN tenant_id INT NULL COMMENT ''所属机构'' AFTER id',
  'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 存量配置归属第一家机构（阳光养老院）
UPDATE settings SET tenant_id = 1 WHERE tenant_id IS NULL;

ALTER TABLE settings MODIFY COLUMN tenant_id INT NOT NULL COMMENT '所属机构';

-- ── 2. 换唯一键：setting_key → (tenant_id, setting_key) ────────────────────
-- 顺序很重要：先加复合唯一键，再删旧键。反过来的话中途一旦失败，
-- 就会留下"没有任何唯一约束"的表，ON DUPLICATE KEY UPDATE 会静默退化成
-- 每次插入新行（配置越改越多，且读到的总是任意一条）。
SET @has_uk := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'settings' AND INDEX_NAME = 'uk_settings_tenant_key'
);
SET @sql := IF(@has_uk = 0,
  'ALTER TABLE settings ADD UNIQUE KEY uk_settings_tenant_key (tenant_id, setting_key)',
  'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_old := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'settings' AND INDEX_NAME = 'setting_key'
);
SET @sql := IF(@has_old > 0, 'ALTER TABLE settings DROP INDEX setting_key', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── 3. 外键 + 索引 ─────────────────────────────────────────────────────────
SET @has_fk := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'settings'
    AND CONSTRAINT_NAME = 'fk_settings_tenant' AND CONSTRAINT_TYPE = 'FOREIGN KEY'
);
SET @sql := IF(@has_fk = 0,
  'ALTER TABLE settings ADD CONSTRAINT fk_settings_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)',
  'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_idx := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'settings' AND INDEX_NAME = 'idx_settings_tenant'
);
SET @sql := IF(@has_idx = 0, 'ALTER TABLE settings ADD KEY idx_settings_tenant (tenant_id)', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── 4. 第二家机构也要有一份可用的配置基线 ──────────────────────────────────
INSERT INTO settings (tenant_id, setting_key, setting_value)
SELECT 2, setting_key, setting_value FROM settings WHERE tenant_id = 1
ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);
