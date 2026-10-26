const { pathToFileURL } = require('node:url');
const operations = new Set([
  'sync.status',
  'sync.settings',
  'sync.prepare',
  'sync.accept',
  'sync.error',
  'bootstrap',
  'social.list',
  'social.save',
  'social.detail',
  'social.refresh',
  'ai.state',
  'ai.config.save',
  'ai.global.save',
  'ai.topics.queue',
  'ai.assistant.preview',
  'ai.assistant.approve',
  'ai.jobs',
  'ai.review.save',
  'ai.reviews',
  'articles',
  'article',
  'state',
  'folder.save',
  'feed.save',
  'source.delete',
  'sources.order',
  'feed.preview',
  'feed.subscribe',
  'feeds.refresh',
  'opml.preview',
  'opml.import',
  'opml.export',
  'case.save',
  'case.revisions',
  'case.link',
  'case.unlink',
  'article.links',
  'evidence.capture',
  'case.evidence',
  'case.report',
  'settings.save',
  'settings.export',
  'settings.import',
  'backup.export',
  'backup.restore',
]);
function validSender(event, window, file) {
  if (
    !window ||
    window.isDestroyed() ||
    event.sender !== window.webContents ||
    event.senderFrame !== window.webContents.mainFrame
  )
    return false;
  try {
    const sender = new URL(event.senderFrame.url);
    sender.hash = '';
    return sender.href === pathToFileURL(file).href;
  } catch {
    return false;
  }
}
function externalURL(raw) {
  if (typeof raw !== 'string' || raw.length > 8192) throw new Error('URLが不正です');
  const url = new URL(raw);
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password)
    throw new Error('HTTP(S)のURLのみ開けます');
  return url.href;
}
module.exports = { operations, validSender, externalURL };
