-- 20_News 数据库初始化脚本
-- Docker MySQL 容器首次启动时自动执行
-- 注意：此脚本仅创建数据库与授权，表结构由 Alembic 迁移管理

CREATE DATABASE IF NOT EXISTS news_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'news_app'@'%'
  IDENTIFIED BY 'CHANGE_ME_IN_ENV';

GRANT ALL PRIVILEGES ON news_db.* TO 'news_app'@'%';
FLUSH PRIVILEGES;

-- 时区
SET GLOBAL time_zone = '+08:00';
