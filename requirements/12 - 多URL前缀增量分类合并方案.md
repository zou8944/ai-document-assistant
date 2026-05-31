# 多 URL 前缀 + 增量分类合并 + 独立 regenerate 方案

## 背景

用户需要将 Apple Developer 等大型文档站的不同子目录爬取到同一个集合中。当前系统每个 ingest task 只支持一个 `recursive_prefix`，用户需要手动发多次请求。此外，每次增量爬取后 categorize + readme 会对全量文档重新生成，浪费 AI token。需要三个改进：

1. **多 prefix 一次提交** — 一个 ingest task 处理多个 (seed_url, prefix) 对
2. **增量分类合并** — 增量爬取后仅对新文档分类，再与已有分类合并 + 自动优化
3. **独立 regenerate 入口** — 不重新爬取，单独触发 categorize + readme

## 如何区分新旧文档

新增 Document 模型字段 `categorized_at`（nullable timestamp）：

- `categorized_at IS NULL` → 未分类（新文档或被清除标记）
- `categorized_at = 有值` → 已参与过分类

三种场景：

| 场景 | 行为 |
|------|------|
| 增量爬取后 | 只取 `categorized_at IS NULL` 的文档交给 LLM，完成后标记全部 |
| 独立 regenerate | 先清除所有 `categorized_at`，再全量分类，最后重新标记 |
| 首次爬取 | 没有已有分类可合并，直接走全量 `_categorize_collection()`，完成后标记 |

---

## Feature 1: 多 prefix 一次提交

### Request 模型变更

**文件:** `backend/models/requests.py`

新增 `UrlConfig`，更新 `IngestUrlsRequest`，加 `model_validator` 保证新旧格式兼容：

```python
class UrlConfig(BaseModel):
    seed_urls: list[str] = Field(..., min_length=1)
    recursive_prefix: str = ""

class IngestUrlsRequest(BaseModel):
    # 旧格式（向后兼容）
    urls: Optional[list[str]] = None
    recursive_prefix: Optional[str] = None
    # 新格式
    url_configs: Optional[list[UrlConfig]] = None

    @model_validator(mode="after")
    def _normalize(self):
        if self.url_configs:
            return self  # 新格式直接用
        if self.urls:    # 旧格式 → 自动转换
            self.url_configs = [UrlConfig(seed_urls=self.urls, recursive_prefix=self.recursive_prefix or "")]
            return self
        raise ValueError("必须提供 urls 或 url_configs")
```

### Route 变更

**文件:** `backend/api/routes/ingest.py`

`input_params` 序列化改为传 `url_configs`，同时保留旧字段方便 task 显示：

```python
input_params = {
    "url_configs": [c.model_dump() for c in request_data.url_configs],
    "urls": request_data.url_configs[0].seed_urls,
    "recursive_prefix": request_data.url_configs[0].recursive_prefix,
}
```

### 核心处理 — crawl 阶段循环

**文件:** `backend/services/task_service.py` — `_process_url_ingestion()`

crawl 阶段改为循环处理多个 config：

- `skip_urls` 在循环前一次性计算，所有 config 共享
- `recovered_urls` 也全局计算，每个 config 按 prefix 过滤
- `stats` 跨 config 累积
- vectorize / categorize / readme 只跑一次

```python
url_configs = input_params.get("url_configs", [...fallback...])

existing_docs = self.doc_repo.get_by_collection(collection_id)
skip_urls = {d.uri for d in existing_docs if d.uri}

for config_idx, config in enumerate(url_configs):
    # 检查取消
    seed_urls = config["seed_urls"]
    prefix = config["recursive_prefix"]
    # ... 现有 crawl 逻辑 ...
    # stats 累积
```

### Task 显示

**文件:** `backend/services/task_service.py` — `_generate_task_title()`

当 `url_configs` 有多个时，标题改为 "多源抓取 (N 个配置)"。

### 边界情况

- **跨 config 去重**：URL 同时出现在 config 1 和 config 2 时，config 1 先爬取，config 2 的 skip_urls 自动跳过。DB unique constraint `(collection_id, uri)` 提供兜底。
- **从 vectorize+ 阶段恢复**：crawl 阶段整体跳过，无需改动。
- **从 crawl 阶段恢复**：所有 config 重新遍历，skip_urls 确保已存储页面被跳过。

---

## Feature 2: 增量分类合并

### 设计流程

1. 新增 `Document.categorized_at` 字段（nullable timestamp）
2. 增量 ingest 后，只对 `categorized_at IS NULL` 的文档分类
3. 将已有 `categories_json` + 新文档传给 LLM，生成合并后的分类
4. 自动优化：检查合并结果，过少分类合并、过多分类拆分
5. 用优化后的结果重新生成 README
6. 标记文档的 `categorized_at`

