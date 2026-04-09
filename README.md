# AI Document Assistant

基于 React + Python 的 AI 文档阅读助手，支持本地文件处理和网站内容抓取，提供智能问答功能。

## 功能

- 支持 PDF、Word、Markdown、文本等多种格式
- 递归抓取同域名下的网页内容
- 基于 RAG 技术的文档问答，回答附带来源引用
- Docker Compose 一键部署

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React + TypeScript + Tailwind CSS，Nginx 托管 |
| 后端 | FastAPI + LangChain + Crawl4AI |
| 数据库 | PostgreSQL（元数据）+ ChromaDB（向量） |
| 部署 | Docker Compose |

## 项目结构

```
ai-document-assistant/
├── backend/                 # Python 后端
│   ├── api/                 # FastAPI 路由
│   ├── crawler/             # 网页爬取
│   ├── data_processing/     # 文件读取和文本切分
│   ├── database/            # ORM 模型、连接、迁移
│   ├── models/              # Pydantic 模型、DTO
│   ├── rag/                 # RAG 核心逻辑
│   ├── repository/          # 数据访问层
│   ├── services/            # 业务逻辑层
│   ├── vector_store/        # ChromaDB 客户端
│   └── api_server.py        # 启动入口
├── frontend/                # React 前端
│   ├── src/
│   └── nginx.conf
├── docker-compose.yml
├── docker-compose.prod.yml
└── .env.example
```

## 快速开始（Docker）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，至少填写 OPENAI_API_KEY

# 2. 启动所有服务
docker compose up -d

# 3. 访问应用
open http://localhost
```

服务启动后端口：

| 服务 | 端口 |
|------|------|
| 前端 | 80 |
| 后端 API | 8888 |
| ChromaDB | 8000 |
| PostgreSQL | 5432 |

## 本地开发

```bash
# 启动依赖服务（PostgreSQL + ChromaDB）
docker compose up postgres chroma -d

# 后端
cd backend
uv sync
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/ai_document_assistant"
export OPENAI_API_KEY="your_key"
uv run python api_server.py

# 前端（另开终端）
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 环境变量

完整说明见 [.env.example](.env.example)，核心变量：

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 是 | LLM / Embedding API Key |
| `OPENAI_BASE_URL` | 是 | API Base URL |
| `POSTGRES_USER` | 否 | 默认 `postgres` |
| `POSTGRES_PASSWORD` | 否 | 默认 `postgres` |
| `POSTGRES_DB` | 否 | 默认 `ai_document_assistant` |

## Docker 常用命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f backend

# 重启某个服务
docker compose restart backend

# 重新构建并启动
docker compose up -d --build

# 停止（保留数据卷）
docker compose down

# 停止并删除所有数据
docker compose down -v
```

## 生产部署

```bash
# 使用生产配置（含资源限制）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

生产环境注意事项：
- 必须配置 HTTPS（推荐用 Traefik 或 Caddy 作反向代理）
- 修改 `.env` 中的默认数据库密码
- 定期备份数据卷（见下方备份命令）

### 数据备份与恢复

```bash
# 备份 PostgreSQL
docker compose exec postgres pg_dump -U postgres ai_document_assistant > backup.sql

# 恢复 PostgreSQL
cat backup.sql | docker compose exec -T postgres psql -U postgres ai_document_assistant

# 备份 ChromaDB 数据卷
docker run --rm -v ai-doc-assistant_chroma-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/chroma-backup.tar.gz /data

# 恢复 ChromaDB 数据卷
docker run --rm -v ai-doc-assistant_chroma-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/chroma-backup.tar.gz -C /
```

## 使用指南

### 创建知识库
1. 进入「集合管理」，点击「创建新集合」

### 上传文档
1. 选择集合，点击「上传文档」
2. 支持 PDF、Word、Markdown、文本等格式
3. 等待处理完成（状态变为 indexed）

### 抓取网站
1. 选择集合，点击「网站抓取」
2. 输入起始 URL，设置抓取范围
3. 等待抓取完成

### 智能问答
1. 进入「智能问答」，选择要查询的集合
2. 输入问题，回答会附带原文来源

## 调试

详见 [DEBUG_GUIDE.md](DEBUG_GUIDE.md)。VS Code 已配置好调试环境，按 F5 选择配置即可。

## 故障排除

**端口被占用**
```bash
lsof -i :80   # 或 :8888 / :8000 / :5432
# 修改 docker-compose.yml 中的端口映射
```

**后端启动失败**
```bash
docker compose logs backend
curl http://localhost:8888/api/v1/health
```

**ChromaDB 连接失败**
```bash
curl http://localhost:8000/api/v1/heartbeat
```

**问答结果不准确**
- 检查 Embedding 模型配置
- 尝试调整 `text.chunk_size` 和 `text.chunk_overlap` 设置

## UI 设计规范

遵循 [UI 设计指南.md](UI%20设计指南.md) 中定义的 Apple Liquid Glass 风格，详见该文件。

## 许可证

MIT
