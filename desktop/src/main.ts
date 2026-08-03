import { app, BrowserWindow, ipcMain, shell } from 'electron'
import path from 'node:path'

import { collectSeedEnv, findFreePort, getDefaultLogDir, startBackend } from './backend.js'
import { createBackendController, installBackendCleanupHooks } from './backendLifecycle.js'
import { waitForHealth } from './health.js'
import { isAllowedAppNavigation, shouldOpenExternally } from './navigation.js'
import { normalizeHttpUrl, resolvePackagedBackendExe } from './paths.js'
import { readSeedEnv } from './seed.js'
import { createFileTelemetryLog, createTelemetryProvider, type TelemetryProvider } from './telemetry.js'

let mainWindow: BrowserWindow | undefined
let logDir = getDefaultLogDir()
const backendController = createBackendController()
let telemetryProvider: TelemetryProvider | undefined

function createWindow(targetUrl: string): BrowserWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 680,
    show: false,
    backgroundColor: '#050608',
    webPreferences: {
      // Sandboxed Electron preloads are executed as CommonJS, even though the
      // application main process uses ESM. `preload.cts` emits this `.cjs` file.
      preload: path.join(app.getAppPath(), 'build', 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  })

  window.once('ready-to-show', () => window.show())
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (shouldOpenExternally(targetUrl, url)) {
      shell.openExternal(url)
    }
    return { action: 'deny' }
  })
  window.webContents.on('will-navigate', (event, url) => {
    if (!isAllowedAppNavigation(targetUrl, url)) {
      event.preventDefault()
      if (shouldOpenExternally(targetUrl, url)) {
        shell.openExternal(url)
      }
    }
  })
  void window.loadURL(targetUrl)
  return window
}

async function boot(): Promise<void> {
  logDir = getDefaultLogDir()
  const port = await findFreePort()
  const targetUrl = normalizeHttpUrl(port)
  const backendExe = resolvePackagedBackendExe({ resourcesPath: process.resourcesPath })

  const backendProcess = startBackend({
    executable: backendExe,
    port,
    logDir,
    seedEnv: {
      ...readSeedEnv(path.join(process.resourcesPath, 'desktop-seed.json')),
      ...collectSeedEnv(),
    },
  })

  backendController.set(backendProcess)

  await waitForHealth({ url: `${targetUrl}/api/health`, timeoutMs: 45000 })
  telemetryProvider = createTelemetryProvider({
    resourcesPath: process.resourcesPath,
    logDir,
    argv: process.argv,
    log: createFileTelemetryLog(logDir),
  })
  await telemetryProvider.beginSession()
  mainWindow = createWindow(targetUrl)
}

ipcMain.handle('desktop:get-log-dir', () => logDir)
ipcMain.handle('desktop:quit', () => app.quit())

app.whenReady()
  .then(boot)
  .catch((error) => {
    console.error(error)
    app.quit()
  })

app.on('window-all-closed', () => {
  app.quit()
})

installBackendCleanupHooks({
  app,
  processRef: process,
  cleanup: () => {
    void telemetryProvider?.shutdown()
    backendController.cleanup()
  },
})
