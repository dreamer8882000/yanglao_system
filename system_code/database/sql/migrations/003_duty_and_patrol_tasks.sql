-- ============================================================================
-- 003 · 排班值守：班次字典 + 巡查任务派发
-- ============================================================================
-- 自查结论：
--   * schedules 只有 uq_user_shift_date(user_id, shift_date) 唯一索引，
--     "一人一天一班"在库层是保住了，但**接口层遇到重复排班会抛 500 而不是
--     可读的冲突提示**，前端无法解释为什么排不上。
--   * shift_type 是裸字符串，没有字典表；start_time/end_time 在每一行重复存储，
--     同一班次的时间一旦写歪也不会有人发现。
--   * 夜间巡查只有 patrol_records（**已完成**的记录），没有"任务"的概念：
--     无法派发、无法看到"谁还没巡"、也无法回写。所以巡查页只能罗列历史。
--
-- 本迁移补上：班次字典 shifts、巡查任务 patrol_tasks（可派发/可回写），
-- 并让 patrol_records 可选地关联到它由哪个任务完成而来。
-- ============================================================================

-- ── 1. 班次字典 ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shifts (
  shift_type VARCHAR(20) PRIMARY KEY COMMENT '班次代码，与 schedules.shift_type 对应',
  label VARCHAR(20) NOT NULL COMMENT '显示名',
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  crosses_midnight TINYINT NOT NULL DEFAULT 0 COMMENT '是否跨夜（end<start）',
  sort_order TINYINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='班次字典：时间定义单一来源';

INSERT INTO shifts (shift_type, label, start_time, end_time, crosses_midnight, sort_order) VALUES
  ('day',   '白班', '08:00:00', '20:00:00', 0, 1),
  ('night', '夜班', '20:00:00', '08:00:00', 1, 2)
ON DUPLICATE KEY UPDATE label=VALUES(label);

-- shift_type 必须是字典里的合法值，杜绝 "dayy" 这类脏数据
ALTER TABLE schedules
  ADD CONSTRAINT fk_schedule_shift FOREIGN KEY (shift_type)
  REFERENCES shifts(shift_type) ON DELETE RESTRICT ON UPDATE CASCADE;

-- ── 2. 巡查任务（可派发、可回写）────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patrol_tasks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  elder_id INT NOT NULL COMMENT '被巡查老人',
  room_no VARCHAR(20) NOT NULL,
  assigned_to INT NULL COMMENT '负责护理员（派单依据当班表自动带出）',
  task_date DATE NOT NULL,
  window_start DATETIME NOT NULL COMMENT '应巡查时段起点',
  window_end DATETIME NOT NULL COMMENT '应巡查时段终点，超过即视为超时',
  status TINYINT NOT NULL DEFAULT 0 COMMENT '0待执行 1已完成 2已跳过 3超时未巡',
  completed_at DATETIME NULL,
  completed_by INT NULL,
  alert_id INT NULL COMMENT '若由某条告警触发，记录来源以便追溯',
  notes VARCHAR(255) NULL,
  created_by INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  -- 同一间房在同一时段只需一条任务，避免重复派发
  UNIQUE KEY uq_patrol_slot (elder_id, window_start),
  KEY idx_patrol_status (status, window_start),
  KEY idx_patrol_assignee (assigned_to, task_date),
  CONSTRAINT fk_ptask_elder   FOREIGN KEY (elder_id)      REFERENCES elders(id)   ON DELETE CASCADE,
  CONSTRAINT fk_ptask_room    FOREIGN KEY (room_no)       REFERENCES rooms(room_no) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_ptask_assign  FOREIGN KEY (assigned_to)   REFERENCES users(id)    ON DELETE SET NULL,
  CONSTRAINT fk_ptask_doneby  FOREIGN KEY (completed_by)  REFERENCES users(id)    ON DELETE SET NULL,
  CONSTRAINT fk_ptask_alert   FOREIGN KEY (alert_id)      REFERENCES alerts(id)   ON DELETE SET NULL,
  CONSTRAINT fk_ptask_creator FOREIGN KEY (created_by)    REFERENCES users(id)    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='夜间巡查任务：可派发、可回写，与告警联动';

-- ── 3. 巡查记录回指任务，形成"派发→完成→留痕"的闭环 ────────────────────────
ALTER TABLE patrol_records
  ADD COLUMN task_id INT NULL COMMENT '由哪条巡查任务完成',
  ADD CONSTRAINT fk_patrol_task FOREIGN KEY (task_id)
  REFERENCES patrol_tasks(id) ON DELETE SET NULL;

-- ── 4. 排班页需要的视图：一人一天一班，带出当班时段 ─────────────────────────
CREATE OR REPLACE VIEW v_schedule_detail AS
SELECT s.id, s.user_id, u.name AS user_name, u.role, u.username,
       s.shift_date, s.shift_type, sh.label AS shift_label,
       s.start_time, s.end_time, sh.crosses_midnight,
       s.note, s.created_by, s.created_at
FROM schedules s
LEFT JOIN users  u  ON u.id = s.user_id
LEFT JOIN shifts sh ON sh.shift_type = s.shift_type;
