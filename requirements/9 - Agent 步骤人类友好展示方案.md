# Agent 步骤人类友好展示方案

## 背景

当前 AgentTrace 中工具步骤以机器格式展示：

```
search_documents({"keywords": ["部署", "Docker"]})
```

展开后 Input/Result 也是原始 JSON，用户阅读体验差。需要改为自然语言描述，让用户一眼看懂 Agent 在做什么。

## 目标

- 工具步骤标题用**中文自然语言**描述操作意图
- 参数展示提取关键信息，去除 JSON 噪声
- 结果摘要展示核心结论（如"找到 3 篇文档"）
- 保留原始数据在展开区域，便于调试

## 当前工具清单与友好描述映射

| 工具名 | 友好标题模板 | 参数展示 |
|---|---|---|
| `search_documents` | 搜索文档 | 关键词: `keywords` |
| `grep_documents` | 在文档中查找 "`pattern`" | 模式: `pattern`，正则: `regex` |
| `get_document` | 阅读文档 `document_id` | 第 `page` 页 |
| `get_document_summary` | 查看文档摘要 `document_id` | — |
| `list_collections` | 查看知识库列表 | — |
| `get_collection_overview` | 查看知识库 `collection_id` 概览 | — |
| `citations` | 生成引用标记 | — |

## 详细设计

### 1. 新增 `frontend/src/components/chat/toolRenderers.tsx`

为每个工具定义 `renderTitle(step)` 和 `renderSummary(step)` 函数：

```tsx
// 示例: search_documents
function renderSearchTitle(step: AgentStep): ReactNode {
  const kw = step.toolInput?.keywords ?? []
  return <>搜索包含关键词 "{kw.join('", "')}" 的文档</>
}

function renderSearchSummary(step: AgentStep): string | null {
  // 从 toolPreview 中解析 "Found N documents"
  const m = step.toolPreview?.match(/Found (\d+) documents?/)
  return m ? `找到 ${m[1]} 篇相关文档` : null
}
```

注册表：

```tsx
export const toolRenderers: Record<string, ToolRenderer> = {
  search_documents: { title: renderSearchTitle, summary: renderSearchSummary },
  grep_documents: { title: renderGrepTitle, summary: renderGrepSummary },
  get_document: { title: renderGetDocTitle, summary: renderGetDocSummary },
  // ...
}
```

### 2. 修改 `AgentTraceStep.tsx`

- `StepLabel` 优先使用 `toolRenderers[step.toolName]?.title(step)`，回退到原始 `toolName + JSON`
- 工具步骤的折叠摘要行显示 `summary`，替代或补充原有状态图标
- 展开区域保留原始 JSON 的 `Input` / `Result`，但增加一层人类友好的摘要卡片置顶

### 3. 结果摘要提取策略

由于 `toolPreview` 是工具返回的文本内容，前端用**正则提取关键句**：

| 工具 | 提取正则 | 展示文案 |
|---|---|---|
| `search_documents` | `Found (\d+) documents?` | 找到 N 篇相关文档 |
| `grep_documents` | `Found (\d+) matches?` | 找到 N 处匹配 |
| `get_document` | `Document .+ "(.+)"` | 正在阅读《xxx》 |
| `get_document_summary` | `Summary for .+ "(.+)"` | 文档《xxx》摘要 |
| `list_collections` | `Available collections \((\d+)\)` | 共 N 个知识库 |
| `get_collection_overview` | `# Collection: (.+)` | 知识库《xxx》概览 |

如果正则未命中，summary 为 `null`，不显示摘要行，仅保留展开后的原始结果。

### 4. Thinking 步骤优化（可选）

当前 Thinking 步骤固定显示 "Thinking"，可尝试：
- 提取 thinking 文本的第一句作为子标题
- 或保持简洁，仅在有实际内容时显示缩略

考虑到 thinking 内容可能很长且非结构化，保持 "Thinking" 标签 + 前两行缩略即可，不纳入本次改造重点。

### 5. UI 调整

- 工具步骤的标题行去掉 `ChevronRight/ChevronDown` 左侧的小箭头，改为整行可点击展开
- 摘要信息放在标题行右侧，使用更柔和的灰色（`text-gray-400`）
- 展开后的原始 JSON 折叠进一个 "原始数据" 二级折叠面板，默认收起

## 边界情况

- **未知工具**：无前端 renderer 时，回退到 `toolName` + 截断 JSON，与当前行为一致
- **参数为空**：不显示参数括号，如 `list_collections` 无参数时只显示 "查看知识库列表"
- **结果解析失败**：summary 为 null，不显示摘要，不影响功能
- **长参数**：参数值超过 30 字符时截断加 "..."

## 实现步骤

1. 创建 `frontend/src/components/chat/toolRenderers.tsx`，实现所有已知工具的 renderer
2. 修改 `AgentTraceStep.tsx`：
   - 引入 renderer 注册表
   - 重写 `StepLabel` 逻辑
   - 增加 summary 展示
   - 原始 JSON 折叠进二级面板
3. 自测各工具步骤的展示效果
4. 如有新增工具，补充对应 renderer 即可
