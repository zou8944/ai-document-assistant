# Docker 部署整改方案

## 📋 整改概述

将当前 **Electron 桌面应用架构** 改造为 **Docker 容器化 Web 应用架构**,实现以下目标:
- 前端从 Electron 改为纯 Web 应用(React SPA)
- 后端 Python 服务容器化
- 使用 Docker Compose 编排多服务
- 支持生产环境部署

## 🎯 架构变化对比

### 当前架构 (Electron)
```
┌─────────────────────────────────────┐
│      Electron 桌面应用              │
│  ┌─────────────┐  ┌──────────────┐ │
│  │  React 前端  │  │ Python 后端   │ │
│  │  (渲染进程)  │  │  (子进程)    │ │
│  └─────────────┘  └──────────────┘ │
└─────────────────────────────────────┘
         ↓ 本地文件系统访问
    ┌──────────┐
    │  Chroma  │ (Docker)
    └──────────┘
```

### 目标架构 (Docker Web)
```
┌──────────────────────────────────────────────┐
│              Docker Compose                  │
│                                              │
│  ┌────────────┐  ┌─────────────┐  ┌──────┐ │
│  │  Nginx     │  │  Backend    │  │Chroma│ │
│  │  (前端静态) │  │  (FastAPI)  │  │(向量)│ │
│  │  :80       │  │  :8888      │  │:8000 │ │
│  └────────────┘  └─────────────┘  └──────┘ │
└──────────────────────────────────────────────┘
         ↑
    浏览器访问
```

## 🔧 详细改造步骤

### 1. 前端改造 (Electron → React SPA)

#### 1.1 需要移除的内容
- **删除 Electron 相关依赖**
  ```json
  // package.json 中删除
  "electron"
  "electron-builder"
  "electron-is-dev"
  "vite-plugin-electron"
  "concurrently"
  "wait-on"
  ```

- **删除 Electron 主进程文件**
  - `src/main.ts` (Electron 主进程)
  - `src/preload.ts` (预加载脚本)

- **删除打包配置**
  ```json
  // package.json 中删除 build 字段
  "build": { ... }
  ```

#### 1.2 需要修改的内容
- **更新 package.json scripts**
  ```json
  {
    "scripts": {
      "dev": "vite",
      "build": "vite build",
      "preview": "vite preview",
      "lint": "eslint src --ext ts,tsx",
      "test": "vitest"
    }
  }
  ```

- **修改 API 通信方式**
  - 当前: 通过 Electron IPC 与子进程通信
  - 改为: 通过 HTTP 请求与后端 API 通信

  ```typescript
  // 修改 src/services/api.ts
  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8888';

  export const apiClient = {
    uploadFile: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${API_BASE_URL}/api/files/upload`, {
        method: 'POST',
        body: formData,
      });
      return response.json();
    },
    // ... 其他 API 方法
  };
  ```

- **移除本地文件系统访问**
  - 删除 Electron 的 `fs` 模块调用
  - 所有文件操作改为通过 API 上传

- **添加环境变量配置**
  ```bash
  # .env.development
  VITE_API_URL=http://localhost:8888

  # .env.production
  VITE_API_URL=/api
  ```

#### 1.3 需要添加的内容
- **跨域处理**
  ```typescript
  // vite.config.ts
  export default defineConfig({
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8888',
          changeOrigin: true,
        }
      }
    }
  });
  ```

- **路由配置** (如果需要多页面)
  ```bash
  npm install react-router-dom
  ```

### 2. 后端改造 (独立 FastAPI 服务)

#### 2.1 调整 CORS 配置
```python
# api/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应设置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 2.2 文件上传处理
```python
# api/routes/files.py
from fastapi import UploadFile, File
import aiofiles

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 保存到临时目录
    file_path = f"/tmp/uploads/{file.filename}"
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)

    # 处理文件
    result = await process_file(file_path)
    return result
```

#### 2.3 配置文件调整
```python
# config.py
import os

class Config:
    # Docker 环境使用环境变量
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma")
    CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
    CRAWL_API_KEY = os.getenv("CRAWL_API_KEY")
    CRAWL_BASE_URL = os.getenv("CRAWL_BASE_URL")
    AGENT_API_KEY = os.getenv("AGENT_API_KEY")
    AGENT_BASE_URL = os.getenv("AGENT_BASE_URL")
    EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
    EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL")
```

### 3. Docker 配置

