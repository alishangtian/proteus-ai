-- 记忆系统数据库表结构
-- 适用于SQLite，也可适配其他数据库

-- 记忆主表
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,                -- 记忆ID
    content TEXT NOT NULL,              -- 记忆内容
    content_hash TEXT,                  -- 内容哈希（用于去重）
    importance REAL DEFAULT 0.5,        -- 重要性评分 (0.0-1.0)
    memory_type TEXT DEFAULT 'long_term', -- 记忆类型
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 更新时间
    last_accessed TIMESTAMP,            -- 最后访问时间
    access_count INTEGER DEFAULT 0,     -- 访问次数
    embedding_vector BLOB,              -- 嵌入向量（二进制）
    embedding_model TEXT,               -- 嵌入模型名称
    embedding_dim INTEGER,              -- 向量维度
    metadata JSON,                      -- 元数据（JSON格式）
    is_compressed BOOLEAN DEFAULT FALSE, -- 是否已压缩
    compressed_from TEXT,               -- 压缩来源（记忆ID列表）
    expires_at TIMESTAMP,               -- 过期时间（可选）
    
    -- 索引
    CHECK (importance >= 0 AND importance <= 1)
);

-- 标签表（多对多关系）
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,          -- 标签名称
    category TEXT,                      -- 标签类别
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 记忆-标签关联表
CREATE TABLE IF NOT EXISTS memory_tags (
    memory_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (memory_id, tag_id),
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- 用户表（如果支持多用户）
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    display_name TEXT,
    preferences JSON,                   -- 用户偏好
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);

