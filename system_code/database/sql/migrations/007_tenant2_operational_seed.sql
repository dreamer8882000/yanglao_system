-- ============================================================================
-- 007 · 第二家机构的运营数据（演示与验收用）
-- ============================================================================
-- 背景：005 只给和睦护理中心（tenant 2）建了「骨架」——机构、账号、房间、老人、
--       摄像头、告警。但排班、巡查、用药、体征、消息、审计这些表在 tenant 2 下
--       完全是空的。后果有两个，都是实质性的：
--
--   1. **隔离效果无法验证**。两家机构都有数据时，「B 看不到 A 的」才是一个有意义
--      的断言；B 本来就什么都没有时，即使过滤完全失效、B 看到了 A 的全部数据，
--      单看总数也不一定露馅。验收脚本 test_tenant_isolation.py 正是靠
--      「两侧条目集合正好等于各自库内集合」来判定的。
--
--   2. **演示看起来像坏了**。以 hx_admin 登录后除首页外几乎全是空页面，
--      使用者会认为多租户功能有 bug。
--
-- 数据刻意与 tenant 1 **量级不同、内容不同**，这样任何一处过滤失效都会立刻
-- 表现为一个突兀的大数字（例如租户2 的排班从 12 条变成 67 条）。
--
-- 幂等：以「该租户该表是否已有数据」为准，可重复执行。
-- ============================================================================

-- ── 1. 排班：未来 6 天，两位员工轮班 ───────────────────────────────────────
INSERT INTO schedules (tenant_id, user_id, shift_date, shift_type, start_time, end_time, note, created_by)
SELECT 2, 102, DATE_ADD(CURDATE(), INTERVAL d.n DAY), 'day', '08:00:00', '20:00:00', '和睦护理中心日班', 101
FROM (SELECT 0 AS n UNION SELECT 1 UNION SELECT 2) d
WHERE NOT EXISTS (SELECT 1 FROM schedules WHERE tenant_id = 2);

INSERT INTO schedules (tenant_id, user_id, shift_date, shift_type, start_time, end_time, note, created_by)
SELECT 2, 101, DATE_ADD(CURDATE(), INTERVAL d.n DAY), 'night', '20:00:00', '08:00:00', '和睦护理中心夜班', 101
FROM (SELECT 0 AS n UNION SELECT 1 UNION SELECT 2) d
WHERE (SELECT COUNT(*) FROM schedules WHERE tenant_id = 2) < 7;

-- ── 2. 巡查任务 + 巡查记录：最近 3 天 ──────────────────────────────────────
INSERT INTO patrol_tasks (tenant_id, elder_id, room_no, assigned_to, task_date,
                          window_start, window_end, status, completed_at, completed_by,
                          notes, created_by)
SELECT 2, e.id, e.room_no, 102, DATE_SUB(CURDATE(), INTERVAL d.n DAY),
       TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL d.n DAY), '22:00:00'),
       TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL d.n DAY), '22:45:00'),
       1, TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL d.n DAY), '22:20:00'), 102,
       '夜间巡查正常', 101
FROM elders e
CROSS JOIN (SELECT 1 AS n UNION SELECT 2 UNION SELECT 3) d
WHERE e.tenant_id = 2
  AND NOT EXISTS (SELECT 1 FROM patrol_tasks WHERE tenant_id = 2);

INSERT INTO patrol_tasks (tenant_id, elder_id, room_no, assigned_to, task_date,
                          window_start, window_end, status, created_by, notes)
SELECT 2, e.id, e.room_no, 102, CURDATE(),
       TIMESTAMP(CURDATE(), '04:00:00'), TIMESTAMP(CURDATE(), '04:45:00'), 0, 101,
       '待执行'
FROM elders e
WHERE e.tenant_id = 2
  AND (SELECT COUNT(*) FROM patrol_tasks WHERE tenant_id = 2 AND status = 0) = 0;

INSERT INTO patrol_records (tenant_id, elder_id, patrol_time, nurse_id, location, notes, task_id)
SELECT t.tenant_id, t.elder_id, t.completed_at, t.completed_by, t.room_no, t.notes, t.id
FROM patrol_tasks t
WHERE t.tenant_id = 2 AND t.status = 1
  AND NOT EXISTS (SELECT 1 FROM patrol_records WHERE tenant_id = 2);

-- ── 3. 用药与服药记录 ──────────────────────────────────────────────────────
INSERT INTO medications (tenant_id, elder_id, medication_name, dosage, frequency,
                         time_slots, duration_days, notes, status, created_by)
SELECT 2, e.id, m.name, m.dose, '每日2次', '["08:00","20:00"]', 30, m.note, 1, 101
FROM elders e
JOIN (
  SELECT '苯磺酸氨氯地平片' AS name, '5mg' AS dose, '高血压' AS note
  UNION ALL SELECT '二甲双胍缓释片', '0.5g', '2型糖尿病'
  UNION ALL SELECT '阿司匹林肠溶片', '100mg', '抗血小板'
) m
WHERE e.tenant_id = 2
  AND NOT EXISTS (SELECT 1 FROM medications WHERE tenant_id = 2);

INSERT INTO medication_records (tenant_id, medication_id, elder_id, scheduled_time,
                                actual_time, nurse_id, status, notes)
