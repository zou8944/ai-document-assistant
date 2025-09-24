# GitHub Copilot 指令集 (Repository-level Instructions)

本文件用于向 GitHub Copilot（及兼容的 AI 编码助手）提供项目级上下文，使其在生成代码、注释与文档时遵循既定的架构、风格与约束。请保持内容随项目演进而更新。

---
## 1. 项目概述
AI 文档阅读助手：聚合 本地文件 / 文件夹 / 网站 作为知识来源，利用 RAG（Retrieval-Augmented Generation）实现精准问答。前端为 Electron + React + Tailwind 桌面应用，后端为 Python 服务（爬虫 + 数据处理 + 向量存储 + RAG 检索）。

核心路径与模块：
- 后端：`backend/`
  - 爬虫：`crawler/`（含 Crawl4AI、Scrapy 替代/扩展实现）
  - 文本处理：`data_processing/`
  - 向量存储：`vector_store/`（Chroma 客户端）
  - RAG 逻辑：`rag/`（检索链、意图分析、缓存、摘要）
  - 服务接口：`api/` (FastAPI应用定义 + routes/*)
  - 启动入口：`api_server.py`
  - 服务层：`services/`（collection / document / query）
  - 数据模型：`models/`（Pydantic 请求/响应/流式）
- 前端：`frontend/` (Electron + React + TS + Tailwind)
  - 组件：`src/components/`
  - 状态与服务：`src/store/`, `src/services/`
  - 入口：`src/main.tsx`, `App.tsx`

---
## 2. AI 生成内容的基本准则
- 遵循最小侵入：不随意改动未涉及的模块、公共接口或约定命名。
- 优先复用：先查找已有工具函数 / 组件 / 服务再新增。
- 保持幂等：新增函数需写出清晰输入/输出与错误路径。
- 明确边界：RAG 相关回答需说明来源或提供引用字段（若接口需要）。
- 生成代码时：
  - Python：类型注解 + 遵循 PEP8，避免过度魔法写法。
  - TypeScript：启用严格模式友好（显式类型、避免 any）。
  - Tailwind：遵循 Apple Liquid Glass 风格（半透明、柔和渐变、模糊背景）。
- 避免：
  - 引入重量级新依赖（先评估必要性）。
  - 隐式全局状态。
  - 将业务逻辑放入 React 组件渲染体内（应抽离 hooks / service）。

---
## 3. 后端约定
### 3.1 结构与职责
- `crawler/`: 只负责抓取与内容抽取，不做向量化。
- `data_processing/`: 负责文本清洗、分块（RecursiveCharacterTextSplitter 可配置 chunk_size / overlap）。
- `vector_store/`: 封装 Chroma 读写，隔离具体向量库实现。
- `rag/`: 构建检索链、增强策略（多路检索 / 意图分析 / 摘要融合 / 缓存）。
- `services/`: 编排层，组合模型 + 向量库 + 处理逻辑，对外暴露语义清晰的方法。
- `api/routes/`: 仅做请求解析、调用 service、返回模型化响应。

### 3.2 编码规范 (Python)
- 强制：`from __future__ import annotations`（若 Python 版本允许）以减少前置类型引用问题。
- 日志：统一使用 `logging`，模块级 logger：`logger = logging.getLogger(__name__)`。
- 错误：显式自定义异常（如 CrawlingError / VectorStoreError / RetrievalError）放在集中模块（可创建 `exceptions.py`）。
- 数据模型：使用 Pydantic BaseModel；请求与响应分离；流式响应模型单独放置。
- 纯函数优先：涉及 I/O 或外部依赖部分封装，方便 mock。

### 3.3 RAG 指南
- 分块策略：根据文档类型（HTML / Markdown / PDF）可适度自适应 chunk_size；默认 800~1200 chars，overlap 100~150。
- 检索：默认 top_k = 4~8，可根据意图动态调整。
- Prompt 模板集中维护于 `rag/prompt_templates.py`，新增时保持参数化、避免硬编码业务文案。
- 缓存：如有多级缓存（内存 + 磁盘 + 向量召回摘要），调用链需注明失效策略。

### 3.4 测试
- 优先级：RAG 核心 > 向量存储接口 > 爬虫解析 > API 输入输出。
- 约定：测试文件命名 `test_*.py`；使用 `pytest` fixtures 构造临时向量库 / 临时目录。
- Mock：LLM / Embedding / 网络请求必须 mock，确保 CI 可离线运行。

---
## 4. 前端约定
### 4.1 组件
- UI 组件无业务：放在 `components/`；业务逻辑用 `hooks/`（可新增目录）。
- 状态：全局状态（如当前 collection / 索引状态 / 查询历史）集中在 `store/`（可用 Zustand / Redux，视已选方案）。
- 服务：所有与后端交互在 `src/services/`，禁止直接在组件中 fetch。

### 4.2 Electron
- 主进程与渲染进程通信使用 `contextBridge` + 安全的 IPC 通道；禁止 `nodeIntegration: true`。
- 后端 Python 进程生命周期：启动/退出应有统一管理（如 `processManager.ts`）。

### 4.3 样式
- Tailwind class 顺序：布局 > 尺寸 > 间距 > 边框 > 背景/模糊 > 排版 > 动画。
- 玻璃拟态参考：`backdrop-blur-*` + 半透明白/深色渐变 + subtle border (`border-white/10`).

### 4.4 测试
- 使用 Vitest / Jest + React Testing Library；关键交互（提问、加载、错误态）需测试。
- Snapshot 仅用于稳定、低变动组件；其余断言使用语义查询（`getByRole` 等）。

---
## 5. 命名与文档
- 目录/文件：小写下划线 (Python)，小写短横线或驼峰 (TSX 组件首字母大写)。
- 函数：动宾结构，如 `build_retrieval_chain`, `fetchCollections`。
- 变量：语义明确，避免单字母除循环计数。
- 注释：解释“为什么”，不是“做什么”（代码应自解释）。
- README / 架构图更新需同步相关更改（新增模块 / 依赖 / 流程）。

---
## 6. 安全与合规
- 禁止在仓库中硬编码 API Key / 凭证；使用环境变量（.env，且确保在 .gitignore 中）。
- 爬虫遵守 robots.txt（若策略允许可配置忽略，但需显式选项）。
- 对用户私有文档：仅本地存储，不上传外部第三方（除非显式配置）。

---
## 7. 贡献工作流建议
1. 新特性：创建 issue 描述背景/方案 → PR → 代码审查 → 合并。
2. PR 描述：问题背景、方案要点、边界情况、测试说明。
3. CI（可后续添加）：lint + test + type check（mypy / pyright / tsc）。

---
## 8. 生成式 AI 使用指引（给 Copilot）
- 在生成改动前，请先“阅读上下文”并避免重复已存在的工具函数或常量。
- 对涉及跨层（API → Service → RAG）的功能，先给出分层设计草案再填充实现。
- 任何新增可配置参数（如 top_k、chunk_size）需：默认值 + 文档注释 + 可通过配置或函数参数覆盖。
- 返回给调用方的对象需结构稳定；避免无版本管理的破坏性字段改名。
- 若不确定需求（模糊描述）应先输出澄清问题列表，而非直接生成代码。

---
## 9. TODO / 待补充（生成时不要假设已实现）
- 统一异常层与异常映射。
- 检索多策略融合（语义 + BM25 + 摘要向量）。
- LLM / Embedding 模型配置抽象。
- 前端查询对话上下文管理与回溯展示。
- 结果引用高亮与定位。

---
## 10. 更新说明
修改本文件需在 PR 中单独标明 “Update Copilot Instructions”，并说明调整原因。

---
（完）
