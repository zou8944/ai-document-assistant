# AI Document Assistant - Docker 部署指南

## 🚀 快速开始

### 前置要求
- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB 可用内存

### 1. 克隆仓库
```bash
git clone https://github.com/zou8944/ai-document-assistant
cd ai-document-assistant
```

### 2. 配置环境变量
```bash
cp .env.example .env
```

编辑 `.env` 文件,设置必要的配置:
```bash
# OpenAI API 配置
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.siliconflow.cn/v1

# 其他配置保持默认即可
```

### 3. 启动服务
```bash
docker-compose up -d
```

### 4. 访问应用
打开浏览器访问: http://localhost

默认端口:
- 前端: `80`
- 后端 API: `8888`
- Chroma 向量数据库: `8000`

## 📦 架构说明

```
┌──────────────────────────────────────────────┐
│              Docker Compose                  │
│                                              │
│  ┌────────────┐  ┌─────────────┐  ┌──────┐ │
│  │  Nginx     │  │  Backend    │  │Chroma│ │
│  │  (前端)    │  │  (FastAPI)  │  │(向量)│ │
│  │  :80       │  │  :8888      │  │:8000 │ │
│  └────────────┘  └─────────────┘  └──────┘ │
└──────────────────────────────────────────────┘
```

### 服务说明

1. **frontend**: Nginx 服务器,提供 React 前端静态文件和 API 反向代理
2. **backend**: FastAPI Python 服务,处理文档和 RAG 逻辑
3. **chroma**: ChromaDB 向量数据库,存储文档向量

## 🔧 常用命令

### 查看服务状态
```bash
docker-compose ps
```

### 查看日志
```bash
# 所有服务
docker-compose logs -f

# 特定服务
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 重启服务
```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart backend
```

### 停止服务
```bash
docker-compose down
```

### 停止并删除数据卷
```bash
docker-compose down -v
```

### 重新构建并启动
```bash
docker-compose up -d --build
```

## 🔨 开发模式

### 本地开发(不使用 Docker)

#### 启动后端
```bash
cd backend
uv sync
uv run python api_server.py
```

#### 启动前端
```bash
cd frontend
npm install
npm run dev
```

### 查看资源使用
```bash
docker stats
```

## 🌐 生产部署

### 使用生产配置
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 配置 HTTPS
建议使用 Traefik 或 Caddy 作为反向代理来处理 HTTPS:

```yaml
# 示例 Traefik 配置
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.email=your@email.com"
    ports:
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

### 环境变量说明
```bash
# 必需配置
OPENAI_API_KEY         # OpenAI API 密钥
OPENAI_BASE_URL        # API 基础 URL

# 可选配置
OPENAI_CHAT_MODEL      # 默认: gpt-3.5-turbo
EMBEDDING_MODEL        # 默认: text-embedding-ada-002
LOG_LEVEL             # 默认: info
ANONYMIZED_TELEMETRY  # 默认: FALSE
```

## 🔍 故障排除

### 后端无法连接
```bash
# 检查后端日志
docker-compose logs backend

# 检查健康状态
curl http://localhost:8888/health
```

### 前端无法访问
```bash
# 检查 Nginx 配置
docker-compose exec frontend nginx -t

# 重启前端服务
docker-compose restart frontend
```

### Chroma 数据库问题
```bash
# 检查 Chroma 状态
curl http://localhost:8000/api/v1/heartbeat

# 重置 Chroma 数据
docker-compose down -v
docker-compose up -d
```

### 权限问题
```bash
# 修复数据卷权限
docker-compose down
sudo chown -R $USER:$USER backend-data backend-logs chroma-data
docker-compose up -d
```

## 📊 数据备份

### 备份数据卷
```bash
# 备份后端数据
docker run --rm -v ai-doc-assistant_backend-data:/data -v $(pwd):/backup alpine tar czf /backup/backend-data-backup.tar.gz /data

# 备份 Chroma 数据
docker run --rm -v ai-doc-assistant_chroma-data:/data -v $(pwd):/backup alpine tar czf /backup/chroma-data-backup.tar.gz /data
```

### 恢复数据卷
```bash
# 恢复后端数据
docker run --rm -v ai-doc-assistant_backend-data:/data -v $(pwd):/backup alpine tar xzf /backup/backend-data-backup.tar.gz -C /

# 恢复 Chroma 数据
docker run --rm -v ai-doc-assistant_chroma-data:/data -v $(pwd):/backup alpine tar xzf /backup/chroma-data-backup.tar.gz -C /
```

## 🔐 安全建议

1. **更改默认端口**: 修改 `docker-compose.yml` 中的端口映射
2. **使用 HTTPS**: 在生产环境中必须使用 HTTPS
3. **限制访问**: 使用防火墙或网络策略限制访问
4. **定期备份**: 设置自动备份脚本
5. **更新镜像**: 定期更新 Docker 镜像以获取安全补丁

## 📝 更新应用

### 拉取最新代码
```bash
git pull origin main
```

### 重新构建并部署
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 🤝 获取帮助

- GitHub Issues: https://github.com/zou8944/ai-document-assistant/issues
- 文档: 查看 `requirements/` 目录下的详细文档

## 📄 许可证

MIT License
