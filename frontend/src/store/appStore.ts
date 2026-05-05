/**
 * Global application store using Zustand
 */

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { AppState, KnowledgeBase, ChatSession, AppSettings, SidebarSection } from '../types/app'

interface AppStore extends AppState {
  // Layout state
  sidebarWidth: number

  // Doc chat sidebar state
  docChatSidebarOpen: boolean
  docChatSidebarWidth: number

  // Language display preference: 'source' = original language, 'zh' = Chinese
  displayLanguage: 'source' | 'zh'

  // Actions
  setActiveSidebarSection: (section: SidebarSection) => void
  setActiveKnowledgeBase: (id: string | null) => void
  setActiveChat: (id: string | null) => void
  setSidebarWidth: (width: number) => void
  setDocChatSidebarOpen: (open: boolean) => void
  setDocChatSidebarWidth: (width: number) => void
  setDisplayLanguage: (lang: 'source' | 'zh') => void
  addKnowledgeBase: (kb: KnowledgeBase) => void
  updateKnowledgeBase: (id: string, updates: Partial<KnowledgeBase>) => void
  deleteKnowledgeBase: (id: string) => void
  addChatSession: (chat: ChatSession) => void
  updateChatSession: (id: string, updates: Partial<ChatSession>) => void
  deleteChatSession: (id: string) => void
  reorderChatSessions: (fromIndex: number, toIndex: number) => void
  updateSettings: (settings: Partial<AppSettings>) => void

  // Computed getters
  getCurrentKnowledgeBase: () => KnowledgeBase | null
  getCurrentChat: () => ChatSession | null
  getChatsByKnowledgeBase: (kbId: string) => ChatSession[]
}

const initialSettings: AppSettings = {
  llm: {
    api_key: '',
    base_url: 'https://api.openai.com/v1',
    chat_model: 'gpt-3.5-turbo'
  },
  embedding: {
    api_key: '',
    base_url: 'https://api.openai.com/v1',
    model: 'text-embedding-ada-002'
  },
  knowledge_base: {
    max_crawl_pages: 1000,
    max_file_size_mb: 10
  },
  system: {
    log_level: 'info'
  }
}

export const useAppStore = create<AppStore>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        activeSidebarSection: 'knowledge',
        sidebarWidth: 256, // 16rem equivalent
        docChatSidebarOpen: false,
        docChatSidebarWidth: 320,
        displayLanguage: 'zh',
        knowledgeBases: [],
        chatSessions: [],
        activeKnowledgeBase: null,
        activeChat: null,
        settings: initialSettings,

        // Actions
        setActiveSidebarSection: (section) =>
          set({ activeSidebarSection: section }),

        setActiveKnowledgeBase: (id) =>
          set({ activeKnowledgeBase: id }),

        setActiveChat: (id) =>
          set({ activeChat: id }),

        setSidebarWidth: (width) =>
          set({
            sidebarWidth: Math.max(
              200,
              Math.min(
                typeof window !== 'undefined' ? window.innerWidth * 0.5 : 400,
                width
              )
            )
          }),

        setDocChatSidebarOpen: (open) =>
          set({ docChatSidebarOpen: open }),

        setDocChatSidebarWidth: (width) =>
          set({
            docChatSidebarWidth: Math.max(
              240,
              Math.min(
                typeof window !== 'undefined' ? window.innerWidth * 0.4 : 500,
                width
              )
            )
          }),

        setDisplayLanguage: (lang) =>
          set({ displayLanguage: lang }),

        addKnowledgeBase: (kb) =>
          set((state) => ({
            knowledgeBases: [...state.knowledgeBases, kb]
          })),

        updateKnowledgeBase: (id, updates) =>
          set((state) => ({
            knowledgeBases: state.knowledgeBases.map((kb) =>
              kb.id === id ? { ...kb, ...updates } : kb
            )
          })),

        deleteKnowledgeBase: (id) =>
          set((state) => ({
            knowledgeBases: state.knowledgeBases.filter((kb) => kb.id !== id),
            chatSessions: state.chatSessions.filter(
              (chat) => !chat.knowledgeBaseIds.includes(id)
            ),
            activeKnowledgeBase:
              state.activeKnowledgeBase === id ? null : state.activeKnowledgeBase,
          })),

        addChatSession: (chat) =>
          set((state) => ({
            chatSessions: [...state.chatSessions, chat]
          })),

        updateChatSession: (id, updates) =>
          set((state) => ({
            chatSessions: state.chatSessions.map((chat) =>
              chat.id === id ? { ...chat, ...updates } : chat
            )
          })),

        deleteChatSession: (id) =>
          set((state) => ({
            chatSessions: state.chatSessions.filter((chat) => chat.id !== id),
            activeChat: state.activeChat === id ? null : state.activeChat
          })),

        reorderChatSessions: (fromIndex, toIndex) =>
          set((state) => {
            const newChatSessions = [...state.chatSessions]
            const [removed] = newChatSessions.splice(fromIndex, 1)
            newChatSessions.splice(toIndex, 0, removed)
            return { chatSessions: newChatSessions }
          }),

        updateSettings: (newSettings) =>
          set((state) => ({
            settings: {
              llm: { ...state.settings.llm, ...newSettings.llm },
              embedding: { ...state.settings.embedding, ...newSettings.embedding },
              knowledge_base: { ...state.settings.knowledge_base, ...newSettings.knowledge_base },
              system: { ...state.settings.system, ...newSettings.system }
            }
          })),

        // Computed getters
        getCurrentKnowledgeBase: () => {
          const state = get()
          return (
            state.knowledgeBases.find((kb) => kb.id === state.activeKnowledgeBase) ||
            null
          )
        },

        getCurrentChat: () => {
          const state = get()
          return (
            state.chatSessions.find((chat) => chat.id === state.activeChat) || null
          )
        },

        getChatsByKnowledgeBase: (kbId) => {
          const state = get()
          return state.chatSessions.filter((chat) =>
            chat.knowledgeBaseIds.includes(kbId)
          )
        }
      }),
      {
        name: 'ai-document-assistant-store',
        partialize: (state) => ({
          knowledgeBases: state.knowledgeBases,
          chatSessions: state.chatSessions,
          settings: state.settings,
          sidebarWidth: state.sidebarWidth,
          docChatSidebarOpen: state.docChatSidebarOpen,
          docChatSidebarWidth: state.docChatSidebarWidth,
          displayLanguage: state.displayLanguage,
        })
      }
    )
  )
)