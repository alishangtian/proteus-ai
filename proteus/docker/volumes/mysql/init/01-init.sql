-- 初始化脚本示例
-- 这个脚本会在 MySQL 容器首次启动时自动执行

-- 确保 agent 数据库存在
CREATE DATABASE IF NOT EXISTS agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用 agent 数据库
USE agent;

-- 创建一个示例表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_name VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 插入一些示例数据
INSERT IGNORE INTO users (user_name, email) VALUES 
('admin', 'admin@example.com'),
('agent', 'agent@example.com');

-- 显示创建的表
SHOW TABLES;