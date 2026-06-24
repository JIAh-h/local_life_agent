-- 创建数据库
CREATE DATABASE IF NOT EXISTS tianyan_life CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE tianyan_life;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(32) UNIQUE COMMENT '用户名',
    hashed_password VARCHAR(128) COMMENT '密码哈希',
    phone VARCHAR(20) UNIQUE COMMENT '手机号',
    email VARCHAR(128) UNIQUE COMMENT '邮箱',
    openid VARCHAR(64) UNIQUE COMMENT '微信openid',
    qq_openid VARCHAR(64) UNIQUE COMMENT 'QQ openid',
    nickname VARCHAR(32) COMMENT '用户昵称',
    avatar_url VARCHAR(512) COMMENT '头像URL',
    is_active BOOLEAN DEFAULT TRUE COMMENT '账户是否激活',
    login_attempts INT DEFAULT 0 COMMENT '登录失败尝试次数',
    locked_until DATETIME COMMENT '账户锁定截止时间',
    last_login DATETIME COMMENT '最后登录时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_phone (phone),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 用户位置表
CREATE TABLE IF NOT EXISTS user_locations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    name VARCHAR(32) NOT NULL COMMENT '位置名称（家、公司等）',
    address VARCHAR(256) NOT NULL COMMENT '详细地址',
    latitude DECIMAL(10, 7) NOT NULL COMMENT '纬度',
    longitude DECIMAL(10, 7) NOT NULL COMMENT '经度',
    city VARCHAR(64) COMMENT '城市',
    district VARCHAR(64) COMMENT '区县',
    is_default BOOLEAN DEFAULT FALSE COMMENT '是否默认位置',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_is_default (user_id, is_default)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户常用位置表';

-- 定位日志表
CREATE TABLE IF NOT EXISTS location_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    latitude DECIMAL(10, 7) NOT NULL COMMENT '纬度',
    longitude DECIMAL(10, 7) NOT NULL COMMENT '经度',
    accuracy FLOAT COMMENT '定位精度（米）',
    source VARCHAR(32) NOT NULL COMMENT '定位来源（browser/ip/manual）',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    user_agent VARCHAR(512) COMMENT '用户代理',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定位日志表';

