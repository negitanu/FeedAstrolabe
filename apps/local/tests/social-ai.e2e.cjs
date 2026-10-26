const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { mkdtemp, rm, mkdir } = require('node:fs/promises');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
const { _electron } = require('playwright');
const root = resolve(__dirname, '..');
const digest = 'a'.repeat(64);
async function rpc(page, op, data = {}) {
  return page.evaluate(({ op, data }) => window.astrolabe.call(op, data), { op, data });
}
async function nav(page, name) {
  await page.locator('#main-nav').getByRole('button', { name, exact: true }).click();
}
test(
  'SNS and AI desktop workflows with explicit local Ollama fixture',
  { timeout: 90000 },
  async (t) => {
    const dir = await mkdtemp(join(tmpdir(), 'feedastrolabe-social-e2e-'));
    let desktop,
      postCount = 0;
    const server = http.createServer(async (request, response) => {
      response.setHeader('Content-Type', 'application/json');
      if (request.url === '/api/status')
        return response.end(JSON.stringify({ cloud: { disabled: true } }));
      if (request.url === '/api/tags')
        return response.end(
          JSON.stringify({ models: [{ name: 'feedastrolabe-fixture', digest }] }),
        );
      if (request.url === '/api/version')
        return response.end(JSON.stringify({ version: 'fixture-only' }));
      if (request.url === '/api/chat' && request.method === 'POST') {
        let body = '';
        for await (const chunk of request) body += chunk;
        const wire = JSON.parse(body),
          input = JSON.parse(wire.messages[1].content);
        const id = input.sources[0].id;
        postCount++;
        return response.end(
          JSON.stringify({
            model: 'feedastrolabe-fixture',
            done: true,
            done_reason: 'stop',
            prompt_eval_count: 100,
            eval_count: 50,
            message: {
              role: 'assistant',
              content: JSON.stringify({
                answer: 'ローカルの選択根拠に基づく検証用要約です。',
                claims: [{ text: '根拠の事実', citations: [id] }],
                uncertainty: '内容の真偽は未検証です。',
              }),
            },
          }),
        );
      }
      response.statusCode = 404;
      response.end('{}');
    });
    let fixtureAvailable = true;
    try {
      await new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(11434, '127.0.0.1', resolve);
      });
    } catch (error) {
      if (error.code === 'EADDRINUSE') fixtureAvailable = false;
      else throw error;
    }
    try {
      const executable = process.env.FEEDASTROLABE_TEST_EXECUTABLE;
      desktop = await _electron.launch({
        ...(executable ? { executablePath: executable } : {}),
        args: executable ? [] : [root],
        env: { ...process.env, FEEDASTROLABE_LOCAL_DATA_DIR: dir },
      });
      assert.equal(await desktop.evaluate(({ app }) => app.getVersion()), '0.2.0');
      const page = await desktop.firstWindow();
      const errors = [];
      page.on('pageerror', (error) => errors.push(error.message));
      await page.waitForFunction(
        () => document.querySelector('#article-count')?.textContent === '0 件の記事',
      );
      await rpc(page, 'settings.save', {
        ...(await rpc(page, 'bootstrap')).settings,
        pauseCollection: true,
      });
      await t.test(
        'SNS registration, provider settings and persistence without external calls',
        async () => {
          await nav(page, '集める');
          await page.getByRole('textbox', { name: 'SNS調査名', exact: true }).fill('SNS移植検証');
          await page
            .getByRole('textbox', { name: 'SNSの検索条件', exact: true })
            .fill('Go lang:ja');
          await page.getByRole('button', { name: 'SNSを登録', exact: true }).click();
          await page.waitForFunction(() =>
            document.querySelector('#social-detail')?.textContent.includes('Go lang:ja'),
          );
          const b = await rpc(page, 'bootstrap');
          assert.equal(b.feeds.length, 1);
          await rpc(page, 'feed.save', { ...b.feeds[0], paused: true });
          await nav(page, '設定');
          await page.getByRole('combobox', { name: 'AIプロバイダ', exact: true }).waitFor();
          await page
            .getByRole('textbox', { name: 'AIモデル', exact: true })
            .fill('openai/fixture-router');
          await page.getByRole('button', { name: 'AI接続を保存', exact: true }).click();
          await page.waitForFunction(() =>
            document.querySelector('#toast').textContent.includes('接続設定を保存'),
          );
          await page
            .getByRole('combobox', { name: 'AIプロバイダ', exact: true })
            .selectOption('orcarouter');
          await page.waitForFunction(
            () => document.querySelector('#ai-config-form input[name="model"]').value === '',
          );
          await page
            .getByRole('textbox', { name: 'AIモデル', exact: true })
            .fill('google/fixture-orca');
          await page.getByRole('button', { name: 'AI接続を保存', exact: true }).click();
          await page.waitForFunction(
            () =>
              document.querySelector('#ai-config-form input[name="model"]').value ===
              'google/fixture-orca',
          );
          await page
            .getByRole('combobox', { name: 'AIプロバイダ', exact: true })
            .selectOption('openrouter');
          await page.waitForFunction(
            () =>
              document.querySelector('#ai-config-form input[name="model"]').value ===
              'openai/fixture-router',
          );
          assert.equal(postCount, 0);
        },
      );
      await t.test(
        'local Ollama exact preview, explicit approval, citations and review',
        {
          skip:
            !fixtureAvailable && 'Port 11434 already belongs to a user runtime; no requests sent',
        },
        async () => {
          // Populate only synthetic article/evidence data through the normal versioned backup path.
          const backup = await rpc(page, 'backup.export');
          backup.tables.find((t) => t.name === 'articles').rows = [
            [
              1,
              1,
              'fixture-article',
              '検証用の公開資料',
              'https://example.com/public',
              '出典となる合成文章です。実際の利用者資料は含みません。',
              '2026-10-26T00:00:00Z',
              '2026-10-26T00:00:00Z',
              0,
              0,
              '',
            ],
          ];
          await rpc(page, 'backup.restore', { text: JSON.stringify(backup) });
          await page.reload();
          await page.waitForFunction(
            () => document.querySelector('#article-count').textContent === '1 件の記事',
          );
          await nav(page, '設定');
          await page
            .getByRole('combobox', { name: 'AIプロバイダ', exact: true })
            .selectOption('ollama-local');
          await page
            .getByRole('textbox', { name: 'AIモデル', exact: true })
            .fill('feedastrolabe-fixture');
          await page.locator('#ai-config-form input[name="digest"]').fill(digest);
          await page.locator('#ai-config-form input[name="enabled"]').check();
          await page.getByRole('button', { name: 'AI接続を保存', exact: true }).click();
          await page.waitForFunction(() =>
            document.querySelector('#toast').textContent.includes('接続設定を保存'),
          );
          await nav(page, '調べる');
          await page.getByRole('button', { name: '＋ 案件を作成' }).click();
          await page.locator('#dialog input[name="title"]').fill('AI移植調査');
          await page.locator('#dialog-confirm').click();
          await page
            .getByRole('button', { name: '根拠を保存', exact: true })
            .waitFor({ state: 'detached' });
          const b = await rpc(page, 'bootstrap'),
            caseId = b.cases[0].id;
          await rpc(page, 'evidence.capture', { caseId, articleId: 1 });
          await page.getByRole('button', { name: 'AI移植調査', exact: true }).click();
          await page.locator('.assistant-form input[name="evidenceId"]').check();
          await page
            .getByRole('textbox', { name: '調査補助への指示', exact: true })
            .fill('日本語で根拠を要約してください');
          await page.getByRole('button', { name: '送信内容をプレビュー', exact: true }).click();
          await page.locator('.assistant-preview pre').waitFor({ state: 'visible' });
          assert.match(
            await page.locator('.assistant-preview pre').textContent(),
            /出典となる合成文章/,
          );
          assert.equal(postCount, 0);
          await page.getByRole('button', { name: '承認して生成を予約', exact: true }).click();
          assert.equal(postCount, 0);
          await page
            .getByRole('checkbox', { name: '送信内容と費用を確認して承認する', exact: true })
            .check();
          await page.getByRole('button', { name: '承認して生成を予約', exact: true }).click();
          await page.waitForFunction(() =>
            document.querySelector('#toast').textContent.includes('予約しました'),
          );
          let completed;
          for (let attempt = 0; attempt < 200; attempt++) {
            const jobs = await rpc(page, 'ai.jobs', { kind: 'assistant', id: caseId });
            completed = jobs[0];
            if (completed?.state === 'succeeded' || completed?.state === 'failed') break;
            await new Promise((resolve) => setTimeout(resolve, 50));
          }
          assert.equal(completed?.state, 'succeeded', completed?.error);
          await page.getByRole('button', { name: '生成履歴を再読み込み', exact: true }).click();

          await page
            .locator('.ai-job > summary')
            .filter({ hasText: '成功・内容未検証' })
            .first()
            .click();
          await page.locator('.assistant-answer').waitFor({ state: 'visible' });
          assert.equal(postCount, 1);
          assert.match(await page.locator('.ai-job').textContent(), /\[E1\]/);
          await page.getByRole('button', { name: 'レビューを保存', exact: true }).click();
          await page.locator('#dialog select[name="status"]').selectOption('reviewed');
          await page.locator('#dialog textarea').fill('根拠との対応を確認しました');
          await page.locator('#dialog-confirm').click();
          await page.waitForFunction(() =>
            document.querySelector('#toast').textContent.includes('レビューを新しい版'),
          );
          const jobs = await rpc(page, 'ai.jobs', { kind: 'assistant', id: caseId });
          const reviews = await rpc(page, 'ai.reviews', { id: jobs[0].id });
          assert.equal(reviews[0].status, 'reviewed');
          await mkdir(join(root, 'test-results'), { recursive: true });
          await page.screenshot({ path: join(root, 'test-results/social-ai-research.png') });
          await page.locator('#case-classification').selectOption('restricted');
          await page.getByRole('button', { name: 'メモを保存', exact: true }).click();
          await page.waitForFunction(
            () => document.querySelector('#case-classification')?.value === 'restricted',
          );
          assert.equal(postCount, 1);
        },
      );
      assert.deepEqual(errors, []);
    } finally {
      if (desktop) await desktop.close();
      if (fixtureAvailable) await new Promise((resolve) => server.close(resolve));
      await rm(dir, { recursive: true, force: true });
    }
  },
);
