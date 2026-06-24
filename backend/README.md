# 小紫薯 - 后端

基于地理位置的本地生活娱乐AI Agent后端服务。

## 技术栈

- **框架**: FastAPI
- **数据库**: MySQL 8.0
- **缓存**: Redis
- **ORM**: SQLAlchemy
- **任务队列**: Celery

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件，配置以下环境变量：

```env
DATABASE_URL=mysql://user:password@localhost:3306/tianyan_life
REDIS_URL=redis://localhost:6379/3
SECRET_KEY=your-secret-key
AMAP_API_KEY=your-amap-key
```

### 3. 初始化数据库

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE tianyan_life CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 运行数据库迁移
alembic upgrade head
```

### 4. 启动服务

```bash
# 激活虚拟环境
.venv\Scripts\Activate.ps1

# 开发环境
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产环境
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 常用命令

### 数据库迁移

```bash
# 创建迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 测试

```bash
# 运行测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=app --cov-report=html
```

### 部署

```bash
# Docker部署
docker build -t tianyan-life-backend .
docker run -d -p 8000:8000 --name tianyan-life-backend tianyan-life-backend

# Docker Compose部署
docker-compose up -d
```

## API接口模块

| 模块 | 前缀 | 说明 |
|------|------|------|
| 用户认证 | `/api/v1/auth` | 登录、注册、Token管理 |
| 定位服务 | `/api/v1/location` | 位置管理、常用地址 |
| 美食推荐 | `/api/v1/food` | 美食列表、详情 |
| 景点推荐 | `/api/v1/attraction` | 景点列表、详情 |
| 小红书笔记 | `/api/v1/xiaohongshu` | 笔记检索、详情 |
| 自然语言交互 | `/api/v1/chat` | 智能对话 |
| 收藏管理 | `/api/v1/favorites` | 收藏CRUD |
