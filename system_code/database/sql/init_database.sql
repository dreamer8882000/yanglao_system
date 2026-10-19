-- 智慧养老跌倒检测系统数据库初始化脚本
-- 作用：创建数据库、创建全部业务表、插入演示数据，并设置演示账号密码。
-- 数据库：elderly_care_sbbr0v5jespt
-- 默认演示账号：admin / 123456
-- 其它演示用户：nurse_zhang、nurse_li、nurse_wang、nurse_zhao、nurse_sun，密码均为 123456

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP DATABASE IF EXISTS elderly_care_sbbr0v5jespt;

-- ===========================================================================================
-- 智慧养老跌倒检测系统 - 完整数据库结构
-- Database: elderly_care_sbbr0v5jespt
-- 生成时间: 2024
-- 说明: 包含所有表结构，用于快速部署或参考
-- ===========================================================================================

CREATE DATABASE IF NOT EXISTS elderly_care_sbbr0v5jespt DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE elderly_care_sbbr0v5jespt;

-- ===========================
-- 1. 用户表
-- ===========================
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(100) NOT NULL UNIQUE COMMENT '登录账号',
  name VARCHAR(100) NOT NULL COMMENT '姓名',
  email VARCHAR(200) NOT NULL DEFAULT '' COMMENT '邮箱',
  dept_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT '部门名称',
  avatar VARCHAR(500) NULL COMMENT '头像URL',
  password_hash VARCHAR(200) NULL COMMENT '密码哈希',
  last_login_at TIMESTAMP NULL COMMENT '最后登录时间',
  role VARCHAR(20) NOT NULL DEFAULT 'nurse' COMMENT '角色: admin-机构管理员, nurse-护理管理员',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ===========================
