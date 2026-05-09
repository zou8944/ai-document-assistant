# Agent 步骤持久化与计时改造方案

## 背景

当前 Agent 模式下：

1. **Agent Steps 刷新丢失**：聊天卡片上方的 AgentTrace 面板（显示 thinking/tool/compact 步骤）仅在流式传输时存在于前端内存。刷新页面后从 API 加载历史消息时，`agentState` 字段为 `undefined`，AgentTrace 不渲染。
2. **遗留统计未清理**：聊天卡片下方的 `TimingDisplay` 仍显示旧版四阶段统计（意图分析、文档检索、整理上下文、生成回答），Agent 模式已不再使用这些阶段。
3. **计时数据缺失**：Agent 模式在 `runtime.py` 中收集了每轮迭代的 `llm_ms` 和 `tools_ms`，但未暴露给前端，前端无法展示有意义的耗时信息。
4. **Transcript File 存疑**：用户询问持久化后是否能取代 transcript file。

---

## 目标

1. 刷新页面后历史消息的 AgentTrace 正常显示。
2. 移除遗留的四阶段 `TimingDisplay` 统计。
3. 设计新的 Agent 模式计时指标和前端展现方式。
4. 明确 transcript file 的定位和去留。

---

## 方案

### 一、Agent Steps 持久化

#### 问题根因

- 后端 `AgentChatService.process()` 将 `agent_trace` 存入 `ChatMessage.message_metadata`，但 `agent_trace` 只包含 `messages`、`tool_call_summary`、`compactions`、`usage`、`timings` 等 summary 信息，**不包含 UI 所需的 steps 数据**。
- 前端 `mapAPIMessageToUIMessage()` 只读取了 `msg.metadata?.timings`，**没有读取 steps**。

#### 解决思路

在后端直接构建与前端 `AgentMessageState` 完全对齐的数据结构，随 `agent_trace` 一并持久化。

#### 具体改动

**1. 后端 `AgentChatService` 维护 `ui_state`**

在 `process()` 方法的事件循环中，维护一个 `ui_state` 字典，结构和前端 `AgentMessageState` 完全一致：

```python
ui_state: dict = {
    "steps": [],
    "finalText": "",
    "iterations": 0,
    "status": "running",
    "halted": False,
}
```

对每个事件类型做对应处理（与前端 `handleStreamEvent` 逻辑对齐）：

| 事件 | `ui_state` 处理 |
|------|----------------|
| `AGENT_START` | 初始化空 steps，status="running" |
| `ITERATION_START` | steps 追加 `{kind: "thinking", iteration, text: ""}`，更新 iterations |
| `AGENT_THINKING` | 找到对应 iteration 的最后一个 thinking step，追加 delta 到 text |
| `TOOL_CALL` | steps 追加 `{kind: "tool", iteration, toolId, toolName, toolInput, toolStatus: "running"}` |
| `TOOL_RESULT` | 找到对应 toolId 的 tool step，更新 `toolStatus`/`toolPreview`/`toolMs` |
| `COMPACT_TRIGGERED` | steps 追加 `{kind: "compact", iteration, beforeTokens, afterTokens}` |
| `FINAL_TEXT_PROMOTE` | 从 steps 中移除对应 iteration 的 thinking step，其 text 合并到 `finalText` |
| `AGENT_HALTED` | status="done"，halted=True |
| `DONE` | status="done" |

最终持久化时：

```python
agent_trace["ui_state"] = ui_state
self.chat_message_repo.update(
    placeholder_id,
    content=thinking_buffer,
    sources=json.dumps(sources),
    message_metadata=json.dumps(agent_trace),
)
```

**2. 前端 `useChat.ts` 恢复 `agentState`**

修改 `mapAPIMessageToUIMessage`：

```typescript
const mapAPIMessageToUIMessage = (msg: APIChatMessage): Message => {
  const agentState = msg.metadata?.ui_state as AgentMessageState | undefined
  return {
    id: msg.message_id,
    type: msg.role,
    content: msg.content,
    timestamp: msg.created_at,
    sources: msg.sources || [],
    agentState,
  }
}
```

**3. 清理 `timings` 相关代码**

删除 `Message` 接口中的 `timings?: StageTiming` 字段，以及 `mapAPIMessageToUIMessage` 中的 timings 提取逻辑。

---

### 二、去除遗留统计（TimingDisplay）

`TimingDisplay` 组件在以下两处使用：

- `frontend/src/components/chat/ChatInterface.tsx`
- `frontend/src/components/chat/DocChatPanel.tsx`

#### 具体改动

1. 从 `ChatInterface.tsx` 和 `DocChatPanel.tsx` 中**删除 `TimingDisplay` 组件的定义和引用**。
2. 从 `useChat.ts` 中**删除 `StageTiming` 接口**。
3. 从两处组件中**删除 `import { StageTiming } from '../../hooks/useChat'`** 及 `ClockIcon`/`MagnifyingGlassIcon`/`BookOpenIcon`/`PuzzlePieceIcon`/`SparklesIcon` 等仅被 `TimingDisplay` 使用的 icon import。

---

### 三、新的计时方式与展现方式

#### 后端计时指标

Agent 模式有意义的计时维度：

| 指标 | 含义 | 来源 |
|------|------|------|
| `total_ms` | 整个 Agent Run 总耗时 | `AgentChatService` 中 `time.monotonic()` 差值 |
| `llm_total_ms` | 所有迭代 LLM 调用时间之和 | `runtime.py` 中 `timings` 列表聚合 |
| `tools_total_ms` | 所有工具执行时间之和 | `runtime.py` 中 `timings` 列表聚合 |
| `iteration_count` | 实际迭代轮数 | DONE 事件中的 `iterations` |

