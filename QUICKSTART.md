# 快速开始指南

## 🐳 Docker 部署 (推荐,仅需 3 步)

### 步骤 1: 配置 API 密钥
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件,设置你的 OpenAI API Key
# OPENAI_API_KEY=your_api_key_here
```

### 步骤 2: 启动服务
```bash
docker-compose up -d
```

### 步骤 3: 访问应用
打开浏览器访问: **http://localhost**

就这么简单! 🎉

---

## 🛠️ 本地开发部署

### 前置要求
- Node.js 18+
- Python 3.9+
- Docker (用于 Chroma)

### 1. 启动 Chroma 向量数据库
```bash
docker run -d -p 8000:8000 chromadb/chroma:latest
```

### 2. 启动后端服务
```bash
cd backend

# 安装 uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖并启动
uv sync
uv run python api_server.py
```

### 3. 启动前端服务
```bash
cd frontend

# 安装依赖并启动
npm install
npm run dev
```

### 4. 访问应用
打开浏览器访问: **http://localhost:5173**

---

## 📋 使用指南

### 1. 创建知识库集合
1. 点击"集合管理"
2. 点击"创建新集合"
3. 输入集合名称和描述

### 2. 上传文档
1. 选择刚创建的集合
2. 点击"上传文档"
3. 选择文件(支持 PDF, Word, Markdown, 文本等)
4. 等待文档处理完成

### 3. 开始问答
1. 点击"智能问答"
2. 选择要查询的集合
3. 输入你的问题
4. 查看 AI 的回答和引用来源

### 4. 网站抓取
1. 点击"网站抓取"
2. 输入网站 URL
3. 设置抓取深度和范围
4. 等待抓取完成

---

## 🔧 常见问题

### Q: Docker 容器无法启动?
A: 检查端口是否被占用:
```bash
# 检查端口占用
lsof -i :80
lsof -i :8888
lsof -i :8000

# 修改 docker-compose.yml 中的端口映射
```

### Q: API Key 配置不生效?
A: 确保 `.env` 文件在项目根目录,并且重启了 Docker 容器:
```bash
docker-compose down
docker-compose up -d
```

### Q: 前端无法连接后端?
A: 检查后端健康状态:
```bash
curl http://localhost:8888/api/v1/health
```

### Q: 向量搜索结果不准确?
A: 可能需要调整以下配置:
- 增加文档切分的 `chunk_size`
- 调整相似度阈值
- 使用更好的 Embedding 模型

---

## 📚 更多文档

- [完整部署文档](README.md)
- [Docker 部署指南](README.Docker.md)
- [整改方案](requirements/3 - Docker部署整改方案.md)
- [UI 设计指南](UI 设计指南.md)

---

## 💡 提示

- 首次使用建议先上传一些测试文档熟悉系统
- 支持同时管理多个文档集合
- 可以为不同主题创建不同的集合
- 定期备份 Docker 数据卷以防数据丢失

---

## 🆘 获取帮助

遇到问题? 欢迎提交 Issue:
https://github.com/zou8944/ai-document-assistant/issues
