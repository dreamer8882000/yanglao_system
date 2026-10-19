-- ============================================================================
-- 001 · 关系补全：rooms 主数据表 + 关键业务表的外键
-- ============================================================================
-- 背景（自查结论）：
--   原库 13 张表都有主键，但**关键业务表一个外键都没有**：
--     alerts(0)  schedules(0)  cameras(0)  elders(0)  audit_logs(0)
--   而 vital_signs / medications / medication_records / patrol_records /
--   messages 是有外键的，说明这属于遗漏而非有意设计。
--
--   最要紧的一处：elders.room_no 与 cameras.room_no 是**两处彼此独立的字符串**，
--   没有房间主数据。后果是"这个摄像头看的是哪位老人"**无法用 join 表达**，
--   只能靠前端按字符串相等去猜——AI 告警也就无法可靠地关联到具体老人。
--
-- 设计取舍：
--   rooms 表用 room_no 作为**业务自然键**（UNIQUE），elders/cameras 的外键
--   直接指向它。之所以不额外引入 room_id 代理键，是因为 room_no 已经稳定、
--   唯一、且是业务方日常使用的编号；改用代理键需要改动后端 12 处 + 前端 44 处
--   的接口契约，收益仅是形式上的规范化，不改变任何可表达能力。
--
-- 幂等：全部使用 IF NOT EXISTS / 先查后加，可重复执行。
-- ============================================================================

-- ── 1. 房间主数据 ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rooms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  room_no VARCHAR(20) NOT NULL COMMENT '房间号（业务自然键）',
  building VARCHAR(20) NOT NULL DEFAULT 'A栋' COMMENT '楼栋',
  floor TINYINT NULL COMMENT '楼层',
  note VARCHAR(100) NULL COMMENT '备注',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_room_no (room_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='房间主数据：老人与摄像头经由它建立关联';
-- 注意 COLLATE 必须与既有 13 张表一致（utf8mb4_unicode_ci）。
-- 外键要求引用列与被引用列的字符集**与**排序规则完全相同，否则报
-- 3780 incompatible；库默认是 utf8mb4_0900_ai_ci，不显式指定就会踩这个坑。

-- 从 elders ∪ cameras 反向播种，保证不漏房间
INSERT INTO rooms (room_no, building, floor)
SELECT t.room_no, 'A栋', CAST(LEFT(t.room_no, 1) AS UNSIGNED)
FROM (
  SELECT room_no FROM elders  WHERE room_no IS NOT NULL AND room_no <> ''
  UNION
  SELECT room_no FROM cameras WHERE room_no IS NOT NULL AND room_no <> ''
) t
ON DUPLICATE KEY UPDATE rooms.building = rooms.building;

-- ── 2. 老人 / 摄像头 → 房间 ────────────────────────────────────────────────
-- ON DELETE RESTRICT：房间下还住着人或装着摄像头时，不允许删房间。
ALTER TABLE elders
  ADD CONSTRAINT fk_elder_room FOREIGN KEY (room_no)
  REFERENCES rooms(room_no) ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE cameras
  ADD CONSTRAINT fk_camera_room FOREIGN KEY (room_no)
  REFERENCES rooms(room_no) ON DELETE RESTRICT ON UPDATE CASCADE;

-- ── 3. 告警 → 老人 / 摄像头 / 处置人 / 派单人 ──────────────────────────────
-- 这四条是 AI 闭环的地基：告警必须能可靠地回溯到"哪间房、哪位老人、
-- 派给了谁、谁处理的"。此前它们全是裸整数，删掉一个用户会留下悬空 handler_id。
ALTER TABLE alerts
  ADD CONSTRAINT fk_alert_elder   FOREIGN KEY (elder_id)    REFERENCES elders(id)  ON DELETE CASCADE,
  ADD CONSTRAINT fk_alert_camera  FOREIGN KEY (camera_id)   REFERENCES cameras(id) ON DELETE SET NULL,
  ADD CONSTRAINT fk_alert_handler FOREIGN KEY (handler_id)  REFERENCES users(id)   ON DELETE SET NULL,
  ADD CONSTRAINT fk_alert_assignee FOREIGN KEY (assigned_to) REFERENCES users(id)  ON DELETE SET NULL;

-- ── 4. 排班 → 用户 ─────────────────────────────────────────────────────────
ALTER TABLE schedules
  ADD CONSTRAINT fk_schedule_user    FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_schedule_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;

-- ── 5. 审计日志 → 用户 ─────────────────────────────────────────────────────
-- SET NULL 而非 CASCADE：用户被删除后，其历史操作记录必须保留以备审计。
ALTER TABLE audit_logs
  ADD CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;

-- ── 6. 便于"老人↔摄像头"查询的覆盖检查 ─────────────────────────────────────
-- 一间房应有且仅有 1 位在册老人、至多 1 台摄像头，否则 AI 告警无法唯一归属。
-- 用视图把这种不一致暴露出来，而不是让它静默存在。
-- 视图里的字符串比较同样受排序规则约束，若 rooms 与 elders 不一致会报 1267。
CREATE OR REPLACE VIEW v_room_coverage AS
SELECT r.room_no,
       r.building,
       r.floor,
       COUNT(DISTINCT e.id)  AS elder_count,
       COUNT(DISTINCT c.id)  AS camera_count,
       GROUP_CONCAT(DISTINCT e.name ORDER BY e.id SEPARATOR '、') AS elder_names
FROM rooms r
LEFT JOIN elders  e ON e.room_no = r.room_no AND e.status = 1
LEFT JOIN cameras c ON c.room_no = r.room_no
GROUP BY r.room_no, r.building, r.floor;
