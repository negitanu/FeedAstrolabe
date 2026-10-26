const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require('electron');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');
const { open, mkdir } = require('node:fs/promises');
const { mkdirSync } = require('node:fs');
const { join, resolve } = require('node:path');
const { operations, validSender, externalURL } = require('./policy.cjs');
const syncService = require('./sync.cjs');
app.setName('FeedAstrolabe Local');
app.enableSandbox();
if (process.env.FEEDASTROLABE_LOCAL_DATA_DIR) {
  const profile = resolve(process.env.FEEDASTROLABE_LOCAL_DATA_DIR, 'electron-profile');
  mkdirSync(profile, { recursive: true, mode: 0o700 });
  app.setPath('userData', profile);
}
const single = app.requestSingleInstanceLock();
if (!single) app.quit();
let child,
  endpoint,
  window,
  quitting = false,
  exiting = false;
const file = resolve(__dirname, '../ui/index.html');
const dataDir = resolve(
  process.env.FEEDASTROLABE_LOCAL_DATA_DIR || join(app.getPath('userData'), 'library'),
);
async function rpc(op, data = {}) {
  if (!operations.has(op)) throw new Error('未対応の操作です');
  if (!endpoint || !child || child.exitCode !== null)
    throw new Error('データサービスに接続できません');
  const response = await fetch(endpoint.url + '/rpc', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + endpoint.token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ op, data }),
    signal: AbortSignal.timeout(180000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '操作に失敗しました');
  return result.data;
}
function guard(event) {
  if (!validSender(event, window, file)) throw new Error('許可されていない送信元です');
}
function startBackend() {
  return new Promise((resolveReady, reject) => {
    const binary = app.isPackaged
      ? join(
          process.resourcesPath,
          'bin',
          process.platform === 'win32' ? 'feedastrolabe.exe' : 'feedastrolabe',
        )
      : join(
          __dirname,
          '..',
          'bin',
          process.platform === 'win32' ? 'feedastrolabe.exe' : 'feedastrolabe',
        );
    child = spawn(binary, ['--data-dir', dataDir, '--parent-stdin'], {
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    });
    const timeout = setTimeout(() => {
      child.kill();
      reject(new Error('データサービスの起動がタイムアウトしました'));
    }, 15000);
    const lines = createInterface({ input: child.stdout });
    lines.once('line', (line) => {
      try {
        const ready = JSON.parse(line),
          url = new URL(ready.url);
        if (
          ready.type !== 'ready' ||
          url.protocol !== 'http:' ||
          url.hostname !== '127.0.0.1' ||
          !/^[a-f0-9]{64}$/.test(ready.token)
        )
          throw new Error('起動情報が不正です');
        endpoint = ready;
        clearTimeout(timeout);
        resolveReady();
      } catch (e) {
        clearTimeout(timeout);
        reject(e);
      }
    });
    child.stderr.on('data', (bytes) => console.error('[Go]', bytes.toString().trim()));
    child.once('error', (e) => {
      clearTimeout(timeout);
      reject(e);
    });
    child.once('exit', () => {
      clearTimeout(timeout);
      endpoint = undefined;
      if (!quitting) {
        reject(new Error('データサービスが終了しました'));
        dialog.showErrorBox(
          'FeedAstrolabe Local',
          'データサービスが終了しました。アプリを再起動してください。',
        );
        app.quit();
      }
    });
  });
}
function createWindow() {
  window = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 680,
    minHeight: 540,
    show: false,
    backgroundColor: '#f4f5f8',
    title: 'FeedAstrolabe Local',
    webPreferences: {
      preload: join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event) => event.preventDefault());
  window.webContents.on('will-attach-webview', (event) => event.preventDefault());
  window.webContents.session.setPermissionRequestHandler((_wc, _permission, callback) =>
    callback(false),
  );
  window.webContents.session.setPermissionCheckHandler(() => false);
  window.webContents.session.webRequest.onBeforeRequest((details, callback) =>
    callback({
      cancel: !details.url.startsWith('file://') && !details.url.startsWith('devtools://'),
    }),
  );
  window.once('ready-to-show', () => window.show());
  window.on('closed', () => {
    syncService.close();
    window = undefined;
  });
  window.loadFile(file);
}
async function savePrivate(path, text) {
  const handle = await open(path, 'w', 0o600);
  try {
    await handle.chmod(0o600);
    await handle.writeFile(text, 'utf8');
    await handle.sync();
  } finally {
    await handle.close();
  }
}
function installHandlers() {
  ipcMain.handle('astrolabe:sync', async (event) => {
    guard(event);
    return syncService.synchronize(rpc);
  });
  ipcMain.handle('astrolabe:connection', async (event) => {
    guard(event);
    await syncService.openConnection(rpc, window);
  });
  ipcMain.handle('astrolabe:call', async (event, op, data) => {
    guard(event);
    if (op.startsWith('sync.') && !['sync.status', 'sync.settings'].includes(op))
      throw new Error('内部同期操作は呼び出せません');
    if (op === 'sync.settings') syncService.cancel();
    return rpc(op, data);
  });
  ipcMain.handle('astrolabe:external', async (event, raw) => {
    guard(event);
    await shell.openExternal(externalURL(raw));
  });
  ipcMain.handle('astrolabe:export', async (event, kind, id) => {
    guard(event);
    const kinds = {
      opml: ['opml.export', 'subscriptions.opml', 'OPML', ['opml']],
      settings: ['settings.export', 'settings.json', 'JSON', ['json']],
      backup: ['backup.export', 'feedastrolabe-backup.json', 'JSON', ['json']],
      report: ['case.report', 'report.md', 'Markdown', ['md']],
    };
    if (!Object.hasOwn(kinds, kind)) throw new Error('出力形式が不正です');
    const [op, name, label, extensions] = kinds[kind];
    const choice = await dialog.showSaveDialog(window, {
      defaultPath: name,
      filters: [{ name: label, extensions }],
    });
    if (choice.canceled) return false;
    const value = await rpc(op, kind === 'report' ? { id } : {});
    await savePrivate(
      choice.filePath,
      typeof value === 'string' ? value : JSON.stringify(value, null, 2),
    );
    return true;
  });
  ipcMain.handle('astrolabe:import', async (event, kind) => {
    guard(event);
    if (!['opml', 'settings', 'backup'].includes(kind)) throw new Error('入力形式が不正です');
    const choice = await dialog.showOpenDialog(window, {
      properties: ['openFile'],
      filters: [
        {
          name: kind === 'opml' ? 'OPML' : 'JSON',
          extensions: kind === 'opml' ? ['opml', 'xml'] : ['json'],
        },
      ],
    });
    if (choice.canceled) return null;
    const handle = await open(choice.filePaths[0], 'r');
    let text;
    try {
      const stats = await handle.stat();
      if (!stats.isFile() || stats.size > (kind === 'backup' ? 64 : 5) * 1024 * 1024)
        throw new Error('ファイルが大きすぎます');
      text = await handle.readFile('utf8');
    } finally {
      await handle.close();
    }
    if (kind === 'opml') return { text, items: await rpc('opml.preview', { text }) };
    if (kind === 'backup') {
      const answer = await dialog.showMessageBox(window, {
        type: 'warning',
        buttons: ['キャンセル', '復元する'],
        defaultId: 0,
        cancelId: 0,
        title: 'ライブラリを復元',
        message: '現在のライブラリを、このバックアップの内容で置き換えます。',
        detail: '復元前のライブラリはデータフォルダーのbackupsに自動保存します。',
      });
      if (answer.response !== 1) return null;
      return { restored: true, safetyBackup: await rpc('backup.restore', { text }) };
    }
    return { imported: true, result: await rpc('settings.import', JSON.parse(text)) };
  });
}
app.on('second-instance', () => {
  if (window) {
    if (window.isMinimized()) window.restore();
    window.focus();
  }
});
app.on('window-all-closed', () => app.quit());
app.on('before-quit', (event) => {
  quitting = true;
  if (!exiting && child && child.exitCode === null) {
    event.preventDefault();
    exiting = true;
    const timeout = setTimeout(() => child.kill('SIGKILL'), 6000);
    child.once('exit', () => {
      clearTimeout(timeout);
      app.quit();
    });
    child.stdin.end();
  }
});
if (single)
  app
    .whenReady()
    .then(async () => {
      await mkdir(dataDir, { recursive: true, mode: 0o700 });
      Menu.setApplicationMenu(
        Menu.buildFromTemplate([
          {
            label: app.name,
            submenu: [{ role: 'about' }, { type: 'separator' }, { role: 'quit' }],
          },
          {
            label: '編集',
            submenu: [
              { role: 'undo' },
              { role: 'redo' },
              { type: 'separator' },
              { role: 'cut' },
              { role: 'copy' },
              { role: 'paste' },
              { role: 'selectAll' },
            ],
          },
          {
            label: '表示',
            submenu: [
              { role: 'reload' },
              { role: 'toggleDevTools' },
              { role: 'resetZoom' },
              { role: 'zoomIn' },
              { role: 'zoomOut' },
              { role: 'togglefullscreen' },
            ],
          },
        ]),
      );
      installHandlers();
      await startBackend();
      createWindow();
      const timer = setInterval(async () => {
        if (quitting) return;
        try {
          const v = await rpc('sync.status');
          if (v.enabled) {
            await syncService.synchronize(rpc);
            if (window && !window.isDestroyed()) window.webContents.send('astrolabe:synchronized');
          }
        } catch {}
      }, 60000);
      timer.unref();
    })
    .catch((e) => {
      dialog.showErrorBox('起動できませんでした', e.message);
      app.quit();
    });
