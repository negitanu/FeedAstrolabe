const test = require('node:test');
const assert = require('node:assert/strict');
const { operations, externalURL, validSender } = require('../desktop/policy.cjs');
const { pathToFileURL } = require('node:url');
test('only HTTP(S) external URLs with no credentials', () => {
  assert.equal(externalURL('https://example.com/path'), 'https://example.com/path');
  for (const url of [
    'file:///etc/passwd',
    'javascript:alert(1)',
    'https://user:pass@example.com',
    'data:text/html,x',
  ])
    assert.throws(() => externalURL(url));
});
test('bridge authorizes the exact main frame and webContents', () => {
  const file = '/tmp/app/index.html',
    frame = { url: pathToFileURL(file).href },
    contents = { mainFrame: frame },
    window = { isDestroyed: () => false, webContents: contents };
  assert.equal(validSender({ sender: contents, senderFrame: frame }, window, file), true);
  assert.equal(
    validSender({ sender: contents, senderFrame: { url: frame.url } }, window, file),
    false,
  );
  frame.url += '#article-1';
  assert.equal(validSender({ sender: contents, senderFrame: frame }, window, file), true);
  frame.url = pathToFileURL(file).href + '?evil=1';
  assert.equal(validSender({ sender: contents, senderFrame: frame }, window, file), false);
  frame.url = 'https://evil.example';
  assert.equal(validSender({ sender: contents, senderFrame: frame }, window, file), false);
});
test('bridge has no arbitrary fetch, filesystem, shell or SQL operation', () => {
  for (const name of ['fetch', 'file.read', 'shell', 'sql', '__proto__', 'constructor'])
    assert.equal(operations.has(name), false);
});
