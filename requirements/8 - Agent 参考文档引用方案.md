# Agent 参考文档引用方案

## 背景

当前 Agent 模式（`backend/chat/agent_service.py`）下,持久化到 `ChatMessage.sources` 的列表始终为空,前端 `SourceReferences` 组件因此从不渲染。原因:

1. `runtime.py` 工具循环没有发出 `SOURCES` 事件;
2. 各 `Tool.run()` 返回的 `ToolResult.structured` 字段都是 `None`,缺乏可被持久化的结构化引用;
3. `agent_service.py` 中 `sources` 仅在 `event.type == SSEEventType.SOURCES` 时累积,实际无来源。

结果:用户无法看到 Agent 回答所依据的文档,可信度不足。

---

## 目标

让 Agent 在最终回答下方展示「参考来源」列表,语义为**LLM 自己声明引用的文档**,以提升回答可信度。

### 关键决策

| 决策 | 选择 |
|------|------|
| 引用语义 | 由 LLM 自己声明引用(非检索命中、也非读过即引) |
| 前端呈现 | 仅在消息底部展示参考列表(复用 `SourceReferences` 组件,不做正文内联脚注) |
| LLM 不声明时的处理 | 严格策略:不声明 → 不展示参考区(无兜底) |
| `cite_sources` 校验 | 仅允许声明本轮 Agent run 中已访问过的文档 doc_id |

---

## 方案

### 一、新增 `cite_sources` 工具

**文件**:`backend/chat/agent/tools/citations.py`(新建)

**工具签名**:

```python
class CiteSourcesTool(Tool):
    name = "cite_sources"
    description = (
        "在你输出最终回答前必须调用此工具,声明本次回答实际引用了哪些文档。"
        "传入 document_ids 列表(可为空数组,表示未引用任何文档)。"
        "只允许传入你在本轮中已经通过 search_documents / grep_documents / "
        "get_document / get_document_summary 接触过的 document_id。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要声明引用的文档 ID 列表",
            },
        },
        "required": ["document_ids"],
    }
    preserve_in_compact = True
```

**执行逻辑**:

1. 从 `ctx.visited_doc_ids` 取出本轮 Agent run 已访问的 doc_id 集合(由 Runtime 维护并注入 ToolContext);
2. 对 `kwargs["document_ids"]` 中每个 id:
   - 若 id 不在 `visited_doc_ids` 中 → 标记为 `rejected`,不写入 sources,但在 content 中告知 LLM;
   - 若在 → 调用 `ctx.deps.document_repo.get_summary_only(id)` 取出 `name` / `summary` / `category` 等元数据,组装为 SourceReference dict;
3. 返回:
   - `ToolResult.content`:文本说明(`Recorded N citations, rejected M`),反馈给 LLM;
   - `ToolResult.structured = {"sources": [...]}`,供 Runtime 收集。

**SourceReference 字段**(对齐 `frontend/src/services/apiClient.ts:123` 的 `SourceReference`):

```python
{
    "document_id": doc.id,
    "document_name": doc.name,
    "document_uri": doc.uri or "",
    "chunk_index": 0,                # cite_sources 是文档级,固定 0
    "content_preview": (doc.summary or "")[:300],
    "relevance_score": 1.0,          # LLM 显式声明,固定 1.0
}
```

注册到默认 registry:`backend/chat/agent/__init__.py` 的 `build_default_registry()`。

---

### 二、Runtime 维护 `visited_doc_ids`

**文件**:`backend/chat/agent/runtime.py`、`backend/chat/agent/tools/base.py`

#### 改动 1:`ToolContext` 增加 `visited_doc_ids` 字段

```python
@dataclass
class ToolContext:
    chat_id: str
    collection_ids: list[str]
    cancellation: CancellationToken
    emit: Callable[[SSEEvent], Awaitable[None]]
    deps: "AgentDeps"
    visited_doc_ids: set[str]   # 新增:本轮 Agent run 已访问的文档 ID 集合
```

#### 改动 2:Runtime 维护并更新该集合

在 `AgentRuntime.run()` 中:

1. 顶部初始化 `visited_doc_ids: set[str] = set()`;
2. `_build_tool_context()` 增加参数,把同一个 set 传给每次工具调用(共享引用);
3. 在 `TOOL_RESULT` 处理后(每个工具执行完),根据工具名和返回 ID 更新 `visited_doc_ids`。

具体来源:

| 工具 | 提取规则 |
|------|---------|
| `search_documents` | 解析 `result.content` 里的 `[id=xxx]`,加入 set |
| `grep_documents` | 解析 `result.content` 里的 `[id=xxx, line=N]`,加入 set |
| `get_document` | `tu.input["document_id"]`(剥离 `doc_` 前缀)加入 set |
| `get_document_summary` | `tu.input["document_id"]`(剥离 `doc_` 前缀)加入 set |
| `get_collection_overview` | sample documents 也算,解析 content 中的 `[id=xxx]`(可选,更宽松) |
| `cite_sources` 自身 | 不加入 |

为避免 content 解析脆弱,优先方案:在 `search_documents` / `grep_documents` 工具内部通过 `ToolResult.structured = {"doc_ids": [...]}` 直接上报 doc_id 列表。Runtime 优先读 `structured.doc_ids`,fallback 到 content 正则提取。

**实现建议**:

- 修改 `search.py` 中 `SearchDocumentsTool.run()` 和 `GrepDocumentsTool.run()`,在 ToolResult 中加 `structured={"doc_ids": [doc.id for doc in docs]}`;
- Runtime 在 `TOOL_RESULT` 后:`if structured and "doc_ids" in structured: visited_doc_ids.update(structured["doc_ids"])`;
- `get_document` / `get_document_summary` 直接从 `tu.input["document_id"]` 取(已知)。

#### 改动 3:Runtime 收集 `cite_sources` 返回的 sources

在 `TOOL_RESULT` 处理后增加:

```python
if tu.name == "cite_sources" and out.structured and "sources" in out.structured:
    yield SSEEvent(
        type=SSEEventType.SOURCES,
        data={"documents": out.structured["sources"]},
    )
```

`SOURCES` 事件已在 `chat/models.py:91` 定义,前端 `useChat.ts:133` 已处理。

---

### 三、AgentChatService 收集 sources

**文件**:`backend/chat/agent_service.py`

现状:`agent_service.py:207-210` 已有 `SOURCES` 事件处理逻辑。无需新增收集逻辑。

需要确认:

1. 持久化路径(`agent_service.py:221-226`)已经把 `sources` 序列化为 JSON 并写入 `ChatMessage.sources`,无需改动;
2. `_reconstruct_messages()` 不需要改;
3. 是否需要向 `ui_state` 暴露 sources 供 AgentTrace 展示?**不需要**,`SourceReferences` 组件直接读 `msg.sources`,与 `agentState` 解耦。

---

### 四、Prompt 改动

**文件**:`backend/chat/agent/prompts.py`

`RAG_SYSTEM_PROMPT` 在工具列表中增加第 7 项:

```
7. **cite_sources** - **必须**在输出最终答案前调用此工具,声明本次回答引用了哪些文档(doc_id 列表)。
   - 即使你认为没有引用任何文档(例如纯闲聊),也必须传入空数组 [] 调用一次。
   - 只能声明你在本轮中已经实际接触过的 doc_id(通过 search/grep/get_document 等)。
   - 不调用此工具就直接回答,前端将无法显示参考来源。
```

并在「检索策略」段落末尾追加:

```
- **完成检索 → 调用 cite_sources(document_ids=[...]) 声明引用 → 输出最终答案。**
```

---

### 五、前端改动

**无需改动**。

- `frontend/src/hooks/useChat.ts:133` 已经处理 `sources` SSE 事件;
- `frontend/src/components/chat/SourceReferences.tsx` 已经能渲染 `msg.sources`;
- `frontend/src/components/chat/ChatInterface.tsx:229` 已经在消息气泡内渲染 `<SourceReferences sources={msg.sources || []} />`;
- 持久化加载路径 `mapAPIMessageToUIMessage()` 已经把 `msg.sources` 透传(`useChat.ts:31`)。

唯一可能需要确认的地方:`useChat.ts` 在 streaming 过程中收到 `sources` 事件后,会写入 `streamingSourcesRef.current`,DONE 时再合并到消息中(`useChat.ts:171,189`)。逻辑已经走通,无需改动。

---

### 六、SSEEventType 检查

`SOURCES = "sources"` 已经存在(`chat/models.py:91`),无需新增类型。

---

## 改动文件清单

### 后端

| 文件 | 改动 |
|------|------|
| `backend/chat/agent/tools/citations.py` | 新建 `CiteSourcesTool` |
| `backend/chat/agent/tools/base.py` | `ToolContext` 增加 `visited_doc_ids: set[str]` 字段 |
| `backend/chat/agent/tools/search.py` | `SearchDocumentsTool` / `GrepDocumentsTool` 在返回时填充 `structured={"doc_ids": [...]}` |
| `backend/chat/agent/runtime.py` | 维护 `visited_doc_ids`,构造 `ToolContext` 时传入;`cite_sources` 工具结果触发 `SOURCES` 事件 |
| `backend/chat/agent/__init__.py` | `build_default_registry()` 注册 `CiteSourcesTool` |
| `backend/chat/agent/prompts.py` | `RAG_SYSTEM_PROMPT` 增加 cite_sources 工具说明和调用要求 |

### 前端

无改动。

### 测试

| 文件 | 内容 |
|------|------|
| `backend/tests/chat/agent/tools/test_citations.py` | `CiteSourcesTool` 单元测试:空列表 / 合法 ID / 非法(未访问)ID / 越界 ID 混合 |
| `backend/tests/chat/agent/test_runtime_visited.py` | Runtime 集成测试:模拟 search → cite_sources 流程,验证 `visited_doc_ids` 累积、`SOURCES` 事件触发、`agent_trace.ui_state` 不变 |

---

## 风险与回退

1. **LLM 不调 cite_sources**:严格策略下消息 sources 为空,前端不显示参考区。可后续观察实际表现,若漏调率高,再考虑 fallback(运行时强制补调)。
2. **现有 prompt 已经要求"尽可能引用 doc_id"**:与新工具不冲突,但要在 prompt 中突出 cite_sources 的"必须调用"性质。
3. **历史消息**:旧消息没有 sources,加载时仍是 `[]`,行为一致。
4. **回退**:删除工具注册和 prompt 段落即可恢复;visited_doc_ids 字段保留无副作用。

---

## 数据兼容性

- 旧 ChatMessage 的 `sources = "[]"`,加载后 `msg.sources = []`,`SourceReferences` 不渲染,与当前行为一致;
- 新消息持久化 `sources` 包含 LLM 显式声明的引用,前端正常展示。
