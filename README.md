# AI Document Assistant

一个基于 React + Python 的 AI 文档阅读助手，支持本地文件处理和网站内容抓取，并提供智能问答功能。

> 本项目以 [Context Engineering Intro](https://github.com/coleam00/context-engineering-intro?tab=readme-ov-file#template-structure) 为蓝本构建，提供了完整的项目模板结构和最佳实践指南。

## 🚀 功能特性

- **📁 文件处理**: 支持 PDF、Word、Markdown、文本等多种格式
- **🌐 网站抓取**: 递归抓取同域名下的网页内容
- **🤖 智能问答**: 基于 RAG 技术的文档问答系统
- **🐳 容器化部署**: 支持 Docker Compose 一键部署
- **⚡ 高性能**: 使用 Chroma 向量数据库确保快速检索

## 🏗️ 技术架构

### 前端 (React Web 应用)
- **React + TypeScript**: 现代化 UI 开发
- **Tailwind CSS**: 实用优先的 CSS 框架
- **Nginx**: 静态文件服务和 API 反向代理

### 后端 (Python FastAPI)
- **FastAPI**: 高性能 Web 框架
- **LangChain**: RAG 流程编排
- **Crawl4AI**: 智能网页抓取
- **Chroma**: 向量数据库
- **OpenAI Embeddings**: 文本向量化

## 📦 部署方式

### 方式 1: Docker Compose (推荐)
这是最简单的部署方式，适合生产环境和快速体验。

**系统要求**:
- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB 可用内存

**快速开始**:
```bash
# 1. 克隆仓库
git clone https://github.com/zou8944/ai-document-assistant
cd ai-document-assistant

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 设置 OPENAI_API_KEY 等配置

# 3. 启动服务
docker-compose up -d

# 4. 访问应用
# 打开浏览器访问 http://localhost
```

详细文档请查看: [README.Docker.md](README.Docker.md)

### 方式 2: 本地开发部署
适合开发和调试。

**系统要求**:
- Node.js 18+
- Python 3.9+
- Docker (用于 Chroma)

### 配置文件
应用使用 TOML 配置文件进行配置，首次启动时会在用户目录下创建默认配置：
- 配置文件位置：`~/.ai-document-assistant/config.toml`
- 可通过应用内的设置界面进行配置

配置文件示例

```toml
[llm]
api_key = "sk-xxxxxx"
base_url = "https://api.siliconflow.cn/v1"
chat_model = "deepseek-ai/DeepSeek-V3"

[embedding]
api_key = "sk-xxxxxx"
base_url = "https://api.siliconflow.cn/v1"
model = "Pro/BAAI/bge-m3"

[knowledge_base]
max_crawl_pages = 1000
max_file_size_mb = 10

[system]
log_level = "debug"
```

## 🛠️ 快速开始

### 1. 克隆仓库
```bash
git clone https://github.com/zou8944/ai-document-assistant
cd ai-document-assistant
```

### 2. 启动 Chroma 数据库
```bash
docker-compose up -d
```

### 3. 设置后端
```bash
cd backend
# 安装 uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖
uv sync
```

### 4. 设置前端
```bash
cd frontend
npm install
```

### 5. 开发模式启动
```bash
# 在两个终端中分别运行:

# 终端 1: 启动后端
cd backend
uv run python api_server.py

# 终端 2: 启动前端
cd frontend
npm run dev

# 访问 http://localhost:5173
```

## 🐛 开发与调试

### 本地开发模式 (推荐)

这是最方便的调试方式,支持热重载和断点调试。

```bash
# 1. 启动 Chroma (仅需一次)
docker run -d -p 8000:8000 --name chroma chromadb/chroma:latest

# 2. 启动后端 (终端 1)
cd backend
export OPENAI_API_KEY="your_key"
uv run python api_server.py

# 3. 启动前端 (终端 2)
cd frontend
npm run dev

# 访问 http://localhost:5173
```

### VS Code 调试

项目已配置好 VS Code 调试环境:

1. **打开调试面板** (⇧⌘D / Ctrl+Shift+D)
2. **选择调试配置**:
   - `Backend: FastAPI Dev Server` - 后端调试
   - `Frontend: Chrome Debug` - 前端调试
   - `Full Stack: Backend + Frontend` - 全栈调试
3. **按 F5 开始调试**

详细调试指南: [DEBUG_GUIDE.md](DEBUG_GUIDE.md)

## 🧪 测试

### 后端测试
```bash
cd backend
uv run pytest tests/ -v

# 或使用 VS Code 任务: Cmd+Shift+P → "Tasks: Run Task" → "Backend: Run Tests"
```

### 前端测试
```bash
cd frontend
npm test

# 测试覆盖率
npm run test:coverage
```

## 📊 验证步骤

### Level 1: 语法和样式检查
```bash
# 后端
cd backend
uv run black . --check
uv run mypy .
uv run ruff check .

# 前端
cd frontend
npm run lint
npm run type-check
npm run build
```

### Level 2: 单元测试
```bash
# 后端单元测试
cd backend && uv run pytest tests/ -v

# 前端单元测试
cd frontend && npm test
```

### Level 3: 集成测试
```bash
# 启动完整系统
docker-compose up -d
cd frontend && npm run dev

# 测试完整流程:
# 1. 上传测试文档
# 2. 验证处理成功
# 3. 进行问答测试
# 4. 验证返回结果包含来源
```

## 📁 项目结构

```
ai-document-assistant/
├── backend/                     # Python 后端
│   ├── crawler/                # 网页抓取
│   ├── data_processing/        # 数据处理
│   ├── vector_store/           # 向量存储
│   ├── rag/                    # RAG 实现
│   ├── tests/                  # 后端测试
│   └── main.py                 # 入口文件
├── frontend/                    # Electron + React 前端
│   ├── src/
│   │   ├── components/         # React 组件
│   │   ├── services/           # 服务层
│   │   ├── styles/             # 样式文件
│   │   └── tests/              # 前端测试
│   ├── main.ts                 # Electron 主进程
│   └── package.json
├── docker-compose.yml          # Chroma 容器配置
└── README.md
```

## 🎨 UI 设计指南

本项目遵循 `UI 设计指南.md` 中定义的 Apple Liquid Glass 风格：

- **毛玻璃效果**: `backdrop-filter: blur(20px)`
- **半透明背景**: `background-color: rgba(255, 255, 255, 0.8)`
- **柔和阴影**: `box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1)`
- **系统字体**: SF Pro Display
- **原生交互**: 遵循 macOS HIG 指南

## 📋 使用指南

### 1. 处理本地文件
1. 点击"上传文件"选项卡
2. 拖拽文件到上传区域或点击"选择文件"
3. 等待处理完成
4. 切换到"智能问答"开始提问

### 2. 抓取网站内容
1. 点击"抓取网站"选项卡
2. 输入目标网站 URL
3. 点击"开始抓取网站"
4. 等待抓取完成
5. 切换到"智能问答"开始提问

### 3. 智能问答
1. 在聊天界面输入问题
2. 按回车键或点击发送按钮
3. 查看 AI 生成的答案和引用来源
4. 继续对话深入探讨

## 📦 生产部署

### Docker 生产部署(推荐)

```bash
# 使用生产配置启动
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 查看日志
docker-compose logs -f

# 备份数据
docker run --rm \
  -v ai-doc-assistant_backend-data:/data \
  -v $(pwd):/backup alpine \
  tar czf /backup/data-backup.tar.gz /data
```

### 性能优化建议

1. **使用 HTTPS**: 生产环境必须使用 HTTPS
2. **反向代理**: 推荐使用 Traefik 或 Caddy
3. **资源限制**: 在 `docker-compose.prod.yml` 中配置资源限制
4. **日志管理**: 配置日志轮转避免磁盘占满
5. **定期备份**: 设置自动备份脚本

详细配置请参考: [README.Docker.md](README.Docker.md)

## 🔧 开发指南

### 代码规范
- **后端**: 遵循 PEP8，使用 black 格式化
- **前端**: 使用 ESLint + Prettier，遵循 React 最佳实践
- **提交**: 遵循 Conventional Commits 规范

### 添加新功能
1. 创建对应的测试用例
2. 实现功能代码
3. 确保所有测试通过
4. 更新文档

### 性能优化
- 使用 Chroma 的 gRPC 接口提高性能
- 前端使用 React.memo 和 useMemo 优化渲染
- 后端采用异步处理避免阻塞

## 🐛 故障排除

### 常见问题

**1. Python 后端无法启动**
- 检查 Python 环境和依赖安装
- 通过应用设置界面配置 API Key
- 确认 Chroma 容器正在运行

**2. Electron 窗口显示异常**
- 确认 Node.js 版本 18+
- 重新安装 node_modules
- 检查系统兼容性

**3. 向量搜索结果不准确**
- 检查文档是否正确处理
- 调整 chunk_size 和 chunk_overlap 参数
- 验证 embedding 模型配置

### 日志查看
```bash
# 后端日志
tail -f backend/backend.log

# 前端开发者工具
# 在应用中按 F12 打开
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [LangChain](https://python.langchain.com/) - RAG 框架
- [Chroma](https://docs.trychroma.com/docs/overview/introduction) - 向量数据库
- [Crawl4AI](https://github.com/unclecode/crawl4ai) - 网页抓取
- [Electron](https://www.electronjs.org/) - 桌面应用框架
- [React](https://react.dev/) - UI 框架
- [Tailwind CSS](https://tailwindcss.com/) - CSS 框架