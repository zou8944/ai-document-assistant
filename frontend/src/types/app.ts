/**
 * Application types and interfaces
 */

export type SidebarSection = 'knowledge' | 'chat' | 'settings'

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  createdAt: string
  documentCount: number
  sourceType: 'files' | 'website' | 'mixed'
}

export interface ChatSession {
  id: string
  name: string
  knowledgeBaseIds: string[]
  createdAt: string
  lastMessageAt: string
  messageCount: number
}

export interface Document {
  id: string
  name: string
  source: string
  url?: string
  createdAt: string
  size: string
  type: 'file' | 'website'
}

export interface ImportStatus {
  isActive: boolean
  progress: number
  message: string
}

export interface LLMConfig {
  api_key: string
  base_url: string
  chat_model: string
}

export interface EmbeddingConfig {
  api_key: string
  base_url: string
  model: string
}

export interface KnowledgeBaseConfig {
  max_crawl_pages: number
  max_file_size_mb: number
}

export interface SystemConfig {
  log_level: string
}

export interface AppSettings {
  llm: LLMConfig
  embedding: EmbeddingConfig
  knowledge_base: KnowledgeBaseConfig
  system: SystemConfig
}

export interface AppState {
  activeSidebarSection: SidebarSection
  knowledgeBases: KnowledgeBase[]
  chatSessions: ChatSession[]
  activeKnowledgeBase: string | null
  activeChat: string | null
  settings: AppSettings
}