SELECT 2, md.id, md.elder_id,
       TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 1 DAY), '08:00:00'),
       TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 1 DAY), '08:06:00'), 102, 1, '已按时服用'
FROM medications md WHERE md.tenant_id = 2
  AND NOT EXISTS (SELECT 1 FROM medication_records WHERE tenant_id = 2);

INSERT INTO medication_records (tenant_id, medication_id, elder_id, scheduled_time, status)
SELECT 2, md.id, md.elder_id, TIMESTAMP(CURDATE(), '20:00:00'), 0
FROM medications md WHERE md.tenant_id = 2
  AND (SELECT COUNT(*) FROM medication_records WHERE tenant_id = 2 AND status = 0) = 0;

-- ── 4. 生命体征：每位老人最近 7 天，其中带一条越界值 ───────────────────────
INSERT INTO vital_signs (tenant_id, elder_id, record_time, systolic_pressure,
                         diastolic_pressure, heart_rate, blood_glucose, temperature,
                         spo2, weight, recorder_id, notes)
SELECT 2, e.id, TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL d.n DAY), '07:30:00'),
       118 + (e.id % 7) + d.n, 74 + (d.n % 5), 68 + (d.n * 2),
       5.20 + (d.n * 0.15), 36.40 + (d.n * 0.05), 96 - d.n, 58.0 + (e.id % 5),
       102, '晨间常规测量'
FROM elders e
CROSS JOIN (SELECT 0 AS n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3
            UNION SELECT 4 UNION SELECT 5 UNION SELECT 6) d
WHERE e.tenant_id = 2
  AND NOT EXISTS (SELECT 1 FROM vital_signs WHERE tenant_id = 2);

-- 一条明确越界：血糖 9.6 高于默认上限 8.0，让「体征告警」页面不是空的
INSERT INTO vital_signs (tenant_id, elder_id, record_time, systolic_pressure,
                         diastolic_pressure, heart_rate, blood_glucose, temperature,
                         spo2, weight, recorder_id, notes)
SELECT 2, 101, TIMESTAMP(CURDATE(), '06:10:00'), 152, 94, 88, 9.60, 37.10, 93, 61.5, 102,
       '血糖偏高，已通知医生复核'
WHERE NOT EXISTS (
  SELECT 1 FROM vital_signs WHERE tenant_id = 2 AND record_time = TIMESTAMP(CURDATE(), '06:10:00')
);

-- ── 5. 体征告警规则（按老人配置，体现"规则真的被读取"）────────────────────
INSERT INTO vital_alert_rules (tenant_id, elder_id, vital_type, min_value, max_value, status)
SELECT 2, e.id, r.vt, r.lo, r.hi, 1
FROM elders e
JOIN (
  SELECT 'systolic_pressure' AS vt, 90 AS lo, 140 AS hi
  UNION ALL SELECT 'diastolic_pressure', 60, 90
  UNION ALL SELECT 'heart_rate', 50, 100
  UNION ALL SELECT 'temperature', 36.0, 37.5
  UNION ALL SELECT 'blood_glucose', 4.0, 8.0
  UNION ALL SELECT 'spo2', 92, 100
) r
WHERE e.tenant_id = 2
  AND NOT EXISTS (SELECT 1 FROM vital_alert_rules WHERE tenant_id = 2);

-- ── 6. 消息 ────────────────────────────────────────────────────────────────
INSERT INTO messages (tenant_id, user_id, type, title, content, related_id, is_read)
SELECT 2, u.uid, m.tp, m.title, m.content, NULL, m.rd
FROM (SELECT 101 AS uid UNION ALL SELECT 102) u
JOIN (
  SELECT 'alert' AS tp, '血糖异常提醒' AS title, '钱爷爷晨间血糖 9.6 mmol/L，高于 8.0 上限，请复核。' AS content, 0 AS rd
  UNION ALL SELECT 'system', '机构配置已就绪', '和睦护理中心的房间、老人、摄像头与排班已初始化完成。', 1
  UNION ALL SELECT 'patrol', '夜间巡查已完成', '昨晚 22:00 轮次的三间房巡查均已记录。', 1
) m
WHERE NOT EXISTS (SELECT 1 FROM messages WHERE tenant_id = 2);

-- ── 7. 审计日志 ────────────────────────────────────────────────────────────
INSERT INTO audit_logs (tenant_id, user_id, username, action, resource_type, resource_id, detail, ip)
SELECT 2, a.uid, a.un, a.act, a.rt, a.rid, a.dt, '10.20.30.40'
FROM (
  SELECT 101 AS uid, 'hx_admin' AS un, '登录成功' AS act, 'auth' AS rt, NULL AS rid, '{"role":"admin"}' AS dt
  UNION ALL SELECT 101, 'hx_admin', '新增老人', 'elders', '101', '{"name":"钱爷爷"}'
  UNION ALL SELECT 101, 'hx_admin', '新增摄像头', 'cameras', '101', '{"roomNo":"101"}'
  UNION ALL SELECT 102, 'hx_nurse', '完成巡查', 'patrol_tasks', '1', '{"notes":"夜间巡查正常"}'
  UNION ALL SELECT 102, 'hx_nurse', '告警处置', 'alert', '101', '{"notes":"已联系家属"}'
) a
WHERE NOT EXISTS (SELECT 1 FROM audit_logs WHERE tenant_id = 2);
