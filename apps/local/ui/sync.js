'use strict';
(async () => {
  const form = document.querySelector('#sync-form');
  const url = document.querySelector('#sync-url');
  const enabled = document.querySelector('#sync-enabled');
  const detail = document.querySelector('#sync-detail');
  let editing = false;
  let syncing = false;
  form.addEventListener('input', () => {
    editing = true;
  });
  async function status() {
    const v = await api.call('sync.status');
    if (!editing) {
      url.value = v.url;
      enabled.checked = v.enabled;
    }
    document.querySelector('#sync-now').disabled = !v.enabled || syncing;
    document.querySelector('#sync-connect').disabled = !v.url;
    detail.textContent =
      v.error ||
      (v.enabled
        ? `最終同期: ${v.lastSuccess ? date(v.lastSuccess) : '未実行'} · 送信待ち ${v.pending} 件`
        : '同期は停止中です。このデバイスだけで利用できます。');
  }
  form.addEventListener(
    'submit',
    safe(async (event) => {
      event.preventDefault();
      await api.call('sync.settings', { url: url.value.trim(), enabled: enabled.checked });
      editing = false;
      await status();
      toast('同期設定を保存しました');
    }),
  );
  document.querySelector('#sync-connect').addEventListener(
    'click',
    safe(async () => {
      await api.openConnection();
    }),
  );
  document.querySelector('#sync-now').addEventListener(
    'click',
    safe(async (event) => {
      const b = event.currentTarget;
      syncing = true;
      b.disabled = true;
      detail.textContent = '同期しています…';
      try {
        const result = await api.synchronize();
        if (result.busy) {
          toast('同期は実行中です');
          return;
        }
        if (result.cancelled) {
          toast('同期を停止しました');
          return;
        }
        await refreshLoaded();
        toast('同期しました');
      } finally {
        syncing = false;
        b.disabled = false;
        await status();
      }
    }),
  );
  async function refreshLoaded() {
    const loaded = state.articles.length,
      epoch = state.epoch,
      filter = JSON.stringify(state.filter);
    await boot();
    const items = [];
    let total = state.total,
      more = state.more;
    for (let offset = 0; offset < Math.max(loaded, 60); offset += 60) {
      const result = await api.call('articles', { ...JSON.parse(filter), offset });
      items.push(...result.items);
      total = result.total;
      more = result.hasMore;
      if (!result.hasMore) break;
    }
    if (epoch !== state.epoch || JSON.stringify(state.filter) !== filter) return;
    state.articles = items;
    state.total = total;
    state.more = more;
    const main = document.querySelector('#main'),
      scroll = main.scrollTop;
    renderArticles();
    main.scrollTop = scroll;
    document.querySelector('#article-count').textContent = `${total.toLocaleString()} 件の記事`;
    document.querySelector('#load-more').hidden = !more;
  }
  api.onSynchronized(async () => {
    try {
      await refreshLoaded();
      await status();
    } catch (e) {
      toast(message(e), true);
    }
  });
  await status();
  setInterval(() => {
    status().catch(() => {});
  }, 10000);
})().catch((e) => toast(message(e), true));
