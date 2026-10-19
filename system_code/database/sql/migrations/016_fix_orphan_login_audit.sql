-- 016 修正被误归属的登录失败审计
--
-- 现象：用户名根本不存在的登录失败记录，本该是"无机构归属"（tenant_id IS NULL），
-- 实测却有 150 行被记到了机构 1 名下。
--
-- 根因：record_audit 把"调用方明确传 None"和"调用方没传"当成同一件事，
-- 于是 auth.py 传进来的 None 被忽略，回落到 ContextVar 里上一个请求绑定的租户。
-- 已在 services/audit.py 用哨兵值修掉（显式 None 不再回落）。
--
-- 这里把已经写错的历史数据改回来：只针对"登录/鉴权类"且"该用户名在 users 表里
-- 不存在"的记录 —— 用户名不存在，就意味着无法判断它属于哪个机构，
-- 这正是平台层安全视图要看的那些行。
-- 已存在账号的失败记录不动：那些确实属于某个机构，归到该机构是对的。

UPDATE audit_logs a
SET a.tenant_id = NULL
WHERE a.resource_type = 'auth'
  AND a.action IN ('登录失败', '登录被限流')
  AND a.username IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM users u WHERE u.username = a.username);
