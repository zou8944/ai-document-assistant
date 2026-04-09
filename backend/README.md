# AI Document Assistant Backend

基于 Python 的 AI 文档处理后端，使用 FastAPI 提供 HTTP 接口，uv 管理依赖。

## 项目结构

```
backend/
├── api/                    # FastAPI 路由和中间件
├── crawler/                # 网页爬取模块
├── data_processing/        # 文件读取和文本切分
├── database/               # 数据库相关（连接、模型、迁移）
│   ├── base.py             # SQLAlchemy Base
│   ├── connection.py       # engine / session 管理
│   ├── models/             # ORM 模型
│   │   ├── chat.py
│   │   ├── collection.py
│   │   ├── document.py
│   │   ├── settings.py
│   │   └── task.py
│   └── migrations/         # Alembic 迁移脚本
│       └── versions/
├── models/                 # Pydantic 模型、DTO、请求/响应
├── rag/                    # RAG 核心逻辑
├── repository/             # 数据访问层
├── services/               # 业务逻辑层
├── vector_store/           # ChromaDB 客户端
├── alembic.ini             # Alembic 配置
├── api_server.py           # 启动入口
└── pyproject.toml          # 项目配置和依赖
```

## 快速开始

### 1. 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 安装依赖

```bash
cd backend
uv sync          # 含开发依赖
uv sync --no-dev # 仅生产依赖
```

### 3. 配置环境变量

```bash
cp ../.env.example ../.env
```

必填项：

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 连接串，如 `postgresql://postgres:postgres@localhost:5432/ai_document_assistant` |
| `OPENAI_API_KEY` | LLM / Embedding API Key |
| `OPENAI_BASE_URL` | API Base URL，默认 `https://api.openai.com/v1` |

### 4. 启动数据库

本地开发需要运行 PostgreSQL 和 ChromaDB：

```bash
# 在项目根目录启动
docker compose up postgres chroma -d
```

### 5. 运行服务

```bash
uv run python api_server.py
```

服务启动时会自动执行数据库迁移（`alembic upgrade head`）。

## 数据库

### 表结构

```
collections (知识库)
├── documents (文档)
│   └── document_chunks (文档块，与 ChromaDB 向量映射)
└── tasks (异步任务)
    └── task_logs (任务日志)

chats (对话)
└── chat_messages (消息)

settings (系统设置)
```

### 迁移操作

```bash
# 新增表或修改字段后，生成迁移脚本
uv run alembic revision --autogenerate -m "描述变更内容"

# 检查生成的脚本（在 database/migrations/versions/ 下），确认无误后执行
uv run alembic upgrade head

# 其他常用命令
uv run alembic current       # 查看当前版本
uv run alembic history       # 查看迁移历史
uv run alembic downgrade -1  # 回滚一个版本
```

### 添加初始数据

需要随首次建表一起插入的数据，写在初始迁移脚本
`database/migrations/versions/766923fa4157_initial_database_schema.py` 的 `upgrade()` 末尾，使用 `op.bulk_insert()`。

## 开发

### 代码质量

```bash
uv run black .       # 格式化
uv run ruff check .  # Lint
uv run mypy .        # 类型检查
```

### 测试

```bash
uv run pytest                                    # 全部测试
uv run pytest --cov                              # 含覆盖率
uv run pytest tests/test_file_processor.py -v   # 指定文件
```

### 依赖管理

```bash
uv add package_name        # 添加依赖
uv add --dev package_name  # 添加开发依赖
uv sync --upgrade          # 升级依赖
uv tree                    # 查看依赖树
```

## 故障排除

**依赖解析失败**
```bash
uv lock --upgrade
```

**Python 版本问题**
```bash
uv python install 3.11
uv sync
```

**缓存问题**
```bash
uv cache clean
uv sync --refresh
```
