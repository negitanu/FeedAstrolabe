const test = require('node:test');
const assert = require('node:assert/strict');
const { createServer } = require('node:http');
const { mkdtemp, rm } = require('node:fs/promises');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
const { _electron: electron } = require('playwright');
const root = resolve(__dirname, '..');
const events = [
  {
    id: '1'.padStart(32, '0'),
    clock: 10,
    kind: 'feed',
    key: ['https://example.org/sync-rss'],
    value: {
      title: '同期の情報源',
      folder: '同期フォルダー',
      enabled: 0,
      source: 'rss',
      kind: '',
      target: '',
      origin: '',
      interval: 900,
    },
  },
  {
    id: '2'.padStart(32, '0'),
    clock: 11,
    kind: 'article',
    key: ['https://example.org/sync-rss', 'a'],
    value: {
      title: '共有された記事',
      url: 'https://example.org/a',
      content: '同期本文',
      published: '2026-10-26T00:00:00Z',
      collected: '2026-10-26T00:00:00Z',
    },
  },
  {
    id: '3'.padStart(32, '0'),
    clock: 12,
    kind: 'read',
    key: ['https://example.org/sync-rss', 'a'],
    value: { value: 1 },
  },
];
test(
  'Electron sync session, optional standalone, settings and theme flows',
  { timeout: 90000 },
  async () => {
    const dir = await mkdtemp(join(tmpdir(), 'astrolabe-sync-ui-'));
    const journal = [...events];
    let mode = 'normal';
    let authorized = false;
    const server = createServer(async (req, res) => {
      if (req.url === '/') {
        res.setHeader('Set-Cookie', 'CF_Authorization=fixture; HttpOnly; SameSite=Lax; Path=/');
        res.end('<!doctype html><title>Access fixture</title>接続しました');
        return;
      }
      if (req.url === '/access-login') {
        res.setHeader('Content-Type', 'text/html');
        res.end('<html>Access login required</html>');
        return;
      }
      if (!req.headers.cookie?.includes('CF_Authorization=fixture')) {
        res.writeHead(302, { Location: '/access-login' });
        res.end();
        return;
      }
      authorized = true;
      if (mode === 'missing') {
        res.writeHead(404);
        res.end();
        return;
      }
      if (req.method === 'GET') {
        res.writeHead(405, { Allow: 'POST' });
        res.end();
        return;
      }
      if (mode === 'html') {
        res.setHeader('Content-Type', 'text/html');
        res.end('<html>Access expired</html>');
        return;
      }
      let raw = '';
      for await (const chunk of req) raw += chunk;
      const body = JSON.parse(raw);
      for (const ev of body.events) if (!journal.some((x) => x.id === ev.id)) journal.push(ev);
      res.setHeader('Content-Type', 'application/json');
      const selected = journal.slice(body.cursor, body.cursor + 100);
      res.end(
        JSON.stringify({
          version: 1,
          hub: 'f'.repeat(32),
          cursor: body.cursor + selected.length,
          more: body.cursor + selected.length < journal.length,
          events: selected,
        }),
      );
    });
    await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
    const origin = `http://127.0.0.1:${server.address().port}`;
    let desktop;
    try {
      desktop = await electron.launch({
        args: [root],
        cwd: root,
        env: { ...process.env, FEEDASTROLABE_LOCAL_DATA_DIR: dir },
        timeout: 30000,
      });
      const window = await desktop.firstWindow();
      await window.waitForFunction(
        () => document.querySelector('#article-count').textContent !== '記事を読み込み中…',
      );
      assert.equal(
        (await window.evaluate(() => window.astrolabe.call('sync.status'))).enabled,
        false,
      );
      await window.locator('[data-page="settings"]').click();
      const layout = await window.locator('#sync-enabled').evaluate((node) => {
        const box = node.getBoundingClientRect(),
          label = node.closest('label').getBoundingClientRect();
        return {
          width: box.width,
          height: box.height,
          centerDifference: Math.abs(box.top + box.height / 2 - (label.top + label.height / 2)),
        };
      });
      assert.ok(
        layout.width <= 18 && layout.height <= 18 && layout.centerDifference < 3,
        JSON.stringify(layout),
      );
      assert.equal(await window.locator('#sync-now').isEnabled(), false);
      await window.locator('#sync-url').fill(origin);
      await window.locator('#sync-enabled').check();
      await window.locator('#sync-form button[type="submit"]').click();
      await window.waitForFunction(() =>
        document.querySelector('#sync-detail').textContent.includes('未実行'),
      );
      // No Access cookie yet: fail without advancing either cursor or sent position.
      await window.locator('#sync-now').click();
      await window.waitForFunction(() =>
        document.querySelector('#sync-detail').textContent.includes('Access'),
      );
      let status = await window.evaluate(() => window.astrolabe.call('sync.status'));
      assert.equal(status.cursor, 0);
      assert.equal(status.sent, 0);
      const opened = desktop.waitForEvent('window');
      await window.locator('#sync-connect').click();
      const connection = await opened;
      await connection.waitForLoadState('domcontentloaded');
      assert.equal(await connection.evaluate(() => typeof window.astrolabe), 'undefined');
      await connection.close();
      await window.locator('#sync-now').click();
      await window.waitForFunction(
        () =>
          document.querySelector('#sync-detail').textContent.includes('最終同期') &&
          !document.querySelector('#sync-detail').textContent.includes('未実行'),
      );
      assert.equal(authorized, true);
      const articles = await window.evaluate(() => window.astrolabe.call('articles'));
      assert.equal(articles.total, 1);
      assert.equal(articles.items[0].read, true);
      // Theme and narrow screen do not hide sync form controls.
      for (const theme of ['light', 'dark', 'system']) {
        await window.evaluate((theme) => (document.documentElement.dataset.theme = theme), theme);
        await window.setViewportSize({ width: 720, height: 900 });
        await window.locator('#sync-url').scrollIntoViewIfNeeded();
        assert.equal(await window.locator('#sync-url').isVisible(), true);
      }
      status = await window.evaluate(() => window.astrolabe.call('sync.status'));
      mode = 'missing';
      await window.locator('#sync-now').click();
      await window.waitForFunction(() =>
        document.querySelector('#sync-detail').textContent.includes('同期APIがありません'),
      );
      assert.equal(
        (await window.evaluate(() => window.astrolabe.call('sync.status'))).cursor,
        status.cursor,
      );
      mode = 'html';
      await window.locator('#sync-now').click();
      await window.waitForFunction(() =>
        document.querySelector('#sync-detail').textContent.includes('JSON'),
      );
      assert.equal(
        (await window.evaluate(() => window.astrolabe.call('sync.status'))).cursor,
        status.cursor,
      );
      await window.locator('#sync-enabled').uncheck();
      await window.locator('#sync-form button[type="submit"]').click();
      await window.waitForFunction(() =>
        document.querySelector('#sync-detail').textContent.includes('停止中'),
      );
      assert.equal((await window.evaluate(() => window.astrolabe.call('articles'))).total, 1);
      await window.evaluate(async () => {
        let denied = false;
        try {
          await window.astrolabe.call('sync.prepare');
        } catch {
          denied = true;
        }
        if (!denied) throw new Error('internal sync RPC exposed');
      });
    } finally {
      if (desktop) await desktop.close();
      await new Promise((resolve) => server.close(resolve));
      await rm(dir, { recursive: true, force: true });
    }
  },
);