### 数据库变更

**新增字段:** `backend/database/models/document.py`

```python
categorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

**迁移文件:** `backend/database/migrations/versions/<hash>_add_categorized_at_to_documents.py`

```python
def upgrade():
    op.add_column('documents', sa.Column('categorized_at', sa.DateTime(timezone=True), nullable=True))
```

### 增量分类逻辑

**文件:** `backend/services/task_service.py`

新增方法 `_categorize_incremental()`：

```python
async def _categorize_incremental(self, task_id, collection_id):
    # 1. 获取未分类文档
    all_docs = self.doc_repo.get_by_collection(collection_id, exclude_statuses=["not_found"])
    new_docs = [d for d in all_docs if d.source_path and not d.categorized_at]
    existing_categorized = [d for d in all_docs if d.source_path and d.categorized_at]

    if not new_docs:
        return

    if not existing_categorized:
        # 首次分类，走全量
        await self._categorize_collection(task_id, collection_id)
        self._mark_categorized(collection_id)
        return

    # 2. 获取已有分类
    collection = self.collection_repo.get_by_id(collection_id)
    old_categories = json.loads(collection.categories_json or "[]")

    # 3. LLM 合并
    new_page_records = [{"id": d.id, "path": d.source_path, "title": d.name} for d in new_docs]
    merged = await self.llm_service.merge_categories(
        existing_categories=old_categories,
        new_pages=new_page_records,
    )

    # 4. 自动优化
    all_page_records = [{"id": d.id, "path": d.source_path, "title": d.name} for d in all_docs if d.source_path]
    optimized = await self.llm_service.optimize_categories(
        categories=merged,
        all_pages=all_page_records,
    )

    # 5. 英文源翻译
    if collection.source_language == "en" and collection.categories_json_zh:
        old_categories_zh = json.loads(collection.categories_json_zh)
        merged_zh = await self.llm_service.merge_categories(
            existing_categories=old_categories_zh,
            new_pages=new_page_records,
        )
        optimized_zh = await self.llm_service.optimize_categories(
            categories=merged_zh,
            all_pages=all_page_records,
        )
    else:
        optimized_zh = optimized

    # 6. 存储合并结果
    self.collection_repo.update_readme(
        collection_id,
        categories_json=json.dumps(optimized, ensure_ascii=False),
        categories_json_zh=json.dumps(optimized_zh, ensure_ascii=False) if optimized_zh else None,
    )

    # 7. 标记已分类
    self._mark_categorized(collection_id)
```

辅助方法 — 标记已分类：

```python
def _mark_categorized(self, collection_id):
    self.doc_repo.mark_categorized(collection_id)
```

**文件:** `backend/repository/document.py`

新增：

```python
def mark_categorized(self, collection_id: str) -> int:
    with session_context() as session:
        now = datetime.now(timezone.utc)
        stmt = (
            update(Document)
            .where(Document.collection_id == collection_id,
                   Document.status == "indexed",
                   Document.categorized_at.is_(None))
            .values(categorized_at=now)
        )
        result = session.execute(stmt)
        session.flush()
        return result.rowcount

def clear_categorized(self, collection_id: str) -> int:
    with session_context() as session:
        stmt = (
            update(Document)
            .where(Document.collection_id == collection_id,
                   Document.categorized_at.is_not(None))
            .values(categorized_at=None)
        )
        result = session.execute(stmt)
        session.flush()
        return result.rowcount
```

### LLM 合并 + 优化

**文件:** `backend/services/llm_service.py`

新增 `merge_categories()` — 将新文档归入已有分类或创建新分类：

```python
async def merge_categories(self, existing_categories: list[dict], new_pages: list[dict]) -> list[dict]:
    prompt = f"""你是一个文档分类专家。

已有分类结构：
{json.dumps(existing_categories, ensure_ascii=False, indent=2)}

新增文档：
{json.dumps(new_pages, ensure_ascii=False, indent=2)}

请将新增文档合并到已有分类中：
- 如果新文档适合已有分类，将其加入
- 如果新文档不适合任何已有分类，创建新分类
- 保持分类从基础到高级的顺序

输出与已有分类相同格式的 JSON 数组。"""
    # 调用 LLM ...
```

新增 `optimize_categories()` — 检查均衡性并自动调整：

```python
async def optimize_categories(self, categories: list[dict], all_pages: list[dict]) -> list[dict]:
    prompt = f"""你是一个文档分类专家。以下是当前的分类结构和全部文档列表。

当前分类：
{json.dumps(categories, ensure_ascii=False, indent=2)}

全部文档：
{json.dumps(all_pages, ensure_ascii=False, indent=2)}

请检查并优化分类结构：
- 合并文档数过少的分类（少于 2 篇的考虑合并到相近分类）
- 拆分文档数过多的分类（超过 20 篇的考虑按子主题拆分）
- 确保分类名称清晰、有层次
- 确保每个文档都在且只在一个分类中
- 保持从基础到高级的排列顺序

输出优化后的 JSON 数组，格式与输入相同。如果没有需要调整的，原样返回。"""
    # 调用 LLM ...