-- 商家表
CREATE TABLE IF NOT EXISTS merchants (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL COMMENT '商家名称',
    address VARCHAR(256) NOT NULL COMMENT '详细地址',
    latitude DECIMAL(10, 7) NOT NULL COMMENT '纬度',
    longitude DECIMAL(10, 7) NOT NULL COMMENT '经度',
    city VARCHAR(64) COMMENT '城市',
    district VARCHAR(64) COMMENT '区县',
    category VARCHAR(64) NOT NULL COMMENT '商家类别（火锅、烧烤、日料等）',
    subcategory VARCHAR(64) COMMENT '子类别',
    rating DECIMAL(3, 1) DEFAULT 0 COMMENT '评分（0-5）',
    rating_count INT DEFAULT 0 COMMENT '评分人数',
    avg_price DECIMAL(10, 2) DEFAULT 0 COMMENT '人均消费（元）',
    phone VARCHAR(20) COMMENT '联系电话',
    business_hours VARCHAR(128) COMMENT '营业时间',
    tags JSON COMMENT '标签（如人气最高、新开店铺）',
    recommended_dishes JSON COMMENT '推荐菜品',
    images JSON COMMENT '商家图片',
    description TEXT COMMENT '商家描述',
    source VARCHAR(32) DEFAULT 'gaode' COMMENT '数据来源',
    source_id VARCHAR(64) COMMENT '来源ID',
    status TINYINT DEFAULT 1 COMMENT '状态（0禁用 1正常）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_city_district (city, district),
    INDEX idx_rating (rating),
    INDEX idx_avg_price (avg_price),
    INDEX idx_location (latitude, longitude),
    INDEX idx_source (source, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商家表';

-- 商家评分表
CREATE TABLE IF NOT EXISTS merchant_ratings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    merchant_id BIGINT NOT NULL COMMENT '商家ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    rating DECIMAL(3, 1) NOT NULL COMMENT '评分（0-5）',
    comment TEXT COMMENT '评价内容',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_merchant_user (merchant_id, user_id),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商家评分表';

-- 景点表
CREATE TABLE IF NOT EXISTS attractions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL COMMENT '景点名称',
    address VARCHAR(256) NOT NULL COMMENT '详细地址',
    latitude DECIMAL(10, 7) NOT NULL COMMENT '纬度',
    longitude DECIMAL(10, 7) NOT NULL COMMENT '经度',
    city VARCHAR(64) COMMENT '城市',
    district VARCHAR(64) COMMENT '区县',
    category VARCHAR(64) NOT NULL COMMENT '景点类别（公园、博物馆、商场等）',
    subcategory VARCHAR(64) COMMENT '子类别',
    rating DECIMAL(3, 1) DEFAULT 0 COMMENT '评分（0-5）',
    rating_count INT DEFAULT 0 COMMENT '评分人数',
    ticket_price DECIMAL(10, 2) DEFAULT 0 COMMENT '门票价格（0表示免费）',
    opening_hours VARCHAR(128) COMMENT '开放时间',
    phone VARCHAR(20) COMMENT '联系电话',
    tags JSON COMMENT '标签（如免费景点、亲子友好）',
    highlights JSON COMMENT '亮点介绍',
    images JSON COMMENT '景点图片',
    description TEXT COMMENT '景点描述',
    source VARCHAR(32) DEFAULT 'gaode' COMMENT '数据来源',
    source_id VARCHAR(64) COMMENT '来源ID',
    status TINYINT DEFAULT 1 COMMENT '状态（0禁用 1正常）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_city_district (city, district),
    INDEX idx_rating (rating),
    INDEX idx_ticket_price (ticket_price),
    INDEX idx_location (latitude, longitude),
    INDEX idx_source (source, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='景点表';

-- 景点评分表
CREATE TABLE IF NOT EXISTS attraction_ratings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    attraction_id BIGINT NOT NULL COMMENT '景点ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    rating DECIMAL(3, 1) NOT NULL COMMENT '评分（0-5）',
    comment TEXT COMMENT '评价内容',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attraction_id) REFERENCES attractions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_attraction_user (attraction_id, user_id),
    INDEX idx_attraction_id (attraction_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='景点评分表';

-- 小红书笔记表
CREATE TABLE IF NOT EXISTS xiaohongshu_notes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    merchant_id BIGINT COMMENT '关联商家ID',
    attraction_id BIGINT COMMENT '关联景点ID',
    title VARCHAR(256) NOT NULL COMMENT '笔记标题',
    author VARCHAR(64) NOT NULL COMMENT '作者昵称',
    author_avatar VARCHAR(512) COMMENT '作者头像',
    publish_time DATETIME NOT NULL COMMENT '发布时间',
    like_count INT DEFAULT 0 COMMENT '点赞数',
    comment_count INT DEFAULT 0 COMMENT '评论数',
    collect_count INT DEFAULT 0 COMMENT '收藏数',
    content TEXT COMMENT '笔记内容',
    summary TEXT COMMENT '内容摘要',
    pros JSON COMMENT '优点列表',
    cons JSON COMMENT '缺点列表',
    tips JSON COMMENT '避坑提示',
    original_url VARCHAR(512) NOT NULL COMMENT '原文链接',
    images JSON COMMENT '笔记图片',
    source VARCHAR(32) DEFAULT 'xiaohongshu' COMMENT '数据来源',
    source_id VARCHAR(64) COMMENT '来源ID',
    status TINYINT DEFAULT 1 COMMENT '状态（0禁用 1正常）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
    FOREIGN KEY (attraction_id) REFERENCES attractions(id) ON DELETE CASCADE,
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_attraction_id (attraction_id),
    INDEX idx_publish_time (publish_time),
    INDEX idx_like_count (like_count),
    INDEX idx_comment_count (comment_count),
    INDEX idx_collect_count (collect_count),
    INDEX idx_source (source, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='小红书笔记表';

-- 笔记缓存表
CREATE TABLE IF NOT EXISTS note_cache (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    cache_key VARCHAR(256) NOT NULL COMMENT '缓存键',
    cache_value TEXT NOT NULL COMMENT '缓存值',
    expire_time DATETIME NOT NULL COMMENT '过期时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_cache_key (cache_key),
    INDEX idx_expire_time (expire_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='笔记缓存表';

-- 对话历史表
CREATE TABLE IF NOT EXISTS chat_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    session_id VARCHAR(64) NOT NULL COMMENT '会话ID',
    message_type ENUM('user', 'ai') NOT NULL COMMENT '消息类型',
    content TEXT NOT NULL COMMENT '消息内容',
    message_metadata JSON COMMENT '消息元数据（如推荐结果）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_session_id (session_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话历史表';

-- 对话上下文表
CREATE TABLE IF NOT EXISTS chat_context (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    session_id VARCHAR(64) NOT NULL COMMENT '会话ID',
    context_key VARCHAR(64) NOT NULL COMMENT '上下文键',
    context_value TEXT NOT NULL COMMENT '上下文值',
    expire_time DATETIME COMMENT '过期时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_session_key (user_id, session_id, context_key),
    INDEX idx_session_id (session_id),
    INDEX idx_expire_time (expire_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话上下文表';

-- 意图识别日志表
CREATE TABLE IF NOT EXISTS intent_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    session_id VARCHAR(64) NOT NULL COMMENT '会话ID',
    query TEXT NOT NULL COMMENT '用户查询',
    intent VARCHAR(64) NOT NULL COMMENT '识别意图',
    entities JSON COMMENT '提取实体',
    confidence DECIMAL(5, 4) COMMENT '置信度',
    response_time BIGINT COMMENT '响应时间（毫秒）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_session_id (session_id),
    INDEX idx_intent (intent),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='意图识别日志表';

-- 用户收藏表
CREATE TABLE IF NOT EXISTS user_favorites (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    merchant_id BIGINT COMMENT '商家ID',
    attraction_id BIGINT COMMENT '景点ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
    FOREIGN KEY (attraction_id) REFERENCES attractions(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_attraction_id (attraction_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户收藏表';

-- 分享日志表
CREATE TABLE IF NOT EXISTS share_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '分享用户ID',
    share_type ENUM('merchant', 'attraction') NOT NULL COMMENT '分享类型',
    share_id BIGINT NOT NULL COMMENT '分享对象ID',
    share_channel VARCHAR(32) NOT NULL COMMENT '分享渠道（wechat/moments/link）',
    share_url VARCHAR(512) NOT NULL COMMENT '分享链接',
    view_count INT DEFAULT 0 COMMENT '访问次数',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_share_type_id (share_type, share_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分享日志表';

-- 今日推荐表
CREATE TABLE IF NOT EXISTS daily_recommendations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    recommend_type ENUM('merchant', 'attraction') NOT NULL COMMENT '推荐类型',
    recommend_id BIGINT NOT NULL COMMENT '推荐对象ID',
    recommend_reason VARCHAR(256) NOT NULL COMMENT '推荐理由',
    weather_info JSON COMMENT '天气信息',
    score DECIMAL(5, 2) DEFAULT 0 COMMENT '推荐分数',
    is_clicked BOOLEAN DEFAULT FALSE COMMENT '是否被点击',
    feedback TINYINT COMMENT '用户反馈（1喜欢 0无反馈 -1不喜欢）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_recommend_type_id (recommend_type, recommend_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='今日推荐表';

-- 搜索历史表
CREATE TABLE IF NOT EXISTS search_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    keyword VARCHAR(128) NOT NULL COMMENT '搜索关键词',
    search_type VARCHAR(32) NOT NULL COMMENT '搜索类型（food/attraction）',
    result_count INT DEFAULT 0 COMMENT '结果数量',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='搜索历史表';

-- 插入测试数据
-- 注意：测试用户的密码哈希为 'password123' 的bcrypt哈希值
INSERT INTO users (username, hashed_password, phone, email, openid, qq_openid, nickname, avatar_url, is_active) VALUES
('testuser1', '$2b$12$LJ3m4ys3Lz0QX9x5J5Z5ZeK5Z5ZeK5Z5ZeK5Z5ZeK5Z5ZeK5Z5Ze', '13800138001', 'test1@example.com', 'test_openid_1', NULL, '测试用户1', 'https://example.com/avatar1.jpg', TRUE),
('testuser2', '$2b$12$LJ3m4ys3Lz0QX9x5J5Z5ZeK5Z5ZeK5Z5ZeK5Z5ZeK5Z5ZeK5Z5Ze', '13800138002', 'test2@example.com', 'test_openid_2', NULL, '测试用户2', 'https://example.com/avatar2.jpg', TRUE),
('testuser3', '$2b$12$LJ3m4ys3Lz0QX9x5J5Z5ZeK5Z5ZeK5Z5ZeK5Z5ZeK5Z5ZeK5Z5Ze', '13800138003', 'test3@example.com', 'test_openid_3', NULL, '测试用户3', 'https://example.com/avatar3.jpg', TRUE);

-- 插入测试商家数据
INSERT INTO merchants (name, address, latitude, longitude, city, district, category, rating, avg_price, phone, business_hours, tags, recommended_dishes) VALUES
('海底捞火锅', '北京市朝阳区三里屯路19号', 39.9342, 116.4544, '北京', '朝阳区', '火锅', 4.8, 120.00, '010-12345678', '10:00-22:00', '["人气最高", "服务好"]', '["毛肚", "虾滑", "牛肉"]'),
('星巴克咖啡', '北京市海淀区中关村大街1号', 39.9842, 116.3074, '北京', '海淀区', '咖啡', 4.5, 45.00, '010-87654321', '08:00-22:00', '["环境好", "适合办公"]', '["拿铁", "美式", "卡布奇诺"]'),
('烤肉季', '北京市东城区前门大街12号', 39.8992, 116.3974, '北京', '东城区', '烧烤', 4.6, 150.00, '010-11111111', '11:00-23:00', '["老字号", "正宗烤肉"]', '["烤羊肉", "烤牛肉", "烤鸡翅"]');

-- 插入测试景点数据
INSERT INTO attractions (name, address, latitude, longitude, city, district, category, rating, ticket_price, opening_hours, phone, tags, highlights) VALUES
('天安门广场', '北京市东城区天安门广场', 39.9042, 116.4074, '北京', '东城区', '公园', 4.9, 0.00, '06:00-22:00', '010-63095630', '["免费景点", "必去打卡"]', '["世界最大广场", "历史意义重大"]'),
('故宫博物院', '北京市东城区景山前街4号', 39.9163, 116.3972, '北京', '东城区', '博物馆', 4.8, 60.00, '08:30-17:00', '010-65131892', '["世界文化遗产", "必去景点"]', '["明清皇宫", "珍贵文物"]'),
('颐和园', '北京市海淀区新建宫门路19号', 39.9999, 116.2755, '北京', '海淀区', '公园', 4.7, 30.00, '06:30-18:00', '010-62881144', '["皇家园林", "世界遗产"]', '["昆明湖", "万寿山", "长廊"]');