-- 2. 老人档案表
-- ===========================
CREATE TABLE IF NOT EXISTS elders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL COMMENT '姓名',
  gender TINYINT NOT NULL DEFAULT 1 COMMENT '性别: 1-男, 2-女',
  age INT NOT NULL COMMENT '年龄',
  room_no VARCHAR(20) NOT NULL COMMENT '房间号',
  admission_date DATE NOT NULL COMMENT '入院日期',
  health_notes TEXT NULL COMMENT '健康状况备注',
  contact_name VARCHAR(100) NOT NULL DEFAULT '' COMMENT '紧急联系人姓名',
  contact_phone VARCHAR(20) NOT NULL DEFAULT '' COMMENT '紧急联系人电话',
  avatar VARCHAR(500) NULL COMMENT '照片URL',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1-在档, 0-已离院',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_status (status),
  INDEX idx_room_no (room_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='老人档案表';

-- ===========================
-- 3. 摄像头表
-- ===========================
CREATE TABLE IF NOT EXISTS cameras (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL COMMENT '摄像头名称',
  room_no VARCHAR(20) NOT NULL COMMENT '绑定房间号',
  stream_url VARCHAR(500) NULL COMMENT '视频流地址',
  source_type VARCHAR(20) NOT NULL DEFAULT 'stream' COMMENT '视频源类型: local-本地摄像头, stream-流地址',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1-正常, 0-禁用',
  last_heartbeat TIMESTAMP NULL COMMENT '最近心跳时间',
  offline_notified TINYINT NOT NULL DEFAULT 0 COMMENT '离线已通知: 0-否, 1-是',
  yolo_enabled TINYINT NOT NULL DEFAULT 1 COMMENT 'YOLOv8推理开关: 1-启用, 0-禁用',
  yolo_model VARCHAR(50) NOT NULL DEFAULT 'pose' COMMENT 'AI推理模型: pose-融合推理, face-表情辅助, none-关闭推理',
  yolo_models JSON NULL COMMENT '推理模型列表（JSON数组）: ["pose","face"] 等',
  model_weights VARCHAR(255) NULL COMMENT '自定义模型权重文件路径（相对于 models/ 目录）',
  confidence_threshold DECIMAL(3,2) NOT NULL DEFAULT 0.50 COMMENT 'YOLO推理置信度阈值 (0.00-1.00)',
  inference_fps INT NOT NULL DEFAULT 1 COMMENT 'YOLO推理帧率 (每秒处理帧数)',
  note VARCHAR(200) NULL COMMENT '备注',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_room_no (room_no),
  INDEX idx_status (status),
  INDEX idx_cameras_model (yolo_model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='摄像头表';

-- ===========================
-- 4. 告警记录表
-- ===========================
CREATE TABLE IF NOT EXISTS alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  elder_id INT NULL COMMENT '关联老人ID',
  camera_id INT NULL COMMENT '触发摄像头ID',
  risk_level VARCHAR(10) NOT NULL COMMENT '风险等级: LOW/MEDIUM/HIGH/URGENT',
  fall_event_at DATETIME NULL COMMENT '跌倒事件标识（confirmed_fall_at，同一事件去重）',
  posture_type VARCHAR(24) NULL COMMENT '姿态类型: fall_like/lying/sitting/bending/standing/unknown',
  evidence_mode VARCHAR(24) NULL COMMENT '证据模式: pose_expression/pose_only/expression_only/no_evidence',
  fall_score DECIMAL(4,3) NULL COMMENT '跌倒分',
  pain_score DECIMAL(4,3) NULL COMMENT '痛苦分',
  confidence INT NOT NULL COMMENT '置信度百分比',
  alert_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '告警时间',
  status TINYINT NOT NULL DEFAULT 0 COMMENT '处理状态: 0-待处理, 1-已处理, 2-误报',
  handler_id INT NULL COMMENT '处理人ID',
  assigned_to INT NULL COMMENT '指派给的护士ID',
  handler_notes VARCHAR(200) NULL COMMENT '处置备注',
  handled_at TIMESTAMP NULL COMMENT '处理时间',
  escalated_at TIMESTAMP NULL COMMENT '超时升级通知时间',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_elder_id (elder_id),
  INDEX idx_camera_id (camera_id),
  INDEX idx_risk_level (risk_level),
  INDEX idx_status (status),
  INDEX idx_alert_time (alert_time),
  INDEX idx_assigned (assigned_to),
  INDEX idx_escalated (escalated_at),
  INDEX idx_elder_camera_time (elder_id, camera_id, alert_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警记录表';

-- ===========================
-- 5. 值班排班表
-- ===========================
CREATE TABLE IF NOT EXISTS schedules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL COMMENT '值班人员ID',
  shift_date DATE NOT NULL COMMENT '值班日期',
  shift_type VARCHAR(20) NOT NULL DEFAULT 'day' COMMENT '班次: day-白班, night-夜班, full-全天',
  start_time TIME NOT NULL DEFAULT '08:00:00' COMMENT '开始时间',
  end_time TIME NOT NULL DEFAULT '20:00:00' COMMENT '结束时间',
  note VARCHAR(200) NULL COMMENT '备注',
  created_by INT NULL COMMENT '创建人ID',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_shift_date (user_id, shift_date),
  INDEX idx_user_id (user_id),
  INDEX idx_shift_date (shift_date),
  INDEX idx_shift_type (shift_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='值班排班表';

-- ===========================
-- 6. 操作审计日志
-- ===========================
CREATE TABLE IF NOT EXISTS audit_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL COMMENT '操作人ID',
  username VARCHAR(100) NULL COMMENT '操作人账号',
  action VARCHAR(100) NOT NULL COMMENT '操作描述',
  resource_type VARCHAR(50) NULL COMMENT '资源类型: alert/elder/camera/setting/schedule',
  resource_id VARCHAR(50) NULL COMMENT '资源ID',
  detail TEXT NULL COMMENT '操作详情JSON',
  ip VARCHAR(50) NULL COMMENT 'IP地址',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_id (user_id),
  INDEX idx_action (action),
  INDEX idx_resource_type (resource_type),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作审计日志';

-- ===========================
-- 7. 系统配置表
-- ===========================
CREATE TABLE IF NOT EXISTS settings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  setting_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
  setting_value TEXT NULL COMMENT '配置值（支持JSON）',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_key (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- ===========================
-- 8. 消息中心（站内信）
-- ===========================
CREATE TABLE IF NOT EXISTS messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL COMMENT '接收用户ID',
  type VARCHAR(20) NOT NULL DEFAULT 'system' COMMENT '消息类型：alert/schedule/system',
  title VARCHAR(100) NOT NULL COMMENT '消息标题',
  content TEXT NOT NULL COMMENT '消息内容',
  related_id INT NULL COMMENT '关联对象ID（如告警ID、排班ID）',
  is_read TINYINT DEFAULT 0 COMMENT '是否已读：0未读/1已读',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  INDEX idx_user_read (user_id, is_read),
  INDEX idx_created (created_at),
  INDEX idx_type (type),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息中心';

-- ===========================
-- 9. 夜间巡查记录表
-- ===========================
CREATE TABLE IF NOT EXISTS patrol_records (
  id INT AUTO_INCREMENT PRIMARY KEY,
  elder_id INT NOT NULL COMMENT '老人ID',
  patrol_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '巡查时间',
  nurse_id INT NOT NULL COMMENT '巡查护士ID',
  location VARCHAR(50) NULL COMMENT '巡查位置(房间号)',
  notes VARCHAR(500) NULL COMMENT '巡查备注',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX idx_elder_id (elder_id),
  INDEX idx_nurse_id (nurse_id),
  INDEX idx_patrol_time (patrol_time),
  
  CONSTRAINT fk_patrol_elder FOREIGN KEY (elder_id) REFERENCES elders(id) ON DELETE CASCADE,
  CONSTRAINT fk_patrol_nurse FOREIGN KEY (nurse_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='夜间巡查记录表';

-- ===========================
-- 10. 用药清单表
-- ===========================
CREATE TABLE IF NOT EXISTS medications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  elder_id INT NOT NULL COMMENT '老人ID',
  medication_name VARCHAR(100) NOT NULL COMMENT '药品名称',
  dosage VARCHAR(50) NOT NULL COMMENT '剂量(如:2片)',
  frequency VARCHAR(50) NOT NULL COMMENT '频次(如:每日3次)',
  time_slots VARCHAR(200) NOT NULL COMMENT '服药时间段(JSON数组,如:["08:00","14:00","20:00"])',
  duration_days INT NULL COMMENT '持续天数(NULL表示长期)',
  notes VARCHAR(500) NULL COMMENT '用药说明',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '状态:1-启用,0-停用',
  created_by INT NOT NULL COMMENT '创建人ID',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  INDEX idx_elder_id (elder_id),
  INDEX idx_status (status),
  INDEX idx_created_by (created_by),
  
  CONSTRAINT fk_medication_elder FOREIGN KEY (elder_id) REFERENCES elders(id) ON DELETE CASCADE,
  CONSTRAINT fk_medication_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用药清单表';

-- ===========================
-- 11. 用药记录表
-- ===========================
CREATE TABLE IF NOT EXISTS medication_records (
  id INT AUTO_INCREMENT PRIMARY KEY,
  medication_id INT NOT NULL COMMENT '用药清单ID',
  elder_id INT NOT NULL COMMENT '老人ID',
  scheduled_time TIMESTAMP NOT NULL COMMENT '计划服药时间',
  actual_time TIMESTAMP NULL COMMENT '实际服药时间',
  nurse_id INT NULL COMMENT '确认护士ID',
  status TINYINT NOT NULL DEFAULT 0 COMMENT '状态:0-待服药,1-已服药,2-已跳过',
  notes VARCHAR(200) NULL COMMENT '备注',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX idx_medication_id (medication_id),
  INDEX idx_elder_id (elder_id),
  INDEX idx_scheduled_time (scheduled_time),
  INDEX idx_status (status),
  INDEX idx_nurse_id (nurse_id),
  
  CONSTRAINT fk_med_record_medication FOREIGN KEY (medication_id) REFERENCES medications(id) ON DELETE CASCADE,
  CONSTRAINT fk_med_record_elder FOREIGN KEY (elder_id) REFERENCES elders(id) ON DELETE CASCADE,
  CONSTRAINT fk_med_record_nurse FOREIGN KEY (nurse_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用药记录表';

-- ===========================
-- 12. 生命体征记录表
-- ===========================
CREATE TABLE IF NOT EXISTS vital_signs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  elder_id INT NOT NULL COMMENT '老人ID',
  record_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
  systolic_pressure INT NULL COMMENT '收缩压(mmHg)',
  diastolic_pressure INT NULL COMMENT '舒张压(mmHg)',
  heart_rate INT NULL COMMENT '心率(bpm)',
  blood_glucose DECIMAL(5,2) NULL COMMENT '血糖(mmol/L)',
  temperature DECIMAL(4,2) NULL COMMENT '体温(℃)',
  spo2 INT NULL COMMENT '血氧饱和度(%)',
  weight DECIMAL(5,2) NULL COMMENT '体重(kg)',
  notes VARCHAR(500) NULL COMMENT '备注',
  recorder_id INT NOT NULL COMMENT '记录人ID',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX idx_elder_id (elder_id),
  INDEX idx_record_time (record_time),
  INDEX idx_recorder_id (recorder_id),
  
  CONSTRAINT fk_vital_elder FOREIGN KEY (elder_id) REFERENCES elders(id) ON DELETE CASCADE,
  CONSTRAINT fk_vital_recorder FOREIGN KEY (recorder_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='生命体征记录表';

-- ===========================
-- 13. 体征预警规则表
-- ===========================
CREATE TABLE IF NOT EXISTS vital_alert_rules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  elder_id INT NOT NULL COMMENT '老人ID',
  vital_type VARCHAR(30) NOT NULL COMMENT '体征类型:systolic_pressure,diastolic_pressure,heart_rate,blood_glucose,temperature,spo2',
  min_value DECIMAL(10,2) NULL COMMENT '最小值',
  max_value DECIMAL(10,2) NULL COMMENT '最大值',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '状态:1-启用,0-停用',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  INDEX idx_elder_id (elder_id),
  INDEX idx_vital_type (vital_type),
  INDEX idx_status (status),
  
  CONSTRAINT fk_vital_rule_elder FOREIGN KEY (elder_id) REFERENCES elders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='体征预警规则表';

-- ===========================
-- 初始化配置数据
-- ===========================
INSERT IGNORE INTO settings (setting_key, setting_value) VALUES
('aiConfig', '{"minConfidence":20,"lowMin":20,"lowMax":50,"mediumMin":50,"mediumMax":80,"highMin":80}'),
('notifyConfig', '{"hiEnabled":true,"smsEnabled":true,"receivers":""}');


USE elderly_care_sbbr0v5jespt;

-- ===========================================================================================
-- 智慧养老跌倒检测系统 - 完整 Mock 数据插入脚本
-- Database: elderly_care_sbbr0v5jespt
-- 生成时间: 2024
-- 说明: 包含所有核心业务表的演示数据，用于功能展示和测试
-- ===========================================================================================

-- ===========================
-- 1. 用户表（users）- 6条
-- ===========================
INSERT INTO users (id, username, name, email, dept_name, avatar, role) VALUES
(1, 'admin', '系统管理员', 'admin@example.com', '机构管理部', 'https://images.pexels.com/photos/3184360/pexels-photo-3184360.jpeg?w=200', 'admin'),
(2, 'nurse_zhang', '张小芳', 'zhang.xf@example.com', '一楼护理部', 'https://images.pexels.com/photos/5327585/pexels-photo-5327585.jpeg?w=200', 'nurse'),
(3, 'nurse_li', '李明华', 'li.mh@example.com', '一楼护理部', 'https://images.pexels.com/photos/8942581/pexels-photo-8942581.jpeg?w=200', 'nurse'),
(4, 'nurse_wang', '王芳芳', 'wang.ff@example.com', '二楼护理部', 'https://images.pexels.com/photos/7108344/pexels-photo-7108344.jpeg?w=200', 'nurse'),
(5, 'nurse_zhao', '赵丽娟', 'zhao.lj@example.com', '二楼护理部', 'https://images.pexels.com/photos/8942557/pexels-photo-8942557.jpeg?w=200', 'nurse'),
(6, 'nurse_sun', '孙小梅', 'sun.xm@example.com', '三楼护理部', 'https://images.pexels.com/photos/8942664/pexels-photo-8942664.jpeg?w=200', 'nurse');

-- ===========================
-- 2. 老人档案表（elders）- 10条
-- ===========================
INSERT INTO elders (id, name, gender, age, room_no, admission_date, health_notes, contact_name, contact_phone, avatar, status) VALUES
(1, '张国强', 1, 78, '101', '2023-03-15', '高血压、冠心病，需定期监测血压，夜间注意防跌倒', '张晓明（儿子）', '13800138001', 'https://images.pexels.com/photos/2379004/pexels-photo-2379004.jpeg?w=300', 1),
(2, '李桂芳', 2, 82, '102', '2023-05-20', '糖尿病、骨质疏松，需控制饮食，行动需辅助器具', '李军（女儿）', '13800138002', 'https://images.pexels.com/photos/3768131/pexels-photo-3768131.jpeg?w=300', 1),
(3, '王德华', 1, 75, '103', '2023-07-10', '轻度认知障碍，需陪伴和认知训练，视力较弱', '王芳（女儿）', '13800138003', 'https://images.pexels.com/photos/3785079/pexels-photo-3785079.jpeg?w=300', 1),
(4, '赵淑珍', 2, 80, '104', '2023-08-05', '心脏病、高血脂，情绪稳定，饮食清淡', '赵勇（儿子）', '13800138004', 'https://images.pexels.com/photos/3823488/pexels-photo-3823488.jpeg?w=300', 1),
(5, '刘建国', 1, 76, '105', '2023-09-12', '脑梗康复期，左侧肢体活动受限，需康复训练', '刘婷（女儿）', '13800138005', 'https://images.pexels.com/photos/3785106/pexels-photo-3785106.jpeg?w=300', 1),
(6, '陈秀英', 2, 84, '201', '2023-06-18', '慢性支气管炎、关节炎，气候变化需注意', '陈强（儿子）', '13800138006', 'https://images.pexels.com/photos/3768114/pexels-photo-3768114.jpeg?w=300', 1),
(7, '杨志明', 1, 79, '202', '2023-04-22', '前列腺增生、高血压，夜间如厕频繁需关注', '杨丽（女儿）', '13800138007', 'https://images.pexels.com/photos/3823483/pexels-photo-3823483.jpeg?w=300', 1),
(8, '孙玉兰', 2, 81, '203', '2023-10-08', '糖尿病、视网膜病变，血糖监测，行动需搀扶', '孙伟（儿子）', '13800138008', 'https://images.pexels.com/photos/3785082/pexels-photo-3785082.jpeg?w=300', 1),
(9, '周国庆', 1, 77, '204', '2023-11-15', '慢性肾病、贫血，需低蛋白饮食，定期复查', '周敏（女儿）', '13800138009', 'https://images.pexels.com/photos/3823490/pexels-photo-3823490.jpeg?w=300', 1),
(10, '吴秀兰', 2, 83, '205', '2023-02-28', '阿尔茨海默病早期，情绪波动大，需耐心陪伴', '吴刚（儿子）', '13800138010', 'https://images.pexels.com/photos/3768117/pexels-photo-3768117.jpeg?w=300', 1);

-- ===========================
-- 3. 摄像头表（cameras）- 10条
-- ===========================
INSERT INTO cameras (id, name, room_no, stream_url, status, source_type, yolo_enabled, yolo_model, yolo_models, confidence_threshold, inference_fps, note) VALUES
(1, '101房摄像头', '101', 'rtsp://192.168.1.101:554/stream', 1, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.50, 1, '张国强房间监控'),
(2, '102房摄像头', '102', 'rtsp://192.168.1.102:554/stream', 1, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.50, 1, '李桂芳房间监控'),
(3, '103房摄像头', '103', 'rtsp://192.168.1.103:554/stream', 1, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.55, 1, '王德华房间监控'),
(4, '104房摄像头', '104', 'rtsp://192.168.1.104:554/stream', 1, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.50, 1, '赵淑珍房间监控'),
(5, '105房摄像头', '105', 'rtsp://192.168.1.105:554/stream', 1, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.50, 1, '刘建国房间监控'),
(6, '201房摄像头', '201', 'rtsp://192.168.1.201:554/stream', 1, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.50, 1, '陈秀英房间监控'),
(7, '202房摄像头', '202', 'rtsp://192.168.1.202:554/stream', 1, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.50, 1, '杨志明房间监控'),
(8, '203房摄像头', '203', 'rtsp://192.168.1.203:554/stream', 1, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.50, 1, '孙玉兰房间监控'),
(9, '204房摄像头', '204', 'rtsp://192.168.1.204:554/stream', 0, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.50, 1, '周国庆房间监控（离线）'),
(10, '205房摄像头', '205', 'rtsp://192.168.1.205:554/stream', 1, 'stream', 1, 'pose', JSON_ARRAY('pose'), 0.50, 1, '吴秀兰房间监控');

-- ===========================
-- 4. 告警记录表（alerts）- 25条
-- ===========================
INSERT INTO alerts (id, elder_id, camera_id, risk_level, confidence, alert_time, status, handler_id, handler_notes, handled_at) VALUES
-- 未处理告警（最新10条）
(1, 8, 8, 'HIGH', 92, DATE_SUB(NOW(), INTERVAL 15 MINUTE), 0, NULL, NULL, NULL),
(2, 3, 3, 'MEDIUM', 68, DATE_SUB(NOW(), INTERVAL 45 MINUTE), 0, NULL, NULL, NULL),
(3, 1, 1, 'HIGH', 88, DATE_SUB(NOW(), INTERVAL 1 HOUR), 0, NULL, NULL, NULL),
(4, 6, 6, 'LOW', 35, DATE_SUB(NOW(), INTERVAL 2 HOUR), 0, NULL, NULL, NULL),
(5, 10, 10, 'MEDIUM', 72, DATE_SUB(NOW(), INTERVAL 3 HOUR), 0, NULL, NULL, NULL),
(6, 5, 5, 'HIGH', 85, DATE_SUB(NOW(), INTERVAL 4 HOUR), 0, NULL, NULL, NULL),
(7, 7, 7, 'MEDIUM', 65, DATE_SUB(NOW(), INTERVAL 5 HOUR), 0, NULL, NULL, NULL),
(8, 2, 2, 'LOW', 42, DATE_SUB(NOW(), INTERVAL 6 HOUR), 0, NULL, NULL, NULL),
(9, 9, 9, 'HIGH', 90, DATE_SUB(NOW(), INTERVAL 7 HOUR), 0, NULL, NULL, NULL),
(10, 4, 4, 'MEDIUM', 70, DATE_SUB(NOW(), INTERVAL 8 HOUR), 0, NULL, NULL, NULL),

-- 已处理告警（历史15条）
(11, 1, 1, 'HIGH', 86, DATE_SUB(NOW(), INTERVAL 1 DAY), 1, 2, '老人已扶起，无外伤，情绪稳定', DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 5 MINUTE),
(12, 3, 3, 'MEDIUM', 65, DATE_SUB(NOW(), INTERVAL 1 DAY), 1, 3, '老人自行起身，已确认安全', DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 3 MINUTE),
(13, 5, 5, 'HIGH', 91, DATE_SUB(NOW(), INTERVAL 2 DAY), 1, 2, '紧急处理，已通知医生，无大碍', DATE_SUB(NOW(), INTERVAL 2 DAY) + INTERVAL 8 MINUTE),
(14, 7, 7, 'LOW', 38, DATE_SUB(NOW(), INTERVAL 2 DAY), 1, 4, '误报，老人正常活动', DATE_SUB(NOW(), INTERVAL 2 DAY) + INTERVAL 2 MINUTE),
(15, 2, 2, 'MEDIUM', 72, DATE_SUB(NOW(), INTERVAL 3 DAY), 1, 3, '老人床边跌倒，已协助回床', DATE_SUB(NOW(), INTERVAL 3 DAY) + INTERVAL 6 MINUTE),
(16, 8, 8, 'HIGH', 88, DATE_SUB(NOW(), INTERVAL 3 DAY), 1, 2, '如厕时摔倒，已处理伤口', DATE_SUB(NOW(), INTERVAL 3 DAY) + INTERVAL 10 MINUTE),
(17, 4, 4, 'LOW', 45, DATE_SUB(NOW(), INTERVAL 4 DAY), 1, 5, '误报，老人做康复训练', DATE_SUB(NOW(), INTERVAL 4 DAY) + INTERVAL 1 MINUTE),
(18, 10, 10, 'MEDIUM', 68, DATE_SUB(NOW(), INTERVAL 4 DAY), 1, 4, '轻微滑倒，无外伤', DATE_SUB(NOW(), INTERVAL 4 DAY) + INTERVAL 4 MINUTE),
(19, 6, 6, 'HIGH', 92, DATE_SUB(NOW(), INTERVAL 5 DAY), 1, 3, '起夜摔倒，腿部轻微擦伤，已处理', DATE_SUB(NOW(), INTERVAL 5 DAY) + INTERVAL 12 MINUTE),
(20, 9, 9, 'MEDIUM', 70, DATE_SUB(NOW(), INTERVAL 5 DAY), 1, 2, '老人坐轮椅时滑落，已扶正', DATE_SUB(NOW(), INTERVAL 5 DAY) + INTERVAL 5 MINUTE),
(21, 1, 1, 'LOW', 40, DATE_SUB(NOW(), INTERVAL 6 DAY), 1, 5, '误报，老人弯腰捡物', DATE_SUB(NOW(), INTERVAL 6 DAY) + INTERVAL 2 MINUTE),
(22, 7, 7, 'HIGH', 89, DATE_SUB(NOW(), INTERVAL 6 DAY), 1, 3, '浴室滑倒，无骨折，已通知家属', DATE_SUB(NOW(), INTERVAL 6 DAY) + INTERVAL 15 MINUTE),
(23, 3, 3, 'MEDIUM', 66, DATE_SUB(NOW(), INTERVAL 7 DAY), 1, 4, '床边轻微跌坐，老人状态良好', DATE_SUB(NOW(), INTERVAL 7 DAY) + INTERVAL 3 MINUTE),
(24, 5, 5, 'LOW', 42, DATE_SUB(NOW(), INTERVAL 7 DAY), 1, 2, '误报，老人正常起身', DATE_SUB(NOW(), INTERVAL 7 DAY) + INTERVAL 1 MINUTE),
(25, 2, 2, 'HIGH', 87, DATE_SUB(NOW(), INTERVAL 8 DAY), 1, 3, '夜间如厕摔倒，轻微擦伤已处理', DATE_SUB(NOW(), INTERVAL 8 DAY) + INTERVAL 10 MINUTE);

-- ===========================
-- 5. 值班排班表（schedules）- 56条
-- ===========================
-- 最近14天排班数据（前7天+今天+未来6天）
INSERT INTO schedules (user_id, shift_date, shift_type, start_time, end_time, note, created_by) VALUES
-- 前7天（历史）
(2, DATE_SUB(CURDATE(), INTERVAL 7 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(3, DATE_SUB(CURDATE(), INTERVAL 7 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(4, DATE_SUB(CURDATE(), INTERVAL 7 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(5, DATE_SUB(CURDATE(), INTERVAL 7 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(2, DATE_SUB(CURDATE(), INTERVAL 6 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(4, DATE_SUB(CURDATE(), INTERVAL 6 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(3, DATE_SUB(CURDATE(), INTERVAL 6 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(6, DATE_SUB(CURDATE(), INTERVAL 6 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(3, DATE_SUB(CURDATE(), INTERVAL 5 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(2, DATE_SUB(CURDATE(), INTERVAL 5 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(5, DATE_SUB(CURDATE(), INTERVAL 5 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(4, DATE_SUB(CURDATE(), INTERVAL 5 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(4, DATE_SUB(CURDATE(), INTERVAL 4 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(5, DATE_SUB(CURDATE(), INTERVAL 4 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(2, DATE_SUB(CURDATE(), INTERVAL 4 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(3, DATE_SUB(CURDATE(), INTERVAL 4 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(5, DATE_SUB(CURDATE(), INTERVAL 3 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(3, DATE_SUB(CURDATE(), INTERVAL 3 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(4, DATE_SUB(CURDATE(), INTERVAL 3 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(2, DATE_SUB(CURDATE(), INTERVAL 3 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(2, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(4, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(3, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(5, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(3, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(2, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(4, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(6, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

-- 今天
(4, CURDATE(), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(5, CURDATE(), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(2, CURDATE(), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(3, CURDATE(), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

-- 未来6天
(5, DATE_ADD(CURDATE(), INTERVAL 1 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(3, DATE_ADD(CURDATE(), INTERVAL 1 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(4, DATE_ADD(CURDATE(), INTERVAL 1 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(2, DATE_ADD(CURDATE(), INTERVAL 1 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(2, DATE_ADD(CURDATE(), INTERVAL 2 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(4, DATE_ADD(CURDATE(), INTERVAL 2 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(3, DATE_ADD(CURDATE(), INTERVAL 2 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(5, DATE_ADD(CURDATE(), INTERVAL 2 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(3, DATE_ADD(CURDATE(), INTERVAL 3 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(2, DATE_ADD(CURDATE(), INTERVAL 3 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(5, DATE_ADD(CURDATE(), INTERVAL 3 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(4, DATE_ADD(CURDATE(), INTERVAL 3 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(4, DATE_ADD(CURDATE(), INTERVAL 4 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(5, DATE_ADD(CURDATE(), INTERVAL 4 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(2, DATE_ADD(CURDATE(), INTERVAL 4 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(3, DATE_ADD(CURDATE(), INTERVAL 4 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(5, DATE_ADD(CURDATE(), INTERVAL 5 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(3, DATE_ADD(CURDATE(), INTERVAL 5 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(4, DATE_ADD(CURDATE(), INTERVAL 5 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(2, DATE_ADD(CURDATE(), INTERVAL 5 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1),

(2, DATE_ADD(CURDATE(), INTERVAL 6 DAY), 'day', '08:00:00', '20:00:00', '一楼白班', 1),
(4, DATE_ADD(CURDATE(), INTERVAL 6 DAY), 'night', '20:00:00', '08:00:00', '一楼夜班', 1),
(3, DATE_ADD(CURDATE(), INTERVAL 6 DAY), 'day', '08:00:00', '20:00:00', '二楼白班', 1),
(6, DATE_ADD(CURDATE(), INTERVAL 6 DAY), 'night', '20:00:00', '08:00:00', '二楼夜班', 1);

-- ===========================
-- 6. 审计日志表（audit_logs）- 50条
-- ===========================
INSERT INTO audit_logs (user_id, username, action, resource_type, resource_id, detail, ip) VALUES
(1, 'admin', '登录系统', NULL, NULL, '{"browser":"Chrome","os":"Windows 10"}', '192.168.1.100'),
(2, 'nurse_zhang', '处理告警', 'alert', '11', '{"status":"已处理","notes":"老人已扶起"}', '192.168.1.101'),
(1, 'admin', '创建排班', 'schedule', '1', '{"user":"张小芳","date":"2024-01-20","shift":"day"}', '192.168.1.100'),
(3, 'nurse_li', '处理告警', 'alert', '12', '{"status":"已处理","notes":"老人自行起身"}', '192.168.1.102'),
(4, 'nurse_wang', '更新老人档案', 'elder', '1', '{"field":"health_notes","action":"更新健康备注"}', '192.168.1.103'),
(2, 'nurse_zhang', '处理告警', 'alert', '13', '{"status":"已处理","notes":"紧急处理"}', '192.168.1.101'),
(1, 'admin', '修改系统配置', 'setting', 'aiConfig', '{"minConfidence":20}', '192.168.1.100'),
(5, 'nurse_zhao', '添加用药记录', 'medication', '1', '{"elder":"张国强","medication":"降压药"}', '192.168.1.104'),
(3, 'nurse_li', '处理告警', 'alert', '15', '{"status":"已处理"}', '192.168.1.102'),
(1, 'admin', '新增用户', 'user', '6', '{"username":"nurse_sun","name":"孙小梅"}', '192.168.1.100'),
(4, 'nurse_wang', '更新摄像头', 'camera', '3', '{"field":"yolo_enabled","value":true}', '192.168.1.103'),
(2, 'nurse_zhang', '记录生命体征', 'vital_sign', '1', '{"elder":"张国强","bp":"130/85"}', '192.168.1.101'),
(3, 'nurse_li', '处理告警', 'alert', '16', '{"status":"已处理"}', '192.168.1.102'),
(5, 'nurse_zhao', '夜间巡查', 'patrol', '1', '{"room":"101","notes":"睡眠正常"}', '192.168.1.104'),
(1, 'admin', '创建排班', 'schedule', '8', '{"user":"李明华","date":"2024-01-21"}', '192.168.1.100'),
(4, 'nurse_wang', '处理告警', 'alert', '17', '{"status":"已处理"}', '192.168.1.103'),
(2, 'nurse_zhang', '更新老人档案', 'elder', '3', '{"field":"contact_phone"}', '192.168.1.101'),
(3, 'nurse_li', '处理告警', 'alert', '18', '{"status":"已处理"}', '192.168.1.102'),
(1, 'admin', '登录系统', NULL, NULL, '{"browser":"Chrome","os":"Windows 10"}', '192.168.1.100'),
(5, 'nurse_zhao', '记录生命体征', 'vital_sign', '2', '{"elder":"李桂芳","bg":"6.2"}', '192.168.1.104'),
(3, 'nurse_li', '处理告警', 'alert', '19', '{"status":"已处理"}', '192.168.1.102'),
(4, 'nurse_wang', '添加用药记录', 'medication', '2', '{"elder":"李桂芳"}', '192.168.1.103'),
(2, 'nurse_zhang', '处理告警', 'alert', '20', '{"status":"已处理"}', '192.168.1.101'),
(1, 'admin', '修改系统配置', 'setting', 'notifyConfig', '{"hiEnabled":true}', '192.168.1.100'),
(5, 'nurse_zhao', '处理告警', 'alert', '21', '{"status":"已处理"}', '192.168.1.104'),
(3, 'nurse_li', '处理告警', 'alert', '22', '{"status":"已处理"}', '192.168.1.102'),
(4, 'nurse_wang', '处理告警', 'alert', '23', '{"status":"已处理"}', '192.168.1.103'),
(2, 'nurse_zhang', '处理告警', 'alert', '24', '{"status":"已处理"}', '192.168.1.101'),
(1, 'admin', '创建排班', 'schedule', '15', '{"user":"王芳芳"}', '192.168.1.100'),
(3, 'nurse_li', '处理告警', 'alert', '25', '{"status":"已处理"}', '192.168.1.102'),
(5, 'nurse_zhao', '夜间巡查', 'patrol', '5', '{"room":"105"}', '192.168.1.104'),
(4, 'nurse_wang', '记录生命体征', 'vital_sign', '8', '{"elder":"孙玉兰"}', '192.168.1.103'),
(1, 'admin', '登录系统', NULL, NULL, '{"browser":"Chrome"}', '192.168.1.100'),
(2, 'nurse_zhang', '更新老人档案', 'elder', '6', '{"field":"health_notes"}', '192.168.1.101'),
(3, 'nurse_li', '添加用药记录', 'medication', '3', '{"elder":"王德华"}', '192.168.1.102'),
(5, 'nurse_zhao', '记录生命体征', 'vital_sign', '10', '{"elder":"吴秀兰"}', '192.168.1.104'),
(4, 'nurse_wang', '夜间巡查', 'patrol', '8', '{"room":"203"}', '192.168.1.103'),
(1, 'admin', '更新摄像头', 'camera', '9', '{"status":"离线"}', '192.168.1.100'),
(2, 'nurse_zhang', '登录系统', NULL, NULL, '{"browser":"Chrome"}', '192.168.1.101'),
(3, 'nurse_li', '登录系统', NULL, NULL, '{"browser":"Chrome"}', '192.168.1.102'),
(4, 'nurse_wang', '登录系统', NULL, NULL, '{"browser":"Chrome"}', '192.168.1.103'),
(5, 'nurse_zhao', '登录系统', NULL, NULL, '{"browser":"Chrome"}', '192.168.1.104'),
(1, 'admin', '修改系统配置', 'setting', 'aiConfig', '{"highMin":80}', '192.168.1.100'),
(2, 'nurse_zhang', '记录生命体征', 'vital_sign', '5', '{"elder":"刘建国"}', '192.168.1.101'),
(3, 'nurse_li', '夜间巡查', 'patrol', '3', '{"room":"103"}', '192.168.1.102'),
(4, 'nurse_wang', '更新老人档案', 'elder', '7', '{"field":"contact_name"}', '192.168.1.103'),
(5, 'nurse_zhao', '添加用药记录', 'medication', '5', '{"elder":"刘建国"}', '192.168.1.104'),
(1, 'admin', '创建排班', 'schedule', '22', '{"user":"赵丽娟"}', '192.168.1.100'),
(2, 'nurse_zhang', '记录生命体征', 'vital_sign', '7', '{"elder":"杨志明"}', '192.168.1.101'),
(3, 'nurse_li', '登录系统', NULL, NULL, '{"browser":"Chrome"}', '192.168.1.102');

-- ===========================
-- 7. 消息中心表（messages）- 23条
-- ===========================
INSERT INTO messages (user_id, type, title, content, related_id, is_read) VALUES
-- 未读消息（8条）
(2, 'alert', '新告警：101房高危跌倒', '张国强（101房）检测到高危跌倒，置信度88%，请立即处理', 3, 0),
(4, 'alert', '新告警：203房高危跌倒', '孙玉兰（203房）检测到高危跌倒，置信度92%，请立即处理', 1, 0),
(3, 'alert', '新告警：103房中危跌倒', '王德华（103房）检测到中危跌倒，置信度68%，请及时处理', 2, 0),
(5, 'alert', '新告警：105房高危跌倒', '刘建国（105房）检测到高危跌倒，置信度85%，请立即处理', 6, 0),
(2, 'schedule', '排班提醒', '您明天（2024-01-21）的排班：二楼白班 08:00-20:00', NULL, 0),
(3, 'schedule', '排班提醒', '您明天（2024-01-21）的排班：二楼夜班 20:00-08:00', NULL, 0),
(4, 'system', '系统升级通知', '系统将于今晚23:00-23:30进行升级维护，请提前保存工作', NULL, 0),
(2, 'system', '新功能上线', '生命体征趋势分析功能已上线，可在生命体征页面查看', NULL, 0),

-- 已读消息（15条）
(2, 'alert', '告警已处理：101房', '张国强（101房）的告警已被您处理', 11, 1),
(3, 'alert', '告警已处理：103房', '王德华（103房）的告警已被您处理', 12, 1),
(2, 'alert', '告警已处理：105房', '刘建国（105房）的告警已被您处理', 13, 1),
(4, 'schedule', '排班变更通知', '您的排班已调整：1月18日 一楼夜班→二楼白班', NULL, 1),
(3, 'alert', '告警已处理：102房', '李桂芳（102房）的告警已被您处理', 15, 1),
(2, 'alert', '告警已处理：203房', '孙玉兰（203房）的告警已被您处理', 16, 1),
(5, 'system', '设备离线提醒', '204房摄像头离线，请检查网络连接', NULL, 1),
(4, 'alert', '告警已处理：205房', '吴秀兰（205房）的告警已被您处理', 18, 1),
(3, 'alert', '告警已处理：201房', '陈秀英（201房）的告警已被您处理', 19, 1),
(2, 'alert', '告警已处理：204房', '周国庆（204房）的告警已被您处理', 20, 1),
(5, 'schedule', '排班提醒', '您后天的排班：一楼夜班 20:00-08:00', NULL, 1),
(3, 'alert', '告警已处理：202房', '杨志明（202房）的告警已被您处理', 22, 1),
(4, 'alert', '告警已处理：103房', '王德华（103房）的告警已被您处理', 23, 1),
(2, 'system', '数据备份完成', '每日数据备份已完成，备份文件存储正常', NULL, 1),
(3, 'system', '培训通知', '新版系统操作培训将于下周一下午2点举行', NULL, 1);

-- ===========================
-- 8. 体征预警规则表（vital_alert_rules）- 40条
-- ===========================
INSERT INTO vital_alert_rules (elder_id, vital_type, min_value, max_value, status) VALUES
-- 张国强（高血压患者）
(1, 'systolic_pressure', 90, 150, 1),
(1, 'diastolic_pressure', 60, 90, 1),
(1, 'heart_rate', 50, 100, 1),
(1, 'temperature', 36.0, 37.5, 1),

-- 李桂芳（糖尿病患者）
(2, 'systolic_pressure', 90, 140, 1),
(2, 'diastolic_pressure', 60, 90, 1),
(2, 'heart_rate', 60, 100, 1),
(2, 'blood_glucose', 4.0, 8.0, 1),
(2, 'temperature', 36.0, 37.5, 1),

-- 王德华（轻度认知障碍）
(3, 'systolic_pressure', 90, 140, 1),
(3, 'diastolic_pressure', 60, 90, 1),
(3, 'heart_rate', 60, 100, 1),
(3, 'temperature', 36.0, 37.5, 1),

-- 赵淑珍（心脏病患者）
(4, 'systolic_pressure', 90, 140, 1),
(4, 'diastolic_pressure', 60, 90, 1),
(4, 'heart_rate', 50, 90, 1),
(4, 'temperature', 36.0, 37.5, 1),

-- 刘建国（脑梗康复期）
(5, 'systolic_pressure', 90, 150, 1),
(5, 'diastolic_pressure', 60, 90, 1),
(5, 'heart_rate', 55, 95, 1),
(5, 'temperature', 36.0, 37.5, 1),

-- 陈秀英（慢性支气管炎）
(6, 'systolic_pressure', 90, 140, 1),
(6, 'diastolic_pressure', 60, 90, 1),
(6, 'heart_rate', 60, 100, 1),
(6, 'spo2', 90, 100, 1),
(6, 'temperature', 36.0, 37.5, 1),

-- 杨志明（高血压）
(7, 'systolic_pressure', 90, 150, 1),
(7, 'diastolic_pressure', 60, 90, 1),
(7, 'heart_rate', 55, 95, 1),
(7, 'temperature', 36.0, 37.5, 1),

-- 孙玉兰（糖尿病+视网膜病变）
(8, 'systolic_pressure', 90, 140, 1),
(8, 'diastolic_pressure', 60, 90, 1),
(8, 'heart_rate', 60, 100, 1),
(8, 'blood_glucose', 4.0, 8.0, 1),
(8, 'temperature', 36.0, 37.5, 1),

-- 周国庆（慢性肾病）
(9, 'systolic_pressure', 90, 140, 1),
(9, 'diastolic_pressure', 60, 90, 1),
(9, 'heart_rate', 60, 100, 1),
(9, 'temperature', 36.0, 37.5, 1),

-- 吴秀兰（阿尔茨海默病）
(10, 'systolic_pressure', 90, 140, 1),
(10, 'diastolic_pressure', 60, 90, 1),
(10, 'heart_rate', 60, 100, 1),
(10, 'temperature', 36.0, 37.5, 1);

-- ===========================
-- 9. 夜间巡查记录表（patrol_records）- 10条
-- ===========================
INSERT INTO patrol_records (elder_id, patrol_time, nurse_id, location, notes) VALUES
(1, '2024-01-20 22:30:00', 1, '101', '老人睡眠正常，房间温度适宜'),
(2, '2024-01-20 22:35:00', 1, '102', '老人已入睡，被褥整理完毕'),
(3, '2024-01-20 22:45:00', 2, '103', '老人暂未入睡，协助翻身'),
(1, '2024-01-21 01:15:00', 2, '101', '老人睡眠平稳'),
(2, '2024-01-21 01:20:00', 2, '102', '老人轻微咳嗽，已记录'),
(3, '2024-01-21 01:30:00', 1, '103', '老人醒来如厕，协助完成'),
(1, '2024-01-21 04:00:00', 1, '101', '老人睡眠深沉，各项正常'),
(4, '2024-01-21 22:30:00', 1, '104', '老人已入睡，生命体征平稳'),
(5, '2024-01-21 22:40:00', 2, '105', '老人睡前情绪良好'),
(1, '2024-01-22 01:00:00', 1, '101', '巡查正常，房间安静');

-- ===========================
-- 10. 用药清单表（medications）- 8条
-- ===========================
INSERT INTO medications (elder_id, medication_name, dosage, frequency, time_slots, duration_days, notes, status, created_by) VALUES
(1, '阿司匹林肠溶片', '100mg 1片', '每日1次', '[\"08:00\"]', NULL, '饭后服用，预防心血管疾病', 1, 1),
(1, '降压药（缬沙坦）', '80mg 1片', '每日2次', '[\"08:00\",\"20:00\"]', NULL, '早晚各1次，监测血压', 1, 1),
(2, '二甲双胍缓释片', '500mg 2片', '每日3次', '[\"08:00\",\"13:00\",\"18:00\"]', NULL, '控制血糖，餐后服用', 1, 1),
(2, '钙片+维生素D', '1片', '每日1次', '[\"20:00\"]', NULL, '睡前服用，预防骨质疏松', 1, 1),
(3, '胃药（奥美拉唑）', '20mg 1粒', '每日2次', '[\"07:30\",\"19:30\"]', 14, '餐前半小时服用，疗程2周', 1, 2),
(3, '安眠药（艾司唑仑）', '1mg 1片', '每晚1次', '[\"21:30\"]', NULL, '睡前服用，注意观察', 1, 2),
(4, '抗生素（头孢）', '0.5g 1粒', '每日3次', '[\"08:00\",\"14:00\",\"20:00\"]', 7, '饭后服用，疗程7天', 1, 1),
(5, '复合维生素', '1片', '每日1次', '[\"09:00\"]', NULL, '早餐后服用，增强免疫力', 1, 2);

-- ===========================
-- 11. 用药记录表（medication_records）- 15条
-- ===========================
INSERT INTO medication_records (medication_id, elder_id, scheduled_time, actual_time, nurse_id, status, notes) VALUES
-- 已服药
(1, 1, '2024-01-20 08:00:00', '2024-01-20 08:05:00', 2, 1, '按时服用'),
(2, 1, '2024-01-20 08:00:00', '2024-01-20 08:05:00', 2, 1, '与阿司匹林一起服用'),
(3, 2, '2024-01-20 08:00:00', '2024-01-20 08:10:00', 2, 1, '餐后服用'),
(5, 3, '2024-01-20 07:30:00', '2024-01-20 07:35:00', 3, 1, '餐前服用'),
(7, 4, '2024-01-20 08:00:00', '2024-01-20 08:15:00', 4, 1, '疗程第3天'),
(2, 1, '2024-01-20 20:00:00', '2024-01-20 20:05:00', 5, 1, '晚间按时服用'),
(6, 3, '2024-01-20 21:30:00', '2024-01-20 21:35:00', 5, 1, '睡前服用'),
(3, 2, '2024-01-21 08:00:00', '2024-01-21 08:08:00', 2, 1, '餐后服用'),
(1, 1, '2024-01-21 08:00:00', '2024-01-21 08:05:00', 2, 1, '按时服用'),

-- 待服药
(3, 2, '2024-01-21 13:00:00', NULL, NULL, 0, NULL),
(7, 4, '2024-01-21 14:00:00', NULL, NULL, 0, NULL),
(3, 2, '2024-01-21 18:00:00', NULL, NULL, 0, NULL),
(5, 3, '2024-01-21 19:30:00', NULL, NULL, 0, NULL),
(2, 1, '2024-01-21 20:00:00', NULL, NULL, 0, NULL),
(7, 4, '2024-01-21 20:00:00', NULL, NULL, 0, NULL);

-- ===========================
-- 12. 生命体征记录表（vital_signs）- 20条
-- ===========================
INSERT INTO vital_signs (elder_id, record_time, systolic_pressure, diastolic_pressure, heart_rate, blood_glucose, temperature, spo2, notes, recorder_id) VALUES
-- 正常数据（最近7天）
(1, DATE_SUB(NOW(), INTERVAL 7 DAY), 135, 85, 78, NULL, 36.8, 97, '血压略高，继续观察', 2),
(2, DATE_SUB(NOW(), INTERVAL 7 DAY), 128, 82, 75, 6.2, 36.7, 98, '血糖控制良好', 2),
(3, DATE_SUB(NOW(), INTERVAL 7 DAY), 125, 80, 72, NULL, 36.6, 98, '各项正常', 3),

(1, DATE_SUB(NOW(), INTERVAL 6 DAY), 132, 84, 76, NULL, 36.7, 97, '血压稳定', 2),
(2, DATE_SUB(NOW(), INTERVAL 6 DAY), 130, 83, 77, 6.5, 36.8, 97, '血糖稍高', 3),
(3, DATE_SUB(NOW(), INTERVAL 6 DAY), 128, 82, 74, NULL, 36.7, 98, '状态良好', 3),

(1, DATE_SUB(NOW(), INTERVAL 5 DAY), 130, 82, 75, NULL, 36.6, 98, '各项指标正常', 4),
(2, DATE_SUB(NOW(), INTERVAL 5 DAY), 125, 80, 73, 5.9, 36.6, 98, '血糖控制较好', 4),
(3, DATE_SUB(NOW(), INTERVAL 5 DAY), 130, 84, 76, NULL, 36.8, 97, '血压正常', 2),

(1, DATE_SUB(NOW(), INTERVAL 4 DAY), 128, 81, 74, NULL, 36.7, 98, '状态稳定', 2),
(2, DATE_SUB(NOW(), INTERVAL 4 DAY), 132, 85, 78, 6.8, 36.9, 97, '血糖偏高，调整饮食', 3),
(3, DATE_SUB(NOW(), INTERVAL 4 DAY), 125, 79, 71, NULL, 36.5, 98, '各项正常', 3),

(1, DATE_SUB(NOW(), INTERVAL 3 DAY), 133, 83, 77, NULL, 36.8, 97, '血压略高', 4),
(2, DATE_SUB(NOW(), INTERVAL 3 DAY), 127, 81, 75, 6.0, 36.7, 98, '血糖稳定', 4),
(3, DATE_SUB(NOW(), INTERVAL 3 DAY), 128, 82, 73, NULL, 36.6, 98, '状态良好', 2),

-- 异常数据（最近2天）
(8, DATE_SUB(NOW(), INTERVAL 2 DAY), 160, 95, 105, 9.5, 37.2, 95, '⚠️ 血压过高、心率过快、血糖超标，已通知医生', 3),
(8, DATE_SUB(NOW(), INTERVAL 1 DAY), 155, 92, 102, 8.8, 37.0, 96, '⚠️ 持续偏高，密切观察', 4),

(1, DATE_SUB(NOW(), INTERVAL 1 HOUR), 138, 86, 80, NULL, 36.8, 97, '今日测量，血压稍高', 2),
(2, DATE_SUB(NOW(), INTERVAL 1 HOUR), 130, 83, 76, 6.3, 36.7, 98, '今日测量，血糖正常', 2),
(8, DATE_SUB(NOW(), INTERVAL 30 MINUTE), 158, 94, 103, 9.2, 37.1, 95, '⚠️ 仍然偏高，继续监测', 5);

-- ===========================
-- 完成提示
-- ===========================
-- ✅ 完整 Mock 数据插入完成！
-- 
-- 数据统计：
-- ✅ 6 个用户（1管理员 + 5护士）
-- ✅ 10 个老人档案（覆盖常见慢性病场景）
-- ✅ 10 个摄像头（9在线 + 1离线）
-- ✅ 25 条告警记录（10未处理 + 15已处理）
-- ✅ 56 条排班记录（前7天+今天+未来6天，双班次）
-- ✅ 50 条审计日志（覆盖所有核心操作）
-- ✅ 23 条站内消息（8未读 + 15已读）
-- ✅ 40 条体征预警规则（10个老人，每人4-5条规则）
-- ✅ 10 条夜间巡查记录
-- ✅ 8 条用药清单（长期+短期用药）
-- ✅ 15 条用药记录（9已服药 + 6待服药）
-- ✅ 20 条生命体征记录（含正常和异常数据）
--
-- 所有页面均有完整数据支持：
-- ✅ Dashboard（首页）
-- ✅ Monitor（实时监控）
-- ✅ Alerts（告警记录）
-- ✅ Elders（老人档案）
-- ✅ Schedule（排班管理）
-- ✅ Audit（审计日志）
-- ✅ Patrol（夜间巡查）
-- ✅ Medication（用药管理）
-- ✅ VitalSign（生命体征）
-- ✅ Settings（系统设置）
-- ✅ SystemMonitor（系统监控）


UPDATE users SET password_hash = '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92';

SET FOREIGN_KEY_CHECKS = 1;
