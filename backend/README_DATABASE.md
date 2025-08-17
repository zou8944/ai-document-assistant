# AI Document Assistant - Database Architecture

SQLAlchemy 数据库架构已成功构建，符合需求文档中的设计规范。

## 🗄️ 已实现的组件

### 1. 数据库模型 (models/database/)
- **Collection**: 知识库集合模型
- **Document**: 文档模型，支持本地文件和网页
- **DocumentChunk**: 文档块模型，用于精细向量管理
- **Task**: 异步任务模型 (文件导入、URL抓取)
- **TaskLog**: 任务日志模型
- **Chat**: 对话会话模型
- **ChatMessage**: 对话消息模型
- **Settings**: 系统设置模型

### 2. Repository 模式 (repository/)
- **BaseRepository**: 通用 CRUD 操作基类
- **CollectionRepository**: 知识库操作，包含统计更新
- **DocumentRepository**: 文档操作，支持状态管理和检索
- **DocumentChunkRepository**: 文档块操作，与 ChromaDB 映射
- **TaskRepository**: 任务操作，支持进度跟踪
- **TaskLogRepository**: 任务日志操作
- **ChatRepository**: 对话操作，支持消息统计
- **ChatMessageRepository**: 消息操作，支持历史管理
- **SettingsRepository**: 设置操作，支持类型转换和掩码

### 3. 数据库连接 (database/)
- **connection.py**: 数据库连接和会话管理
- **base.py**: SQLAlchemy 声明基类
- **init_data.py**: 默认设置数据
- **initialization.py**: 数据库初始化脚本

### 4. Alembic 迁移
- 完整的迁移环境配置
- 初始数据库架构迁移文件
- 支持自动生成迁移脚本

## 🎯 核心特性

### 数据库设计特性
- **SQLite + WAL 模式**: 提升并发性能
- **完整约束**: CHECK 约束、外键约束、唯一约束
- **索引优化**: 针对查询模式优化的索引
- **类型安全**: 使用 SQLAlchemy 2.0+ 的 Mapped 类型

### Repository 模式特性
- **通用 CRUD**: BaseRepository 提供标准操作
- **业务逻辑**: 各 Repository 包含特定业务方法
- **事务管理**: 自动处理数据库事务
- **类型提示**: 完整的 TypeScript 风格类型注解

### 数据一致性
- **向量映射**: DocumentChunk 与 ChromaDB 精确映射
- **统计缓存**: Collection 统计字段自动更新
- **级联删除**: 合理的级联删除策略
- **状态管理**: 文档和任务状态完整跟踪

## 📊 数据库表结构

```sql
collections (知识库集合)
├── documents (文档) 
│   └── document_chunks (文档块)
├── tasks (任务)
│   └── task_logs (任务日志)
└── 关联: chats ↔ collections (多对多)

chats (对话)
└── chat_messages (消息)

settings (系统设置)
```

## 🔧 使用方法

### 环境配置
```bash
# 复制环境配置文件
cp .env.example .env

# 编辑 .env 文件，设置数据库 URL（可选，默认使用 SQLite）
# DATABASE_URL=sqlite:///./data/app.db
# DATABASE_DEBUG=false
```

### 初始化数据库
```python
from database import initialize_database, ensure_database_initialized

# 首次初始化
initialize_database()

# 确保已初始化（安全调用）
ensure_database_initialized()
```

### 使用 Repository
```python
from database import get_db_session_context
from repository import CollectionRepository

with get_db_session_context() as session:
    collection_repo = CollectionRepository(session)
    
    # 创建知识库
    collection = collection_repo.create(
        id="test_kb",
        name="测试知识库", 
        description="用于测试的知识库"
    )
    
    # 更新统计
    collection_repo.update_stats("test_kb")
```

### 数据库迁移
```bash
# 生成新迁移
uv run alembic revision --autogenerate -m "描述"

# 应用迁移
uv run alembic upgrade head

# 查看当前版本
uv run alembic current
```

## 📋 默认设置

数据库初始化时会自动创建以下设置类别：
- **llm**: LLM 相关配置 (模型、API密钥等)
- **embedding**: Embedding 相关配置
- **paths**: 路径相关配置
- **crawler**: 爬虫相关配置
- **general**: 通用配置 (文本处理等)

## 🗃️ 数据库文件管理

### Git 忽略规则
数据库文件已被正确配置为 Git 忽略：

```gitignore
# .gitignore 中的数据库相关规则
data/                # 数据目录
*.db                 # 数据库文件
*.db-shm            # SQLite 共享内存文件
*.db-wal            # SQLite 预写日志文件
*.sqlite            # SQLite 数据库文件
*.sqlite3           # SQLite3 数据库文件
```

### 数据备份建议
- **开发环境**: 数据库文件位于 `./data/app.db`，会被 Git 忽略
- **生产环境**: 建议定期备份数据库文件
- **迁移数据**: 使用 Alembic 迁移脚本管理数据库结构变更

## ✅ 验收标准

所有任务均已完成：
- ✅ SQLAlchemy 模型符合数据库设计文档
- ✅ Repository 模式提供完整 CRUD 操作
- ✅ Alembic 迁移环境正确配置
- ✅ 数据库连接和事务管理正常
- ✅ 初始设置数据正确插入
- ✅ 代码质量检查通过

## 🚀 下一步

数据库架构构建完成后，可以继续实现：
1. 统一 API 响应框架 (P0-2)
2. 知识库管理核心功能 (P0-3) 
3. 基础文档管理 (P0-4)
4. 设置管理系统 (P0-5)

---

*这个数据库架构为 AI 文档阅读助手提供了稳固的数据存储基础，支持后续所有功能的开发。*