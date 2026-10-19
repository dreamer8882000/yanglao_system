-- 015 平台级账号：跨租户只读视图（SaaS 运营方视角）
--
-- 要解决的两个真实问题：
--
-- 1) 平台运维看不到"有哪些机构"。租户表存在，但除自己所属的那一个之外，
--    任何接口都不会返回别的租户 —— 这是隔离该有的样子，可是运营方需要
--    一个**受控的、只读的**总览：机构列表、各自规模、是否还在用。
--
-- 2) 一批审计记录**谁也看不到**。登录失败时如果用户名不存在，就无从判断
--    属于哪个机构（tenant_of_username 查不到），这行审计的 tenant_id 是 NULL。
--    而审计列表是按 tenant_id 过滤的，于是"有人在反复猜密码"这条最该被
--    看到的记录，所有机构都看不到 —— 实测库里有 147 行这样的孤儿审计。
--    这类记录必须由平台层来看：它本来就不是某一家机构的事。
--
-- 设计取舍（重要）：
--   平台账号的 tenant_id 为 **NULL**，即"不归属任何机构"。
--   这不是为了绕过隔离，恰恰相反 —— core/tenant.py 的 tenant_id_of 对
--   "没有归属"的账号是**默认拒绝**的，所以平台账号访问
--   /api/elders、/api/alerts 等业务接口会被 403 挡住。
--   平台视图是**另一套只读接口**（/api/platform/*），不是"万能租户"。
--   这样原有 82 条跨租户隔离断言仍然全部有意义。

ALTER TABLE users
  ADD COLUMN is_platform TINYINT(1) NOT NULL DEFAULT 0
  COMMENT '平台级账号：不属于任何机构，仅可访问 /api/platform/* 只读视图';

-- users.tenant_id 必须允许 NULL（平台账号无归属）
ALTER TABLE users MODIFY COLUMN tenant_id INT NULL;

-- 平台账号。口令与其余演示账号一致（123456），口令散列由应用写入，
-- 这里只建行；用 INSERT IGNORE 保证迁移可重复执行。
INSERT IGNORE INTO users (username, name, email, dept_name, role, tenant_id, is_platform, password_hash)
VALUES ('platform', '平台运维', 'ops@platform.local', '平台运营', 'admin', NULL, 1, NULL);

-- 已有库中 username 可能有唯一索引冲突，这里再确认一次标记（幂等）
UPDATE users SET is_platform = 1, tenant_id = NULL WHERE username = 'platform';
