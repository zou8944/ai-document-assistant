/**
 * Agent-related types for step-by-step trace UI
 */

export type AgentStepKind = "thinking" | "tool" | "compact"

export interface AgentStep {
  kind: AgentStepKind
  iteration: number
  // thinking
  text?: string
  hidden?: boolean
  thinkingMs?: number
  // tool
  toolId?: string
  toolName?: string
  toolInput?: object
  toolPreview?: string
  toolStatus?: "running" | "done" | "error"
  toolMs?: number
  // compact
  beforeTokens?: number
  afterTokens?: number
}

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
  answering?: boolean
  timings?: AgentTimings
}
