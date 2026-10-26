'use strict';
const { BrowserWindow, session } = require('electron');
const {
  syncOrigin,
  readSyncJSON,
  checkSyncReadiness,
  syncNetworkError,
} = require('./sync-policy.cjs');
let running = false;
let controller;
let login;
const getSession = () => session.fromPartition('persist:feedastrolabe-sync');
async function synchronize(rpc) {
  if (running) return { busy: true };
  running = true;
  controller = new AbortController();
  try {
    let more = true;
    let batches = 0;
    let checkedOrigin;
    while (more && batches++ < 100) {
      const prepared = await rpc('sync.prepare');
      const origin = syncOrigin(prepared.url);
      if (checkedOrigin !== origin) {
        await checkSyncReadiness(
          (url, options) => getSession().fetch(url, options),
          origin,
          AbortSignal.any([AbortSignal.timeout(30000), controller.signal]),
        );
        checkedOrigin = origin;
      }
      const response = await getSession()
        .fetch(origin + '/api/sync/v1/exchange', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(prepared.request),
          redirect: 'manual',
          signal: AbortSignal.any([AbortSignal.timeout(60000), controller.signal]),
        })
        .catch((e) => {
          throw syncNetworkError(e);
        });
      const value = await readSyncJSON(response);
      await rpc('sync.accept', { prepared, response: value });
      more = value.more || prepared.request.events.length > 0;
    }
    return await rpc('sync.status');
  } catch (e) {
    if (controller?.signal.aborted) return { cancelled: true };
    // Never persist remote HTML, cookies or response bodies in errors.
    const message = String(e.message || e).slice(0, 500);
    await rpc('sync.error', { error: message }).catch(() => {});
    throw new Error(message);
  } finally {
    running = false;
    controller = undefined;
  }
}
async function openConnection(rpc, parent) {
  const state = await rpc('sync.status');
  const origin = syncOrigin(state.url);
  if (login && !login.isDestroyed()) {
    login.focus();
    return;
  }
  login = new BrowserWindow({
    parent,
    width: 1000,
    height: 780,
    title: 'FeedAstrolabe 接続先',
    webPreferences: {
      session: getSession(),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true,
    },
  });
  login.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  login.webContents.on('will-attach-webview', (event) => event.preventDefault());
  login.webContents.on('will-navigate', (event, target) => {
    try {
      if (new URL(target).protocol !== 'https:' && !target.startsWith(origin + '/'))
        event.preventDefault();
    } catch {
      event.preventDefault();
    }
  });
  login.on('closed', () => {
    login = undefined;
  });
  getSession().setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  getSession().setPermissionCheckHandler(() => false);
  await login.loadURL(origin + '/');
}
function cancel() {
  controller?.abort();
}
function close() {
  cancel();
  if (login && !login.isDestroyed()) login.destroy();
}
module.exports = { synchronize, openConnection, cancel, close };
