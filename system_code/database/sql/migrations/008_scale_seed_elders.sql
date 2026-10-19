-- ============================================================================
-- 008 · 老人档案的规模化数据（让分页真正被用起来）
-- ============================================================================
-- 背景：老人档案页早就接了共享分页组件（Pagination.vue，含 10/20/30/50/100
--       每页条数选择、首页/末页/跳页），但租户 1 只有 10 位老人、租户 2 只有 3 位，
--       一页就装完了 —— 分页条**从来不显示**，也就从来没人验证过它。
--       真实养老机构是 100~200 张床位，所以这里补到那个量级。
--
-- 规模（刻意让两家不同量级，任何过滤失效都会立刻表现为突兀的大数字）：
--   租户 1 阳光养老院：A 栋 1~6 层 × 24 间 = 144 间 → 144 位老人
--   租户 2 和睦护理中心：B 栋 1~2 层 × 10 间 = 20 间 → 20 位老人
--
-- 房间号沿用既有的「楼层+房号」两位编码（101~124、201~224 …），
-- 与已存在的 101~105 / 201~205 自然衔接，不产生新的编码风格。
--
-- 关于「多人同房」：本迁移**保持一人一房**。中国养老院的双人间/三人间很常见，
-- 而那正是「如何识别是哪位老人」这个问题的关键前提 —— 但它需要先定下识别
-- 方案（空间床位定位 / 人脸核验 / 两者结合），见 docs/planning/12。
-- 在方案确定前先铺多人同房，只会让告警挂到错误的老人名下。
--
-- 幂等：以「房间/老人是否已存在」为准，可重复执行。
--
-- 重跑方式（本迁移在 2025 年曾因取模周期导致重名而修正过一次）：
--   DELETE FROM schema_migrations WHERE version='008';
--   DELETE FROM elders WHERE tenant_id=1 AND id>10;   -- 清掉批量种子
--   DELETE FROM elders WHERE tenant_id=2 AND id>103;
--   .venv/bin/python scripts/db/migrate.py 008
-- ============================================================================

-- ── 1. 租户 1：A 栋 1~6 层 × 24 间 ─────────────────────────────────────────
INSERT INTO rooms (tenant_id, room_no, building, floor, note)
SELECT 1,
       CONCAT(f.fl, LPAD(r.rn, 2, '0')),
       'A栋',
       f.fl,
       CASE WHEN r.rn <= 12 THEN '南向' ELSE '北向' END
FROM (SELECT 1 AS fl UNION ALL SELECT 2 UNION ALL SELECT 3
      UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6) f
CROSS JOIN (SELECT 1 AS rn UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
            UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8
            UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12
            UNION ALL SELECT 13 UNION ALL SELECT 14 UNION ALL SELECT 15 UNION ALL SELECT 16
            UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19 UNION ALL SELECT 20
            UNION ALL SELECT 21 UNION ALL SELECT 22 UNION ALL SELECT 23 UNION ALL SELECT 24) r
WHERE NOT EXISTS (
  SELECT 1 FROM rooms x
  WHERE x.tenant_id = 1 AND x.room_no = CONCAT(f.fl, LPAD(r.rn, 2, '0'))
);

