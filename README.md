# AI Document Assistant

一个基于 Electron + React + Python 的 AI 文档阅读助手，支持本地文件处理和网站内容抓取，并提供智能问答功能。

> 本项目以 [Context Engineering Intro](https://github.com/coleam00/context-engineering-intro?tab=readme-ov-file#template-structure) 为蓝本构建，提供了完整的项目模板结构和最佳实践指南。

## 🚀 功能特性

- **📁 文件处理**: 支持 PDF、Word、Markdown、文本等多种格式
- **🌐 网站抓取**: 递归抓取同域名下的网页内容
- **🤖 智能问答**: 基于 RAG 技术的文档问答系统
- **💎 原生界面**: 遵循 Apple Liquid Glass 设计，提供原生 macOS 体验
- **⚡ 高性能**: 使用 Chroma 向量数据库确保快速检索

## 🏗️ 技术架构

### 前端 (Electron + React)
- **Electron**: 跨平台桌面应用框架
- **React + TypeScript**: 现代化 UI 开发
- **Tailwind CSS**: 实用优先的 CSS 框架
- **Apple Liquid Glass**: 毛玻璃效果设计

### 后端 (Python)
- **LangChain**: RAG 流程编排
- **Crawl4AI**: 智能网页抓取
- **Chroma**: 向量数据库
- **OpenAI Embeddings**: 文本向量化

## 📦 安装要求

### 系统要求
- macOS 10.15+, Windows 10+, 或 Ubuntu 18.04+
- Node.js 18+
- Python 3.9+
- Docker (用于 Chroma)

### 环境变量
```bash
# OpenAI API Key (必需)
export OPENAI_API_KEY="your-openai-api-key"
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

# 终端 1: 启动后端 (可选，前端会自动启动)
cd backend
uv run python main.py

# 终端 2: 启动前端
cd frontend
npm run dev
```

## 🧪 测试

### 后端测试
```bash
cd backend
uv run pytest tests/ -v
```

### 前端测试
```bash
cd frontend
npm test
```

### 测试覆盖率
```bash
cd frontend
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
- 验证 OPENAI_API_KEY 环境变量
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