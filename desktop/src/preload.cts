import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('cwsDesktop', {
  getLogDir: () => ipcRenderer.invoke('desktop:get-log-dir'),
  quit: () => ipcRenderer.invoke('desktop:quit'),
})
