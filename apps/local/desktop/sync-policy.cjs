'use strict';
function syncOrigin(raw) {
  const u = new URL(raw);
  if (
    u.username ||
    u.password ||
    u.search ||
    u.hash ||
    (u.pathname !== '/' && u.pathname !== '') ||
    (u.protocol !== 'https:' &&
      !(u.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(u.hostname)))
  )
    throw new Error('同期先はHTTPSのサイトURLを指定してください');
  return u.origin;
}
const accessMessage = '接続先を開いてCloudflare Accessの認証を確認し、再同期してください';
const missingAPIMessage =
  '接続先のWebに同期APIがありません。Webを更新して再起動してください（HTTP 404）';
function syncNetworkError(error) {
  const raw = String(error?.message || '');
  if (error?.name === 'TimeoutError' || /ERR_(?:TIMED_OUT|CONNECTION_TIMED_OUT)/.test(raw))
    return new Error('同期先への接続がタイムアウトしました');
  if (/ERR_NAME_NOT_RESOLVED/.test(raw))
    return new Error('同期先のホスト名を解決できません。接続先URLを確認してください');
  if (/ERR_CERT_|ERR_SSL_/.test(raw))
    return new Error('同期先のTLS証明書または暗号化接続を確認できません');
  return new Error(
    '同期通信に失敗しました。接続先URL・ネットワークを確認し、接続先を開いてCloudflare Accessの認証も確認してください',
  );
}
async function checkSyncReadiness(fetcher, origin, signal) {
  const endpoint = origin + '/api/sync/v1/exchange';
  const response = await fetcher(endpoint, {
    method: 'GET',
    credentials: 'include',
    redirect: 'follow',
    signal,
  }).catch((e) => {
    throw syncNetworkError(e);
  });
  try {
    if (response.url) {
      const target = new URL(response.url);
      if (target.origin !== origin || target.pathname !== '/api/sync/v1/exchange')
        throw new Error(accessMessage);
    }
    if ([401, 403].includes(response.status)) throw new Error(accessMessage);
    if (response.status === 404) throw new Error(missingAPIMessage);
    if (response.status !== 405)
      throw new Error(
        `同期APIの準備を確認できませんでした（HTTP ${response.status}）。接続先とAccess認証を確認してください`,
      );
  } finally {
    await response.body?.cancel().catch(() => {});
  }
}

async function readSyncJSON(response) {
  if ((response.status >= 300 && response.status < 400) || [401, 403].includes(response.status))
    throw new Error(accessMessage);
  if (response.status === 404) throw new Error(missingAPIMessage);
  if (!response.ok) throw new Error(`同期先がエラーを返しました（HTTP ${response.status}）`);
  if (!(response.headers.get('content-type') || '').startsWith('application/json'))
    throw new Error('同期先がJSONを返しませんでした。接続先とAccess認証を確認してください');
  const limit = 10 * 1024 * 1024;
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) throw new Error('同期応答が大きすぎます');
      chunks.push(Buffer.from(value));
    }
  } catch (e) {
    await reader.cancel().catch(() => {});
    throw e;
  } finally {
    reader.releaseLock();
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw new Error('同期応答のJSONが不正です');
  }
}
module.exports = { syncOrigin, readSyncJSON, checkSyncReadiness, syncNetworkError };
