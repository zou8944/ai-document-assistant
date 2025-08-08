/**
 * Electron main process for AI Document Assistant.
 * Following 2024 best practices for macOS integration with vibrancy support.
 */

import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import isDev from 'electron-is-dev'

// Python subprocess management
import { PythonShell } from 'python-shell'

// Type definitions for IPC
interface PythonCommand {
  command: string
  [key: string]: any
}

interface PythonResponse {
  status: 'success' | 'error' | 'progress'
  [key: string]: any
}

class DocumentAssistantApp {
  private mainWindow: BrowserWindow | null = null
  private pythonProcess: PythonShell | null = null

  constructor() {
    this.setupApp()
  }

  private setupApp() {
    // This method will be called when Electron has finished initialization
    app.whenReady().then(() => {
      this.createWindow()
      this.setupPythonProcess()
      this.setupIpcHandlers()

      app.on('activate', () => {
        // On macOS, re-create window when dock icon is clicked
        if (BrowserWindow.getAllWindows().length === 0) {
          this.createWindow()
        }
      })
    })

    // Quit when all windows are closed, except on macOS
    app.on('window-all-closed', () => {
      if (process.platform !== 'darwin') {
        this.cleanup()
        app.quit()
      }
    })

    app.on('before-quit', () => {
      this.cleanup()
    })
  }

  private createWindow() {
    // CRITICAL: Electron vibrancy requires specific window options
    this.mainWindow = new BrowserWindow({
      width: 1200,
      height: 800,
      minWidth: 800,
      minHeight: 600,
      titleBarStyle: 'hiddenInset', // macOS native title bar
      vibrancy: 'under-window', // macOS only - glass effect
      transparent: true,
      show: false, // Don't show until ready
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: join(__dirname, 'preload.js'),
        webSecurity: !isDev,
      },
    })

    // Load the app
    if (isDev) {
      this.mainWindow.loadURL('http://localhost:5173')
      // Open DevTools in development
      this.mainWindow.webContents.openDevTools()
    } else {
      this.mainWindow.loadFile(join(__dirname, 'renderer/index.html'))
    }

    // Show window when ready to prevent visual flash
    this.mainWindow.once('ready-to-show', () => {
      this.mainWindow?.show()
      
      // Focus window on first show
      if (isDev) {
        this.mainWindow?.focus()
      }
    })

    // Handle window closed
    this.mainWindow.on('closed', () => {
      this.mainWindow = null
    })

    // Handle external links
    this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      shell.openExternal(url)
      return { action: 'deny' }
    })

    // Prevent navigation away from app
    this.mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
      const parsedUrl = new URL(navigationUrl)
      
      if (parsedUrl.origin !== 'http://localhost:5173' && !navigationUrl.includes('renderer/index.html')) {
        event.preventDefault()
        shell.openExternal(navigationUrl)
      }
    })
  }

  private setupPythonProcess() {
    try {
      const backendPath = isDev 
        ? join(process.cwd(), '..', 'backend', 'main.py')
        : join(process.resourcesPath, 'backend', 'main.py')

      // PATTERN: Use python-shell with stdio mode
      this.pythonProcess = new PythonShell(backendPath, {
        mode: 'json', // Automatic JSON parsing
        pythonPath: 'python3',
        pythonOptions: ['-u'], // Unbuffered output
        scriptPath: dirname(backendPath),
      })

      // Handle Python messages
      this.pythonProcess.on('message', (response: PythonResponse) => {
        console.log('Python response:', response)
        
        // Forward response to renderer process
        if (this.mainWindow && !this.mainWindow.isDestroyed()) {
          this.mainWindow.webContents.send('python-response', response)
        }
      })

      // Handle Python errors
      this.pythonProcess.on('error', (error) => {
        console.error('Python process error:', error)
        
        // Send error to renderer
        if (this.mainWindow && !this.mainWindow.isDestroyed()) {
          this.mainWindow.webContents.send('python-error', {
            status: 'error',
            message: `Backend error: ${error.message}`,
          })
        }
      })

      // Handle Python process end
      this.pythonProcess.on('close', (code: number) => {
        console.log(`Python process exited with code ${code}`)
        this.pythonProcess = null
        
        // Notify renderer of process end
        if (this.mainWindow && !this.mainWindow.isDestroyed()) {
          this.mainWindow.webContents.send('python-disconnected', { code })
        }
      })

      console.log('Python backend process started successfully')
      
    } catch (error) {
      console.error('Failed to start Python backend:', error)
      
      // Show error dialog
      dialog.showErrorBox(
        'Backend Error',
        `Failed to start Python backend: ${error}`
      )
    }
  }

  private setupIpcHandlers() {
    // Handle Python commands from renderer
    ipcMain.handle('send-python-command', async (event, command: PythonCommand) => {
      return new Promise<boolean>((resolve, reject) => {
        if (!this.pythonProcess) {
          reject(new Error('Python backend not available'))
          return
        }

        try {
          // GOTCHA: Set up response handler before sending
          const timeout = setTimeout(() => {
            reject(new Error('Python command timeout'))
          }, 30000) // 30 second timeout

          const messageHandler = (response: PythonResponse) => {
            if (response.command === command.command) {
              clearTimeout(timeout)
              this.pythonProcess?.off('message', messageHandler)
              resolve(true)
            }
          }

          this.pythonProcess.on('message', messageHandler)

          // Send JSON command
          this.pythonProcess.send(command)
          
        } catch (error) {
          reject(error)
        }
      })
    })

    // File dialog handlers
    ipcMain.handle('show-open-dialog', async (event, options) => {
      if (!this.mainWindow) return { canceled: true }

      const result = await dialog.showOpenDialog(this.mainWindow, {
        title: 'Select Documents',
        properties: ['openFile', 'multiSelections'],
        filters: [
          { name: 'Documents', extensions: ['pdf', 'txt', 'md', 'docx', 'doc'] },
          { name: 'All Files', extensions: ['*'] }
        ],
        ...options
      })

      return result
    })

    ipcMain.handle('show-open-folder-dialog', async () => {
      if (!this.mainWindow) return { canceled: true }

      const result = await dialog.showOpenDialog(this.mainWindow, {
        title: 'Select Folder',
        properties: ['openDirectory']
      })

      return result
    })

    // Window control handlers
    ipcMain.handle('minimize-window', () => {
      this.mainWindow?.minimize()
    })

    ipcMain.handle('maximize-window', () => {
      if (this.mainWindow?.isMaximized()) {
        this.mainWindow.unmaximize()
      } else {
        this.mainWindow?.maximize()
      }
    })

    ipcMain.handle('close-window', () => {
      this.mainWindow?.close()
    })

    // App info handlers
    ipcMain.handle('get-app-version', () => {
      return app.getVersion()
    })

    ipcMain.handle('get-platform', () => {
      return process.platform
    })

    // External link handler
    ipcMain.handle('open-external', async (event, url: string) => {
      await shell.openExternal(url)
    })
  }

  private cleanup() {
    console.log('Cleaning up resources...')
    
    // Close Python process
    if (this.pythonProcess) {
      try {
        this.pythonProcess.kill()
        this.pythonProcess = null
        console.log('Python backend process terminated')
      } catch (error) {
        console.error('Error terminating Python process:', error)
      }
    }
  }
}

// Create app instance
const documentAssistant = new DocumentAssistantApp()

// Handle certificate errors in development
if (isDev) {
  app.commandLine.appendSwitch('ignore-certificate-errors-spki-list')
  app.commandLine.appendSwitch('ignore-certificate-errors')
}