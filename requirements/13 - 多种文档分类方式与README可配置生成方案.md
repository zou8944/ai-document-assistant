# 多种文档分类方式与 README 可配置生成方案

## 背景与动机

当前系统仅在任务流程的 `categorize` 阶段通过 AI 对文档进行智能分类，并在 `readme` 阶段自动生成 README。实际使用中，很多文档网站（如技术文档）本身就具有良好的路径层级结构，同一子类下的文档路径前缀高度一致。此时 AI 分类可能造成过度拆分或归类不符合用户直觉。同时，README 的自动生成有时并非用户所需，应作为可选项提供。

## 目标

1. 在任务创建时，允许用户选择文档分类方式：**AI 智能分类** 或 **按路径前缀分类**。
2. 在任务创建时，允许用户选择是否生成 README。
3. 在知识库管理页面，提供按钮支持**重新分类**和**重新生成 README**。
4. 重新分类时，同样让用户选择分类方式。

---

## 需求详细设计

### 1. 分类方式定义

#### 1.1 AI 智能分类（现有逻辑）

- 使用 LLM 分析页面标题和路径，将文档归纳为若干语义相关的分类。
- 分类结果经过 `order_categories_by_complexity()` 按学习难度排序。
- 适用于结构不清晰、路径无规律的内容。

#### 1.2 按路径前缀分类（新增）

- 基于文档的 `path` 字段，提取公共路径前缀作为分类依据。
- **分组策略**：
  - 统计所有文档的路径层级，取出现频率最高的前缀深度（如 `/docs/guide/` 中的 `docs/guide`）。
  - 若某前缀下文档数量超过阈值（如 5 篇），则单独为一类。
  - 若前缀下文档过少，向上合并到更短的前缀层级。
  - 根路径或无明确前缀的文档归入 "Other"。
- **分类命名**：使用路径本身作为分类名，如 `api/reference`、`docs/getting-started`。
- **排序**：按路径字符串字典序排序。
- 此方式不调用 LLM，纯本地计算，速度快且结果稳定。

### 2. 任务创建流程改造

#### 2.1 前端：创建任务对话框

在 `InputDialog.tsx`（URL 导入）和文件导入对话框中增加以下选项：

- **分类方式**（单选）：
  - `ai` — AI 智能分类（默认选中）
  - `path_prefix` — 按路径前缀分类
- **生成 README**（复选框）：
  - 默认勾选

这些选项仅在前端展示，随创建请求提交到后端。

#### 2.2 后端：请求模型扩展

在 `backend/models/requests.py` 的 `IngestUrlsRequest` 中增加：

```python
class IngestUrlsRequest(BaseModel):
    urls: Optional[list[str]] = None
    recursive_prefix: Optional[str] = None
    url_configs: Optional[list[UrlConfig]] = None
    categorize_mode: str = "ai"          # 新增: "ai" | "path_prefix"
    generate_readme: bool = True         # 新增
```

文件导入请求（`IngestFilesRequest` 等）同理扩展。

#### 2.3 后端：任务执行流程改造

任务处理阶段 `STAGES` 目前是固定的：

```python
STAGES = ["crawl", "vectorize", "rewrite_static", "categorize", "readme"]
```

改造为根据 `input_params` 动态决定：

- `categorize` 阶段：
  - 若 `categorize_mode == "ai"`，执行现有 AI 分类逻辑。
  - 若 `categorize_mode == "path_prefix"`，调用新的 `_categorize_by_path_prefix()` 方法，不调用 LLM。
  - 两种方式的输出格式保持一致（写入 `categories_json` / `categories_json_zh`）。
- `readme` 阶段：
  - 仅在 `generate_readme == true` 时执行，否则跳过。

#### 2.4 后端：Collection 模型扩展

在 `backend/database/models/collection.py` 中增加字段记录用户选择：

```python
class Collection(Base):
    # ... 现有字段 ...
    categorize_mode: str = Column(String, default="ai")   # "ai" | "path_prefix"
    generate_readme: bool = Column(Boolean, default=True)
```

这些字段在任务完成后更新，用于后续重新分类时记住用户偏好。

### 3. 路径前缀分类实现细节

#### 3.1 算法步骤

```python
def categorize_by_path_prefix(pages: list[dict]) -> list[dict]:
    """
    输入: pages 列表，每项包含 path, title 等字段
    输出: 标准分类格式 [{"category": "...", "pages": [...]}, ...]
    """
    # 1. 提取所有路径的前缀层级并统计
    # 2. 确定合理的分组深度（取文档数 >= 阈值的最深公共前缀）
    # 3. 按前缀分组
    # 4. 将过小分组向上合并
    # 5. 返回标准格式
```

#### 3.2 边界处理

