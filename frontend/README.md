# 小紫薯 - 前端

基于地理位置的本地生活娱乐AI Agent前端应用。

## 技术栈

- **框架**: Vue 3
- **状态管理**: Pinia
- **路由**: Vue Router
- **UI组件**: Element Plus + Vant
- **构建工具**: Vite
- **HTTP客户端**: Axios

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

编辑 `.env` 文件，配置以下环境变量：

```env
VITE_APP_TITLE=小紫薯
VITE_APP_API_BASE_URL=/api/v1
VITE_APP_AMAP_KEY=your-amap-key
```

### 3. 启动开发服务器

```bash
npm run dev
```

开发服务器将在 http://localhost:5174 启动。

### 4. 构建生产版本

```bash
npm run build
```

构建产物将输出到 `dist/` 目录。

## 常用命令

```bash
# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# 代码检查与修复
npm run lint

# 运行单元测试
npm run test:unit

# 运行端到端测试
npm run test:e2e
```

## 页面路由

| 路由 | 说明 |
|------|------|
| `/` | 首页 |
| `/login` | 登录页 |
| `/register` | 注册页 |
| `/food` | 美食列表 |
| `/food/:id` | 美食详情 |
| `/attraction` | 景点列表 |
| `/attraction/:id` | 景点详情 |
| `/chat` | 智能助手 |
| `/favorites` | 我的收藏 |
| `/recommend` | 今日推荐 |

## 部署

### Docker部署

```bash
# 构建镜像
docker build -t tianyan-life-frontend .

# 运行容器
docker run -d -p 80:80 --name tianyan-life-frontend tianyan-life-frontend
```
