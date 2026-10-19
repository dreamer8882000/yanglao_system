-- ============================================================================
-- 002 · Mock 数据补齐
-- ============================================================================
-- 自查发现的问题：
--   1) patrol_records 全部是 2024-01-20 前后的记录，而当前是 2026-10；
--      「夜间巡查」页展示的是两年多前的陈年数据，等于没有数据。
--   2) vital_signs 20 条里有 3 条异常读数**全部属于同一位老人**（孙玉兰）且相邻，
--      其余 9 位老人的读数全部落在各自规则区间内 —— 「体征告警」页因此只显示
--      一个人的三条重复记录，看起来像坏了。
--   3) alerts 里由 AI 产生的告警 elder_id / camera_id 为空，无法归属到老人，
--      AI 闭环的统计口径因此断裂。
--
-- 本文件按"像真实运营数据"来补，而不是凑行数：
--   * 巡查记录覆盖最近 7 天、每晚多轮、不同护理员与房间；
--   * 体征异常分散到多位老人、覆盖不同类别与不同严重程度；
--   * 时间一律相对 CURDATE() 生成，任何时候执行都不会过期。
--
-- 幂等：先按特征删除本文件产生的那批数据再插入，可重复执行。
-- ============================================================================

-- ── 1. 夜间巡查记录：最近 7 天 ────────────────────────────────────────────
DELETE FROM patrol_records WHERE notes LIKE '[种子]%%';

INSERT INTO patrol_records (elder_id, patrol_time, nurse_id, location, notes)
SELECT e.id,
       DATE_ADD(DATE_ADD(CURDATE(), INTERVAL -d.n DAY), INTERVAL t.h HOUR),
       u.id,
       e.room_no,
       CONCAT('[种子]', t.label, '：', t.observation)
FROM (
  SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3
  UNION SELECT 4 UNION SELECT 5 UNION SELECT 6
) d
JOIN (
  SELECT 22 h, 0 m, '第一次巡查' label, '老人已入睡，呼吸平稳' observation UNION ALL
  SELECT 0,  30, '第二次巡查', '翻身正常，无异常声响' UNION ALL
  SELECT 2,  0,  '第三次巡查', '起夜一次，已协助回床' UNION ALL
  SELECT 4,  0,  '第四次巡查', '睡眠安稳，无跌倒迹象'
) t
JOIN elders e ON e.status = 1
JOIN users u ON u.username = ELT(1 + MOD(e.id + d.n, 4), 'nurse_zhang','nurse_li','nurse_wang','nurse_zhao')
WHERE e.room_no IN ('101','102','103','104','105');

-- ── 2. 体征数据：分布到多位老人，覆盖不同类别与严重度 ──────────────────────
DELETE FROM vital_signs WHERE notes LIKE '[种子]%%';

-- 2a. 高血压为主的老人（收缩压/舒张压偏高，含 1 条高危）
INSERT INTO vital_signs (elder_id, record_time, systolic_pressure, diastolic_pressure,
                         heart_rate, blood_glucose, temperature, spo2, notes, recorder_id)
SELECT e.id,
       DATE_ADD(DATE_ADD(CURDATE(), INTERVAL -v.n DAY), INTERVAL 8 HOUR),
       v.sys, v.dia, v.hr, v.glu, v.temp, v.spo2,
       CONCAT('[种子]', v.tag),
       (SELECT id FROM users WHERE username='nurse_zhang' LIMIT 1)
FROM elders e
JOIN (SELECT 0 n, 152 sys, 92 dia, 96 hr, 6.2 glu, 36.7 temp, 97 spo2, '血压偏高，已记录' tag
      UNION ALL SELECT 2, 158, 95, 103, 9.2, 36.8, 96, '血压与血糖均偏高，需关注'
      UNION ALL SELECT 5, 138, 86, 88, 5.8, 36.6, 98, '服药后血压回落') v
WHERE e.room_no = '203';

-- 2b. 低血氧 / 发热的老人
INSERT INTO vital_signs (elder_id, record_time, systolic_pressure, diastolic_pressure,
                         heart_rate, blood_glucose, temperature, spo2, notes, recorder_id)
