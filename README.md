# 小紫薯 AI Agent

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.x-brightgreen.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 项目简介

**小紫薯**是一个基于地理位置的智能本地生活娱乐AI Agent，致力于成为用户的"随身生活雷达"。用户只需告知当前位置和需求，系统就能自动检索并整合全网信息，提供精准、实时、有参考价值的周边吃喝玩乐推荐，并直接展示来自小红书的真实用户评价和热门内容。

### 核心功能

| 功能模块 | 功能说明 |
|---------|---------|
| 用户认证系统 | JWT双令牌机制，支持登录、注册、Token刷新 |
| 定位服务 | 获取用户实时位置，支持经纬度和地址文本输入 |
| 美食推荐系统 | 按条件筛选推荐周边美食商家 |
| 景点/玩乐推荐 | 按条件筛选推荐周边景点和玩乐场所 |
| 小红书内容检索 | 自动检索商家/景点相关小红书笔记，提取关键评价 |
| 自然语言交互 | 支持模糊查询和多轮对话 |

### 技术栈

**前端**：Vue 3 + Pinia + Vue Router + Element Plus + Vant + Vite + Axios

**后端**：FastAPI + SQLAlchemy + MySQL 8.0 + Redis + Celery + Alembic

**AI框架**：HermesAgent + GraphRAG

---

## 环境要求

| 环境 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.9 | 3.11 |
| Node.js | 16.x | 18.x LTS |
| MySQL | 8.0 | 8.0+ |
| Redis | 6.0 | 7.0 |

---

## 快速启动

### 方式一：Docker Compose（推荐）

适用于快速体验或生产部署，一键启动所有服务。

#### 步骤 1：克隆项目

```bash
git clone <repository-url>
cd local_life_agent
```

#### 步骤 2：配置环境变量

```bash
# 复制后端环境变量
cp backend/.env.example backend/.env

# 编辑环境变量，填入数据库密码、API Key等
# Windows: notepad backend/.env
# Linux/Mac: vim backend/.env
```

#### 步骤 3：启动所有服务

```bash
docker-compose up -d
```

#### 步骤 4：初始化数据库

```bash
# 等待MySQL启动完成（约30秒）
docker-compose exec mysql mysql -uroot -p -e "source /docker-entrypoint-initdb.d/init.sql"

# 或手动导入
docker-compose exec -T mysql mysql -uroot -p tianyan_life < backend/init.sql
```

#### 步骤 5：访问应用

**生产模式**（默认）：

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端页面 | http://localhost:80 | Vue前端应用（Nginx） |
| 后端API | http://localhost:8000 | FastAPI服务 |
| API文档 | http://localhost:8000/docs | Swagger交互文档 |

**开发模式**（带热重载）：

```bash
# 使用开发模式配置启动
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端页面 | http://localhost:5174 | Vue前端应用（Vite） |
| 后端API | http://localhost:8000 | FastAPI服务 |
| API文档 | http://localhost:8000/docs | Swagger交互文档 |

---

### 方式二：本地开发

适用于开发调试，分别启动前后端服务。

#### 后端启动

```bash
# 1. 进入后端目录
cd backend

# 2. 创建Python虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库连接等信息

# 5. 初始化数据库
# 创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS tianyan_life CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 导入初始化脚本
mysql -u root -p tianyan_life < init.sql

# 6. 启动后端服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端启动

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 配置环境变量（可选）
# 编辑 .env 文件，配置API地址等

# 4. 启动开发服务器
npm run dev
```

#### 访问应用

- 前端开发服务器：http://localhost:5173
- 后端API服务：http://localhost:8000
- API文档：http://localhost:8000/docs

---

### 环境检查清单

启动前请确认以下服务已启动：

- [ ] MySQL服务已启动，端口3306可访问
- [ ] Redis服务已启动，端口6379可访问
- [ ] 已创建数据库并导入初始化脚本
- [ ] 已配置 `.env` 文件中的数据库连接信息
- [ ] 已申请并配置第三方API Key（高德地图等）

---

## 运行与部署

### 开发环境常用命令

#### 后端命令

```bash
# 启动开发服务器（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 运行测试
pytest

