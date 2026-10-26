// Explicit opt-in: contacts only the official public Go blog feed using temporary data.
const assert = require('node:assert/strict');
const { mkdtemp, rm } = require('node:fs/promises');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
const { _electron } = require('playwright');
(async () => {
  const dir = await mkdtemp(join(tmpdir(), 'feedastrolabe-live-'));
  let desktop;
  try {
    desktop = await _electron.launch({
      args: [resolve(__dirname, '..')],
      env: { ...process.env, FEEDASTROLABE_LOCAL_DATA_DIR: dir },
    });
    const page = await desktop.firstWindow();
    await page.getByRole('button', { name: '集める', exact: true }).click();
    await page
      .getByRole('textbox', { name: 'WebサイトまたはフィードのURL' })
      .fill('https://go.dev/blog/feed.atom');
    await page.getByRole('button', { name: '候補を確認', exact: true }).click();
    await page.locator('.feed-preview').waitFor({ timeout: 45000 });
    assert.match(await page.locator('.feed-preview h3').textContent(), /Go Blog/);
    await page.getByRole('button', { name: '購読する', exact: true }).click();
    await page.locator('.article-card').first().waitFor({ timeout: 45000 });
    const bootstrap = await page.evaluate(() => window.astrolabe.call('bootstrap'));
    const articles = await page.evaluate(() => window.astrolabe.call('articles', {}));
    assert.equal(bootstrap.feeds.length, 1);
    assert.equal(bootstrap.feeds[0].lastError, '');
    assert.ok(articles.total > 0);
    console.log(
      `Real feed preview/subscription passed: ${articles.total} Go Blog articles; TLS12=${process.env.FEEDASTROLABE_LOCAL_TLS12 === '1'}`,
    );
  } finally {
    if (desktop) await desktop.close();
    await rm(dir, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
