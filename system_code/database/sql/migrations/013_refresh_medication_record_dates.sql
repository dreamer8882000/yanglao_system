-- ============================================================================
-- 013 · 修正服药记录的陈旧日期
-- ============================================================================
-- 问题：medication_records.scheduled_time 停留在 2024-01-20 ~ 01-21，
--       距当前（2026-10）已 991 天。这是「patrol_records 日期停留在
--       2024-01-20」的同一个问题 —— 当时只修了巡查记录，用药记录被漏掉了。
--
-- 为什么这会让新做的条件查询形同虚设：护理员打开服药记录，按"最近 7 天"
-- 一筛 → 一条都没有。数据看着是"空的"，实际是"全是两年前的"。
-- mock 数据的时间必须落在当前时间附近，否则任何时间维度的功能都无法演示，
-- 也无法验证。
--
-- 修法：整体平移，让最新一条落到今天，**保持记录之间的相对间隔**
--       （哪些是同一天的、哪条在前哪条在后，这些关系不能被压平）。
--       用 DATEDIFF(CURDATE(), 最新日期) 动态计算偏移，而不是写死一个天数 ——
--       写死的话过一段时间又会变陈旧，正是本次要避免的。
--
-- 幂等：只在该表最新日期已经落后 30 天以上时才平移。
-- ============================================================================

-- 偏移量必须**按租户各算一份**（GROUP BY tenant_id）。
-- 第一版写的是全局 `DATE(MAX(scheduled_time))`，结果取到了**另一家机构**的最新日期
-- （租户 2 的数据是迁移 007 用 CURDATE() 种的，本来就在今天），
-- 于是 DATEDIFF 算出来是 0 —— 整条 UPDATE 影响 0 行，陈旧数据一条没动。
-- 表面上"迁移执行成功"，实际是个静默空操作。凡是逐租户的数据修复，
-- 聚合都必须带上 tenant_id。
UPDATE medication_records r
JOIN (SELECT tenant_id, DATE(MAX(scheduled_time)) AS latest
        FROM medication_records GROUP BY tenant_id) t
  ON t.tenant_id = r.tenant_id
SET r.scheduled_time = DATE_ADD(r.scheduled_time, INTERVAL DATEDIFF(CURDATE(), t.latest) DAY),
    r.actual_time    = CASE WHEN r.actual_time IS NULL THEN NULL
                            ELSE DATE_ADD(r.actual_time, INTERVAL DATEDIFF(CURDATE(), t.latest) DAY) END
WHERE t.latest < DATE_SUB(CURDATE(), INTERVAL 30 DAY);