# 数据库迁移
alembic revision --autogenerate -m "迁移描述"  # 创建迁移
alembic upgrade head                            # 应用迁移
```

#### 前端命令

```bash
# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码检查与修复
npm run lint
```

### 生产环境部署

#### Docker Compose部署

**生产模式**（推荐）：

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 配置生产环境变量
cp backend/.env.example backend/.env
# 编辑生产环境配置，注意：
# - DEBUG=False
# - 使用强随机SECRET_KEY
# - 配置生产数据库连接

# 3. 构建并启动服务
docker-compose up -d --build

# 4. 查看服务状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f backend
```

**开发模式**（带热重载）：

```bash
# 1. 配置开发环境变量
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 2. 启动开发服务
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

# 3. 查看日志
docker-compose logs -f
```

---

## 项目结构

```
local_life_agent/
├── backend/                    # 后端项目
│   ├── app/
│   │   ├── api/               # API路由
│   │   │   └── v1/           # API v1版本
│   │   ├── models/           # 数据库模型
│   │   ├── schemas/          # Pydantic模型
│   │   ├── services/         # 业务逻辑
│   │   ├── utils/            # 工具函数
│   │   ├── config.py         # 配置文件
│   │   ├── database.py       # 数据库连接
│   │   ├── main.py           # 应用入口
│   │   └── redis_client.py   # Redis客户端
│   ├── agent/                # AI Agent核心模块
│   │   └── v2/             # Agent v2（ReAct引擎）
│   ├── alembic/              # 数据库迁移
│   │   └── versions/       # 迁移版本文件
│   ├── init.sql              # 数据库初始化脚本
│   ├── requirements.txt      # Python依赖
│   └── tests/                # 测试目录
├── frontend/                   # 前端项目
│   ├── src/
│   │   ├── api/              # API接口封装
│   │   ├── components/       # 公共组件
│   │   ├── router/           # 路由配置
│   │   ├── stores/           # Pinia状态管理
│   │   ├── views/            # 页面视图
│   │   ├── App.vue           # 根组件
│   │   └── main.js           # 应用入口
│   ├── package.json          # Node依赖
│   └── vite.config.js        # Vite配置
├── docker-compose.yml          # Docker生产模式编排
├── docker-compose.override.yml # Docker开发模式覆盖配置
├── .dockerignore               # Docker构建忽略文件
└── README.md                   # 项目说明
```

---

## API接口文档

启动后端服务后，访问以下地址查看完整API文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要接口模块

| 模块 | 前缀 | 说明 |
|------|------|------|
| 用户认证 | `/api/v1/auth` | 登录、注册、Token管理 |
| 定位服务 | `/api/v1/location` | 位置管理、常用地址 |
| 美食推荐 | `/api/v1/food` | 美食列表、详情 |
| 景点推荐 | `/api/v1/attraction` | 景点列表、详情 |
| 小红书笔记 | `/api/v1/xiaohongshu` | 笔记检索、详情 |
| 自然语言交互 | `/api/v1/chat` | 智能对话 |
| 收藏管理 | `/api/v1/favorites` | 收藏CRUD |

---

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

### 提交规范

```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 代码重构
test: 测试相关
chore: 构建/工具相关
```

---

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

## 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 高性能Python Web框架
- [Vue.js](https://vuejs.org/) - 渐进式JavaScript框架
- [Element Plus](https://element-plus.org/) - Vue 3 UI组件库
- [Vant](https://vant-ui.github.io/vant/) - 移动端Vue组件库
- [高德地图API](https://lbs.amap.com/) - 地图服务
- [小红书开放平台](https://open.xiaohongshu.com/) - 内容数据