```

### 集成点

**文件:** `backend/services/task_service.py` — `_process_url_ingestion()`

categorize 阶段判断：

```python
collection = self.collection_repo.get_by_id(collection_id)
if collection.categories_json:
    # 已有分类 → 增量合并
    await self._categorize_incremental(task_id, collection_id)
else:
    # 首次 → 全量分类
    await self._categorize_collection(task_id, collection_id)
    self._mark_categorized(collection_id)
```

---

## Feature 3: 独立 regenerate 入口

### DB 迁移

**新文件:** `backend/database/migrations/versions/<hash>_add_regenerate_readme_task_type.py`

在 task type CHECK 约束中增加 `regenerate_readme`：

```python
def upgrade():
    op.drop_constraint('chk_task_type', 'tasks', type_='check')
    op.create_check_constraint('chk_task_type', 'tasks',
        "type IN ('ingest_files', 'ingest_urls', 'reindex_collection', 'regenerate_readme')")
```

### API 端点

**文件:** `backend/api/routes/collections.py`

```python
@router.post("/collections/{collection_id}/regenerate-readme", status_code=202)
async def regenerate_readme(collection_id: str, request: Request):
    app_state = get_app_state(request)
    task_service = app_state.task_service

    collection = await app_state.collection_service.get_collection(collection_id)
    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")
    if collection.document_count == 0:
        raise HTTPBadRequestException(f"Collection '{collection_id}' has no documents")

    task = await task_service.create_task(
        task_type="regenerate_readme",
        collection_id=collection_id,
        input_params={"title": "重新生成 README"},
    )
    return {"task_id": task.task_id, "status": task.status}
```

### 处理方法

**文件:** `backend/services/task_service.py`

新增 `_process_regenerate_readme()`，复用现有 `_categorize_collection()` + `_generate_readme()`：

```python
async def _process_regenerate_readme(self, task_id, collection_id, input_params):
    # 清除所有 categorized_at 标记，以便全量重新分类
    self.doc_repo.clear_categorized(collection_id)

    # 全量 categorize
    self._update_stage(task_id, "categorize")
    await self._categorize_collection(task_id, collection_id)
    self._mark_categorized(collection_id)

    # generate readme
    self._update_stage(task_id, "readme")
    stats = UrlTaskStats()
    await self._generate_readme(task_id, collection_id, stats)

    self.task_repo.mark_completed(task_id, True)
```

### 分发

在 `_process_task_with_exception()` 中增加：

```python
elif task.type == "regenerate_readme":
    await self._process_regenerate_readme(task_id, task.collection_id, input_params)
```

---

## 实施顺序

1. **Feature 1 — 多 prefix**
   - `models/requests.py` — UrlConfig + IngestUrlsRequest 重构
   - `api/routes/ingest.py` — url_configs 序列化
   - `services/task_service.py` — crawl 循环 + _generate_task_title

2. **Feature 2 — 增量合并**
   - `database/models/document.py` — categorized_at 字段
   - 数据库迁移
   - `repository/document.py` — mark_categorized + clear_categorized
   - `services/llm_service.py` — merge_categories + optimize_categories
   - `services/task_service.py` — _categorize_incremental + 集成

3. **Feature 3 — regenerate**
   - 数据库迁移（task type 约束）
   - `api/routes/collections.py` — 端点
   - `services/task_service.py` — _process_regenerate_readme + 分发

## 关键文件

| 文件 | 变更内容 |
|------|----------|
| `backend/models/requests.py` | UrlConfig + IngestUrlsRequest 重构 |
| `backend/api/routes/ingest.py` | url_configs 序列化 |
| `backend/api/routes/collections.py` | regenerate-readme 端点 |
| `backend/services/task_service.py` | crawl 循环 + _categorize_incremental + _process_regenerate_readme |
| `backend/database/models/document.py` | categorized_at 字段 |
| `backend/repository/document.py` | mark_categorized + clear_categorized |
| `backend/services/llm_service.py` | merge_categories + optimize_categories |

## 验证

1. **多 prefix**: 发一次请求含 2 个 url_configs，确认只生成一次 README，两个前缀的文档都在集合中
2. **增量合并**: 先爬 prefix A → 确认分类 → 再爬 prefix B → 确认新分类与旧分类合并，未重复全量
3. **regenerate**: 点击 regenerate 按钮 → 确认不重新爬取，仅重新生成 categorize + readme
