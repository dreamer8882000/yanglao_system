-- ============================================================================
-- 005 · 基础多租户：机构隔离
-- ============================================================================
-- 场景：一套系统服务多家养老机构（租户）。每家机构只能看到自己的老人、
--       摄像头、告警、排班、巡查与体征数据，互相完全不可见。
--
-- 设计取舍：
--   * 采用**共享库 + tenant_id 列**（而不是每租户独立库/独立 schema）。
--     理由：本项目的规模是「多机构、每家几十张床位」，独立库会带来
--     迁移、备份、连接池的成倍复杂度，而隔离强度在应用层已足够
--     ——所有查询强制带 tenant_id，跨租户访问一律 404（不泄露"存在性"）。
--   * rooms.room_no 原先是**全局唯一**，多租户下就会冲突（两家机构都有
--     "101 房"）。改为 (tenant_id, room_no) 复合唯一，elders/cameras 的
--     外键同步改成复合外键 —— 这样才能在库层保证"老人只能住本机构的房间"。
--   * tenant_id 一律从**数据库里的用户记录**推导，不信任 JWT 里的快照：
--     令牌有效期 24 小时，期间若用户被调岗/换机构，JWT 会携带过期的租户。
--
-- 幂等：全部先查后加 / IF NOT EXISTS，可重复执行。
-- ============================================================================

-- ── 1. 租户表 ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(32) NOT NULL COMMENT '机构代码，登录与展示用',
  name VARCHAR(64) NOT NULL COMMENT '机构全称',
  contact VARCHAR(32) NULL,
  phone VARCHAR(32) NULL,
  status TINYINT NOT NULL DEFAULT 1 COMMENT '1 正常 / 0 停用',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_tenant_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户（养老机构）';

INSERT INTO tenants (id, code, name, contact, phone) VALUES
  (1, 'SUNSHINE', '阳光养老院', '王主任', '010-8888-0001')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ── 2. 给业务表加 tenant_id ────────────────────────────────────────────────
-- 先加为 NULL 以便回填，随后改 NOT NULL。
-- 注意：MySQL 8 **不支持** ADD COLUMN IF NOT EXISTS（那是 MariaDB 语法，
-- 会直接报语法错并静默导致后续所有步骤失败）。因此这里用普通 ADD COLUMN，
-- 由执行器容忍 "Duplicate column name" 以实现幂等。
ALTER TABLE users         ADD COLUMN tenant_id INT NULL;
ALTER TABLE elders        ADD COLUMN tenant_id INT NULL;
ALTER TABLE cameras       ADD COLUMN tenant_id INT NULL;
ALTER TABLE rooms         ADD COLUMN tenant_id INT NULL;
ALTER TABLE alerts        ADD COLUMN tenant_id INT NULL;
ALTER TABLE schedules     ADD COLUMN tenant_id INT NULL;
ALTER TABLE patrol_records ADD COLUMN tenant_id INT NULL;
ALTER TABLE patrol_tasks  ADD COLUMN tenant_id INT NULL;
ALTER TABLE medications   ADD COLUMN tenant_id INT NULL;
ALTER TABLE medication_records ADD COLUMN tenant_id INT NULL;
ALTER TABLE vital_signs   ADD COLUMN tenant_id INT NULL;
ALTER TABLE vital_alert_rules ADD COLUMN tenant_id INT NULL;
ALTER TABLE messages      ADD COLUMN tenant_id INT NULL;
ALTER TABLE audit_logs    ADD COLUMN tenant_id INT NULL;

-- 既有数据全部归属默认机构（阳光养老院）
UPDATE users SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE elders SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE cameras SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE rooms SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE alerts SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE schedules SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE patrol_records SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE patrol_tasks SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE medications SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE medication_records SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE vital_signs SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE vital_alert_rules SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE messages SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE audit_logs SET tenant_id = 1 WHERE tenant_id IS NULL;