- 路径为空或仅根路径 `/`：归入 "Other"。
- 不同域名混合同一 collection：按域名 + 路径前缀组合分组。
- 单一路径层级（如所有路径都是 `/page1`, `/page2`）：按第一级路径分组，或统一归入一个分类。

### 4. 重新分类与重新生成 README

#### 4.1 前端：知识库管理页面

在 `KnowledgeBaseManagement.tsx` 中，现有知识库卡片或详情区域增加两个操作按钮：

- **重新分类**按钮：
  - 点击后弹出确认对话框，让用户选择分类方式（AI / 路径前缀）。
  - 默认选中当前知识库记录的 `categorize_mode`。
  - 确认后调用重新分类 API。
- **重新生成 README**按钮：
  - 点击后直接调用重新生成 API（基于现有分类数据）。

#### 4.2 后端：API 接口

新增/复用以下接口：

1. **重新分类**（新增）
   ```
   POST /collections/{collection_id}/recategorize
   Body: { "categorize_mode": "ai" | "path_prefix" }
   ```
   - 创建 `recategorize` 类型任务。
   - 任务执行时只走 `categorize` 阶段（跳过 crawl、vectorize）。
   - 完成后更新 collection 的 `categories_json`、`categories_json_zh`、`categorize_mode`。

2. **重新生成 README**（已有）
   ```
   POST /collections/{collection_id}/regenerate-readme
   ```
   - 已有接口，复用即可，无需修改。

#### 4.3 任务类型扩展

在 `task.py` 的任务类型约束中增加：

```python
# 现有: 'ingest_files', 'ingest_urls', 'reindex_collection', 'regenerate_readme'
# 新增: 'recategorize'
```

### 5. 数据流与时序

```
用户创建任务
  │
  ▼
前端提交: { urls, categorize_mode, generate_readme }
  │
  ▼
后端创建任务，input_params 包含上述选项
  │
  ▼
任务执行:
  ├── crawl
  ├── vectorize
  ├── rewrite_static
  ├── categorize (根据 categorize_mode 选择实现)
  └── readme (仅在 generate_readme=true 时执行)
  │
  ▼
任务完成，更新 collection 的 categorize_mode / generate_readme 字段
```

重新分类时：

```
用户点击"重新分类"
  │
  ▼
前端弹出选择: categorize_mode
  │
  ▼
后端创建 recategorize 任务
  │
  ▼
只执行 categorize 阶段，覆盖原有分类数据
  │
  ▼
更新 collection.categorize_mode
```

### 6. 兼容性

- 已有任务和知识库没有 `categorize_mode` 字段，默认视为 `"ai"`。
- 已有知识库没有 `generate_readme` 字段，默认视为 `True`。
- 数据库迁移时需为新增字段设置默认值。

---

## 涉及文件清单

### 后端

| 文件 | 修改内容 |
|------|----------|
| `backend/models/requests.py` | `IngestUrlsRequest` 等增加 `categorize_mode`、`generate_readme` |
| `backend/database/models/collection.py` | 新增 `categorize_mode`、`generate_readme` 字段 |
| `backend/database/models/task.py` | 任务类型约束增加 `recategorize` |
| `backend/api/routes/ingest.py` | 读取新参数并传入 `task_service.create_task()` |
| `backend/api/routes/collections.py` | 新增 `POST /{id}/recategorize` 接口 |
| `backend/services/task_service.py` | 动态阶段执行、新增 `_categorize_by_path_prefix()`、recategorize 任务处理 |
| `backend/services/llm_service.py` | 无需修改（AI 分类逻辑不变） |

### 前端

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/components/InputDialog.tsx` | 增加分类方式选择和生成 README 复选框 |
| `frontend/src/components/knowledge/KnowledgeBaseManagement.tsx` | 增加"重新分类"和"重新生成 README"按钮 |
| `frontend/src/services/apiClient.ts` | 更新请求接口定义，增加 recategorize API |

### 数据库

| 文件 | 修改内容 |
|------|----------|
| Alembic 迁移文件 | 为 `collections` 表新增 `categorize_mode` 和 `generate_readme` 字段 |

---

## 验收标准

1. 创建 URL 导入任务时，对话框显示"分类方式"和"生成 README"选项。
2. 选择"按路径前缀分类"后，任务完成时文档按路径前缀分组，不调用 LLM 分类。
3. 取消勾选"生成 README"后，任务跳过 readme 阶段。
4. 知识库管理页面存在"重新分类"按钮，点击可选择分类方式并重新执行分类。
5. "重新生成 README"按钮可用，基于当前分类数据重新生成。
6. 重新分类后，知识库的文档展示即时反映新分类。
7. 现有知识库（无新字段）行为不变，默认 AI 分类并生成 README。