-- 用户-记忆关联表
CREATE TABLE IF NOT EXISTS user_memories (
    user_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    is_owner BOOLEAN DEFAULT TRUE,      -- 是否拥有该记忆
    can_edit BOOLEAN DEFAULT TRUE,      -- 是否可以编辑
    can_delete BOOLEAN DEFAULT TRUE,    -- 是否可以删除
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (user_id, memory_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

-- 会话表（用于跟踪对话上下文）
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    summary TEXT,                       -- 会话摘要
    topic TEXT,                         -- 主要话题
    metadata JSON,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 会话记忆关联表
CREATE TABLE IF NOT EXISTS session_memories (
    session_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    role TEXT,                          -- 角色: user|assistant|system
    turn_index INTEGER,                 -- 对话轮次索引
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (session_id, memory_id, turn_index),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

-- 事件表（重要事件记录）
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,           -- 事件类型
    title TEXT,                         -- 事件标题
    description TEXT,                   -- 事件描述
    event_date DATE,                    -- 事件日期
    recurrence TEXT,                    -- 重复模式: none|daily|weekly|monthly|yearly
    importance REAL DEFAULT 0.5,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 事件-记忆关联表
CREATE TABLE IF NOT EXISTS event_memories (
    event_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    relationship_type TEXT,             -- 关系类型: related|source|outcome
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (event_id, memory_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

-- 偏好表（结构化用户偏好）
CREATE TABLE IF NOT EXISTS preferences (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    preference_key TEXT NOT NULL,       -- 偏好键
    preference_value TEXT,              -- 偏好值
    value_type TEXT DEFAULT 'string',   -- 值类型: string|number|boolean|array|object
    category TEXT,                      -- 偏好类别
    importance REAL DEFAULT 0.5,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, preference_key)
);

-- 记忆关系表（记忆之间的关联）
CREATE TABLE IF NOT EXISTS memory_relationships (
    source_memory_id TEXT NOT NULL,
    target_memory_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,    -- 关系类型: similar|contradicts|supports|follows
    confidence REAL DEFAULT 0.5,        -- 关系置信度
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (source_memory_id, target_memory_id, relationship_type),
    FOREIGN KEY (source_memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (target_memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

-- 系统日志表
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,                -- 日志级别: DEBUG|INFO|WARNING|ERROR
    module TEXT,                        -- 模块名称
    operation TEXT,                     -- 操作类型
    message TEXT NOT NULL,              -- 日志消息
    details JSON,                       -- 详细信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 审计日志表（重要操作记录）
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    operation TEXT NOT NULL,            -- 操作: create|read|update|delete|search
    resource_type TEXT NOT NULL,        -- 资源类型: memory|user|session|event
    resource_id TEXT,                   -- 资源ID
    changes JSON,                       -- 变更详情
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 备份记录表
CREATE TABLE IF NOT EXISTS backups (
    id TEXT PRIMARY KEY,
    backup_type TEXT NOT NULL,          -- 备份类型: full|incremental
    size_mb REAL,                       -- 备份大小（MB）
    checksum TEXT,                      -- 校验和
    storage_location TEXT,              -- 存储位置
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP                -- 过期时间
);

-- 创建索引以提高查询性能

-- 记忆表索引
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_memories_memory_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_expires_at ON memories(expires_at) WHERE expires_at IS NOT NULL;

-- 标签索引
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);

-- 用户相关索引
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active DESC);

-- 会话索引
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at DESC);

-- 事件索引
CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_importance ON events(importance DESC);

-- 偏好索引
CREATE INDEX IF NOT EXISTS idx_preferences_user_id ON preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_preferences_category ON preferences(category);
CREATE INDEX IF NOT EXISTS idx_preferences_key ON preferences(preference_key);

-- 系统日志索引
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_module_operation ON system_logs(module, operation);

-- 审计日志索引
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_operation ON audit_logs(operation);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- 视图：重要记忆视图
CREATE VIEW IF NOT EXISTS important_memories AS
SELECT 
    m.id,
    m.content,
    m.importance,
    m.memory_type,
    m.created_at,
    m.last_accessed,
    m.access_count,
    GROUP_CONCAT(t.name, ', ') AS tags
FROM memories m
LEFT JOIN memory_tags mt ON m.id = mt.memory_id
LEFT JOIN tags t ON mt.tag_id = t.id
WHERE m.importance >= 0.7
GROUP BY m.id
ORDER BY m.importance DESC, m.last_accessed DESC;

-- 视图：近期活跃记忆视图
CREATE VIEW IF NOT EXISTS recent_active_memories AS
SELECT 
    m.id,
    m.content,
    m.importance,
    m.memory_type,
    m.last_accessed,
    m.access_count,
    julianday('now') - julianday(m.last_accessed) AS days_since_access
FROM memories m
WHERE m.last_accessed IS NOT NULL
ORDER BY m.last_accessed DESC
LIMIT 100;

-- 视图：用户偏好摘要视图
CREATE VIEW IF NOT EXISTS user_preferences_summary AS
SELECT 
    u.id AS user_id,
    u.display_name,
    p.category,
    COUNT(*) AS preference_count,
    GROUP_CONCAT(p.preference_key || '=' || p.preference_value, '; ') AS preferences
FROM users u
JOIN preferences p ON u.id = p.user_id
GROUP BY u.id, p.category
ORDER BY u.id, p.category;

-- 触发器：自动更新记忆的更新时间
CREATE TRIGGER IF NOT EXISTS update_memory_timestamp 
AFTER UPDATE ON memories
FOR EACH ROW
BEGIN
    UPDATE memories 
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

-- 触发器：更新记忆的最后访问时间
CREATE TRIGGER IF NOT EXISTS update_memory_access
AFTER UPDATE OF access_count ON memories
FOR EACH ROW
BEGIN
    UPDATE memories 
    SET last_accessed = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

-- 触发器：清理过期记忆（如果设置了过期时间）
CREATE TRIGGER IF NOT EXISTS cleanup_expired_memories
AFTER INSERT ON memories
BEGIN
    DELETE FROM memories 
    WHERE expires_at IS NOT NULL 
      AND expires_at < CURRENT_TIMESTAMP;
END;

-- 注释
COMMENT ON TABLE memories IS '存储所有记忆的核心表';
COMMENT ON TABLE tags IS '标签定义表，用于分类记忆';
COMMENT ON TABLE memory_tags IS '记忆和标签的多对多关联表';
COMMENT ON TABLE users IS '用户表（如果系统支持多用户）';
COMMENT ON TABLE user_memories IS '用户和记忆的关联表';
COMMENT ON TABLE sessions IS '对话会话记录表';
COMMENT ON TABLE session_memories IS '会话和记忆的关联表';
COMMENT ON TABLE events IS '重要事件记录表';
COMMENT ON TABLE event_memories IS '事件和记忆的关联表';
COMMENT ON TABLE preferences IS '结构化用户偏好表';
COMMENT ON TABLE memory_relationships IS '记忆之间的关系表';
COMMENT ON TABLE system_logs IS '系统运行日志表';
COMMENT ON TABLE audit_logs IS '审计日志表，记录重要操作';
COMMENT ON TABLE backups IS '备份记录表';

-- 初始化数据（可选）
-- INSERT INTO tags (name, category) VALUES 
--   ('饮食', 'lifestyle'),
--   ('健康', 'lifestyle'),
--   ('工作', 'professional'),
--   ('学习', 'education'),
--   ('娱乐', 'lifestyle');
