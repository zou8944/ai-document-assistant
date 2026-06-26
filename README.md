# AI Document Assistant

简体中文 | [English](./README.en.md)

基于 React + Python 的 AI 文档阅读助手，支持本地文件处理和网站内容抓取，提供智能问答功能。

> **Vibe Coding 项目** — 本项目主要通过 AI 辅助编程（Claude Code）完成，代码由 AI 生成并经人工审查，非纯手工编写。

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
│   ├── api_server.py        # 启动入口
│   └── .env.example         # 后端环境变量模板
├── frontend/                # React 前端
│   ├── src/
│   ├── nginx.conf
│   └── .env.example         # 前端环境变量模板
├── docker-compose.yml
└── docker-compose.prod.yml
```

## 快速开始（Docker）

```bash
# 1. 配置 AI 环境变量
cp .env.deploy.example .env.deploy
# 编辑 .env.deploy，至少填写 CRAWL_API_KEY 和 AGENT_API_KEY

# 2. 部署
make deploy-local

# 3. 访问应用
open http://ai-assist.zou8944.com
```

首次部署会自动将 `ai-assist.zou8944.com` 写入 `/etc/hosts`。部署时使用的域名和端口可在 [frontend/nginx.conf](frontend/nginx.conf) 和 [docker-compose.yml](docker-compose.yml) 中修改。

服务端口：

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 | 80 | 通过 nginx 访问 |
| 后端 API | 18888 | 内部使用，不对外暴露 |
| ChromaDB | 18000 | 如需外部连接 |
| PostgreSQL | 15432 | 如需外部连接 |

## 本地开发

### 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Docker & Docker Compose | - | 运行 PostgreSQL 和 ChromaDB |
| Python | >= 3.9 | 后端运行时 |
| [uv](https://docs.astral.sh/uv/) | - | Python 依赖管理（替代 pip） |
| Node.js | >= 18 | 前端构建与开发 |
| npm | - | 前端依赖管理（随 Node.js 安装） |

### 第一步：启动基础服务

使用 Docker Compose 启动 PostgreSQL 和 ChromaDB：

```bash
docker compose up postgres chroma -d
```

验证服务是否正常运行：

```bash
docker compose ps
# 应看到 postgres (healthy) 和 chroma 两个容器
```

### 第二步：配置后端

```bash
cd backend

# 从模板创建 .env 文件
cp .env.example .env
```

编辑 `.env`，填入以下必填项：

```env
# 爬取阶段 LLM（兼容 OpenAI 接口的第三方服务均可，如 SiliconFlow）
CRAWL_API_KEY=your_api_key_here
CRAWL_BASE_URL=https://api.siliconflow.cn/v1
CRAWL_MODEL=gpt-4o

# 聊天 Agent LLM（Anthropic Claude）
AGENT_API_KEY=your_anthropic_api_key_here
AGENT_MODEL=claude-sonnet-4-20250514

# Embedding 模型（兼容 OpenAI 接口）
EMBEDDING_API_KEY=your_api_key_here
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-ada-002
```

其余数据库和 Chroma 连接项保持 `.env.example` 中的默认值即可（本地开发指向 `localhost`）。

### 第三步：安装依赖并启动后端

```bash
cd backend
uv sync                           # 安装 Python 依赖
uv run python api_server.py       # 启动后端服务，默认监听 8888 端口
```

后端启动成功后访问 `http://localhost:8888/api/v1/health` 应返回正常响应。

### 第四步：启动前端

另开一个终端：

```bash
cd frontend
npm install          # 安装前端依赖
npm run dev          # 启动 Vite 开发服务器
```

访问 `http://localhost:5173` 即可使用。

### 一键启动（macOS）

```bash
make dev
```

此命令会在新终端窗口中启动后端，在当前终端启动前端。首次使用需授权终端 App 的 Automation 权限。

### Makefile 常用命令

| 命令 | 说明 |
|------|------|
| `make install` | 安装前后端所有依赖 |
| `make dev` | 一键启动本地开发环境 |
| `make dev-backend` | 仅启动后端 |
| `make dev-frontend` | 仅启动前端 |
| `make test` | 运行全部测试 |
| `make lint` | 运行代码检查（ruff + black + tsc） |
| `make migrate` | 执行数据库迁移 |

## 环境变量

### 部署（Docker）

部署专用配置位于项目根目录的 `.env.deploy`，模板见 [.env.deploy.example](.env.deploy.example)。**只包含 AI 相关配置**，数据库和 Chroma 配置已硬编码在 docker-compose.yml 中：

| 变量 | 必填 | 说明 |
|------|------|------|
| `CRAWL_API_KEY` | 是 | 爬取阶段 LLM API Key |
| `CRAWL_BASE_URL` | 是 | 爬取阶段 API Base URL |
| `AGENT_API_KEY` | 是 | 聊天 Agent LLM API Key（Anthropic） |
| `EMBEDDING_API_KEY` | 是 | Embedding API Key |
| `EMBEDDING_BASE_URL` | 是 | Embedding API Base URL |
| `LOG_LEVEL` | 否 | 默认 `info` |

### 本地开发

开发环境配置见 [backend/.env.example](backend/.env.example)，除 AI 配置外还包含数据库连接信息：

| 变量 | 说明 |
|------|------|
| `POSTGRES_HOST` | 本地开发填 `localhost` |
| `POSTGRES_PORT` | 默认 `5432` |
| `POSTGRES_USER` | 默认 `postgres` |
| `POSTGRES_PASSWORD` | 默认 `postgres` |
| `POSTGRES_DB` | 默认 `ai_document_assistant` |

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
make deploy-local
```

或手动：
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

生产环境注意事项：
- 必须配置 HTTPS（推荐用 Traefik 或 Caddy 作反向代理）
- 修改 `docker-compose.yml` 中的默认数据库密码
- 定期备份数据目录（见下方备份命令）

### 数据备份与恢复

所有数据存储在宿主机 `~/.ai-document-assistant/data/` 下：

```bash
# 备份整个数据目录
tar czf ~/ai-doc-backup.tar.gz ~/.ai-document-assistant/data/

# 恢复
tar xzf ~/ai-doc-backup.tar.gz -C /

# 备份 PostgreSQL
docker compose exec postgres pg_dump -U postgres ai_document_assistant > backup.sql

# 恢复 PostgreSQL
cat backup.sql | docker compose exec -T postgres psql -U postgres ai_document_assistant
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
lsof -i :80   # 或 :18888 / :18000 / :15432
# 修改 docker-compose.yml 中的端口映射
```

**后端启动失败**
```bash
docker compose logs backend
curl http://localhost:18888/api/v1/health
```

**ChromaDB 连接失败**
```bash
curl http://localhost:18000/api/v1/heartbeat
```

**问答结果不准确**
- 检查 Embedding 模型配置
- 尝试调整 `text.chunk_size` 和 `text.chunk_overlap` 设置

## UI 设计规范

遵循 [UI 设计指南.md](UI%20设计指南.md) 中定义的 Apple Liquid Glass 风格，详见该文件。

## 许可证

MIT