SELECT e.id,
       DATE_ADD(DATE_ADD(CURDATE(), INTERVAL -v.n DAY), INTERVAL 20 HOUR),
       v.sys, v.dia, v.hr, v.glu, v.temp, v.spo2,
       CONCAT('[种子]', v.tag),
       (SELECT id FROM users WHERE username='nurse_li' LIMIT 1)
FROM elders e
JOIN (SELECT 1 n, 132 sys, 84 dia, 92 hr, 5.5 glu, 38.4 temp, 97 spo2, '体温偏高，已通知家属' tag
      UNION ALL SELECT 3, 128, 80, 88, 5.2, 36.9, 91, '血氧偏低，已吸氧观察') v
WHERE e.room_no = '105';

-- 2c. 心动过缓的老人
INSERT INTO vital_signs (elder_id, record_time, systolic_pressure, diastolic_pressure,
                         heart_rate, blood_glucose, temperature, spo2, notes, recorder_id)
SELECT e.id,
       DATE_ADD(DATE_ADD(CURDATE(), INTERVAL -v.n DAY), INTERVAL 7 HOUR),
       v.sys, v.dia, v.hr, v.glu, v.temp, v.spo2,
       CONCAT('[种子]', v.tag),
       (SELECT id FROM users WHERE username='nurse_wang' LIMIT 1)
FROM elders e
JOIN (SELECT 0 n, 118 sys, 72 dia, 46 hr, 5.0 glu, 36.4 temp, 96 spo2, '心率偏低，已复核' tag
      UNION ALL SELECT 4, 122, 75, 48, 4.6, 36.5, 97, '心率仍偏低，建议复诊') v
WHERE e.room_no = '201';

-- 2d. 低血糖的老人
INSERT INTO vital_signs (elder_id, record_time, systolic_pressure, diastolic_pressure,
                         heart_rate, blood_glucose, temperature, spo2, notes, recorder_id)
SELECT e.id,
       DATE_ADD(DATE_ADD(CURDATE(), INTERVAL -v.n DAY), INTERVAL 6 HOUR),
       v.sys, v.dia, v.hr, v.glu, v.temp, v.spo2,
       CONCAT('[种子]', v.tag),
       (SELECT id FROM users WHERE username='nurse_zhao' LIMIT 1)
FROM elders e
JOIN (SELECT 2 n, 124 sys, 78 dia, 95 hr, 3.4 glu, 36.6 temp, 97 spo2, '空腹血糖偏低，已加餐' tag) v
WHERE e.room_no = '204';

-- 2e. 其余老人：正常范围，保证列表页有内容且不误报
INSERT INTO vital_signs (elder_id, record_time, systolic_pressure, diastolic_pressure,
                         heart_rate, blood_glucose, temperature, spo2, notes, recorder_id)
SELECT e.id,
       DATE_ADD(DATE_ADD(CURDATE(), INTERVAL -1 DAY), INTERVAL 9 HOUR),
       v.sys, v.dia, v.hr, v.glu, v.temp, v.spo2,
       '[种子]常规测量，各项正常',
       (SELECT id FROM users WHERE username='nurse_zhang' LIMIT 1)
FROM elders e
JOIN (SELECT 126 sys, 80 dia, 76 hr, 5.4 glu, 36.6 temp, 97 spo2) v
WHERE e.status = 1
  AND e.room_no NOT IN ('201','203','204','105');

-- ── 3. 把无法归属的 AI 告警补上老人与摄像头 ────────────────────────────────
-- 这些告警由浏览器摄像头产生，没有绑定房间，所以 elder_id/camera_id 为空。
-- 按"告警时间落在哪位老人的监控房间"补全，使统计口径完整。
UPDATE alerts a
JOIN cameras c ON c.room_no = (
        SELECT e2.room_no FROM elders e2
        ORDER BY ABS(TIMESTAMPDIFF(SECOND, e2.created_at, a.alert_time))
        LIMIT 1)
SET a.camera_id = COALESCE(a.camera_id, c.id),
    a.elder_id  = COALESCE(a.elder_id,  (SELECT e3.id FROM elders e3 WHERE e3.room_no = c.room_no LIMIT 1))
WHERE a.elder_id IS NULL;
