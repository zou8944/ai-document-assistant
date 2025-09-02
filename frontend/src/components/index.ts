/**
 * Components index file for easy importing
 */

// Layout components
export { default as Sidebar } from './layout/Sidebar'
export { default as MainLayout } from './layout/MainLayout'

// Knowledge base components  
export { default as KnowledgeBaseOverview } from './knowledge/KnowledgeBaseOverview'
export { default as KnowledgeBaseManagement } from './knowledge/KnowledgeBaseManagement'
export { default as AddKnowledgeBaseModal } from './knowledge/AddKnowledgeBaseModal'

// Chat components
export { default as ChatInterface } from './chat/ChatInterface'
export { default as KnowledgeBaseSelector } from './chat/KnowledgeBaseSelector'

// Settings components
export { default as SettingsPage } from './settings/SettingsPage'

// Startup components
export { default as StartupScreen } from './StartupScreen'

// Legacy components (keeping for compatibility)
export { default as FileUpload } from './FileUpload'
export { default as URLInput } from './URLInput'
export { default as StatusIndicator } from './StatusIndicator'
export type { StatusType } from './StatusIndicator'