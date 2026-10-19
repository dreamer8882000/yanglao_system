-- ============================================================================
-- 014 · 告警通知：渠道配置 + 投递记录
-- ============================================================================
-- 背景：此前的「通知」是**完全装饰的**。
--   * settings.notifyConfig 存了 hiEnabled / smsEnabled / receivers，
--     但**后端零处读取** —— 勾选与保存不会产生任何行为；
--   * 唯一的通知实现是进程内 SSE hub，只能推给**当前打开的页面**；
--   * 没有任何投递留痕，所以"我没收到告警"永远查不出原因。
-- 对一个跌倒检测系统来说这是最要命的缺口：检测得准，但护士不在电脑前时没人知道。
--
-- 设计取舍：
--   1. 渠道做成**独立的表**（而不是继续塞在 settings 的一个 JSON 里）。
--      理由：需要多渠道路由（按等级）、需要启用/停用、需要被投递记录外键引用，
--      而且每个渠道都要按租户隔离 —— 一个全局 JSON 承载不了这些。
--   2. 建 notification_logs。**这是本迁移最重要的部分**：
--      没有它就无法回答"这条告警通知发出去了吗、发给谁了、为什么没到"。
--      通知的失败是最不该静默的失败。
--   3. config 用 JSON 存渠道私有参数（webhook 地址 / SMTP 账号）。
--      不含密码时留空即可；密码走同一字段但接口层做脱敏返回。
--
-- 幂等：先查后建。
-- ============================================================================

CREATE TABLE IF NOT EXISTS notification_channels (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id   INT NOT NULL COMMENT '所属机构',
  type        VARCHAR(16) NOT NULL COMMENT 'wecom / dingtalk / email',
  name        VARCHAR(64) NOT NULL COMMENT '展示名，如「值班群」「护士长邮箱」',
  config      JSON NOT NULL COMMENT '渠道私有参数：webhook / SMTP 账号等',
  min_level   VARCHAR(10) NOT NULL DEFAULT 'HIGH'
              COMMENT '触发该渠道的最低告警等级：LOW/MEDIUM/HIGH/URGENT',
  enabled     TINYINT NOT NULL DEFAULT 1,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_nc_tenant (tenant_id),
  CONSTRAINT fk_nc_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警通知渠道';

CREATE TABLE IF NOT EXISTS notification_logs (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  tenant_id    INT NOT NULL,
  alert_id     INT NULL COMMENT '关联告警；手动测试发送时为 NULL',
  channel_id   INT NULL COMMENT '渠道被删除后置空，但记录保留',
  channel_type VARCHAR(16) NOT NULL,
  channel_name VARCHAR(64) NULL COMMENT '发送当时的渠道名（渠道改名/删除后仍可读）',
  target       VARCHAR(255) NULL COMMENT '实际投递目标：webhook 主机 / 收件人',
  status       VARCHAR(12) NOT NULL COMMENT 'success / failed / skipped',
  reason       VARCHAR(16) NULL COMMENT '触发原因：new/escalated/timeout/confirmed/test',
  alert_level  VARCHAR(10) NULL COMMENT '发送当时的告警等级',
  error        VARCHAR(500) NULL COMMENT '失败原因；绝不能为空地失败',
  duration_ms  INT NULL,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  KEY idx_nl_tenant_time (tenant_id, created_at),
  KEY idx_nl_alert (alert_id),
  CONSTRAINT fk_nl_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='通知投递记录';

-- ── 第二家机构也要有独立的渠道配置（不继承，避免"一家改了影响两家"）────────
INSERT INTO notification_channels (tenant_id, type, name, config, min_level, enabled)
SELECT 1, 'wecom', '值班群（企业微信）', JSON_OBJECT('webhook', ''), 'MEDIUM', 0
WHERE NOT EXISTS (SELECT 1 FROM notification_channels WHERE tenant_id = 1);

INSERT INTO notification_channels (tenant_id, type, name, config, min_level, enabled)
SELECT 2, 'wecom', '值班群（企业微信）', JSON_OBJECT('webhook', ''), 'MEDIUM', 0
WHERE NOT EXISTS (SELECT 1 FROM notification_channels WHERE tenant_id = 2);
