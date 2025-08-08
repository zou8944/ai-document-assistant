# AI Document Assistant Backend

基于 Python 的 AI 文档处理后端，使用 uv 进行依赖管理。

## 🚀 快速开始

### 1. 安装 uv (如果尚未安装)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 项目设置
```bash
cd backend

# 安装依赖 (包括开发依赖)
uv sync

# 或仅安装生产依赖
uv sync --no-dev
```

### 3. 环境配置
```bash
# 设置 OpenAI API Key
export OPENAI_API_KEY="your-openai-api-key"
```

### 4. 运行应用
```bash
# 使用 uv 运行
uv run python main.py

# 或激活虚拟环境后运行
source .venv/bin/activate  # macOS/Linux
# 或 .venv\Scripts\activate  # Windows
python main.py
```

## 🧪 开发和测试

### 代码质量检查
```bash
# 格式化代码
uv run black .

# 代码检查
uv run ruff check .

# 类型检查
uv run mypy .
```

### 运行测试
```bash
# 运行所有测试
uv run pytest

# 运行测试并生成覆盖率报告
uv run pytest --cov

# 运行特定测试
uv run pytest tests/test_file_processor.py -v
```

### 依赖管理
```bash
# 添加新依赖
uv add package_name

# 添加开发依赖
uv add --dev package_name

# 更新依赖
uv sync --upgrade

# 查看依赖树
uv tree
```

## 📦 项目结构

```
backend/
├── pyproject.toml          # 项目配置和依赖
├── uv.lock                 # 锁定的依赖版本
├── .python-version         # Python 版本
├── main.py                 # 应用入口
├── crawler/                # 网页爬取模块
├── data_processing/        # 数据处理模块
├── vector_store/           # 向量存储模块
├── rag/                    # RAG 实现模块
└── tests/                  # 测试文件
```

## 🔧 配置说明

### pyproject.toml
- 定义了项目依赖、开发工具配置
- 包含 ruff、black、mypy、pytest 的配置
- 支持多个 Python 版本 (3.9-3.12)

### uv 特性
- **快速**: 比 pip 快 10-100 倍
- **可靠**: 确定性依赖解析
- **兼容**: 与 pip/setuptools 完全兼容
- **现代**: 支持 PEP 621 标准

## 🐳 Docker 支持

如果需要在 Docker 中使用：

```dockerfile
FROM python:3.11-slim

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装依赖
RUN uv sync --frozen --no-dev

# 复制应用代码
COPY . .

# 运行应用
CMD ["uv", "run", "python", "main.py"]
```

## 🔍 故障排除

### uv 常见问题

1. **依赖解析失败**
   ```bash
   uv lock --upgrade
   ```

2. **Python 版本问题**
   ```bash
   uv python install 3.11
   uv sync
   ```

3. **缓存问题**
   ```bash
   uv cache clean
   uv sync --refresh
   ```

4. **查看详细日志**
   ```bash
   uv sync -v
   ```