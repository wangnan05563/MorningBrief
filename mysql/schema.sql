-- ============================================================
-- 20_News 项目数据库 DDL（MVP 阶段，11 张表）
-- 字符集：utf8mb4 / 引擎：InnoDB
-- 依据：概要设计说明书 V1.4 第 7.2 节
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. user 表（C 端用户，HLD 7.2.1）
--    微信小程序登录用户，记录收听累计数据
-- ------------------------------------------------------------
CREATE TABLE `user` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `openid` VARCHAR(64) NOT NULL UNIQUE,
  `unionid` VARCHAR(64),
  `nickname` VARCHAR(64),
  `avatar` VARCHAR(512),
  `total_listen_duration` INT DEFAULT 0 COMMENT '累计收听时长（秒）',
  `total_listen_count` INT DEFAULT 0 COMMENT '累计收听期数',
  `created_at` DATETIME DEFAULT NOW(),
  `updated_at` DATETIME DEFAULT NOW() ON UPDATE NOW(),
  INDEX idx_openid (openid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='C 端用户表';

-- ------------------------------------------------------------
-- 2. admin_user 表（B 端运营，HLD 7.2.2）
--    后台运营/管理员账号
-- ------------------------------------------------------------
CREATE TABLE `admin_user` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL UNIQUE,
  `password_hash` VARCHAR(128) NOT NULL COMMENT 'bcrypt 加盐哈希',
  `role` ENUM('admin','operator') NOT NULL DEFAULT 'operator',
  `nickname` VARCHAR(64),
  `status` TINYINT DEFAULT 1 COMMENT '1启用 0禁用',
  `last_login_at` DATETIME,
  `created_at` DATETIME DEFAULT NOW(),
  `updated_at` DATETIME DEFAULT NOW() ON UPDATE NOW()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='B 端运营表';

-- ------------------------------------------------------------
-- 3. script 表（稿件，HLD 7.2.4 / 3.3.6）
--    LLM 改写生成的播报稿件及分段结构
-- ------------------------------------------------------------
CREATE TABLE `script` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `workflow_id` VARCHAR(64) NOT NULL,
  `episode_date` DATE NOT NULL,
  `full_text` TEXT NOT NULL COMMENT '完整稿件',
  `segments` JSON NOT NULL COMMENT '分段结构 [{seq,title,content,start_sec,end_sec,material_ids}]',
  `total_words` INT,
  `estimated_duration` INT COMMENT '估算时长（秒）',
  `referenced_materials` JSON COMMENT '引用素材 URL 列表',
  `categories` JSON,
  `status` ENUM('draft','approved','rejected') DEFAULT 'draft',
  `created_at` DATETIME DEFAULT NOW(),
  INDEX idx_workflow (workflow_id),
  INDEX idx_date (episode_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='稿件表';

-- ------------------------------------------------------------
-- 4. material 表（爬取素材，HLD 7.2.12 / 3.2.4）
--    爬虫抓取的新闻原始素材
-- ------------------------------------------------------------
CREATE TABLE `material` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `source` VARCHAR(64) NOT NULL COMMENT '来源名称',
  `source_type` ENUM('rss','list') NOT NULL,
  `title` VARCHAR(256) NOT NULL,
  `content` TEXT NOT NULL COMMENT '正文全文',
  `summary` VARCHAR(512) COMMENT '摘要（前200字）',
  `url` VARCHAR(512) NOT NULL UNIQUE COMMENT '原始 URL（去重）',
  `published_at` DATETIME,
  `crawled_at` DATETIME DEFAULT NOW(),
  `category` VARCHAR(32) COMMENT '品类',
  `status` ENUM('pending','selected','skipped') DEFAULT 'pending',
  `simhash` VARCHAR(64) COMMENT '标题指纹（SimHash 去重）',
  `workflow_id` VARCHAR(64),
  INDEX idx_crawled_at (crawled_at),
  INDEX idx_workflow (workflow_id),
  INDEX idx_category (category),
  INDEX idx_simhash (simhash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='爬取素材表';

-- ------------------------------------------------------------
-- 5. ad_material 表（广告素材，HLD 7.2.5）
--    广告音频素材，不绑定位置
-- ------------------------------------------------------------
CREATE TABLE `ad_material` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(128) NOT NULL,
  `description` VARCHAR(512),
  `file_url` VARCHAR(512) NOT NULL,
  `duration` INT NOT NULL COMMENT '时长（秒）',
  `is_default` TINYINT DEFAULT 0 COMMENT '是否默认自营占位素材',
  `created_at` DATETIME DEFAULT NOW(),
  INDEX idx_default (is_default)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='广告素材表';

-- ------------------------------------------------------------
-- 6. ad_placement 表（广告投放规则，HLD 7.2.6）
--    指定素材在 head/mid/tail 位置及生效日期区间
-- ------------------------------------------------------------
CREATE TABLE `ad_placement` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `material_id` BIGINT NOT NULL,
  `position` ENUM('head','mid','tail') NOT NULL,
  `start_date` DATE NOT NULL,
  `end_date` DATE NOT NULL,
  `created_at` DATETIME DEFAULT NOW(),
  FOREIGN KEY (`material_id`) REFERENCES `ad_material`(`id`),
  INDEX idx_date_range (start_date, end_date),
  INDEX idx_position (position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='广告投放规则表';

-- ------------------------------------------------------------
-- 7. workflow 表（工作流，HLD 7.2.8）
--    单次「爬取→改写→TTS→拼接→审核→发布」流程记录
-- ------------------------------------------------------------
CREATE TABLE `workflow` (
  `id` VARCHAR(64) PRIMARY KEY COMMENT 'workflow_id',
  `episode_date` DATE NOT NULL,
  `source` ENUM('cron','manual') NOT NULL,
  `status` ENUM('running','success','failed','cancelled') DEFAULT 'running',
  `started_at` DATETIME DEFAULT NOW(),
  `finished_at` DATETIME,
  `error` TEXT,
  INDEX idx_date (episode_date),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流表';

-- ------------------------------------------------------------
-- 8. workflow_step 表（工作流步骤，HLD 7.2.8）
--    工作流内每个步骤的状态与产出
-- ------------------------------------------------------------
CREATE TABLE `workflow_step` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `workflow_id` VARCHAR(64) NOT NULL,
  `step_name` ENUM('crawl','rewrite','tts','stitch','review','publish') NOT NULL,
  `status` ENUM('pending','running','success','failed','retrying') DEFAULT 'pending',
  `started_at` DATETIME,
  `finished_at` DATETIME,
  `retry_count` INT DEFAULT 0,
  `error` TEXT,
  `result` JSON COMMENT '步骤产出（如素材数、稿件ID、音频URL）',
  FOREIGN KEY (`workflow_id`) REFERENCES `workflow`(`id`),
  INDEX idx_workflow_step (workflow_id, step_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流步骤表';

-- ------------------------------------------------------------
-- 9. review 表（审核，HLD 7.2.9）
--    人工审核记录，关联稿件与音频
-- ------------------------------------------------------------
CREATE TABLE `review` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `workflow_id` VARCHAR(64) NOT NULL,
  `episode_date` DATE NOT NULL,
  `script_id` BIGINT NOT NULL,
  `audio_url` VARCHAR(512) NOT NULL,
  `status` ENUM('pending','approved','rejected','replaced') DEFAULT 'pending',
  `reviewer_id` BIGINT COMMENT '审核人 admin_user.id',
  `reviewer_name` VARCHAR(64),
  `reason` TEXT COMMENT '打回/替换理由',
  `reviewed_at` DATETIME,
  `created_at` DATETIME DEFAULT NOW(),
  FOREIGN KEY (`script_id`) REFERENCES `script`(`id`),
  INDEX idx_status (status),
  INDEX idx_date (episode_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审核表';

-- ------------------------------------------------------------
-- 10. episode 表（节目，HLD 7.2.3）
--     单日播出的节目，关联稿件与审核记录
--     is_backup=1 标记备播节目，audio_url 指向前一日节目音频
-- ------------------------------------------------------------
CREATE TABLE `episode` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `date` DATE NOT NULL UNIQUE,
  `title` VARCHAR(128) NOT NULL,
  `duration` INT NOT NULL COMMENT '时长（秒）',
  `audio_url` VARCHAR(512) NOT NULL,
  `cover_url` VARCHAR(512),
  `script_id` BIGINT,
  `categories` JSON,
  `status` ENUM('draft','published','offline') DEFAULT 'draft',
  `is_backup` TINYINT DEFAULT 0 COMMENT '是否备播节目',
  `workflow_id` VARCHAR(64),
  `review_id` BIGINT,
  `published_at` DATETIME,
  `created_at` DATETIME DEFAULT NOW(),
  `updated_at` DATETIME DEFAULT NOW() ON UPDATE NOW(),
  FOREIGN KEY (`script_id`) REFERENCES `script`(`id`),
  FOREIGN KEY (`review_id`) REFERENCES `review`(`id`),
  INDEX idx_date (date),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='节目表';

-- ------------------------------------------------------------
-- 11. play_log 表（播放日志，HLD 7.2.7）
--     由后端异步从 Redis 批量落库（每 1 分钟一次）
-- ------------------------------------------------------------
CREATE TABLE `play_log` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT,
  `episode_id` BIGINT NOT NULL,
  `position` INT DEFAULT 0 COMMENT '播放位置（秒）',
  `duration` INT COMMENT '本次会话已播放时长（秒）',
  `completed` TINYINT DEFAULT 0,
  `played_at` DATETIME DEFAULT NOW(),
  FOREIGN KEY (`user_id`) REFERENCES `user`(`id`),
  FOREIGN KEY (`episode_id`) REFERENCES `episode`(`id`),
  INDEX idx_user_episode (user_id, episode_id),
  INDEX idx_played_at (played_at),
  INDEX idx_episode (episode_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='播放日志表';

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- 默认管理员账号（密码占位，部署前需替换为 bcrypt 真实哈希）
-- ------------------------------------------------------------
INSERT INTO `admin_user` (`username`, `password_hash`, `role`, `nickname`, `status`)
VALUES ('admin', '__BCRYPT_HASH_PLACEHOLDER__', 'admin', '超级管理员', 1);