-- ── 3. rooms 的唯一键改为复合，并同步 elders/cameras 的外键 ────────────────
-- 必须先去外键，才能改被引用的唯一键。
ALTER TABLE elders  DROP FOREIGN KEY fk_elder_room;
ALTER TABLE cameras DROP FOREIGN KEY fk_camera_room;
-- patrol_tasks 也引用了 rooms.room_no —— 漏掉它会报
-- 1553 "Cannot drop index 'uk_room_no': needed in a foreign key constraint"
-- DROP FOREIGN KEY 只删约束、**不删它自动创建的索引**；同名索引残留会让
-- 后面的 ADD CONSTRAINT 报 1061 Duplicate key name。因此索引也要一并删掉。
ALTER TABLE patrol_tasks DROP FOREIGN KEY fk_ptask_room;
ALTER TABLE patrol_tasks DROP INDEX fk_ptask_room;
-- v_room_coverage 依赖 rooms.room_no 的旧键，先删视图稍后重建
DROP VIEW IF EXISTS v_room_coverage;

ALTER TABLE rooms DROP INDEX uk_room_no;
ALTER TABLE rooms ADD UNIQUE KEY uk_tenant_room (tenant_id, room_no);

ALTER TABLE rooms ADD CONSTRAINT fk_room_tenant
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

-- 复合外键：老人/摄像头只能引用**本租户**的房间。
-- 这是库层的强隔离 —— 应用层写错 tenant_id 也插不进去。
ALTER TABLE elders ADD CONSTRAINT fk_elder_room
  FOREIGN KEY (tenant_id, room_no) REFERENCES rooms(tenant_id, room_no)
  ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE cameras ADD CONSTRAINT fk_camera_room
  FOREIGN KEY (tenant_id, room_no) REFERENCES rooms(tenant_id, room_no)
  ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE patrol_tasks ADD CONSTRAINT fk_ptask_room
  FOREIGN KEY (tenant_id, room_no) REFERENCES rooms(tenant_id, room_no)
  ON DELETE RESTRICT ON UPDATE CASCADE;

-- ── 4. 其余表的外键与索引 ──────────────────────────────────────────────────
ALTER TABLE users   ADD CONSTRAINT fk_user_tenant   FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;
ALTER TABLE elders  ADD CONSTRAINT fk_elder_tenant  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE cameras ADD CONSTRAINT fk_camera_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE alerts  ADD CONSTRAINT fk_alert_tenant  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE schedules ADD CONSTRAINT fk_sched_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE patrol_records ADD CONSTRAINT fk_patrol_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE patrol_tasks ADD CONSTRAINT fk_ptask_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE medications ADD CONSTRAINT fk_med_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE medication_records ADD CONSTRAINT fk_medrec_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE vital_signs ADD CONSTRAINT fk_vital_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE vital_alert_rules ADD CONSTRAINT fk_vrule_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE messages ADD CONSTRAINT fk_msg_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

-- 租户维度的索引：隔离之后几乎所有查询都带 tenant_id，没有索引会全表扫
ALTER TABLE alerts  ADD INDEX idx_alert_tenant (tenant_id, alert_time);
ALTER TABLE elders  ADD INDEX idx_elder_tenant (tenant_id, status);
ALTER TABLE cameras ADD INDEX idx_camera_tenant (tenant_id, status);
ALTER TABLE patrol_tasks ADD INDEX idx_ptask_tenant (tenant_id, task_date);
ALTER TABLE vital_signs ADD INDEX idx_vital_tenant (tenant_id, record_time);
ALTER TABLE schedules ADD INDEX idx_sched_tenant (tenant_id, shift_date);

-- 房间覆盖视图：同样按租户分组
CREATE OR REPLACE VIEW v_room_coverage AS
SELECT r.tenant_id, r.room_no, r.building, r.floor,
       COUNT(DISTINCT e.id) AS elder_count,
       COUNT(DISTINCT c.id) AS camera_count,
       GROUP_CONCAT(DISTINCT e.name ORDER BY e.id SEPARATOR '、') AS elder_names
FROM rooms r
LEFT JOIN elders  e ON e.room_no = r.room_no AND e.tenant_id = r.tenant_id AND e.status = 1
LEFT JOIN cameras c ON c.room_no = r.room_no AND c.tenant_id = r.tenant_id
GROUP BY r.tenant_id, r.room_no, r.building, r.floor;

