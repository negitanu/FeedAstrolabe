const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld(
  'astrolabe',
  Object.freeze({
    onSynchronized: (callback) => {
      if (typeof callback !== 'function') return;
      ipcRenderer.on('astrolabe:synchronized', () => callback());
    },
    synchronize: () => ipcRenderer.invoke('astrolabe:sync'),
    openConnection: () => ipcRenderer.invoke('astrolabe:connection'),
    call: (op, data = {}) => ipcRenderer.invoke('astrolabe:call', op, data),
    openExternal: (url) => ipcRenderer.invoke('astrolabe:external', url),
    exportFile: (kind, id) => ipcRenderer.invoke('astrolabe:export', kind, id),
    importFile: (kind) => ipcRenderer.invoke('astrolabe:import', kind),
  }),
);
