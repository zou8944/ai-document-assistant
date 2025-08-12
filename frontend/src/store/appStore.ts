/**
 * Global application store using Zustand
 */

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { AppState, KnowledgeBase, ChatSession, AppSettings, SidebarSection } from '../types/app'

interface AppStore extends AppState {
  // Layout state
  sidebarWidth: number
  
  // Actions
  setActiveSidebarSection: (section: SidebarSection) => void
  setActiveKnowledgeBase: (id: string | null) => void
  setActiveChat: (id: string | null) => void
  setSidebarWidth: (width: number) => void
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
    apiKey: '',
    baseUrl: 'https://api.openai.com/v1',
    chatModel: 'gpt-3.5-turbo'
  },
  embedding: {
    apiKey: '',
    baseUrl: 'https://api.openai.com/v1',
    embeddingModel: 'text-embedding-ada-002'
  },
  dataLocation: './data'
}

export const useAppStore = create<AppStore>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        activeSidebarSection: 'knowledge',
        sidebarWidth: 256, // 16rem equivalent
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
          set({ sidebarWidth: Math.max(200, Math.min(400, width)) }),

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
            settings: { ...state.settings, ...newSettings }
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
          sidebarWidth: state.sidebarWidth
        })
      }
    )
  )
)