-- ── 5. 第二个租户：用来证明隔离确实生效 ────────────────────────────────────
-- 只有一家机构时"隔离"是无法验证的 —— 看不到任何越界数据也无从判断
-- 是真的隔离了，还是本来就没数据。这里造第二家机构，至少能验证：
-- 各自只看到自己的老人/摄像头/告警，房间号可以重名。
INSERT INTO tenants (id, code, name, contact, phone) VALUES
  (2, 'HARMONY', '和睦护理中心', '李院长', '021-6666-0002')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 第二家机构的管理员与护理员（密码沿用 admin/123456 便于演示）
INSERT IGNORE INTO users (id, username, tenant_id, name, email, dept_name, role, password_hash)
SELECT 101, 'hx_admin', 2, '和睦管理员', 'a@harmony.local', '和睦护理中心', 'admin', password_hash
FROM users WHERE username = 'admin' LIMIT 1;
INSERT IGNORE INTO users (id, username, tenant_id, name, email, dept_name, role, password_hash)
SELECT 102, 'hx_nurse', 2, '赵小云', 'n@harmony.local', '和睦护理中心', 'nurse', password_hash
FROM users WHERE username = 'nurse_zhang' LIMIT 1;

-- 第二家机构的房间（房间号与第一家重名，用来验证复合唯一键）
INSERT IGNORE INTO rooms (tenant_id, room_no, building, floor) VALUES
  (2, '101', 'B栋', 1), (2, '102', 'B栋', 1), (2, '201', 'B栋', 2);

-- 第二家机构的老人
INSERT IGNORE INTO elders (id, tenant_id, name, gender, age, room_no, admission_date,
                           health_notes, contact_name, contact_phone, status) VALUES
  (101, 2, '钱爷爷', 1, 79, '101', '2026-03-12', '高血压，行动不便', '钱敏', '13800000101', 1),
  (102, 2, '孙奶奶', 0, 83, '102', '2026-04-02', '糖尿病，需控糖饮食', '孙浩', '13800000102', 1),
  (103, 2, '周伯伯', 1, 75, '201', '2026-05-20', '术后康复期', '周琳', '13800000103', 1);

-- 第二家机构的摄像头
INSERT IGNORE INTO cameras (id, tenant_id, name, room_no, stream_url, source_type,
                            status, yolo_enabled, inference_fps) VALUES
  (101, 2, '和睦101房摄像头', '101', 'rtsp://10.20.1.101:554/stream', 'stream', 0, 1, 5),
  (102, 2, '和睦102房摄像头', '102', 'rtsp://10.20.1.102:554/stream', 'stream', 0, 1, 5),
  (103, 2, '和睦201房摄像头', '201', 'rtsp://10.20.1.201:554/stream', 'stream', 0, 1, 5);

-- 第二家机构的告警（带完整证据明细，供评测页归因使用）
INSERT IGNORE INTO alerts (id, tenant_id, elder_id, camera_id, risk_level, confidence,
                           alert_time, status, posture_type, evidence_mode,
                           fall_score, pain_score, torso_angle, knee_hip_ratio, pose_quality,
                           body_keypoints, rapid_descent, fall_state, track_id,
                           expression_top, expression_confidence, expr_quality,
                           face_available, face_method, belief_fall, belief_unknown,
                           handler_notes)
VALUES
  (101, 2, 101, 101, 'HIGH', 88, DATE_SUB(NOW(), INTERVAL 2 DAY), 1,
   'fall_like', 'pose_expression', 0.92, 0.61, 74.0, 1.04, 0.90, 16, 1, 'confirmed_fall', 1,
   'Fear', 0.71, 0.68, 1, 'keypoint+aligned', 0.88, 0.09, '护理员复核：确认真实跌倒'),
  (102, 2, 102, 102, 'MEDIUM', 62, DATE_SUB(NOW(), INTERVAL 1 DAY), 2,
   'unknown', 'pose_only', 0.44, 0.0, 42.0, 1.18, 0.72, 11, 0, 'suspected_fall', 1,
   NULL, NULL, 0.0, 0, NULL, 0.38, 0.35, '护理员复核：老人只是蹲下'),
  (103, 2, 103, 103, 'HIGH', 81, DATE_SUB(NOW(), INTERVAL 6 HOUR), 0,
   'fall_like', 'pose_expression', 0.87, 0.72, 71.0, 1.05, 0.88, 15, 1, 'confirmed_fall', 1,
   'Disgust', 0.66, 0.71, 1, 'keypoint+aligned', 0.84, 0.11, '待护理员处置');