#### 3.1 创建 Dockerfile (后端)
```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装 Python 依赖
RUN uv sync --frozen --no-dev

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/logs

# 暴露端口
EXPOSE 8888

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8888/health')"

# 启动命令
CMD ["uv", "run", "python", "api_server.py", "--host", "0.0.0.0", "--port", "8888"]
```

#### 3.2 创建 Dockerfile (前端)
```dockerfile
# frontend/Dockerfile
# 构建阶段
FROM node:18-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖
RUN npm ci

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# 生产阶段
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

#### 3.3 创建 Nginx 配置
```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # 前端路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api/ {
        proxy_pass http://backend:8888/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

#### 3.4 创建 docker-compose.yml
```yaml
# docker-compose.yml (根目录)
version: '3.8'

services:
  # 前端服务
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: ai-doc-assistant-frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - app-network
    restart: unless-stopped

  # 后端服务
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: ai-doc-assistant-backend
    ports:
      - "8888:8888"
    environment:
      - CHROMA_HOST=chroma
      - CHROMA_PORT=8000
      - CRAWL_API_KEY=${CRAWL_API_KEY}
      - CRAWL_BASE_URL=${CRAWL_BASE_URL}
      - AGENT_API_KEY=${AGENT_API_KEY}
      - AGENT_BASE_URL=${AGENT_BASE_URL}
      - EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
      - EMBEDDING_BASE_URL=${EMBEDDING_BASE_URL}
      - DATABASE_URL=sqlite:////app/data/app.db
    volumes:
      - backend-data:/app/data
      - backend-logs:/app/logs
    depends_on:
      chroma:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8888/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Chroma 向量数据库
  chroma:
    image: chromadb/chroma:latest
    container_name: ai-doc-assistant-chroma
    ports:
      - "8000:8000"
    volumes:
      - chroma-data:/chroma/chroma
    environment:
      - ANONYMIZED_TELEMETRY=${ANONYMIZED_TELEMETRY:-TRUE}
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

networks:
  app-network:
    driver: bridge

volumes:
  backend-data:
  backend-logs:
  chroma-data:
```

#### 3.5 创建 .dockerignore
```
# backend/.dockerignore
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.coverage
htmlcov
dist
build
*.egg-info
.venv
.env
*.log
.DS_Store
.idea
.vscode
tests/
docs/

# frontend/.dockerignore
node_modules
dist
.vite
.env.local
.env.*.local
*.log
.DS_Store
.idea
.vscode
coverage
```

### 4. 环境变量配置

#### 4.1 创建 .env 文件
```bash
# .env (根目录)
# Crawl LLM 配置
CRAWL_API_KEY=sk-xxxxxx
CRAWL_BASE_URL=https://api.siliconflow.cn/v1

# Agent LLM 配置
AGENT_API_KEY=sk-xxxxxx
AGENT_BASE_URL=

# Embedding 配置
EMBEDDING_API_KEY=sk-xxxxxx
EMBEDDING_BASE_URL=https://api.openai.com/v1

# Chroma 配置
ANONYMIZED_TELEMETRY=FALSE

# 应用配置
LOG_LEVEL=info
```

#### 4.2 创建 .env.example
```bash
# .env.example
CRAWL_API_KEY=your_api_key_here
CRAWL_BASE_URL=https://api.siliconflow.cn/v1
AGENT_API_KEY=your_anthropic_api_key_here
AGENT_BASE_URL=
EMBEDDING_API_KEY=your_api_key_here
EMBEDDING_BASE_URL=https://api.openai.com/v1
ANONYMIZED_TELEMETRY=FALSE
LOG_LEVEL=info
```

### 5. 健康检查端点

```python
# backend/api/routes/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-document-assistant-backend"
    }
```

### 6. 部署命令

#### 6.1 开发环境
```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 重启某个服务
docker-compose restart backend

# 停止所有服务
docker-compose down

# 停止并清除数据卷
docker-compose down -v
```

#### 6.2 生产环境
```bash
# 使用生产配置
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 构建并启动
docker-compose up -d --build

# 查看资源使用
docker stats

# 备份数据卷
docker run --rm -v ai-doc-assistant_backend-data:/data -v $(pwd):/backup alpine tar czf /backup/backup.tar.gz /data
```

### 7. 生产环境优化

#### 7.1 创建 docker-compose.prod.yml
```yaml
version: '3.8'

services:
  frontend:
    build:
      args:
        NODE_ENV: production
    environment:
      - NGINX_WORKER_PROCESSES=auto
      - NGINX_WORKER_CONNECTIONS=1024

  backend:
    environment:
      - LOG_LEVEL=warning
      - WORKERS=4
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  chroma:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

#### 7.2 添加反向代理 (可选)
```yaml
# 使用 Traefik 或 Caddy 作为入口
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik/acme.json:/acme.json
    networks:
      - app-network

  frontend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`yourdomain.com`)"
      - "traefik.http.routers.frontend.entrypoints=websecure"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
