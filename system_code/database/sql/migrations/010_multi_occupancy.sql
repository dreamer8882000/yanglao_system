-- ============================================================================
-- 010 · 多人同房数据（双人间 / 三人间）
-- ============================================================================
-- 为什么必须铺：009 让系统「能表达身份不确定」，但如果没有多人同房的真实数据，
-- 这条路径**永远走不到** —— 等于写了一条没人验证过的分支。而"运行中被走到"
-- 恰恰是发现「静默挂错人」的前提。
--
-- 同时给 (tenant_id, room_no, bed_no) 加唯一键：数据库层保证"同房内床位号不重复"，
-- 这是"多人同房"这件事最基础的约束。没有它，两张床可以都叫 1 号床。
--
-- 布局（刻意与既有数据区分，便于肉眼核对）：
--   租户 1 阳光养老院：A栋 301~306 = 双人间（+6 位）
--                     A栋 401~402 = 三人间（各 +2 位）
--   租户 2 和睦护理中心：B栋 105~106 = 双人间（各 +1 位）
--
-- 姓名不与同机构既有的老人重复（跨机构重名是允许的，现实里也如此）。
-- 幂等：以 (tenant_id, room_no, bed_no) 是否已存在为准。
-- ============================================================================

-- 注：本迁移还包含第 5 节的**摄像头**。没有摄像头覆盖多人房，
-- 身份不确定这条路径在界面上永远触发不了 —— 数据铺了却看不到效果，
-- 等于没铺。

-- ── 1. 床位号唯一约束（先于插入，保证后面插的数据本身就合法）─────────────
SET @has := (SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='elders' AND INDEX_NAME='uk_elder_bed');
SET @sql := IF(@has=0,
  'ALTER TABLE elders ADD UNIQUE KEY uk_elder_bed (tenant_id, room_no, bed_no)',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- ── 2. 租户 1：6 间双人间（bed_no = 2）────────────────────────────────────
INSERT INTO elders (tenant_id, name, gender, age, room_no, bed_no, admission_date,
                    health_notes, contact_name, contact_phone, status)
SELECT 1, m.nm, m.gd, m.age, m.room, 2,
       DATE_SUB(CURDATE(), INTERVAL m.days DAY), m.note,
       CONCAT('家属-', m.room, '-2'), CONCAT('137', LPAD(m.ph, 8, '0')), 1
FROM (
  SELECT '301' AS room, '冯秀云' AS nm, 2 AS gd, 84 AS age, 210 AS days, '31000001' AS ph, '高血压、轻度耳背' AS note
  UNION ALL SELECT '302', '曾长海', 1, 79, 340, '31000002', '冠心病，夜间需巡视'
  UNION ALL SELECT '303', '彭素芬', 2, 88, 150, '31000003', '骨质疏松，跌倒风险高'
  UNION ALL SELECT '304', '萧振华', 1, 82, 420, '31000004', '脑梗后遗症，行动不便'
  UNION ALL SELECT '305', '田兰英', 2, 76, 90,  '31000005', '糖尿病，监测血糖'
  UNION ALL SELECT '306', '董伟民', 1, 71, 500, '31000006', '身体状况稳定'
) m
WHERE NOT EXISTS (SELECT 1 FROM elders e
                  WHERE e.tenant_id=1 AND e.room_no=m.room AND e.bed_no=2);

-- ── 3. 租户 1：2 间三人间（bed_no = 2 和 3）───────────────────────────────
INSERT INTO elders (tenant_id, name, gender, age, room_no, bed_no, admission_date,
                    health_notes, contact_name, contact_phone, status)
SELECT 1, m.nm, m.gd, m.age, m.room, m.bed,
       DATE_SUB(CURDATE(), INTERVAL m.days DAY), m.note,
       CONCAT('家属-', m.room, '-', m.bed),
       CONCAT('136', LPAD(m.ph, 8, '0')), 1
FROM (
  SELECT '401' AS room, 2 AS bed, '袁凤兰' AS nm, 2 AS gd, 80 AS age, 260 AS days, '36000101' AS ph, '白内障，视力较差' AS note
  UNION ALL SELECT '401', 3, '潘志远', 1, 77, 180, '36000102', '帕金森，手抖'
  UNION ALL SELECT '402', 2, '于慧敏', 2, 85, 610, '36000103', '阿尔茨海默病早期'
  UNION ALL SELECT '402', 3, '蒋天成', 1, 74, 55,  '36000104', '术后康复期'
) m
WHERE NOT EXISTS (SELECT 1 FROM elders e
                  WHERE e.tenant_id=1 AND e.room_no=m.room AND e.bed_no=m.bed);

-- ── 4. 租户 2：2 间双人间 ─────────────────────────────────────────────────
INSERT INTO elders (tenant_id, name, gender, age, room_no, bed_no, admission_date,
                    health_notes, contact_name, contact_phone, status)
SELECT 2, m.nm, m.gd, m.age, m.room, 2,
       DATE_SUB(CURDATE(), INTERVAL m.days DAY), m.note,
       CONCAT('家属-', m.room, '-2'), CONCAT('135', LPAD(m.ph, 8, '0')), 1
FROM (
  SELECT '105' AS room, '秦淑芬' AS nm, 2 AS gd, 81 AS age, 200 AS days, '35000001' AS ph, '高血压，控制尚可' AS note
  UNION ALL SELECT '106', '许文华', 1, 78, 130, '35000002', '慢阻肺，注意保暖'
) m
WHERE NOT EXISTS (SELECT 1 FROM elders e
                  WHERE e.tenant_id=2 AND e.room_no=m.room AND e.bed_no=2);

-- ── 5. 给多人房装上摄像头（否则"身份不确定"在界面上永远不出现）────────────
-- 摄像头是分机构资产，且新建一律先按离线入库（status=0）——
-- 在线只能由真实心跳推导，见 cameras.py 的说明。
INSERT INTO cameras (tenant_id, name, room_no, stream_url, source_type, yolo_model,
                     yolo_models, yolo_enabled, status, note)
SELECT 1, CONCAT('A栋', m.room, '室摄像头'), m.room, CONCAT('rtsp://mock.local/a/', m.room),
       'rtsp', 'cascade', '["pose","expression"]', 1, 0,
       CASE WHEN m.beds > 2 THEN '三人间：身份需床位级判定' ELSE '双人间：身份需床位级判定' END
FROM (SELECT '301' AS room, 2 AS beds UNION ALL SELECT '302', 2 UNION ALL SELECT '303', 2
      UNION ALL SELECT '304', 2 UNION ALL SELECT '305', 2 UNION ALL SELECT '306', 2
      UNION ALL SELECT '401', 3 UNION ALL SELECT '402', 3) m
WHERE NOT EXISTS (SELECT 1 FROM cameras c WHERE c.tenant_id=1 AND c.room_no=m.room);

INSERT INTO cameras (tenant_id, name, room_no, stream_url, source_type, yolo_model,
                     yolo_models, yolo_enabled, status, note)
SELECT 2, CONCAT('B栋', m.room, '室摄像头'), m.room, CONCAT('rtsp://mock.local/b/', m.room),
       'rtsp', 'cascade', '["pose","expression"]', 1, 0, '双人间：身份需床位级判定'
FROM (SELECT '105' AS room UNION ALL SELECT '106') m
WHERE NOT EXISTS (SELECT 1 FROM cameras c WHERE c.tenant_id=2 AND c.room_no=m.room);
