FROM docker.1ms.run/library/python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./
COPY README.md ./

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
    CMD curl -f http://localhost:8888/health || exit 1

# 启动命令
CMD ["uv", "run", "python", "api_server.py", "--host", "0.0.0.0", "--port", "8888"]