```

## 📦 文件变更清单

### 需要新建的文件
```
├── docker-compose.yml              # Docker Compose 配置
├── docker-compose.prod.yml         # 生产环境配置
├── .env.example                    # 环境变量示例
├── backend/
│   ├── Dockerfile                  # 后端 Dockerfile
│   ├── .dockerignore              # Docker 忽略文件
│   └── api/routes/health.py       # 健康检查端点
└── frontend/
    ├── Dockerfile                  # 前端 Dockerfile
    ├── .dockerignore              # Docker 忽略文件
    └── nginx.conf                  # Nginx 配置
```

### 需要修改的文件
```
├── frontend/
│   ├── package.json               # 移除 Electron 依赖和脚本
│   ├── vite.config.ts            # 添加代理配置
│   ├── src/
│   │   ├── services/api.ts       # HTTP 客户端替换 IPC
│   │   └── App.tsx               # 移除 Electron API 调用
└── backend/
    ├── config.py                  # 支持环境变量配置
    ├── api/main.py               # 添加 CORS 中间件
    └── api_server.py             # 调整启动参数
```

### 需要删除的文件
```
frontend/
├── src/main.ts                    # Electron 主进程
├── src/preload.ts                # Electron 预加载脚本
└── (所有 Electron 特定代码)
```

## 🔄 迁移步骤

### Phase 1: 准备阶段 (1-2天)
1. ✅ 创建 Docker 相关配置文件
2. ✅ 添加健康检查端点
3. ✅ 准备环境变量模板

### Phase 2: 后端改造 (2-3天)
1. ✅ 调整配置文件支持环境变量
2. ✅ 添加 CORS 中间件
3. ✅ 完善文件上传接口
4. ✅ 构建后端 Docker 镜像
5. ✅ 测试后端独立运行

### Phase 3: 前端改造 (3-4天)
1. ✅ 移除 Electron 依赖
2. ✅ 实现 HTTP API 客户端
3. ✅ 移除本地文件系统访问
4. ✅ 添加环境变量配置
5. ✅ 构建前端 Docker 镜像
6. ✅ 配置 Nginx 反向代理

### Phase 4: 集成测试 (2-3天)
1. ✅ Docker Compose 本地测试
2. ✅ 验证所有功能
3. ✅ 性能测试和优化
4. ✅ 文档更新

### Phase 5: 部署上线 (1-2天)
1. ✅ 生产环境配置
2. ✅ CI/CD 流程设置
3. ✅ 监控和日志配置
4. ✅ 备份恢复方案

## ⚠️ 注意事项

### 1. 功能限制
- **本地文件访问**: Web 应用无法直接访问用户本地文件系统
  - 解决方案: 通过文件上传组件让用户主动上传

- **系统集成**: 无法像桌面应用那样深度集成系统
  - 解决方案: 使用 Web API (如 File System API) 或 PWA 特性

### 2. 安全考虑
- **API 认证**: 添加用户认证机制
  ```python
  # 使用 JWT 或 OAuth2
  from fastapi.security import OAuth2PasswordBearer
  ```

- **文件上传限制**: 限制文件大小和类型
  ```python
  MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
  ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}
  ```

- **HTTPS**: 生产环境必须使用 HTTPS
  ```yaml
  # 使用 Let's Encrypt 自动获取证书
  ```

### 3. 性能优化
- **静态资源 CDN**: 将前端静态资源部署到 CDN
- **数据库连接池**: 使用连接池优化数据库访问
- **缓存策略**: Redis 缓存热点数据
- **负载均衡**: 多实例部署 + Nginx 负载均衡

### 4. 监控和日志
```yaml
# 添加监控服务 (可选)
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

## 📚 参考资料

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [Nginx 配置指南](https://nginx.org/en/docs/)
- [React 生产部署](https://react.dev/learn/start-a-new-react-project)

## 🎉 预期收益

1. **更好的可扩展性**: 可以轻松水平扩展
2. **更低的部署成本**: 无需为每个用户分发安装包
3. **更快的迭代速度**: 一次部署所有用户立即更新
4. **更好的维护性**: 统一的环境和配置管理
5. **跨平台访问**: 支持任何设备和操作系统通过浏览器访问