-- ── 2. 租户 1：每个空房间补一位老人 ────────────────────────────────────────
-- 姓名生成用**行序号 rn** 而不是房间 id：id 依赖插入顺序、并不连续，
-- 按它取模会出现周期（第一版用 MOD(id,24)/MOD(id*7,30)，周期 lcm(24,30)=120，
-- 144 条里必然撞名 —— 实测出现「李桂芳」×3）。
--
-- 给定名池**刻意避开原有 10 位老人用过的字**（国强/桂芳/德华/淑珍/建国/秀英/
-- 志明/玉兰/国庆/秀兰），否则「李桂芳」这种组合会与样板数据重名；原有的人是
-- 演示时被认脸的对象，不该和批量数据混淆。
--
-- 公式 姓 = rn%24, 名 = (rn//24 + rn%24)%20 已逐条验证：在 rn∈[0,143] 上
-- **144 个组合全部互不相同，且与原有 10 个姓名零交集**。
INSERT INTO elders (tenant_id, name, gender, age, room_no, admission_date,
                    health_notes, contact_name, contact_phone, status, avatar)
SELECT 1,
       CONCAT(
         ELT(1 + MOD(r.rn, 24),
             '张','王','李','赵','刘','陈','杨','黄','周','吴','徐','孙',
             '马','朱','胡','郭','何','高','林','罗','郑','梁','谢','宋'),
         ELT(1 + MOD((r.rn DIV 24) + MOD(r.rn, 24), 20),
             '淑英','文博','秀荣','金凤','志强','桂英','海燕','玉梅','建华','秀珍',
             '立新','春梅','德明','凤英','学军','淑华','文军','玉华','志刚','小燕')
       ),
       1 + MOD(r.rn, 2),
       66 + MOD(r.rn, 29),
       r.room_no,
       DATE_SUB(CURDATE(), INTERVAL (MOD(r.rn * 13, 900) + 30) DAY),
       ELT(1 + MOD(r.rn, 8),
           '高血压，长期服药控制',
           '2 型糖尿病，注意饮食',
           '冠心病，避免剧烈活动',
           '骨质疏松，跌倒风险高',
           '轻度认知障碍，需陪同活动',
           '关节炎，行动不便',
           '慢性支气管炎',
           '身体一般情况良好，定期体检'),
       CONCAT('家属-', r.room_no),
       CONCAT('138', LPAD(MOD(r.rn * 7919, 100000000), 8, '0')),
       1,
       NULL
FROM (
  SELECT rm.room_no,
         ROW_NUMBER() OVER (ORDER BY rm.room_no) - 1 AS rn
  FROM rooms rm
  WHERE rm.tenant_id = 1
    AND NOT EXISTS (SELECT 1 FROM elders e
                    WHERE e.tenant_id = 1 AND e.room_no = rm.room_no)
) r;

-- ── 3. 租户 2：B 栋 1~2 层 × 10 间 ────────────────────────────────────────
INSERT INTO rooms (tenant_id, room_no, building, floor, note)
SELECT 2,
       CONCAT(f.fl, LPAD(r.rn, 2, '0')),
       'B栋',
       f.fl,
       '和睦护理中心'
FROM (SELECT 1 AS fl UNION ALL SELECT 2) f
CROSS JOIN (SELECT 1 AS rn UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
            UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8
            UNION ALL SELECT 9 UNION ALL SELECT 10) r
WHERE NOT EXISTS (
  SELECT 1 FROM rooms x
  WHERE x.tenant_id = 2 AND x.room_no = CONCAT(f.fl, LPAD(r.rn, 2, '0'))
);

INSERT INTO elders (tenant_id, name, gender, age, room_no, admission_date,
                    health_notes, contact_name, contact_phone, status, avatar)
SELECT 2,
       CONCAT(
         ELT(1 + MOD(r.rn, 16),
             '冯','曾','彭','萧','田','董','袁','潘','于','蒋','蔡','余','杜','叶','程','苏'),
         ELT(1 + MOD((r.rn DIV 16) + MOD(r.rn, 16), 20),
             '秀云','长海','素芬','振华','兰英','伟民','凤兰','志远','慧敏','天成',
             '月华','国栋','雅琴','建军','瑞芳','志国','美玲','文杰','桂香','立群')
       ),
       1 + MOD(r.rn, 2),
       68 + MOD(r.rn, 26),
       r.room_no,
       DATE_SUB(CURDATE(), INTERVAL (MOD(r.rn * 17, 700) + 15) DAY),
       ELT(1 + MOD(r.rn, 6),
           '高血压，血压控制尚可',
           '糖尿病，需监测血糖',
           '术后康复期，行动需搀扶',
           '心功能不全，注意休息',
           '白内障，视力较差',
           '身体状况稳定，生活基本自理'),
       CONCAT('家属-', r.room_no),
       CONCAT('139', LPAD(MOD(r.rn * 6271, 100000000), 8, '0')),
       1,
       NULL
FROM (
  SELECT rm.room_no,
         ROW_NUMBER() OVER (ORDER BY rm.room_no) - 1 AS rn
  FROM rooms rm
  WHERE rm.tenant_id = 2
    AND NOT EXISTS (SELECT 1 FROM elders e
                    WHERE e.tenant_id = 2 AND e.room_no = rm.room_no)
) r;
