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

export interface ImportProgress {
  isActive: boolean
  currentFile?: string
  progress: number
  total: number
  message: string
}

export interface AppSettings {
  llm: {
    apiKey: string
    baseUrl: string
    chatModel: string
  }
  embedding: {
    apiKey: string
    baseUrl: string
    embeddingModel: string
  }
  dataLocation: string
}

export interface AppState {
  activeSidebarSection: SidebarSection
  knowledgeBases: KnowledgeBase[]
  chatSessions: ChatSession[]
  activeKnowledgeBase: string | null
  activeChat: string | null
  settings: AppSettings
}