#### 后端改动

1. **`AgentChatService.process()` 记录总时间**：
   - 在 `AGENT_START` 时记录 `start_time = time.monotonic()`
   - DONE 事件处理时计算 `total_ms = int((time.monotonic() - start_time) * 1000)`

2. **`runtime.py` 暴露迭代级计时**：
   - 当前 `timings` 列表在 `run()` 结束后持有每轮数据，但**未暴露**。
   - 修改 DONE 事件数据结构，增加 `agent_timings` 字段：

```python
yield SSEEvent(
    type=SSEEventType.DONE,
    data={
        "iterations": iteration,
        "usage": {...},
        "agent_timings": {
            "total_ms": total_ms,
            "llm_total_ms": sum(t.llm_ms for t in timings),
            "tools_total_ms": sum(t.tools_ms for t in timings),
            "iteration_count": iteration,
        },
    },
)
```

同样修改 `_force_final_answer()` 中的 DONE 事件。

3. **`AgentChatService` 将计时存入 `ui_state`**：

```python
ui_state["timings"] = {
    "total_ms": total_ms,
    "llm_total_ms": event.data["agent_timings"]["llm_total_ms"],
    "tools_total_ms": event.data["agent_timings"]["tools_total_ms"],
    "iteration_count": event.data["agent_timings"]["iteration_count"],
}
```

#### 前端展现方式

**策略**：将计时信息整合进 `AgentTrace` 组件，而非在消息气泡下方另起一行。

理由：计时是 Agent 执行过程的元信息，与 AgentTrace 天然属于同一信息层级。

**展现设计**：

1. **Header 区域（总览）**：保持简洁，显示总耗时。
   - 运行中：`Agent (3 steps · 总计 4.2s)`（total_ms 实时更新）
   - 完成：`Agent (3 steps · 总计 6.5s)`

2. **展开后底部（详情）**：在 steps 列表最下方增加一行灰色小字统计：
   ```
   LLM 4.2s · Tools 1.8s · 2 轮迭代 · 输入 1,240 tokens · 输出 890 tokens
   ```

**前端类型扩展**：

```typescript
export interface AgentTimings {
  total_ms: number
  llm_total_ms: number
  tools_total_ms: number
  iteration_count: number
}

export interface AgentMessageState {
  steps: AgentStep[]
  finalText: string
  iterations: number
  status: "running" | "done" | "error" | "cancelled"
  halted?: boolean
  timings?: AgentTimings  // 新增
}
```

**`AgentTrace.tsx` 修改**：

- Header 文本逻辑：当有 `timings?.total_ms` 时显示总时间。
- 展开后底部：渲染 `timings` 详情行（如果存在）。

---

### 四、Transcript File 是否可以被取代

**结论：不能取代，但应改造为可选（默认关闭）**

#### Transcript File 的独特价值

| 能力 | Transcript File | 数据库存储 |
|------|----------------|----------|
| 精确时间戳 | 每条事件有独立 `ts`（UTC ISO） | 只有消息级 `created_at` |
| 完整原始数据 | tool input/output 完整保留 | 前端展示用简化版（截断） |
| 实时写入 | 流式过程中逐条追加 JSONL | 只有结束后一次性写入 |
| 离线审计 | 不依赖数据库 | 依赖数据库可用性 |
| 故障恢复 | 即使进程崩溃也有部分记录 | 崩溃则全部丢失 |

#### 建议

1. **新增配置项**：`AgentConfig.enable_transcript: bool = False`（默认关闭）
2. **保留 `TranscriptWriter`**：作为调试/审计工具，需要深度排查时手动开启
3. **日常运行**：依赖数据库中的 `ui_state` 即可满足前端展示和基本问题排查

---

## 改动文件清单

### 后端

| 文件 | 改动内容 |
|------|---------|
| `backend/chat/agent_service.py` | 维护 `ui_state`，事件循环中同步更新 steps；计算 `total_ms`；持久化 `ui_state` 到 `agent_trace` |
| `backend/chat/agent/runtime.py` | DONE 事件增加 `agent_timings` 字段（`total_ms`/`llm_total_ms`/`tools_total_ms`/`iteration_count`） |
| `backend/models/config.py` | 新增 `enable_transcript: bool = False` |

### 前端

| 文件 | 改动内容 |
|------|---------|
| `frontend/src/hooks/useChat.ts` | 删除 `StageTiming` 接口和 `timings` 字段；`mapAPIMessageToUIMessage` 从 `metadata.ui_state` 恢复 `agentState`；DONE 事件处理 `agent_timings` |
| `frontend/src/types/agent.ts` | 新增 `AgentTimings` 接口；`AgentMessageState` 增加 `timings?` 字段 |
| `frontend/src/components/chat/AgentTrace.tsx` | Header 显示总耗时；展开后底部显示详细计时行 |
| `frontend/src/components/chat/ChatInterface.tsx` | 删除 `TimingDisplay` 组件定义、import、引用 |
| `frontend/src/components/chat/DocChatPanel.tsx` | 删除 `TimingDisplay` 组件定义、import、引用 |

---

## 数据兼容性

- **旧消息**：`metadata.ui_state` 不存在，`mapAPIMessageToUIMessage` 返回 `agentState: undefined`，AgentTrace 不渲染（和当前行为一致，可接受）。
- **新消息**：正常渲染 AgentTrace 和计时信息。
