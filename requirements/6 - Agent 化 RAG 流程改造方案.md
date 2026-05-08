# Agent 化 RAG 流程改造方案

## Context

### 为什么改

`ai-document-assistant` 当前的 chat 链路是一段 280 行的过程式函数 [backend/chat/service.py:58](backend/chat/service.py#L58) `ChatService.process`，固定走「router → retrieve → relevance judge → assemble → generate → 自评估循环」流水线，所有决策点 hardcode：

- 检索策略由 `RetrievalOrchestrator` 一次并行 chunk+doc+keyword，top_k 固定。
- 是否拉全文由 `ContextExpander` 在 token 预算内被动决定。
- 「不够好就再查一次」由 `SelfEvaluator` 离线评估，最多 3 轮。
- 整个过程**完全没有 tool_use / function_calling**（grep 验证零命中）。

这种结构有几个固有问题：

1. **决策权与执行权耦合在 Python 代码里**：模型只能"按既定顺序消费检索结果"，不能根据当前掌握的信息主动决定下一步去查哪。
2. **自评估是离线的**：evaluator 拿不到 generator 的完整心路，只能粗放判 confidence；agent 模式下"答得不好 → 自己再调 search"是天然行为。
3. **延展性差**：每加一种检索能力（如按 category 浏览、跨 collection 比较）都要修改 orchestrator 与 service，无法配置化。

### 学到了什么

参考 `/Users/zouguodong/Code/Personal/learn-claude-code/agents/s06_context_compact.py` 的 agent 模式（主循环 + tool_use 协议 + micro/auto compact），把 RAG 的能力收敛为一组「同形状的查询工具」，主循环不变，所有差异收敛到 `ToolRegistry`。这样：

- 模型自主决定查询路径，简单问题直接答（零工具调用），复杂问题多轮检索。
- 上下文超 80% 自动压缩，准确性兜底（最坏挨个读文档也能给答案）。
- 每个工具调用流式上报到前端，让用户看到「正在做什么」。

### 用户已敲定的关键决策

| 决策 | 选择 |
|---|---|
| LLM provider | **先做 Claude**（AsyncAnthropic tool_use），OpenAI 后端留 NotImplementedError stub |
| Router | **彻底取消**，所有 query 直接进 agent 主循环 |
| 历史持久化 | `ChatMessage.message_metadata.agent_trace` 存完整 messages |
| Compact 策略 | **保守**，仅在 token 估算 ≥ 上下文窗口 80% 时触发 auto_compact |
| 替换策略 | **完成后直接替换**，不做 feature flag 共存；M3 切换 + 删除旧 ChatService 在同一 PR 内完成 |

---

## 整体架构

### 新模块布局

```
backend/chat/agent/
├── __init__.py
├── runtime.py           # AgentRuntime 主循环
├── registry.py          # ToolRegistry + Tool 注册
├── cancellation.py      # CancellationToken
├── compaction.py        # micro_compact / auto_compact / token 估算
├── trace.py             # AgentTrace + JSONL 落盘
├── prompts.py           # 系统 prompt 模板
├── tools/
│   ├── base.py          # Tool ABC + ToolContext + ToolResult
│   ├── collections.py   # list_collections / get_collection_overview
│   ├── search.py        # search_chunks / search_documents
│   ├── documents.py     # get_document / get_document_summary
│   └── _formatting.py   # 工具输出统一 markdown 格式化
└── llm/
    ├── base.py          # ToolCallingBackend ABC
    ├── claude.py        # ClaudeToolBackend（实现 generate_with_tools）
    └── openai.py        # OpenAIToolBackend（NotImplementedError stub）
```

### 与现有 `ChatService` 的关系

**M1-M2 并行开发，M3 切换 + 删除旧实现一并落地**（不做 feature flag 共存）：

- M1-M2 阶段：`backend/chat/agent/` 模块独立开发，旧 `ChatService` 不动，前端无感。
- M3 阶段（同一 PR 内完成接入与清理）：
  - [backend/api/state.py:42-138](backend/api/state.py#L42-L138) 把 chat service 注入直接换成 `AgentChatService`。
  - 路由层 [backend/api/routes/chats.py:198](backend/api/routes/chats.py#L198) `send_message_stream` 复用 `service.process(...)` 接口（同签名 `AsyncIterator[SSEEvent]`），并删除按 `document_ids` 分流到 legacy `services/chat_service.py` 的 if/else 分支。
  - 跑通回归集后，**同 PR 内**删除以下文件（详见 M3 清理清单）：
    - [backend/chat/service.py](backend/chat/service.py)（新版 `ChatService`）
    - [backend/services/chat_service.py](backend/services/chat_service.py)（按 document_ids 走的 legacy service）
    - [backend/chat/router.py](backend/chat/router.py)（决策已不再使用）
    - [backend/chat/evaluation.py](backend/chat/evaluation.py)（自评估循环由 agent 主循环替代）
    - [backend/chat/retrieval/relevance_judge.py](backend/chat/retrieval/relevance_judge.py)（agent 模式不调用）
    - [backend/chat/context/assembler.py](backend/chat/context/assembler.py)（不再统一 assemble，由模型自主组装）
    - 仅供上述模块使用的 prompt 常量与 helper（顺手清理）
- **保留并复用**的组件（作为 tool 内部实现）：
  - [backend/chat/retrieval/document_index.py](backend/chat/retrieval/document_index.py)、[keyword_index.py](backend/chat/retrieval/keyword_index.py)
  - [backend/chat/context/expander.py](backend/chat/context/expander.py)（`get_document` 工具内部按需用）
  - [backend/chat/retrieval/orchestrator.py](backend/chat/retrieval/orchestrator.py) 中的 `fetch_collection_overviews`（如可单独抽出更好；否则保留 orchestrator 但只用这一个方法）
  - [backend/chat/generation/claude_backend.py](backend/chat/generation/claude_backend.py)、[openai_backend.py](backend/chat/generation/openai_backend.py)（`BaseLLMService` 抽象 + embeddings 客户端供 fast_llm/auto_compact 复用）
  - [backend/chat/retrieval/chunk_index.py](backend/chat/retrieval/chunk_index.py) **暂时保留但不接工具**（M1 工具集不实现 `search_chunks`，参见工具集说明）

### 关键抽象签名

```python
# tools/base.py
class Tool(ABC):
    name: str
    description: str
    input_schema: dict
    preserve_in_compact: bool = False

    @abstractmethod
    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult: ...

@dataclass
class ToolContext:
    chat_id: str
    collection_ids: list[str]
    cancellation: CancellationToken
    emit: Callable[[SSEEvent], Awaitable[None]]
    deps: AgentDeps  # 持有 chunk_index / repos / chroma_client / 等

@dataclass
class ToolResult:
    content: str               # 给模型的 markdown
    structured: dict | None    # 给前端的结构化数据 + sources 抽取
    is_error: bool = False
```

```python
# llm/base.py
class ToolCallingBackend(ABC):
    @abstractmethod
    async def generate_with_tools(
        self, *, system: str, messages: list[dict], tools: list[dict],
        max_tokens: int, temperature: float,
        cancellation: CancellationToken,
        on_text_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> AssistantTurn: ...

@dataclass
class AssistantTurn:
    raw_content: list[dict]   # provider-native blocks，原样塞回 messages
    stop_reason: str          # "tool_use" | "end_turn" | "max_tokens"
    tool_uses: list[ToolUseBlock]
    usage: Usage
```

---

## 工具集（M1 落地 6 个）

**设计哲学**：参考 Claude Code 的「Glob + Grep + Read」三件套，第一阶段**只用关键词与字面匹配**，不引入向量相似度。理由：
- 当前 chunk_size 偏大，向量相似度检索效果不明显；与其先实现一套用不好的语义检索，不如先把关键词流程跑顺。
- Claude Code 在大型代码库上主要靠 grep + read，效果已经足够；文档库结构与代码库类似，关键词路径同样有效。
- 向量检索（`search_chunks`）作为 v2 工具，等 chunk_size / embedding 配置调优后再加（参见开放问题）。

所有工具输出统一「YAML-like markdown」：首行结果摘要，后跟分块条目，每条带稳定 ID（`doc_42`）方便后续轮次引用。

### `list_collections` (preserve=True)
- **何时调用**：会话开始不知道用户意图时；或用户问"有哪些库"。
- **input**：无参数。
- **实现**：基于 `ToolContext.collection_ids`，调 `CollectionRepository.list_by_ids`。

### `get_collection_overview` (preserve=True)
- **何时调用**：用户问"这个库里有什么"或决定用哪个 collection 时。
- **input**：`{collection_id: string}`
- **实现**：复用 [backend/chat/retrieval/orchestrator.py](backend/chat/retrieval/orchestrator.py) `fetch_collection_overviews([id])` + 按 category 聚合 top N 文档。

### `search_documents` (preserve=False) — Glob 类
- **何时调用**：按主题/类别筛文档列表（"列出与 X 相关的所有文档"、"按类别浏览"）。
- **input**：`{keywords: string[], collection_ids?: string[], category?: string, limit?: int(default=15, max=50)}`
- **实现**：复用 [backend/chat/retrieval/keyword_index.py](backend/chat/retrieval/keyword_index.py) 已有逻辑；**M1 需在 [backend/repository/document.py](backend/repository/document.py) 新建 `search_by_keywords` 方法**（当前 `DocumentRepository` 仅有 `BaseRepository.get_by_id`，需新增 SELECT，匹配字段：`Document.name` / `summary` / `keywords` / `category`）。
- **输出条目**：`[doc:doc_42] title | category | summary(200字) | keywords=[...]`

### `grep_documents` (preserve=False) — Grep 类
- **何时调用**：定位"某个具体术语 / 配置项 / 函数名 / 短语"在哪几篇文档的什么位置出现。这是替代 `search_chunks` 的细粒度检索手段。
- **input**：`{pattern: string, collection_ids?: string[], category?: string, regex?: bool(default=false), case_sensitive?: bool(default=false), max_matches?: int(default=20, max=50), context_lines?: int(default=2, max=5)}`。**`collection_ids` 与 `category` 至少必传一个**（否则全库 ILIKE seq scan，性能不可接受），`run` 入口校验缺失则直接返回 `Error: must specify collection_ids or category to scope grep`。
- **实现**：在 `Document.content`（Markdown 全文）上做匹配。优先方案：
  1. 走 Postgres `pg_trgm` GIN 索引（**M1 前置 DB 任务**：在 `Document.content` 上建 `gin_trgm_ops` 索引，alembic revision 单独 PR 提前合入）；
  2. 索引未到位时走 `Document.content ILIKE`（已被 collection_ids/category 缩到候选集），Python 内对每篇 split lines 做正则/字面匹配，返回命中行号 + 上下文。
- **输出条目**：`[doc_42:L120] | doc="服务韧性指南" | "...> 断路器在 5xx 错误率 ..."`，每条命中带 `±context_lines` 行上下文。
- **错误处理**：模式无效（regex 编译失败）→ `Error: invalid regex: <reason>`；未传 collection_ids/category → 见上方 input 说明；命中过多被截断 → 末尾追加 `(truncated; 还有 N 条匹配未返回，可缩小 collection_ids 或加更多关键词)`；零命中 → 固定文案 `No matches. Try synonyms or broader keywords.`（让模型有明确的"换词"指引）。

### `get_document` (preserve=True)
- **何时调用**：通过 `search_documents` / `grep_documents` 已定位到关键文档、需要看详细内容。**单篇可能很大，所以分页**。
- **input**：`{document_id: string, page?: int(default=1), page_size_tokens?: int(default=2000, max=5000)}`。**用 token 而非 char 分页**——上下文预算按 token 计，char 分页与 micro_compact 阈值估算容易打架，中文/代码混排时尤甚。
- **实现**：`DocumentRepository.get_by_id` + 切片。**token 计数策略**（避免每次分页都调 Anthropic `count_tokens`）：
  1. 首次取文档时调用一次 `count_tokens`，记录 `token_per_char = tokens / len(content)`；
  2. 后续同文档的分页用 `estimated_tokens = len(chunk) * token_per_char` 估算，不再打 API；
  3. 缓存粒度为 `document_id`，存于 `AgentDeps` 的进程内缓存（LRU，max 128 条目）。若缓存 miss（重启后首次），fallback 回 `count_tokens` API。
- 返回 `total_pages` / `current_page` / 头部元信息。`grep_documents` 命中的行号可作为 `page` 计算的提示。
- **核心证据，micro_compact 永不替换其结果**。

### `get_document_summary` (preserve=True)
- **何时调用**：判断一篇是否值得 `get_document`（避免直接拉全文浪费 token）。
- **input**：`{document_id: string}`
- **实现**：**M1 需在 [backend/repository/document.py](backend/repository/document.py) 新建 `get_summary_only` 投影查询**（只 SELECT summary/keywords/category/total_tokens，避免拉 `content` 大列）。

**不加的工具**（在 v1 阶段）：
- `search_chunks`（向量相似度）—— **暂不实现**，等 chunk_size / embedding 调优后再启用。`backend/chat/retrieval/chunk_index.py` 文件保留，但不接入工具注册表。
- `cross_collection_search` —— `search_documents` / `grep_documents` 默认支持多 `collection_ids`，无需独立工具。
- `expand_chunk_neighbors` —— 先靠 `get_document` + `grep_documents` 命中行号兜底。

---

## 主循环骨架

```python
# runtime.py
async def run(self, *, chat_id, query, history, collection_ids, cancellation):
    messages = list(history) + [{"role": "user", "content": query}]
    yield SSEEvent("agent_start", {"max_iter": self.config.max_iter})

    for iteration in range(1, self.config.max_iter + 1):
        cancellation.raise_if_cancelled()

        # ---- compaction ----
        token_est = estimate_tokens(messages, self.backend)
        if token_est > 0.8 * self.config.context_window:
            yield SSEEvent("compact_triggered",
                           {"kind": "auto", "before_tokens": token_est})
            messages = await auto_compact(messages, self.fast_backend,
                                          original_query=query,
                                          transcript=transcript_path)
        else:
            micro_compact(messages, registry=self.registry,
                          keep_recent=self.config.keep_recent_tool_results)

        yield SSEEvent("iteration_start", {"iteration": iteration})

        # ---- LLM call (streaming) ----
        # 流式期间一律 emit agent_thinking（无 buffer-and-flush，零首字延迟）
        turn = await self.backend.generate_with_tools(
            system=self.system_prompt(collection_ids),
            messages=messages, tools=self.registry.schemas(),
            cancellation=cancellation,
            on_text_delta=lambda d: emit("agent_thinking", {"delta": d, "iteration": iteration}),
        )
        # 关键：assistant 整个 raw_content 原样 append（含 tool_use 块）
        messages.append({"role": "assistant", "content": turn.raw_content})

        if turn.stop_reason != "tool_use":
            # 本 turn 是最终回答：发提级事件，让前端把本 iteration 已流出的 agent_thinking
            # buffer 整体迁移到正文区（不再重复发 content delta）
            yield SSEEvent("final_text_promote", {"iteration": iteration})
            yield SSEEvent("done", {"iterations": iteration, "usage": turn.usage})
            return

        # ---- run tools ----
        results = []
        for tu in turn.tool_uses:
            yield SSEEvent("tool_call",
                           {"id": tu.id, "name": tu.name, "input": tu.input})
            t0 = time.monotonic()
            try:
                cancellation.raise_if_cancelled()
                tool = self.registry.handler(tu.name)
                out = await tool.run(ctx=tool_ctx, **tu.input)
                yield SSEEvent("tool_result", {
                    "id": tu.id, "name": tu.name,
                    "preview": out.content[:500],
                    "structured": out.structured,
                    "is_error": out.is_error,
                    "ms": int((time.monotonic() - t0) * 1000),
                })
                results.append({"type": "tool_result",
                                "tool_use_id": tu.id,
                                "content": out.content,
                                "is_error": out.is_error})
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("tool %s failed", tu.name)
                results.append({"type": "tool_result",
                                "tool_use_id": tu.id,
                                "content": f"Error: {type(e).__name__}: {e}",
                                "is_error": True})
        messages.append({"role": "user", "content": results})

    # 达到 max_iterations，强制再生成一次（不带 tools）
    yield SSEEvent("agent_halted",
                   {"reason": "max_iterations", "iterations": self.config.max_iter})
    final = await self.backend.generate_with_tools(
        system=self.system_prompt(collection_ids) + "\n\nMax iterations reached. "
               "Please synthesize a best-effort answer from the information collected.",
        messages=messages, tools=[],  # 强制不调工具
        cancellation=cancellation,
        on_text_delta=lambda d: emit("agent_thinking", {"delta": d, "iteration": -1}))
    yield SSEEvent("final_text_promote", {"iteration": -1})
    yield SSEEvent("done", {"iterations": self.config.max_iter,
                            "halted": True, "usage": final.usage})
```

### 上下文管理

**micro_compact（每轮无条件执行）**：
- 找出所有 `tool_result` 块，反查对应 `tool_use.name`。
- 若该工具 `preserve_in_compact=True` → 跳过。
- 否则若距末尾超过 `keep_recent=2` 轮 → 把 `content` 替换为 `[Compacted: tool '<name>' called with <input_brief>, returned <n_chars> chars]`，**保留 `tool_use_id` 与 `is_error=False`**（Anthropic 协议硬约束，且避免模型误判该轮失败）。

**单 turn 输入硬上限保护（≥ 95% 强制截断）**：
- micro_compact 之外，每轮 LLM 调用前再做一次"单请求体量"估算（messages + system + tools schema 序列化）。
- 若估算 ≥ 95% × `context_window`，**强制截断**最早的非 preserve `tool_result`（content 替为 `[Truncated: too large for single request]`），重新估算直到 ≤ 90%。这是防御 Anthropic 单 `messages.create` body 大小限制（200k token 上下文也并非单请求都能塞满）。
- 若截断后仍超限（preserve 类工具结果就 ≥ 95%），降级走 auto_compact 整段总结。

**auto_compact（token ≥ 80% 上下文窗口）**：
- 阈值估算：先 `client.messages.count_tokens` API，失败回退 `len(json.dumps(m)) // 4`，每 5 轮缓存。
- 算法：保留首条 user query + 最近 1 轮 assistant/user，中段送 `fast_llm` 总结成单条 user 消息，prompt：
  > 你是会话压缩器。请把以下 agent 工作日志压成结构化记忆，保留：(1) 用户原始问题 (2) 已确认事实+doc_id 引用 (3) 未解决子问题 (4) 引用过的 doc_id/chunk_id 列表 (5) 已尝试但失败的检索策略。Markdown 格式，1500 字内。
- transcript 全程落盘：`./var/agent_transcripts/{chat_id}/{message_id}-{iso_ts}.jsonl`。

### max_iterations
- 默认 **15**（与 learn-claude-code 一致），可通过 `agent.max_iterations` 配置。
- 超出后强制不带 tools 再 generate 一次，保证用户拿到回答。

---

## SSE 事件协议扩展

在 [backend/chat/models.py:86](backend/chat/models.py#L86) `SSEEventType` 上**追加**新值（不破坏旧枚举；注意：现有枚举里 `THINKING` 已被 useChat 用作"模型思考过程"，新协议改用 `agent_thinking` 避免语义冲突）：

| 事件 | payload | 说明 |
|---|---|---|
| `agent_start` | `{max_iter, model}` | turn 开始 |
| `iteration_start` | `{iteration}` | 每轮 LLM 调用前 |
| `agent_thinking` | `{delta, iteration}` | LLM text 增量；流式期间无差别 emit，前端先全部进步骤面板的累积 buffer |
| `tool_call` | `{id, name, input}` | 模型决定调工具 |
| `tool_progress` | `{id, message, percent?}` | 工具内部主动 emit（可选） |
| `tool_result` | `{id, name, preview, structured?, is_error, ms}` | 工具返回 |
| `compact_triggered` | `{kind, before_tokens, after_tokens?}` | 压缩 |
| `sources` | （沿用旧 schema） | 累积 sources，工具产出文档时增量更新 |
| `final_text_promote` | `{iteration}` | **关键事件**：通知前端"本 iteration 累积的 agent_thinking buffer 即正式答案，把它从步骤面板迁移到正文区域"。仅在 `stop_reason==end_turn` 时发出 |
| `agent_halted` | `{reason, iterations}` | 达到 max_iter |
| `done` | `{iterations, usage, timings}` | 正常结束 |

**没有 `content` 事件**：所有 LLM text 一律走 `agent_thinking`。流式期间用户能看到逐字输出（零首字延迟），turn 结束后若是最终答案，前端收 `final_text_promote` 后把累积 buffer 整体切到正文区域（视觉上等于"思考折叠 + 答案提级"）。turn 结束若是 `tool_use`，agent_thinking buffer 自然留在步骤面板里作为思考记录，无需额外事件。

---

## 取消机制

### 服务端 CancellationToken

```python
class CancellationToken:
    def __init__(self): self._cancelled = asyncio.Event()
    def cancel(self): self._cancelled.set()
    def cancelled(self) -> bool: return self._cancelled.is_set()
    def raise_if_cancelled(self):
        if self._cancelled.is_set(): raise asyncio.CancelledError()
```

### 三路触发

1. **客户端断开**：在 [backend/api/routes/chats.py:198](backend/api/routes/chats.py#L198) 起 `disconnect_watcher` 协程，**优先订阅 `request.receive` 监听 disconnect 事件**（事件驱动、低延迟）；不可用时降级到每 100ms 轮询 `request.is_disconnected()` → cancel。0.5s 轮询过粗（与 Verification 的"0.5s 内退出"承诺只在工具瞬时返回时同时成立）。
2. **显式 stop API**：新增 `POST /chats/{chat_id}/messages/stop?message_id=<mid>`，按 `(chat_id, message_id)` 复合键维护 `dict[tuple[str, str], CancellationToken]`；前端 stop 按钮带上当前 message_id 调它。**不可只用 chat_id**——同一 chat 多 tab / 同一 chat 上一轮未完时再发都会冲突。
3. **超时**（可选）：单 turn 超 5 分钟自动 cancel。

### 工具 / LLM 内部感知

- 所有工具 `run` 在每个 await 点前 `ctx.cancellation.raise_if_cancelled()`。
- `ClaudeToolBackend.generate_with_tools` 内部用 `asyncio.wait([stream_task, cancellation.wait()], return_when=FIRST_COMPLETED)` 双路等待。**取消优先时必须显式清理 stream**：
  ```python
  if cancellation.cancelled():
      stream_task.cancel()
      try:
          await asyncio.shield(stream_ctx.aclose())  # anthropic SDK 的 streaming context 显式关闭
      except Exception:
          logger.exception("stream close failed during cancellation")
      raise asyncio.CancelledError()
  ```
  否则会留下未关闭的 HTTP 连接 + 持续计费 token。

---

## 持久化与历史恢复

### `agent_trace` schema（写入 `ChatMessage.message_metadata`）

```json
{
  "version": 1,
  "engine": "agent",
  "model": "claude-sonnet-4-5",
  "iterations": 4,
  "stop_reason": "end_turn",
  "messages": [
    {"role":"user","content":"..."},
    {"role":"assistant","content":[
      {"type":"text","text":"我先看一下..."},
      {"type":"tool_use","id":"tu_01","name":"search_documents","input":{"keywords":["断路器"]}}
    ]},
    {"role":"user","content":[
      {"type":"tool_result","tool_use_id":"tu_01","content":"Found 8 docs..."}
    ]}
  ],
  "tool_call_summary":[{"id":"tu_01","name":"search_documents","ms":312,"ok":true}],
  "compactions":[{"iteration":7,"kind":"auto","before_tokens":162000,"after_tokens":40000}],
  "usage":{"input_tokens":...,"output_tokens":...,"cache_read":...},
  "timings":{"total_ms":...,"by_iteration":[...]}
}
```

**`messages` 字段的用途严格限定**：仅供 transcript 查看（M5 endpoint `GET /chats/{id}/messages/{mid}/trace`），**永不回填给下一轮 LLM**——历史恢复走 `tool_call_summary` + `ChatMessage.content`（最终人类可读文本），见下节。这样既保留完整审计 trail，又规避 `tool_use_id` 跨 turn 校验坑。

### 保存时机
- 会话结束（`done` / `error` / `agent_halted`）时整体写库。
- 中间事件全程写 transcript JSONL，崩溃也可追溯。

### 历史恢复（关键 trick）

跨 turn **不**还原中间 `tool_use`/`tool_result`——历史 assistant message 仅以 `ChatMessage.content`（最终 markdown 文本）形式作为纯文本注入下一 turn 的 messages 数组。理由：
- `tool_use_id` 跨 turn 容易踩 Anthropic API 校验坑（必须同 request 内配对）。
- 把历史压成纯文本，新 turn 重新检索行为更稳定，token 也省。
- `agent_trace.messages` 是审计快照，不是 replay 源——这是上述 schema 字段说明的硬约束。

实现位置：[backend/chat/agent_service.py](backend/chat/agent_service.py) 的 `_load_history` 方法，从 `ChatMessage` 表读取 `(role, content)`，跳过 `metadata.engine != 'agent'` 的记录（即被归档前残留的老消息，理论上 M3 migration 后不应该有）。

**不兼容老 chat 数据**：M3 上线时一次性归档（或清空）所有 legacy 写入的 `ChatMessage`，新系统只服务 agent 模式。详见 M3 节的 migration 步骤。`_load_history` 不做 legacy schema 兼容分支。

### Schema 迁移
`ChatMessage.message_metadata` 已是 JSON 列，**不需要 alembic**。

---

## 前端改造

### 新组件

```
frontend/src/components/chat/AgentTrace.tsx       # 折叠卡片容器
frontend/src/components/chat/AgentTraceStep.tsx   # 单步（thinking / tool / compact）
frontend/src/types/agent.ts                       # AgentStep / AgentMessageState 类型
```

形态参考 Claude Code 的 Thinking 块，每步带状态图标 + 耗时 + 可点开看 input/output preview：

```
┌─ Agent (4 steps · 6.2s) ──────── ▼
│ ① Thinking: 用户在问断路器配置...
│ ② search_chunks(query="断路器") → 8 chunks
│ ③ get_document(doc_42) → 12k chars
│ ④ Final answer ↓
└──────────────────────────────────
```

### `useChat.ts` 扩展

修改 [frontend/src/hooks/useChat.ts:54](frontend/src/hooks/useChat.ts#L54)，增加 reducer-like state：

```ts
type AgentStep =
  | {kind:"thinking", text:string, iteration:number}    // 内部 state，由 agent_thinking 事件累积
  | {kind:"tool", id:string, name:string, input:object,
     status:"running"|"done"|"error", preview?:string, ms?:number}
  | {kind:"compact", before:number, after:number}

type AgentMessageState = {
  steps: AgentStep[];
  finalText: string;       // 来自 final_text_promote：从最近一条 thinking step 整体迁过来的
  iterations: number;
  status: "running"|"done"|"error"|"cancelled";
}
```

[frontend/src/hooks/useChat.ts:108](frontend/src/hooks/useChat.ts#L108) `handleStreamEvent` 增加 case：`agent_start` / `iteration_start` / `agent_thinking`（追加到当前 iteration 的 thinking step）/ `tool_call` / `tool_result` / `compact_triggered` / `final_text_promote`（把最近一条 thinking step 的 text 拷到 finalText，并在步骤面板把它折叠隐藏）/ `agent_halted`。**M3 PR 必须同时改前端 case**——后端发了 `agent_thinking` / `final_text_promote` 而前端不识别会导致最终答案不显示，是阻塞级 bug。

**空 thinking edge case**：某 turn 模型输出为空（直接 `tool_use`，无任何 text delta）时，`agent_thinking` 不会收到任何 delta，前端该 iteration 的 thinking step text 为空字符串。**Reducer 处理**：`final_text_promote` 时若最近 thinking step 的 text.trim().length === 0`，不渲染该 thinking 条目，直接跳过；步骤面板上该 iteration 只展示 tool_call / tool_result 卡片。`agent_thinking` 为空的 iteration 依然推进 iterations 计数（模型确实思考了，只是没输出文字）。

### 挂载位置

[frontend/src/components/chat/ChatInterface.tsx:67](frontend/src/components/chat/ChatInterface.tsx#L67) 在 assistant message bubble 上方挂 `<AgentTrace state={msg.agentState}/>`。`SourceReferences` 仍然末尾展示，与步骤面板正交。

### 历史消息重放

加载历史时反序列化 `metadata.agent_trace.tool_call_summary` 为 `AgentStep[]` **静态展示终态**（不重放流）。完整 transcript 通过新 endpoint `GET /chats/{id}/messages/{mid}/trace` 按需懒加载（M5）。

---

## 配置新增

[backend/models/config.py:11](backend/models/config.py#L11) 增加：

```python
class AgentConfig(BaseModel):
    max_iterations: int = 15
    context_window: int = 200_000          # Claude Sonnet 4
    compact_threshold: float = 0.8
    keep_recent_tool_results: int = 2
    transcript_dir: str = "./var/agent_transcripts"
    model: Literal["fast","standard","deep"] = "standard"
```

挂在 `Settings.agent`。**不需要 ChatEngineConfig**——直接替换路径下没有 engine 切换。

`agent.model="standard"` → 复用 [backend/api/state.py](backend/api/state.py) 的 `standard_llm`（Claude Sonnet）封装为 `ClaudeToolBackend`。`fast_llm` 用于 auto_compact 总结。

---

## 实施分期

```
M1 (Tool 框架 + Claude backend + 6 工具) ──┐
                                           ├─ M2 (Runtime + compaction) ── M3 (AgentChatService 接入 + SSE + 删除旧实现)
                                           │                                     │
                                           │                                     ├── M4 (前端 AgentTrace) ── M5 (持久化 + 恢复)
                                           │                                     │
                                           └────────────────────────────────────┘
```

### M1：Tool 框架 + Claude backend + 6 工具

**目标**：tool_use 协议跑通，单元测试覆盖每个工具。
**新建**：
- [backend/chat/agent/__init__.py](backend/chat/agent/__init__.py)
- [backend/chat/agent/registry.py](backend/chat/agent/registry.py)
- [backend/chat/agent/cancellation.py](backend/chat/agent/cancellation.py)
- [backend/chat/agent/tools/base.py](backend/chat/agent/tools/base.py)
- [backend/chat/agent/tools/_formatting.py](backend/chat/agent/tools/_formatting.py)
- [backend/chat/agent/tools/collections.py](backend/chat/agent/tools/collections.py)
- [backend/chat/agent/tools/search.py](backend/chat/agent/tools/search.py)
- [backend/chat/agent/tools/documents.py](backend/chat/agent/tools/documents.py)
- [backend/chat/agent/llm/base.py](backend/chat/agent/llm/base.py)
- [backend/chat/agent/llm/claude.py](backend/chat/agent/llm/claude.py)
- [backend/chat/agent/llm/openai.py](backend/chat/agent/llm/openai.py) (NotImplementedError stub)
- [backend/tests/agent/test_tools_*.py](backend/tests/agent/test_tools_collections.py)
- [backend/tests/agent/test_claude_backend.py](backend/tests/agent/test_claude_backend.py)（mock anthropic）

**复用**：
- [backend/chat/retrieval/chunk_index.py:19](backend/chat/retrieval/chunk_index.py#L19) `ChunkIndex.search`（M1 不接工具，但保留供 v2）
- [backend/chat/retrieval/document_index.py](backend/chat/retrieval/document_index.py)
- [backend/chat/retrieval/keyword_index.py](backend/chat/retrieval/keyword_index.py)
- [backend/chat/retrieval/orchestrator.py:fetch_collection_overviews](backend/chat/retrieval/orchestrator.py)
- [backend/chat/context/expander.py](backend/chat/context/expander.py)
- [backend/repository/document.py](backend/repository/document.py)（注意：项目目录是 `backend/repository/` 单数，无 `database/` 前缀）
- [backend/repository/collection.py](backend/repository/collection.py)

**修改**（M1 内必做的最小化 schema/repo 扩展）：
- [backend/repository/document.py](backend/repository/document.py)：新增两个方法
  - `search_by_keywords(keywords, collection_ids, category, limit)` —— 给 `search_documents` 工具用；当前仅有 `BaseRepository.get_by_id`，需要新写 SELECT。
  - `get_summary_only(document_id)` —— 给 `get_document_summary` 工具用；只 SELECT `summary/keywords/category/total_tokens`，避免拉 `content` 大列。

**M1 前置 DB 任务**（独立小 PR，建议先于 M1 主 PR 合入）：
- alembic revision：在 `Document.content` 上建 `pg_trgm` GIN 索引（`CREATE INDEX ... USING gin (content gin_trgm_ops)`），供 `grep_documents` 工具加速 ILIKE/正则。未启用 pg_trgm 扩展时同 PR 加 `CREATE EXTENSION IF NOT EXISTS pg_trgm`。

**单元测试要点**：每个 tool 的成功/边界/错误三场景；ClaudeBackend 一次完整 tool_use round-trip。

**依赖**：无(4 个 subagent 可并行：collection 工具组 / search 工具组 / document 工具组 / Claude backend）。

### M2：Runtime + Compaction + Transcript

**目标**：主循环 + micro/auto_compact + 落盘，纯后端可单测。
**新建**：
- [backend/chat/agent/runtime.py](backend/chat/agent/runtime.py)
- [backend/chat/agent/compaction.py](backend/chat/agent/compaction.py)
- [backend/chat/agent/trace.py](backend/chat/agent/trace.py)
- [backend/chat/agent/prompts.py](backend/chat/agent/prompts.py)
- [backend/tests/agent/test_runtime.py](backend/tests/agent/test_runtime.py)（mock backend，构造多轮 tool_use → end_turn）
- [backend/tests/agent/test_compaction.py](backend/tests/agent/test_compaction.py)

**修改**：
- [backend/models/config.py](backend/models/config.py)（追加 AgentConfig）

**依赖**：M1 完成。

### M3：AgentChatService 接入 + SSE 事件 + 删除旧实现

**目标**：用 AgentChatService 替换旧链路端到端跑通；回归集通过后**同 PR 内**删除 legacy 代码并归档老消息。建议 PR 内分三个 commit：
1. `feat: 接入 AgentChatService` —— 切换路由 / 注入，但保留旧文件（便于回滚 diff 审阅）
2. `chore: 归档 legacy chat_messages` —— migration 一次性把老消息搬到归档表（或直接清空，视产品决策）
3. `chore: 删除 legacy ChatService 与相关组件` —— 清理无用文件

**新建**：
- [backend/chat/agent_service.py](backend/chat/agent_service.py)（与旧 `ChatService.process` 同签名 `AsyncIterator[SSEEvent]`）
  - **`message_id` 预生成**：`process()` 入口先用 `uuid4()` 预分配 `message_id`，写库占位（status=`pending`，role=`assistant`），再启动 SSE generator 与 CancellationToken 注册。这样 stop API 在 generator 启动前即可拿到确定的 `(chat_id, message_id)` 复合键，避免竞态。turn 结束后 UPDATE 该记录为 `done` 并填充 content/sources/metadata。
  - **wrapper 层职责边界**（`process()` 不是直接 yield `AgentRuntime.run()`，而是包裹三层职责）：
    ```python
    async def process(self, chat_id, query) -> AsyncIterator[SSEEvent]:
        message_id = uuid4()
        self.chat_repo.add_message(chat_id, role="assistant", status="pending")  # placeholder
        token = CancellationToken()
        self._cancel_registry[(chat_id, message_id)] = token
        try:
            # disconnect watcher 也在 wrapper 内起，与 runtime generator 并行 gather
            async for event in self.runtime.run(chat_id=chat_id, query=query, cancellation=token):
                yield event
        finally:
            self.chat_repo.update_message(message_id, status="done", content=..., metadata=...)
            del self._cancel_registry[(chat_id, message_id)]
    ```
    说明：transcript JSONL 落盘由 `AgentRuntime.run()` 内部驱动（`trace.py` 负责），`process()` 只管目录创建和异常时 flush；metadata 持久化（`agent_trace`）在 `finally` 块内等 generator 耗尽后统一 UPDATE。
- [backend/api/routes/chats_stop.py](backend/api/routes/chats_stop.py)（stop endpoint）
- 一次性 migration 脚本（位置：alembic revision under `backend/database/migrations/` 或类似目录；如缺 migration 框架则独立 `scripts/archive_legacy_chats.py`）：
  - 方案 A（推荐，可逆）：把现有 `chat_messages` / `chats` 全表移到 `chat_messages_legacy` / `chats_legacy` 归档表，业务表清空。
  - 方案 B（激进，简单）：`TRUNCATE chat_messages, chats CASCADE`。**需产品确认是否真的可清**。
  - 默认采用方案 A；上线 release notes 中说明"历史对话已归档"。
  - **`alembic downgrade` 必须可执行**：包含从 `_legacy` 表 `INSERT INTO ... SELECT` 反向迁移的 SQL。`git revert M3` 不会自动跑反向 migration，需运维 `alembic downgrade -1` 配合；migration 描述里写明这一点。方案 B 不可逆——选 B 即放弃 SQL 级回滚。

**修改**：
- [backend/chat/models.py:86](backend/chat/models.py#L86)（追加 SSEEventType 新值；同时**删除**旧 `THINKING` 枚举值）
- [backend/api/state.py:42-138](backend/api/state.py#L42-L138)（chat service 注入直接替换为 `AgentChatService`，移除按 document_ids 选 service 的逻辑；**`AppState.new_chat_service` 字段改名为 `chat_service`**，避免新旧字段并存歧义）
- [backend/api/routes/chats.py:198](backend/api/routes/chats.py#L198)（cancellation token + disconnect watcher；删除按 document_ids 分流的 if/else）

**CancellationToken registry 线程安全**：`dict[tuple[str, str], CancellationToken]` 在 FastAPI 单线程 async 事件循环下无需显式 `asyncio.Lock`（dict 读写原子），但注册/注销与 `chats_stop.py` 的 cancel 调用是协程间并发——需确保 `del self._cancel_registry[key]` 和 cancel 操作顺序安全（cancel 先于 del 或捕获 KeyError）。

**删除（回归集通过后执行）**：
- [backend/chat/service.py](backend/chat/service.py)
- [backend/services/chat_service.py](backend/services/chat_service.py)（按 document_ids 走的 legacy service）
- [backend/chat/router.py](backend/chat/router.py)
- [backend/chat/evaluation.py](backend/chat/evaluation.py)
- [backend/chat/retrieval/relevance_judge.py](backend/chat/retrieval/relevance_judge.py)
- [backend/chat/context/assembler.py](backend/chat/context/assembler.py)
- 仅供上述模块使用的 prompt 常量、helper、import；测试文件 `backend/tests/chat/test_*` 中针对 legacy 的用例同步删除（保留对 `chunk_index` / `keyword_index` / `expander` 的现有测试，因为这些组件保留）
- `backend/chat/models.py:86` 的 `SSEEventType.THINKING` 枚举值——新协议完全不发 `thinking`，保留会造成前后端事件类型混淆，必须删除。
- 评估是否删除 M1 前置 PR 建的 `pg_trgm` GIN 索引（`Document.content`）：若回滚到 legacy，该索引对旧链路无用且增加写入开销。agent 模式稳定后可在独立清理 PR 中 drop。

**注意保留**：
- `state.py` 中 `fast_llm` 实例（`auto_compact` 总结仍要用）；`router_llm` / `relevance_judge_llm` 如仅供 legacy，可一并删除。
- `chat/retrieval/chunk_index.py`（暂不接工具，但保留供未来 v2 `search_chunks` 用）

**集成测试**：mock LLM 跑完整问答；取消测试；多轮对话恢复（仅 agent 写入的消息，不再覆盖 legacy 兼容场景）。

**回归集**（合并门禁，详见 Verification 节）：100 条预先准备的 query 分层抽样跑过；任一项不达标则不合并 M3，推回迭代直至通过。

**依赖**：M2 完成。

### M4：前端 AgentTrace + 事件处理

**目标**：UI 步骤面板。
**新建**：
- [frontend/src/components/chat/AgentTrace.tsx](frontend/src/components/chat/AgentTrace.tsx)
- [frontend/src/components/chat/AgentTraceStep.tsx](frontend/src/components/chat/AgentTraceStep.tsx)
- [frontend/src/types/agent.ts](frontend/src/types/agent.ts)

**修改**：
- [frontend/src/hooks/useChat.ts:54](frontend/src/hooks/useChat.ts#L54) 与 `:108`
- [frontend/src/components/chat/ChatInterface.tsx:67](frontend/src/components/chat/ChatInterface.tsx#L67)

**测试要点**：
- `AgentTrace` + `AgentTraceStep` snapshot 测试（各状态：running/done/error/cancelled）
- `useChat.ts` reducer 状态转换测试：`agent_thinking` 追加、`final_text_promote` 提级、空 thinking 跳过、多 iteration 累积
- `ChatInterface` 集成测试：加载历史消息后 `AgentTrace` 静态展示终态（不重放流）

**依赖**：M3 提供事件协议（可与 M3 并行开发，最后联调）。

### M5：持久化 + 恢复 + transcript 查看

**目标**：刷新页面看到 trace；提供 transcript API。
**新建**：
- [backend/api/routes/chats_trace.py](backend/api/routes/chats_trace.py)（`GET /chats/{id}/messages/{mid}/trace`）

**修改**：
- [backend/chat/agent_service.py](backend/chat/agent_service.py)（写 metadata.agent_trace）
- [backend/repository/chat.py](backend/repository/chat.py)（trace 读写；注意路径是 `backend/repository/`）
- [frontend/src/hooks/useChat.ts](frontend/src/hooks/useChat.ts)（加载历史时反序列化 trace）

**依赖**：M3、M4。

---

## 风险与回滚

| 风险 | 缓解 |
|---|---|
| Latency 上升（多轮 tool_use） | system prompt 引导"简单问题直接回答不调工具"；步骤面板降低等待感；max_iter 兜底 |
| Token 成本（messages 累积） | micro_compact + Anthropic prompt caching（system + tools schema 设 `cache_control`）；每条 message usage 写库 |
| 模型工具选择能力 | tool description 写真实例子（"何时该用 X 而不是 Y"）；M3 PR 强制跑 50 条 query 回归集，未通过不合并 |
| 关键词检索召回率不足 | 工具 description 引导模型"先 search_documents 拿候选 → grep_documents 精定位 → get_document 看全文"的三步策略；命中为零时返回明确提示让模型换关键词 |
| `tool_use_id` 跨 turn 错配 | 历史只保留 final text 注入下一 turn，不带中间 tool 块 |
| 取消时数据一致性 | 所有工具均只读，无副作用 |
| Migration 误删用户数据 | M3 默认采用归档方案（搬到 `_legacy` 表），可恢复；release notes 提前公告 |

### 上线门禁（M3 PR 必经）

合并 M3 PR 之前必须通过以下三道关，**任一不达标则不合并，推回迭代**：
- 单元测试：6 个工具 + ClaudeBackend + AgentRuntime + 两层 compact 全绿
- 集成测试：mock LLM 端到端、取消、多轮历史恢复全绿
- 回归集：100 条预备 query 分层抽样跑通，准确性人工评分 ≥ legacy 平均；P95 latency ≤ legacy 的 2x；token 成本均值 ≤ legacy 的 3x（详见 Verification 节）

### 出问题怎么回退

没有 feature flag 兜底，**回退靠 git revert + 数据库归档表**：
- M1-M2 是独立模块、未接入主链路，本身无回退需求；M4-M5 也是叠加式改动，单独 revert 即可。
- M3 PR 单独 revert 即可恢复到包含 legacy 的状态。M3 PR 内"接入"/"归档"/"删除" 拆三个 commit（见 M3 节描述），便于细粒度回退。
- 数据回退：legacy 老消息已搬到 `chat_messages_legacy` / `chats_legacy`，需要时可写 SQL 复原；但通常不需要——agent 上线后产生的新消息全在 `chat_messages` 主表。
- 上线后若发现回归集未覆盖到的问题：
  1. **小问题**：在 main 上 hot-fix（agent 模式有完整 transcript JSONL 落盘，调试材料充足）。
  2. **大问题**：`git revert <M3 commit(s)>` 一键回到 legacy；如确需恢复老对话，再从归档表 INSERT 回主表。

---

## Verification

### 单元测试
```bash
cd backend
PYTHONPATH=. uv run pytest tests/agent/ -v
```
覆盖：
- 6 个工具各自的成功/边界/错误场景
- ClaudeBackend tool_use round-trip（mock anthropic SDK）
- AgentRuntime 主循环：单轮 end_turn / 多轮 tool_use / max_iter 触发
- micro_compact：preserve 工具不替换、老结果替换为占位
- auto_compact：阈值触发、总结 prompt 输出格式

### 集成测试（mock LLM）
- 端到端跑一个 query：`agent_service.process(...)` → 完整 SSE 事件序列
- 取消测试：触发后 0.5s 内 generator 退出
- 历史恢复：第二轮对话能正确加载第一轮的 final text

### 手工 e2e
1. 启动后端：`docker compose up postgres chroma -d && cd backend && uv run python api_server.py`
2. 启动前端：`cd frontend && npm run dev`
3. 问一个简单问题（"你好"）→ 期望 0 工具调用直接回答（agent_thinking 流出 → final_text_promote → done）
4. 问一个具体问题（"X 文档里 Y 怎么配置"）→ 期望步骤面板看到 search_documents → grep_documents → get_document → final answer
5. 长会话灌 100 轮工具调用 → 期望触发 auto_compact 事件，前端展示压缩步骤
6. 中途点 stop → 期望步骤面板状态变 cancelled，后端日志显示 cancellation 传播完成（包括 stream_task 已关闭）

### 回归集（M3 PR 合并门禁）
在 M3 PR 分支跑 **100 条预先准备的 query**，按"category 覆盖矩阵"分层抽样（每类不少于 15 条），覆盖：
- 简单问答 / 闲聊 / 元问题（期望 0 工具调用）
- 单文档查找（期望 search_documents → get_document）
- 跨文档比较（期望多次 search/grep + 多次 get_document）
- 找具体配置项 / 术语（期望 grep_documents 命中）
- 长会话连续追问（验证 micro_compact / auto_compact 不破坏答案质量）
- ……（M3 PR 准备阶段由产品 + 开发联合定义）

对比 main 分支（legacy）与 PR 分支（agent）两套答案的：
- 准确性评估：主路径用 **LLM-as-judge**（如 GPT-4 / Claude 以评分 prompt 对两套答案打分 1-5），减少人工负担；首次建立基线时人工抽样复核（≥20 条），后续用自动化 diff 监控回归。人工复核与 LLM 评分差异大时以人工为准。
- P50 / P95 latency
- 平均 token 成本
- 工具调用次数分布（额外观察 `grep_documents` / `search_documents` / `get_document` 的调用比例，便于后续 prompt 调优）

通过标准（任一不达标则推回 M3 迭代）：
- 准确性 ≥ legacy 平均
- P95 latency ≤ legacy 的 2x
- token 成本均值 ≤ legacy 的 3x

通过后才允许合并 M3 PR（接入 + 归档 + 删除三个 commit 一起进 main）。

---

## 开放问题（实施时再决定）

1. `system_prompt` 的具体文本：要写多少 few-shot 例子引导工具选择？建议 M3 时基于回归集迭代。重点示范"search_documents → grep_documents → get_document"三步法。**必须加入约束**："若连续 2 次 `grep_documents` 零命中，停止换词重试，改用 `search_documents` 扩大候选集，或基于已有信息直接回答"——避免模型在 max_iter 内死循环空转。
2. `tool_progress` 事件是否在 M1 实现：可推到 M3 之后，按需求加。
3. Anthropic prompt caching 的 cache_control 粒度：M3 性能测后决定。
4. transcript 文件保留期：先不限制，按需加 cron 清理 90 天前文件。
5. **`grep_documents` 实现细节**：是否依赖 Postgres `pg_trgm` / `tsvector` 索引？还是先用 `ILIKE` + Python 端切片兜底？M1 起步阶段以"能跑"为先，性能问题等回归集出现明显瓶颈再优化。
6. **legacy 数据归档 vs 清空**：M3 migration 默认走"归档到 _legacy 表"方案 A，是否改为方案 B（直接 TRUNCATE）需产品最终决策；release notes 必须提前公告"历史对话不再可见"。
7. **v2 - 重启 `search_chunks`**：等 chunk_size / embedding 模型调优后（见后端独立任务），将向量相似度作为 `grep_documents` 的语义补充加回工具集。届时模型可灵活选用关键词 vs 语义两种检索路径。
8. **docker volume 挂载**：`transcript_dir: "./var/agent_transcripts"` 需在 `docker-compose.yml` 中挂载为 named volume 或 host bind mount，否则容器重启 transcript 丢失、M5 trace API 404。M3 上线前检查 `docker-compose.yml` 和 `docker-compose.prod.yml`。
9. **Anthropic API rate limit**：高频工具调用场景下（长会话多轮 `grep_documents` + `get_document`），`generate_with_tools` 与 `count_tokens`（首次分页）是否触发 rate limit？M3 回归集加"高频工具调用"观察项（连续 10 轮以上 tool_use 的 latency 稳定性）。
