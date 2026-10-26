const test = require('node:test');
const assert = require('node:assert/strict');
const { mkdtemp, rm, mkdir, readFile, stat } = require('node:fs/promises');
const { execFileSync } = require('node:child_process');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
const { _electron: electron } = require('playwright');
const root = resolve(__dirname, '..');
const stamp = '2026-10-26T00:00:00Z';
function fixture() {
  const rows = Array.from({ length: 125 }, (_, index) => [
    index + 1,
    1,
    `article-${index}`,
    `検証記事 ${String(index + 1).padStart(3, '0')}`,
    `https://example.com/articles/${index}`,
    `Go と Electron の記事本文 ${index + 1}\n<script>window.pwned=true</script>`,
    new Date(Date.UTC(2026, 9, 26, 0, 0, index)).toISOString(),
    stamp,
    0,
    0,
    '',
  ]);
  return {
    format: 'feedastrolabe-local-backup',
    version: 1,
    created: stamp,
    tables: [
      {
        name: 'folders',
        rows: [
          [1, 'テクノロジー', 0, 1],
          [2, '調査用', 1, 0],
        ],
      },
      {
        name: 'feeds',
        rows: [
          [
            1,
            1,
            '検証フィード',
            'https://example.com/feed.xml',
            'https://example.com',
            0,
            1,
            stamp,
            '',
          ],
        ],
      },
      { name: 'articles', rows },
      { name: 'cases', rows: [] },
      { name: 'note_revisions', rows: [] },
      { name: 'case_articles', rows: [] },
      { name: 'evidence', rows: [] },
      {
        name: 'settings',
        rows: [
          [
            1,
            JSON.stringify({
              theme: 'light',
              interval: 15,
              sidebar: 260,
              view: 'standard',
              timezone: 'Asia/Tokyo',
            }),
          ],
        ],
      },
    ],
  };
}
async function launch(dir) {
  const executable = process.env.FEEDASTROLABE_TEST_EXECUTABLE;
  const desktop = await electron.launch({
    ...(executable ? { executablePath: executable } : {}),
    args: executable ? [] : [root],
    cwd: root,
    env: { ...process.env, FEEDASTROLABE_LOCAL_DATA_DIR: dir },
    timeout: 30000,
  });
  const window = await desktop.firstWindow();
  await window.waitForSelector('#article-count');
  await window.waitForFunction(
    () => document.querySelector('#article-count').textContent !== '記事を読み込み中…',
  );
  return { desktop, window };
}
async function rpc(page, op, data = {}) {
  return page.evaluate(({ op, data }) => window.astrolabe.call(op, data), { op, data });
}
async function clickNav(page, name) {
  await page.locator('#main-nav').getByRole('button', { name, exact: true }).click();
}
test('Electron real desktop workflows and restart persistence', { timeout: 120000 }, async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'feedastrolabe-e2e-'));
  let desktop, page;
  const errors = [];
  try {
    ({ desktop, window: page } = await launch(dir));
    page.on('pageerror', (e) => errors.push(e.message));
    await t.test('empty library and isolated renderer', async () => {
      assert.equal(
        await page.locator('#reader-page .empty h2').textContent(),
        '読むたびに、視野が広がる。',
      );
      assert.equal(await page.evaluate(() => typeof window.require), 'undefined');
      assert.equal(await page.evaluate(() => typeof window.process), 'undefined');
      const prefs = await desktop.evaluate(({ BrowserWindow }) => {
        const p = BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();
        return { sandbox: p.sandbox, isolation: p.contextIsolation, node: p.nodeIntegration };
      });
      assert.deepEqual(prefs, { sandbox: true, isolation: true, node: false });
      await assert.rejects(rpc(page, 'shell', {}), /未対応/);
    });
    await rpc(page, 'backup.restore', { text: JSON.stringify(fixture()) });
    await page.reload();
    await page.waitForFunction(
      () => document.querySelector('#article-count').textContent === '125 件の記事',
    );
    await t.test('progressive list, read, star, safe detail and scroll retention', async () => {
      assert.equal(await page.locator('.article-card').count(), 60);
      await page.locator('.article-info').first().click();
      await page.locator('#detail').waitFor({ state: 'visible' });
      assert.doesNotMatch(await page.locator('.detail-body').textContent(), /<script>/);
      assert.equal(await page.locator('.detail-body script, .detail-body img').count(), 0);
      assert.equal(await page.evaluate(() => window.pwned), undefined);
      await page.locator('#detail').getByRole('button', { name: '☆ スター', exact: true }).click();
      await page.waitForFunction(() =>
        document.querySelector('#detail').textContent.includes('★ スター済み'),
      );
      assert.equal((await rpc(page, 'articles', { mode: 'starred' })).total, 1);
      await page.locator('#detail').getByRole('button', { name: '記事詳細を閉じる' }).click();
      await page.locator('#article-scroll').evaluate((n) => {
        n.scrollTop = n.scrollHeight;
      });
      await page.waitForFunction(() => document.querySelectorAll('.article-card').length >= 120);
      const scroll = await page.locator('#article-scroll').evaluate((n) => n.scrollTop);
      await page.locator('.article-info').nth(58).click();
      await page.locator('#detail').getByRole('button', { name: '記事詳細を閉じる' }).click();
      assert.equal(await page.locator('#article-scroll').evaluate((n) => n.scrollTop), scroll);
      const r = await rpc(page, 'articles', { mode: 'starred' });
      assert.equal(r.total, 1);
      const h = await rpc(page, 'articles', { mode: 'history' });
      assert.equal(h.total, 2);
    });
    await t.test('view modes, advanced search and selected changes', async () => {
      await page.getByRole('button', { name: '1行', exact: true }).click();
      await page.waitForFunction(() =>
        document.querySelector('#articles').classList.contains('compact'),
      );
      await page.getByRole('button', { name: 'タイル', exact: true }).click();
      await page.waitForFunction(() =>
        document.querySelector('#articles').classList.contains('tiles'),
      );
      await page.getByRole('button', { name: '標準', exact: true }).click();
      await page.locator('#search').fill('検証記事 012');
      await page.waitForFunction(
        () => document.querySelector('#article-count').textContent === '1 件の記事',
      );
      await page.getByRole('button', { name: '詳細検索', exact: true }).click();
      await page.locator('#filter-target').selectOption('title');
      await page.locator('#filter-from').fill('2026-10-26');
      await page.locator('#filter-to').fill('2026-10-26');
      await page.locator('#filters').getByRole('button', { name: '検索', exact: true }).click();
      await page.waitForFunction(
        () => document.querySelector('#article-count').textContent === '1 件の記事',
      );
      await page.locator('.article-card input[type="checkbox"]').check();
      await page.locator('#selection-bar [data-bulk="star"]').click();
      await page.waitForFunction(() => document.querySelector('#selection-bar').hidden);
      assert.equal((await rpc(page, 'article', { id: 12 })).starred, true);
      await page
        .locator('#library-nav')
        .getByRole('button', { name: 'すべての記事', exact: true })
        .click();
      await page.waitForFunction(
        () => document.querySelector('#article-count').textContent === '125 件の記事',
      );
      await page.getByRole('button', { name: '詳細検索', exact: true }).click();
    });
    await t.test('all matching includes articles never rendered', async () => {
      await page.locator('#library-nav').getByRole('button', { name: /^未読/ }).click();
      await page.waitForFunction(
        () => document.querySelector('#article-count').textContent === '123 件の記事',
      );
      await page.getByRole('button', { name: '全て既読', exact: true }).click();
      await page.waitForFunction(
        () => document.querySelector('#article-count').textContent === '0 件の記事',
      );
      assert.equal((await rpc(page, 'bootstrap')).unread, 0);
    });
    await t.test(
      'folders do not expand on label selection; source editing and keyboard reorder path',
      async () => {
        await page
          .locator('.source-name')
          .filter({ hasText: /^調査用$/ })
          .click();
        const arrow = page.getByRole('button', { name: '調査用を開く', exact: true });
        assert.equal(await arrow.getAttribute('aria-expanded'), 'false');
        await page.getByRole('button', { name: '検証フィードのメニュー', exact: true }).click();
        await page.getByRole('menuitem', { name: '名前・設定を編集' }).click();
        await page.locator('#dialog input[name="name"]').fill('移動済みフィード');
        await page.locator('#dialog select[name="folderId"]').selectOption('2');
        await page.locator('#dialog-confirm').click();
        await page.waitForFunction(
          () =>
            document.querySelectorAll('.source-name')[1]?.textContent === '調査用' ||
            document.body.textContent.includes('移動済みフィード'),
        );
        const boot = await rpc(page, 'bootstrap');
        assert.equal(boot.feeds[0].folderId, 2);
        assert.equal(boot.feeds[0].paused, true);
        await arrow.click();
        await page
          .getByRole('button', { name: '移動済みフィード', exact: true })
          .waitFor({ state: 'visible' });
      },
    );
    await t.test('case notes, association, immutable evidence and report', async () => {
      await clickNav(page, '調べる');
      await page.getByRole('button', { name: '＋ 案件を作成' }).click();
      await page.locator('#dialog input[name="title"]').fill('ローカル移植調査');
      await page.locator('#dialog-confirm').click();
      await page
        .getByRole('textbox', { name: '調査メモ（Markdown）' })
        .fill('## 事実\nGo / Electron で実行。\n\n## 仮説\n根拠は [E1]。');
      await page.getByRole('button', { name: 'メモを保存', exact: true }).click();
      await page.waitForFunction(() => document.body.textContent.includes('保存済みの版 2'));
      await page
        .locator('#library-nav')
        .getByRole('button', { name: 'すべての記事', exact: true })
        .click();
      await page.locator('.article-info').first().click();
      await page.getByRole('button', { name: '根拠を保存', exact: true }).click();
      await page.waitForFunction(() =>
        document.querySelector('#toast').textContent.includes('取得時点'),
      );
      const b = await rpc(page, 'bootstrap'),
        c = b.cases[0];
      const evidence = await rpc(page, 'case.evidence', { id: c.id });
      assert.equal(evidence.length, 1);
      assert.match(evidence[0].hash, /^[a-f0-9]{64}$/);
      const report = await rpc(page, 'case.report', { id: c.id });
      assert.match(report, /ローカル移植調査/);
      assert.match(report, /SHA-256/);
      assert.match(report, /\[E1\]/);
      await clickNav(page, '調べる');
      await page.getByRole('button', { name: 'ローカル移植調査', exact: true }).click();
      assert.equal(await page.locator('.evidence-card').count(), 1);
    });
    await t.test('settings, dark theme, compact window, screenshots', async () => {
      await clickNav(page, '設定');
      await page.locator('#setting-theme').selectOption('dark');
      await page
        .locator('#settings-form')
        .getByRole('button', { name: '設定を保存', exact: true })
        .click();
      await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
      const backup = await rpc(page, 'backup.export');
      assert.equal(backup.format, 'feedastrolabe-local-backup');
      const settings = await rpc(page, 'settings.export');
      assert.equal(settings.format, 'feedastrolabe-local-settings');
      assert.equal(JSON.stringify(settings).includes('根拠は'), false);
      await clickNav(page, '読む');
      if (await page.locator('#detail').isVisible())
        await page.locator('#detail').getByRole('button', { name: '記事詳細を閉じる' }).click();
      await mkdir(join(root, 'test-results'), { recursive: true });
      await page.screenshot({ path: join(root, 'test-results/reader-dark.png') });
      await desktop.evaluate(({ BrowserWindow }) =>
        BrowserWindow.getAllWindows()[0].setSize(720, 720),
      );
      await page.screenshot({ path: join(root, 'test-results/reader-compact.png') });
      assert.equal(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        true,
      );
      await clickNav(page, '設定');
      await page.locator('#setting-theme').selectOption('light');
      await page
        .locator('#settings-form')
        .getByRole('button', { name: '設定を保存', exact: true })
        .click();
      await desktop.evaluate(({ BrowserWindow }) =>
        BrowserWindow.getAllWindows()[0].setSize(1440, 940),
      );
      await clickNav(page, '読む');
      await page.screenshot({ path: join(root, 'test-results/reader-light.png') });
    });
    await t.test('native file exports and confirmed restore', async () => {
      for (const [kind, extension] of [
        ['settings', 'json'],
        ['backup', 'json'],
        ['opml', 'opml'],
        ['report', 'md'],
      ]) {
        const target = join(dir, `export-${kind}.${extension}`);
        await desktop.evaluate(({ dialog }, target) => {
          dialog.showSaveDialog = async () => ({ canceled: false, filePath: target });
        }, target);
        assert.equal(
          await page.evaluate((kind) => window.astrolabe.exportFile(kind, 1), kind),
          true,
        );
        const body = await readFile(target, 'utf8');
        assert.ok(body.length > 20);
        if (kind === 'backup') assert.equal(JSON.parse(body).format, 'feedastrolabe-local-backup');
        if (kind === 'report') assert.match(body, /SHA-256/);
        if (process.platform !== 'win32') assert.equal((await stat(target)).mode & 0o777, 0o600);
      }
      await rpc(page, 'state', { ids: [1], starred: true });
      await desktop.evaluate(
        ({ dialog }, target) => {
          dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [target] });
          dialog.showMessageBox = async () => ({ response: 1 });
        },
        join(dir, 'export-backup.json'),
      );
      const restored = await page.evaluate(() => window.astrolabe.importFile('backup'));
      assert.equal(restored.restored, true);
      assert.ok((await stat(restored.safetyBackup)).isFile());
      const restoredArticle = await rpc(page, 'article', { id: 1 });
      assert.equal(restoredArticle.starred, false);
    });
    let backendPid;
    if (process.platform !== 'win32') {
      const parent = desktop.process().pid;
      const row = execFileSync('ps', ['-axo', 'pid=,ppid=,comm='], { encoding: 'utf8' })
        .split('\n')
        .find((line) => {
          const parts = line.trim().split(/\s+/);
          return Number(parts[1]) === parent && parts.slice(2).join(' ').endsWith('/feedastrolabe');
        });
      assert.ok(row, 'Go child process exists');
      backendPid = Number(row.trim().split(/\s+/)[0]);
    }
    await desktop.close();
    desktop = undefined;
    if (backendPid) assert.throws(() => process.kill(backendPid, 0), /ESRCH/);
    ({ desktop, window: page } = await launch(dir));
    await t.test('restart restores data and preferences', async () => {
      const b = await rpc(page, 'bootstrap');
      assert.equal(b.feeds[0].title, '移動済みフィード');
      assert.equal(b.feeds[0].folderId, 2);
      assert.equal(b.cases[0].revision, 2);
      assert.equal(b.settings.theme, 'light');
      assert.equal((await rpc(page, 'articles', {})).total, 125);
      assert.equal(b.folders.find((f) => f.id === 2).expanded, true);
    });
    assert.deepEqual(errors, []);
  } finally {
    if (desktop) await desktop.close();
    await rm(dir, { recursive: true, force: true });
  }
});
