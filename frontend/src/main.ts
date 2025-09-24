/**
 * Electron main process for AI Document Assistant.
 * Following 2024 best practices for macOS integration with vibrancy support.
 */

import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron'
import { join } from 'path'
import isDev from 'electron-is-dev'

// API server subprocess management
import { spawn, ChildProcess } from 'child_process'
import { join as pathJoin } from 'path'

// Type definitions for API server management
interface APIServerInfo {
  port: number
  pid: number
  baseURL: string
}

class DocumentAssistantApp {
  private mainWindow: BrowserWindow | null = null
  private apiServerProcess: ChildProcess | null = null
  private apiServerInfo: APIServerInfo | null = null

  constructor() {
    this.setupApp()
  }

  private setupApp() {
    // This method will be called when Electron has finished initialization
    app.whenReady().then(async () => {
      this.setupIpcHandlers()
      this.createWindow()
      await this.startAPIServer()

      app.on('activate', () => {
        // On macOS, re-create window when dock icon is clicked
        if (BrowserWindow.getAllWindows().length === 0) {
          this.createWindow()
        }
      })
    })

    // Quit when all windows are closed, except on macOS
    app.on('window-all-closed', async () => {
      if (process.platform !== 'darwin') {
        await this.cleanup()
        app.quit()
      }
    })

    app.on('before-quit', async () => {
      await this.cleanup()
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

  private async startAPIServer(): Promise<void> {
    try {
      // Get the project root directory
      const projectRoot = isDev
        ? join(process.cwd(), '..')  // When running from frontend, go up one level
        : process.resourcesPath

      const backendDir = join(projectRoot, 'backend')
      const apiServerScript = 'api_server.py'

      console.log('Starting API server...')
      console.log('Project root:', projectRoot)
      console.log('Backend dir:', backendDir)
      console.log('API server script:', apiServerScript)

      // Run database migrations first
      await this.runAlembicMigrations(backendDir)

      // Find available port
      const port = await this.findAvailablePort(8000)
      
      // Start API server using uv
      this.apiServerProcess = spawn('uv', [
        'run', apiServerScript,
        '--host', '127.0.0.1',
        '--port', port.toString()
      ], {
        cwd: backendDir,
        env: {
          ...process.env,
          UV_PROJECT_DIR: backendDir
        },
        stdio: ['pipe', 'pipe', 'pipe']
      })

      // Create log files for API server output
      const logDir = pathJoin(backendDir, 'logs')
      const fs = await import('fs/promises')
      try {
        await fs.mkdir(logDir, { recursive: true })
      } catch {
        // Directory might already exist
      }
      
      this.apiServerProcess.stdout?.on('data', (data) => {
        console.log('API Server stdout:', data.toString())
      })

      this.apiServerProcess.stderr?.on('data', (data) => {
        console.log('API Server stderr:', data.toString())
      })

      this.apiServerProcess.on('error', (error) => {
        console.error('API server process error:', error)
        
        // Show error dialog
        dialog.showErrorBox(
          'Backend Error',
          `Failed to start API server: ${error.message}`
        )
      })

      this.apiServerProcess.on('close', (code: number) => {
        console.log(`API server process exited with code ${code}`)
        this.apiServerProcess = null
        this.apiServerInfo = null
        
        // Notify renderer of process end
        if (this.mainWindow && !this.mainWindow.isDestroyed()) {
          this.mainWindow.webContents.send('api-server-disconnected', { code })
        }
      })

      // Store server info
      this.apiServerInfo = {
        port,
        pid: this.apiServerProcess.pid || 0,
        baseURL: `http://127.0.0.1:${port}`
      }

      // Wait for server to be ready
      await this.waitForServerReady(this.apiServerInfo.baseURL)
      
      console.log(`API server started successfully on port ${port}`)
      
      // Send server info to renderer process
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('api-server-ready', this.apiServerInfo)
      }
      
    } catch (error) {
      console.error('Failed to start API server:', error)

      // Show error dialog with appropriate message
      const errorMessage = error instanceof Error ? error.message : String(error)
      let dialogTitle = 'Backend Error'
      let dialogMessage = `Failed to start API server: ${errorMessage}`

      if (errorMessage.includes('Migration failed')) {
        dialogTitle = 'Database Migration Error'
        dialogMessage = `Database migration failed: ${errorMessage}\n\nPlease check the application logs for more details.`
      }

      dialog.showErrorBox(dialogTitle, dialogMessage)
    }
  }

  private setupIpcHandlers() {
    // Handle API server info requests
    ipcMain.handle('get-api-server-info', async () => {
      return this.apiServerInfo
    })
    
    // Handle API server restart
    ipcMain.handle('restart-api-server', async () => {
      if (this.apiServerProcess) {
        this.apiServerProcess.kill()
        this.apiServerProcess = null
        this.apiServerInfo = null
      }
      
      await this.startAPIServer()
      return this.apiServerInfo
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

  private async findAvailablePort(startPort: number = 8000): Promise<number> {
    const net = await import('net')
    
    const isPortAvailable = (port: number): Promise<boolean> => {
      return new Promise((resolve) => {
        const server = net.createServer()
        server.listen(port, '127.0.0.1', () => {
          server.close(() => resolve(true))
        })
        server.on('error', () => resolve(false))
      })
    }
    
    for (let port = startPort; port < startPort + 100; port++) {
      if (await isPortAvailable(port)) {
        return port
      }
    }
    
    throw new Error('No available port found')
  }
  
  private async runAlembicMigrations(backendDir: string): Promise<void> {
    console.log('Running database migrations...')

    return new Promise((resolve, reject) => {
      const migrationProcess = spawn('uv', [
        'run', 'alembic', 'upgrade', 'head'
      ], {
        cwd: backendDir,
        env: {
          ...process.env,
          UV_PROJECT_DIR: backendDir
        },
        stdio: ['pipe', 'pipe', 'pipe']
      })

      let stderr = ''

      migrationProcess.stdout?.on('data', (data) => {
        console.log('Migration:', data.toString().trim())
      })

      migrationProcess.stderr?.on('data', (data) => {
        stderr += data.toString()
        console.log('Migration stderr:', data.toString().trim())
      })

      migrationProcess.on('close', (code) => {
        console.log(`Migration process exited with code ${code}`)

        if (code === 0) {
          console.log('Database migrations completed successfully')
          resolve()
        } else {
          reject(new Error(`Migration failed with code ${code}. Error: ${stderr}`))
        }
      })

      migrationProcess.on('error', (error) => {
        console.error('Migration process error:', error)
        reject(new Error(`Failed to start migration process: ${error.message}`))
      })
    })
  }

  private async waitForServerReady(baseURL: string, maxAttempts: number = 30): Promise<void> {
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const response = await fetch(`${baseURL}/api/v1/health`)
        if (response.ok) {
          console.log(`API server ready after ${attempt} attempts`)
          return
        }
      } catch (error) {
        // Server not ready yet
      }

      console.log(`Waiting for API server... (${attempt}/${maxAttempts})`)
      await new Promise(resolve => setTimeout(resolve, 1000))
    }

    throw new Error('API server failed to start within timeout')
  }

  private async cleanup(): Promise<void> {
    console.log('Cleaning up resources...')
    
    // Close API server process
    if (this.apiServerProcess) {
      try {
        // Try graceful shutdown first
        this.apiServerProcess.kill('SIGTERM')
        
        // Wait a bit for graceful shutdown
        await new Promise(resolve => setTimeout(resolve, 2000))
        
        // Force kill if still running
        if (!this.apiServerProcess.killed) {
          this.apiServerProcess.kill('SIGKILL')
        }
        
        this.apiServerProcess = null
        this.apiServerInfo = null
        console.log('API server process terminated')
      } catch (error) {
        console.error('Error terminating API server process:', error)
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