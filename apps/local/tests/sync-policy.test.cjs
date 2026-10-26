const test = require('node:test');
const assert = require('node:assert/strict');
const { syncOrigin, readSyncJSON } = require('../desktop/sync-policy.cjs');
test('sync transport binds requests to a saved origin', () => {
  assert.equal(syncOrigin('https://reader.example/'), 'https://reader.example');
  assert.equal(syncOrigin('http://127.0.0.1:5123'), 'http://127.0.0.1:5123');
  for (const u of [
    'http://example.com',
    'file:///tmp/x',
    'https://u:p@example.com',
    'https://example.com/a',
    'https://example.com/?token=x',
  ])
    assert.throws(() => syncOrigin(u));
});
test('Access redirect, HTML and malformed/oversized JSON preserve pending work', async () => {
  await assert.rejects(
    readSyncJSON(new Response('', { status: 302, headers: { location: 'https://login.example' } })),
    /Access/,
  );
  await assert.rejects(
    readSyncJSON(new Response('<html>login</html>', { headers: { 'Content-Type': 'text/html' } })),
    /JSON/,
  );
  await assert.rejects(
    readSyncJSON(new Response('{', { headers: { 'Content-Type': 'application/json' } })),
    /JSON/,
  );
  await assert.rejects(
    readSyncJSON(
      new Response('x'.repeat(10 * 1024 * 1024 + 1), {
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
    /大きすぎ/,
  );
  assert.deepEqual(
    await readSyncJSON(
      new Response('{"version":1}', { headers: { 'Content-Type': 'application/json' } }),
    ),
    { version: 1 },
  );
});

test('read-only readiness separates login, missing deployment and connection failures', async () => {
  const { checkSyncReadiness, syncNetworkError } = require('../desktop/sync-policy.cjs');
  let observed;
  await checkSyncReadiness(async (url, options) => {
    observed = { url, ...options };
    return new Response('', { status: 405 });
  }, 'https://reader.example');
  assert.equal(observed.method, 'GET');
  assert.equal(observed.body, undefined);
  await assert.rejects(
    checkSyncReadiness(async () => new Response('', { status: 404 }), 'https://reader.example'),
    /同期APIがありません/,
  );
  await assert.rejects(
    checkSyncReadiness(async () => new Response('', { status: 403 }), 'https://reader.example'),
    /Access/,
  );
  await assert.rejects(
    checkSyncReadiness(
      async () => ({ status: 200, url: 'https://login.example/access', body: null }),
      'https://reader.example',
    ),
    /Access/,
  );
  assert.match(syncNetworkError(new Error('net::ERR_NAME_NOT_RESOLVED')).message, /ホスト名/);
  assert.match(syncNetworkError(new Error('net::ERR_CERT_AUTHORITY_INVALID')).message, /TLS/);
  assert.match(syncNetworkError({ name: 'TimeoutError' }).message, /タイムアウト/);
});
