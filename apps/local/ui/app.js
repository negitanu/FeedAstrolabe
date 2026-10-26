'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const api = window.astrolabe;
const state = {
  boot: null,
  page: 'reader',
  filter: { mode: 'all', sort: 'newest' },
  articles: [],
  total: 0,
  more: false,
  selected: new Set(),
  detail: null,
  caseId: 0,
  loading: false,
  epoch: 0,
  drag: null,
};
const modes = { all: 'すべての記事', unread: '未読', starred: 'スター', history: '閲覧履歴' };
const pageNames = {
  reader: '読む',
  collect: '集める',
  research: '調べる',
  reports: 'まとめる',
  settings: '設定',
};
function el(tag, attrs = {}, children = []) {
  const n = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null) continue;
    if (key === 'text') n.textContent = value;
    else if (key === 'class') n.className = value;
    else if (key.startsWith('on')) n.addEventListener(key.slice(2), value);
    else if (key === 'checked') n.checked = value;
    else n.setAttribute(key, value);
  }
  for (const c of children) if (c) n.append(typeof c === 'string' ? document.createTextNode(c) : c);
  return n;
}
function button(text, onClick, cls = 'subtle', attrs = {}) {
  return el('button', { type: 'button', text, class: cls, onclick: safe(onClick), ...attrs });
}
function safe(fn) {
  return async (event) => {
    try {
      await fn(event);
    } catch (e) {
      toast(message(e), true);
    }
  };
}
function message(e) {
  return String(e?.message || e).replace(/^Error invoking remote method '[^']+': Error: /, '');
}
let toastTimer;
function toast(text, error = false) {
  const box = $('#toast');
  box.textContent = text;
  box.classList.toggle('error', error);
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(
    () => {
      box.hidden = true;
    },
    error ? 10000 : 4500,
  );
}
function date(raw) {
  if (!raw) return '';
  const d = new Date(raw);
  return Number.isNaN(d.getTime())
    ? raw
    : new Intl.DateTimeFormat('ja-JP', {
        timeZone: state.boot?.settings.timezone || 'Asia/Tokyo',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }).format(d);
}
function option(value, text, selected) {
  const o = el('option', { value, text });
  o.selected = !!selected;
  return o;
}
function folderSelect(id = 0) {
  return el('select', { name: 'folderId', 'aria-label': 'フォルダー' }, [
    option(0, 'フォルダーなし', !id),
    ...state.boot.folders.map((f) => option(f.id, f.name, f.id === id)),
  ]);
}
function field(text, input) {
  return el('label', { text }, [input]);
}
function empty(title, description, action) {
  return el('div', { class: 'empty' }, [
    el('span', { text: '✧', 'aria-hidden': 'true' }),
    el('h2', { text: title }),
    el('p', { text: description }),
    action,
  ]);
}
async function boot() {
  state.boot = await api.call('bootstrap');
  state.social = await api.call('social.list');
  applySettings();
  renderSidebar();
  fillSettings();
  renderCases();
  renderReports();
}
function applySettings() {
  const v = state.boot.settings;
  document.documentElement.dataset.theme = v.theme;
  document.documentElement.style.setProperty('--sidebar-width', `${v.sidebar}px`);
  $('#resize').setAttribute('aria-valuenow', v.sidebar);
  $('#articles').className = v.view;
  $$('#view-controls button').forEach((b) => {
    const active = b.dataset.view === v.view;
    b.classList.toggle('active', active);
    b.setAttribute('aria-pressed', active);
  });
}
async function saveSettings(patch) {
  const next = { ...state.boot.settings, ...patch };
  await api.call('settings.save', next);
  state.boot.settings = next;
  applySettings();
  fillSettings();
}
function fillSettings() {
  if (!state.boot) return;
  $('#setting-pause').checked = !!state.boot.settings.pauseCollection;
  for (const key of ['theme', 'interval', 'view', 'timezone'])
    $(`#setting-${key}`).value = state.boot.settings[key];
}
function page(name) {
  state.page = name;
  $$('.page').forEach((p) => {
    p.hidden = p.id !== `${name}-page`;
  });
  $$('#main-nav button').forEach((b) => {
    b.classList.toggle('active', b.dataset.page === name);
    b.setAttribute('aria-current', b.dataset.page === name ? 'page' : 'false');
  });
  $('#main').setAttribute('aria-label', pageNames[name]);
  $('#location').textContent = name === 'reader' ? 'ライブラリ' : 'ワークスペース';
  $('#current-label').textContent = name === 'reader' ? filterTitle() : pageNames[name];
  if (name === 'settings') fillSettings();
  if (name === 'research') {
    renderCases();
    if (typeof renderSocialList === 'function') safe(renderSocialList)();
  }
  if (name === 'settings' && typeof renderAISettings === 'function') safe(renderAISettings)();
  if (name === 'collect' && typeof renderSocialForm === 'function') renderSocialForm();
  if (name === 'reports') renderReports();
}
function filterTitle() {
  if (state.filter.feedId)
    return state.boot?.feeds.find((f) => f.id === state.filter.feedId)?.title || '情報源';
  if (state.filter.folderId)
    return state.boot?.folders.find((f) => f.id === state.filter.folderId)?.name || 'フォルダー';
  if (state.filter.caseId)
    return state.boot?.cases.find((c) => c.id === state.filter.caseId)?.title || '案件';
  return modes[state.filter.mode || 'all'];
}
async function chooseFilter(filter) {
  state.filter = { ...filter, sort: filter.mode === 'history' ? 'history' : 'newest' };
  $('#search').value = '';
  $('#sort').value = state.filter.sort;
  clearAdvanced();
  closeDetail();
  page('reader');
  renderSidebar();
  await loadArticles(true);
}
function renderSidebar() {
  const nav = $('#library-nav');
  nav.replaceChildren();
  for (const [mode, symbol] of [
    ['all', '▤'],
    ['unread', '◉'],
    ['starred', '☆'],
    ['history', '◷'],
  ]) {
    const active =
      !state.filter.feedId &&
      !state.filter.folderId &&
      !state.filter.caseId &&
      state.filter.mode === mode;
    nav.append(
      el(
        'button',
        {
          class: `nav-row${active ? ' active' : ''}`,
          onclick: safe(() => chooseFilter({ mode })),
          'aria-current': active ? 'true' : 'false',
        },
        [
          el('span', { class: 'nav-symbol', text: symbol, 'aria-hidden': 'true' }),
          el('span', { text: modes[mode] }),
          mode === 'unread' ? el('span', { class: 'badge', text: state.boot.unread }) : null,
        ],
      ),
    );
  }
  const tree = $('#source-tree');
  tree.replaceChildren();
  if (!state.boot.feeds.length && !state.boot.folders.length)
    tree.append(
      el('div', { class: 'no-sources', text: '「集める」から、最初の情報源を追加してください。' }),
    );
  for (const folder of state.boot.folders) {
    const row = sourceRow('folder', folder);
    const arrow = button(
      folder.expanded ? '▾' : '▸',
      async () => {
        await api.call('folder.save', { ...folder, expanded: !folder.expanded });
        await boot();
      },
      'expand',
      {
        'aria-label': `${folder.name}を${folder.expanded ? '折り畳む' : '開く'}`,
        'aria-expanded': folder.expanded,
      },
    );
    row.prepend(arrow);
    tree.append(row);
    const group = el('div', { class: 'folder-feeds' });
    group.hidden = !folder.expanded;
    for (const feed of state.boot.feeds.filter((f) => f.folderId === folder.id))
      group.append(sourceRow('feed', feed));
    tree.append(group);
  }
  for (const feed of state.boot.feeds.filter((f) => !f.folderId))
    tree.append(sourceRow('feed', feed));
  const feeds = $('#filter-feeds');
  const selected = state.filter.feedIds || [];
  feeds.replaceChildren(
    ...state.boot.feeds.map((f) => option(f.id, f.title, selected.includes(f.id))),
  );
}
function sourceRow(kind, source) {
  const folder = kind === 'folder',
    active = folder ? state.filter.folderId === source.id : state.filter.feedId === source.id;
  const row = el('div', {
    class: `source-row${active ? ' active' : ''}${source.paused ? ' paused' : ''}`,
    draggable: 'true',
    'data-kind': kind,
    'data-id': source.id,
  });
  row.append(
    el('span', {
      class: 'source-icon',
      text: folder ? '▱' : source.paused ? 'Ⅱ' : '◔',
      'aria-hidden': 'true',
    }),
    button(
      folder ? source.name : source.title,
      () =>
        chooseFilter(
          folder ? { mode: 'all', folderId: source.id } : { mode: 'all', feedId: source.id },
        ),
      'source-name',
      {
        title: folder
          ? source.name
          : [
              source.title,
              source.url,
              source.lastError
                ? `取得エラー: ${source.lastError}`
                : source.paused
                  ? '購読停止中'
                  : '',
            ]
              .filter(Boolean)
              .join('\n'),
      },
    ),
    button('⋯', (event) => showSourceMenu(event, kind, source), 'more', {
      'aria-label': `${folder ? source.name : source.title}のメニュー`,
      'aria-haspopup': 'menu',
    }),
  );
  row.addEventListener('contextmenu', (event) => {
    event.preventDefault();
    showSourceMenu(event, kind, source);
  });
  row.addEventListener('dragstart', (event) => {
    state.drag = { kind, source };
    event.dataTransfer.setData('text/plain', `${kind}:${source.id}`);
    event.dataTransfer.effectAllowed = 'move';
  });
  row.addEventListener('dragover', (event) => {
    event.preventDefault();
    row.classList.add('drag-over');
  });
  row.addEventListener('dragleave', () => row.classList.remove('drag-over'));
  row.addEventListener(
    'drop',
    safe(async (event) => {
      event.preventDefault();
      row.classList.remove('drag-over');
      if (state.drag) await moveSource(state.drag, { kind, source });
      state.drag = null;
    }),
  );
  row.addEventListener('dragend', () => {
    state.drag = null;
    $$('.drag-over').forEach((n) => n.classList.remove('drag-over'));
  });
  return row;
}
function orderedSources() {
  return [
    ...state.boot.folders.map((f) => ({ kind: 'folder', id: f.id, folderId: 0 })),
    ...state.boot.feeds.map((f) => ({ kind: 'feed', id: f.id, folderId: f.folderId })),
  ];
}
async function moveSource(drag, target) {
  if (drag.kind === 'folder' && target.kind !== 'folder') return;
  if (drag.kind === target.kind && drag.source.id === target.source.id) return;
  let items = orderedSources();
  const from = items.findIndex((v) => v.kind === drag.kind && v.id === drag.source.id);
  const [moved] = items.splice(from, 1);
  if (drag.kind === 'feed')
    moved.folderId = target.kind === 'folder' ? target.source.id : target.source.folderId;
  let index =
    target.kind === 'folder' && drag.kind === 'feed'
      ? items.length
      : items.findIndex((v) => v.kind === target.kind && v.id === target.source.id);
  items.splice(index, 0, moved);
  await api.call('sources.order', { items });
  await boot();
}
async function nudgeSource(kind, source, direction) {
  const siblings =
    kind === 'folder'
      ? state.boot.folders
      : state.boot.feeds.filter((f) => f.folderId === source.folderId);
  const index = siblings.findIndex((v) => v.id === source.id),
    other = siblings[index + direction];
  if (!other) return;
  const items = orderedSources(),
    a = items.findIndex((v) => v.kind === kind && v.id === source.id),
    b = items.findIndex((v) => v.kind === kind && v.id === other.id);
  [items[a], items[b]] = [items[b], items[a]];
  await api.call('sources.order', { items });
  await boot();
}
function showSourceMenu(event, kind, source) {
  const menu = $('#context-menu');
  menu.replaceChildren();
  menu.append(button('名前・設定を編集', () => editSource(kind, source), '', { role: 'menuitem' }));
  if (kind === 'feed') {
    const sns = state.social?.find((v) => v.feedId === source.id);
    if (sns)
      menu.append(
        button('SNS調査・収集設定', () => showSocial(source.id), '', { role: 'menuitem' }),
      );
    menu.append(
      button(
        source.paused ? '購読を再開' : '購読を停止',
        async () => {
          await api.call('feed.save', { ...source, paused: !source.paused });
          await boot();
          toast(
            source.paused ? '購読を再開しました' : '購読を停止しました。保存記事は保持しています',
          );
        },
        '',
        { role: 'menuitem' },
      ),
    );
    menu.append(button('この情報源を更新', () => refresh(source.id), '', { role: 'menuitem' }));
  }
  menu.append(
    button('上へ移動', () => nudgeSource(kind, source, -1), '', { role: 'menuitem' }),
    button('下へ移動', () => nudgeSource(kind, source, 1), '', { role: 'menuitem' }),
    button(
      kind === 'folder' ? 'フォルダーを削除' : '購読と記事を削除',
      () => deleteSource(kind, source),
      'danger',
      { role: 'menuitem' },
    ),
  );
  const rect = event.currentTarget?.getBoundingClientRect();
  const x = event.type === 'contextmenu' ? event.clientX : rect?.right || 20,
    y = event.type === 'contextmenu' ? event.clientY : rect?.bottom || 20;
  menu.style.left = `${Math.min(x, innerWidth - 195)}px`;
  menu.style.top = `${Math.min(y, innerHeight - 280)}px`;
  menu.hidden = false;
  $('button', menu).focus();
}
function modal(title, nodes, confirmText = '保存') {
  return new Promise((resolve) => {
    const dialog = $('#dialog');
    $('#dialog-title').textContent = title;
    $('#dialog-body').replaceChildren(...nodes);
    $('#dialog-confirm').textContent = confirmText;
    const done = (value) => {
      $('#dialog-form').onsubmit = null;
      dialog.oncancel = null;
      dialog.close();
      resolve(value);
    };
    $('#dialog-form').onsubmit = (e) => {
      e.preventDefault();
      done(Object.fromEntries(new FormData(e.currentTarget)));
    };
    $('#dialog-close').onclick = () => done(null);
    $('#dialog-cancel').onclick = () => done(null);
    dialog.oncancel = (e) => {
      e.preventDefault();
      done(null);
    };
    dialog.showModal();
    const first = $('input, select, textarea', $('#dialog-body'));
    if (first) first.focus();
    else $('#dialog-cancel').focus();
  });
}
async function editSource(kind, source) {
  const input = el('input', {
    name: 'name',
    value: kind === 'folder' ? source.name : source.title,
    required: '',
    maxlength: '128',
  });
  const nodes = [field('名前', input)];
  if (kind === 'feed')
    nodes.push(
      field('フォルダー', folderSelect(source.folderId)),
      el('p', { text: source.url }),
      el('p', {
        text: source.lastError
          ? `最終取得エラー: ${source.lastError}`
          : `最終取得: ${date(source.lastFetched) || '未取得'}`,
      }),
    );
  if (kind === 'feed' && !state.social?.some((v) => v.feedId === source.id))
    nodes.push(
      field(
        '収集間隔（秒）',
        el('input', {
          name: 'interval',
          type: 'number',
          min: 60,
          max: 86400,
          value: source.interval || state.boot.settings.interval * 60,
        }),
      ),
    );
  const result = await modal(kind === 'folder' ? 'フォルダーを編集' : '情報源を編集', nodes);
  if (!result) return;
  await api.call(
    kind === 'folder' ? 'folder.save' : 'feed.save',
    kind === 'folder'
      ? { ...source, name: result.name }
      : {
          ...source,
          title: result.name,
          folderId: Number(result.folderId),
          interval: result.interval === undefined ? source.interval : Number(result.interval),
        },
  );
  await boot();
  $('#current-label').textContent = filterTitle();
}
async function deleteSource(kind, source) {
  const yes = await modal(
    '削除の確認',
    [
      el('p', {
        text:
          kind === 'folder'
            ? `「${source.name}」を削除します。中の購読と記事は「フォルダーなし」に残ります。`
            : `「${source.title}」とその記事・既読・スターを削除します。保存済みの根拠は残ります。`,
      }),
    ],
    '削除する',
  );
  if (!yes) return;
  await api.call('source.delete', { kind, id: source.id });
  await boot();
  await chooseFilter({ mode: 'all' });
}
async function refresh(id = 0) {
  const control = $('#refresh');
  control.disabled = true;
  $('#sync-status').textContent = '収集中…';
  try {
    const result = await api.call('feeds.refresh', { id });
    await boot();
    if (state.page === 'reader' && !state.detail) await loadArticles(true);
    toast(
      result.errors.length
        ? `${result.updated}件更新。${result.errors.join('\n')}`
        : `${result.updated}件の情報源を更新しました`,
      result.errors.length > 0,
    );
  } finally {
    control.disabled = false;
    $('#sync-status').textContent = 'ローカルライブラリ';
  }
}
function clearAdvanced() {
  for (const id of ['filter-any', 'filter-exclude', 'filter-from', 'filter-to'])
    $(`#${id}`).value = '';
  $('#filter-target').value = '';
  $$('#filter-feeds option').forEach((o) => {
    o.selected = false;
  });
}
function applyFilters() {
  state.filter = {
    ...state.filter,
    query: $('#search').value,
    any: $('#filter-any').value,
    exclude: $('#filter-exclude').value,
    target: $('#filter-target').value,
    from: $('#filter-from').value,
    to: $('#filter-to').value,
    feedIds: $$('#filter-feeds option:checked').map((o) => Number(o.value)),
    sort: $('#sort').value,
  };
}
async function loadArticles(reset = false) {
  if (!state.boot) return;
  if (state.loading && !reset) return;
  if (reset) {
    state.epoch++;
    state.selected.clear();
    state.articles = [];
    state.total = 0;
    state.more = false;
    closeDetail();
  }
  const epoch = state.epoch;
  state.loading = true;
  $('#load-more').disabled = true;
  let offset = state.articles.length;
  if (state.filter.mode === 'unread') offset = state.articles.filter((a) => !a.read).length;
  try {
    const result = await api.call('articles', { ...state.filter, offset });
    if (epoch !== state.epoch) return;
    const seen = new Set(state.articles.map((a) => a.id));
    state.articles.push(...result.items.filter((a) => !seen.has(a.id)));
    state.total = result.total;
    state.more = result.hasMore;
    if (reset) renderArticles();
    else appendArticles(result.items.filter((a) => !seen.has(a.id)));
    $('#article-count').textContent = `${state.total.toLocaleString()} 件の記事`;
    $('#load-more').hidden = !state.more;
    updateSelection();
  } finally {
    if (epoch === state.epoch) {
      state.loading = false;
      $('#load-more').disabled = false;
    }
  }
}
function renderArticles() {
  $('#articles').replaceChildren();
  if (!state.articles.length) {
    $('#articles').append(
      state.boot.feeds.length
        ? empty('記事が見つかりません', '表示条件を変えるか、情報源を更新してください。')
        : empty(
            '読むたびに、視野が広がる。',
            'お気に入りのサイトやブログを登録して、あなただけのライブラリを育てましょう。',
            button('＋ 最初の情報源を追加', () => page('collect'), 'primary'),
          ),
    );
  } else appendArticles(state.articles);
}
function appendArticles(items) {
  const list = $('#articles');
  for (const a of items) list.append(articleCard(a));
}
// Build safe DOM nodes explicitly; remote article markup never owns attributes or scripts.
function richArticle(raw) {
  const box = el('div', { class: 'detail-body' });
  const doc = new DOMParser().parseFromString(raw, 'text/html');
  const allowed = new Set([
    'P',
    'BR',
    'A',
    'STRONG',
    'EM',
    'B',
    'I',
    'UL',
    'OL',
    'LI',
    'BLOCKQUOTE',
    'PRE',
    'CODE',
    'H2',
    'H3',
    'H4',
    'HR',
    'TABLE',
    'THEAD',
    'TBODY',
    'TR',
    'TH',
    'TD',
  ]);
  function copy(node, parent) {
    if (node.nodeType === Node.TEXT_NODE) {
      parent.append(document.createTextNode(node.textContent));
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    if (['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'SVG', 'MATH', 'TEMPLATE'].includes(node.tagName))
      return;
    let target = parent;
    if (allowed.has(node.tagName)) {
      target = document.createElement(node.tagName.toLowerCase());
      parent.append(target);
      if (node.tagName === 'A') {
        try {
          const u = new URL(node.getAttribute('href'));
          if (['http:', 'https:'].includes(u.protocol) && !u.username && !u.password) {
            target.href = u.href;
            target.addEventListener(
              'click',
              safe(async (e) => {
                e.preventDefault();
                await api.openExternal(u.href);
              }),
            );
          }
        } catch {}
      }
    }
    for (const child of node.childNodes) copy(child, target);
  }
  for (const child of doc.body.childNodes) copy(child, box);
  return box;
}
function articleExcerpt(raw) {
  return new DOMParser().parseFromString(raw, 'text/html').body.textContent;
}

function articleCard(a) {
  const checkbox = el('input', {
    type: 'checkbox',
    'aria-label': `${a.title}を選択`,
    checked: state.selected.has(a.id),
    onchange: safe((event) => {
      if (event.target.checked && state.selected.size >= 100) {
        event.target.checked = false;
        toast('一度に選択できるのは100件までです', true);
        return;
      }
      if (event.target.checked) state.selected.add(a.id);
      else state.selected.delete(a.id);
      event.target.closest('.article-card').classList.toggle('selected', event.target.checked);
      updateSelection();
    }),
  });
  const info = el(
    'div',
    {
      class: 'article-info',
      role: 'button',
      tabindex: '0',
      onclick: safe(() => openArticle(a.id)),
      onkeydown: safe(async (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          await openArticle(a.id);
        }
      }),
    },
    [
      el('div', { class: 'article-meta' }, [
        el('span', { class: 'feed-dot' }),
        el('span', { text: a.feedTitle }),
        el('span', { text: '·' }),
        el('time', { datetime: a.published, text: date(a.published) }),
        !a.read ? el('span', { class: 'unread-dot', 'aria-label': '未読' }) : null,
      ]),
      el('h2', { text: a.title }),
      el('p', { class: 'article-excerpt', text: articleExcerpt(a.content) }),
    ],
  );
  info.addEventListener(
    'auxclick',
    safe(async (event) => {
      if (event.button === 1 && a.url) {
        event.preventDefault();
        await api.openExternal(a.url);
      }
    }),
  );
  const star = button(
    a.starred ? '★' : '☆',
    () => toggleStar(a.id),
    `star-button${a.starred ? ' starred' : ''}`,
    { 'aria-label': a.starred ? 'スターを解除' : 'スターを付ける', 'aria-pressed': a.starred },
  );
  return el(
    'article',
    {
      class: `article-card${a.read ? ' read' : ''}${state.selected.has(a.id) ? ' selected' : ''}`,
      'data-id': a.id,
    },
    [checkbox, info, star],
  );
}
function updateCard(a) {
  const card = $(`.article-card[data-id="${a.id}"]`);
  if (card) card.replaceWith(articleCard(a));
}
function updateSelection() {
  $('#selection-bar').hidden = !state.selected.size;
  $('#selection-count').textContent = `${state.selected.size}件選択中`;
}
async function toggleStar(id) {
  const a = state.articles.find((a) => a.id === id) || state.detail;
  if (!a) return;
  await api.call('state', { ids: [id], starred: !a.starred });
  a.starred = !a.starred;
  updateCard(a);
  if (state.detail?.id === id) {
    state.detail.starred = a.starred;
    await renderDetail(state.detail);
  }
}
async function bulk(action) {
  const change = ['read', 'unread'].includes(action)
    ? { read: action === 'read' }
    : { starred: action === 'star' };
  await api.call('state', { ids: [...state.selected], ...change });
  await boot();
  await loadArticles(true);
}
async function markAll() {
  if (!state.total) return;
  const count = await api.call('state', { filter: state.filter, read: true });
  await boot();
  await loadArticles(true);
  toast(`${count}件を既読にしました`);
}
let detailEpoch = 0;
async function openArticle(id, push = true) {
  const epoch = ++detailEpoch;
  const a = await api.call('article', { id, visit: true });
  if (epoch !== detailEpoch) return;
  state.detail = a;
  const found = state.articles.find((v) => v.id === id);
  if (found) Object.assign(found, a);
  updateCard(a);
  if (push) history.pushState({ article: id }, '', `#article-${id}`);
  await renderDetail(a);
  await boot();
}
function closeDetail(updateHistory = true) {
  detailEpoch++;
  state.detail = null;
  $('#detail').hidden = true;
  $('#detail').replaceChildren();
  if (updateHistory && history.state?.article) history.replaceState({}, '', location.pathname);
}
async function renderDetail(a) {
  const panel = $('#detail');
  const top = el('div', { class: 'detail-close' }, [
    el('span', { text: a.feedTitle }),
    button('×', () => closeDetail(), 'icon-button', { 'aria-label': '記事詳細を閉じる' }),
  ]);
  panel.replaceChildren(
    top,
    el('h1', {}, [
      button(a.title, () => (a.url ? api.openExternal(a.url) : null), 'article-title-link'),
    ]),
    el('div', {
      class: 'detail-meta',
      text: `${date(a.published)} · ${state.boot.settings.timezone === 'UTC' ? 'UTC' : 'JST'}`,
    }),
  );
  const actions = el('div', { class: 'detail-actions' }, [
    button(
      a.read ? '未読に戻す' : '既読にする',
      async () => {
        await api.call('state', { ids: [a.id], read: !a.read });
        a.read = !a.read;
        const found = state.articles.find((v) => v.id === a.id);
        if (found) found.read = a.read;
        updateCard(a);
        await boot();
        await renderDetail(a);
      },
      'secondary',
    ),
    button(a.starred ? '★ スター済み' : '☆ スター', () => toggleStar(a.id), 'secondary'),
  ]);
  panel.append(
    actions,
    richArticle(a.content || '本文がありません。タイトルから元の記事を開けます。'),
  );
  const research = el('section', { class: 'detail-research' }, [
    el('h2', { text: '調査案件・根拠' }),
  ]);
  const cases = state.boot.cases.filter((c) => !c.archived);
  const select = el(
    'select',
    { 'aria-label': '関連付ける調査案件' },
    cases.length
      ? cases.map((c) => option(c.id, c.title))
      : [option('', '先に調査案件を作成してください')],
  );
  research.append(
    el('div', { class: 'button-row' }, [
      select,
      button(
        '関連付け',
        async () => {
          if (!select.value) return;
          await api.call('case.link', { caseId: Number(select.value), articleId: a.id });
          await renderDetail(a);
          toast('案件に関連付けました');
        },
        'secondary',
      ),
      button(
        '根拠を保存',
        async () => {
          if (!select.value) return;
          await api.call('evidence.capture', { caseId: Number(select.value), articleId: a.id });
          await renderDetail(a);
          toast('取得時点の根拠を保存しました');
        },
        'secondary',
      ),
    ]),
  );
  const index = state.articles.findIndex((v) => v.id === a.id);
  const pager = el('div', { class: 'detail-pagination' }, [
    button(
      '← 前の記事',
      () => (index > 0 ? openArticle(state.articles[index - 1].id, false) : null),
      'subtle',
      { ...(index <= 0 ? { disabled: '' } : {}) },
    ),
    el('span', { text: index >= 0 ? `${index + 1} / ${state.total}` : '' }),
    button(
      '次の記事 →',
      async () => {
        if (index + 1 >= state.articles.length && state.more) await loadArticles();
        if (state.articles[index + 1]) await openArticle(state.articles[index + 1].id, false);
      },
      'subtle',
      { ...(!state.more && index + 1 >= state.articles.length ? { disabled: '' } : {}) },
    ),
  ]);
  panel.append(research, pager);
  panel.hidden = false;
  panel.scrollTop = 0;
  const links = await api.call('article.links', { id: a.id });
  if (state.detail?.id !== a.id) return;
  for (const id of links) {
    const c = state.boot.cases.find((c) => c.id === id);
    if (c)
      research.append(
        el('div', { class: 'case-link-row' }, [
          el('span', { text: c.title }),
          button('開く', async () => {
            state.caseId = id;
            page('research');
            await openCase(id);
          }),
          button('関連解除', async () => {
            await api.call('case.unlink', { caseId: id, articleId: a.id });
            await renderDetail(a);
          }),
        ]),
      );
  }
}
async function discover(event) {
  event.preventDefault();
  const submit = $('button', event.currentTarget);
  submit.disabled = true;
  $('#feed-previews').replaceChildren(el('p', { text: 'フィードを確認しています…' }));
  try {
    const previews = await api.call('feed.preview', { url: $('#feed-url').value });
    $('#feed-previews').replaceChildren();
    for (const p of previews) {
      const name = el('input', { value: p.title || p.url, 'aria-label': '購読名', required: '' }),
        folder = folderSelect();
      const control = el('div', { class: 'preview-controls' }, [
        name,
        folder,
        button(
          '購読する',
          async (event) => {
            event.target.disabled = true;
            try {
              const id = await api.call('feed.subscribe', {
                url: p.url,
                title: name.value,
                folderId: Number(folder.value),
              });
              await boot();
              toast('購読を追加しました');
              await chooseFilter({ mode: 'all', feedId: id });
            } finally {
              event.target.disabled = false;
            }
          },
          'primary',
        ),
      ]);
      $('#feed-previews').append(
        el('section', { class: 'feed-preview' }, [
          el('h3', { text: p.title || 'フィード候補' }),
          el('div', { class: 'preview-url', text: p.url }),
          el(
            'ul',
            { class: 'preview-items' },
            p.items.slice(0, 5).map((a) => el('li', { text: a.title })),
          ),
          control,
        ]),
      );
    }
  } catch (e) {
    $('#feed-previews').replaceChildren(el('p', { text: message(e) }));
    throw e;
  } finally {
    submit.disabled = false;
  }
}
async function importOPML() {
  const result = await api.importFile('opml');
  if (!result) return;
  const target = $('#opml-preview');
  target.replaceChildren();
  const fresh = result.items.filter((v) => !v.duplicate && !v.error).length;
  target.append(
    el('p', { text: `${fresh}件を追加予定 / ${result.items.length - fresh}件は重複または無効` }),
  );
  for (const v of result.items)
    target.append(
      el('div', { class: 'opml-item', text: v.title }, [
        el('small', {
          text:
            v.error ||
            (v.duplicate ? '登録済み・重複のためスキップ' : v.folder || 'フォルダーなし'),
        }),
      ]),
    );
  if (fresh)
    target.append(
      button(
        'この内容で追加',
        async (event) => {
          event.target.disabled = true;
          try {
            const r = await api.call('opml.import', { text: result.text });
            await boot();
            target.replaceChildren(
              el('p', { text: `${r.added}件を追加しました。更新すると記事を取得します。` }),
            );
            toast(`${r.added}件の購読を追加しました`);
          } finally {
            event.target.disabled = false;
          }
        },
        'primary',
      ),
    );
}
function renderCases() {
  if (!state.boot) return;
  const list = $('#case-list');
  list.replaceChildren();
  for (const c of state.boot.cases)
    list.append(
      button('', () => openCase(c.id), `case-card${state.caseId === c.id ? ' active' : ''}`, {
        'aria-label': c.title,
      }),
    );
  $$('.case-card', list).forEach((node, i) => {
    const c = state.boot.cases[i];
    node.append(
      el('strong', { text: c.title }),
      el('small', { text: `${c.archived ? 'アーカイブ · ' : ''}${date(c.updated)}` }),
    );
  });
}
let caseEpoch = 0;
async function openCase(id) {
  const epoch = ++caseEpoch;
  state.caseId = id;
  renderCases();
  const c = state.boot.cases.find((c) => c.id === id);
  if (!c) return;
  const workspace = $('#case-workspace'),
    title = el('input', { value: c.title, required: '', maxlength: 128, 'aria-label': '案件名' }),
    note = el('textarea', {
      'aria-label': '調査メモ（Markdown）',
      placeholder:
        '## 事実\n\n## 情報源の主張\n\n## 仮説\n\n引用は [E1] のように根拠番号を記してください。',
    });
  note.value = c.note;
  const editor = el('form', { class: 'case-editor' }, [
    field('案件名', title),
    field(
      '公開区分',
      el('select', { id: 'case-classification', 'aria-label': '公開区分' }, [
        option('public', '公開', c.classification === 'public'),
        option('internal', '内部', c.classification === 'internal'),
        option('restricted', '制限', c.classification === 'restricted'),
      ]),
    ),
    field('調査メモ（Markdown）', note),
  ]);
  const save = el('button', { type: 'submit', class: 'primary', text: 'メモを保存' });
  editor.append(
    el('div', { class: 'form-actions' }, [
      save,
      button(c.archived ? '再開' : 'アーカイブ', async () => {
        await api.call('case.save', {
          ...c,
          title: title.value,
          note: note.value,
          archived: !c.archived,
          classification: $('#case-classification').value,
        });
        await boot();
        await openCase(id);
      }),
      el('small', { text: `保存済みの版 ${c.revision}` }),
    ]),
  );
  editor.addEventListener(
    'submit',
    safe(async (event) => {
      event.preventDefault();
      save.disabled = true;
      try {
        await api.call('case.save', {
          ...c,
          title: title.value,
          note: note.value,
          classification: $('#case-classification').value,
        });
        await boot();
        await openCase(id);
        toast('新しい版として保存しました');
      } finally {
        save.disabled = false;
      }
    }),
  );
  workspace.replaceChildren(editor);
  const [articles, evidence, revisions] = await Promise.all([
    api.call('articles', { caseId: id }),
    api.call('case.evidence', { id }),
    api.call('case.revisions', { id }),
  ]);
  if (epoch !== caseEpoch) return;
  const linked = el('section', { class: 'case-section' }, [
    el('h3', { text: `関連する記事 · ${articles.total}件` }),
  ]);
  if (!articles.total)
    linked.append(el('p', { text: '記事詳細の「関連付け」から、この案件に記事を追加できます。' }));
  for (const a of articles.items)
    linked.append(
      el('div', { class: 'linked-article' }, [
        button(
          a.title,
          async () => {
            await chooseFilter({ mode: 'all', caseId: id });
            await openArticle(a.id);
          },
          'article-link',
        ),
        button('根拠を保存', async () => {
          await api.call('evidence.capture', { caseId: id, articleId: a.id });
          await openCase(id);
          toast('根拠を保存しました');
        }),
        button('解除', async () => {
          await api.call('case.unlink', { caseId: id, articleId: a.id });
          await openCase(id);
        }),
      ]),
    );
  if (articles.hasMore)
    linked.append(
      button('関連する全記事を読む', () => chooseFilter({ mode: 'all', caseId: id }), 'secondary'),
    );
  const evidenceSection = el('section', { class: 'case-section' }, [
    el('h3', { text: `保存した根拠 · ${evidence.length}件` }),
  ]);
  for (const e of evidence)
    evidenceSection.append(
      el('details', { class: 'evidence-card' }, [
        el('summary', { text: `[E${e.id}] ${e.title}` }),
        el('small', { text: `保存: ${date(e.captured)} · ${e.url}` }),
        el('small', { text: `SHA-256: ${e.hash}` }),
        el('pre', { text: e.content }),
      ]),
    );
  const revs = el('details', { class: 'case-section' }, [
    el('summary', { text: `メモの版履歴 · ${revisions.length}版` }),
  ]);
  for (const r of revisions)
    revs.append(
      el('details', { class: 'revision-item' }, [
        el('summary', { text: `版 ${r.revision} · ${date(r.created)}` }),
        el('pre', { text: r.note || '（空のメモ）' }),
      ]),
    );
  workspace.append(linked, evidenceSection, revs);
  if (typeof appendAssistant === 'function') {
    const assistantRoot = el('div');
    workspace.append(assistantRoot);
    await appendAssistant(assistantRoot, c, evidence);
  }
}
function renderReports() {
  if (!state.boot) return;
  const list = $('#report-list');
  list.replaceChildren();
  if (!state.boot.cases.length)
    list.append(
      empty(
        '調査を、ひとつの成果に。',
        '「調べる」で案件を作成すると、メモと根拠を書き出せます。',
        button('調査案件へ', () => page('research'), 'primary'),
      ),
    );
  for (const c of state.boot.cases)
    list.append(
      el('div', { class: 'panel report-card' }, [
        el('div', {}, [
          el('h2', { text: c.title }),
          el('p', {
            text: `メモ版 ${c.revision} · ${date(c.updated)}${c.archived ? ' · アーカイブ' : ''}`,
          }),
        ]),
        button(
          'Markdown を保存',
          async () => {
            if (await api.exportFile('report', c.id)) toast('レポートを保存しました');
          },
          'secondary',
        ),
      ]),
    );
}
function wireEvents() {
  $$('#main-nav button').forEach((b) => b.addEventListener('click', () => page(b.dataset.page)));
  $('#new-folder').addEventListener(
    'click',
    safe(async () => {
      const result = await modal(
        'フォルダーを追加',
        [field('フォルダー名', el('input', { name: 'name', required: '', maxlength: '128' }))],
        '追加',
      );
      if (result) {
        await api.call('folder.save', { name: result.name });
        await boot();
      }
    }),
  );
  $('#refresh').addEventListener(
    'click',
    safe(() => refresh()),
  );
  $('#mark-all').addEventListener('click', safe(markAll));
  $('#toggle-filters').addEventListener('click', () => {
    $('#filters').hidden = !$('#filters').hidden;
    $('#toggle-filters').setAttribute('aria-expanded', !$('#filters').hidden);
  });
  $('#filters').addEventListener(
    'submit',
    safe(async (event) => {
      event.preventDefault();
      applyFilters();
      await loadArticles(true);
    }),
  );
  $('#clear-filters').addEventListener(
    'click',
    safe(async () => {
      clearAdvanced();
      applyFilters();
      await loadArticles(true);
    }),
  );
  let searchTimer;
  $('#search').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(
      safe(async () => {
        applyFilters();
        await loadArticles(true);
      }),
      300,
    );
  });
  $('#sort').addEventListener(
    'change',
    safe(async () => {
      applyFilters();
      await loadArticles(true);
    }),
  );
  $$('#view-controls button').forEach((b) =>
    b.addEventListener(
      'click',
      safe(() => saveSettings({ view: b.dataset.view })),
    ),
  );
  $$('#selection-bar [data-bulk]').forEach((b) =>
    b.addEventListener(
      'click',
      safe(() => bulk(b.dataset.bulk)),
    ),
  );
  $('#clear-selection').addEventListener('click', () => {
    state.selected.clear();
    renderArticles();
    updateSelection();
  });
  $('#load-more').addEventListener(
    'click',
    safe(() => loadArticles()),
  );
  const observer = new IntersectionObserver(
    (entries) => {
      if (
        entries.some((e) => e.isIntersecting) &&
        state.more &&
        !state.loading &&
        state.page === 'reader'
      )
        safe(() => loadArticles())();
    },
    { root: $('#article-scroll'), rootMargin: '150px' },
  );
  observer.observe($('#load-sentinel'));
  $('#discover-form').addEventListener('submit', safe(discover));
  $('#import-opml').addEventListener('click', safe(importOPML));
  for (const kind of ['opml', 'settings', 'backup'])
    $(`#export-${kind}`).addEventListener(
      'click',
      safe(async () => {
        if (await api.exportFile(kind)) toast('ファイルを保存しました');
      }),
    );
  $('#import-settings').addEventListener(
    'click',
    safe(async () => {
      const r = await api.importFile('settings');
      if (r) {
        await boot();
        toast('設定を読み込みました');
      }
    }),
  );
  $('#restore-backup').addEventListener(
    'click',
    safe(async () => {
      const r = await api.importFile('backup');
      if (r?.restored) {
        closeDetail();
        state.caseId = 0;
        await boot();
        await loadArticles(true);
        toast(`復元しました。復元前バックアップ: ${r.safetyBackup}`);
      }
    }),
  );
  $('#settings-form').addEventListener(
    'submit',
    safe(async (event) => {
      event.preventDefault();
      await saveSettings({
        pauseCollection: $('#setting-pause').checked,
        theme: $('#setting-theme').value,
        interval: Number($('#setting-interval').value),
        view: $('#setting-view').value,
        timezone: $('#setting-timezone').value,
      });
      toast('設定を保存しました');
    }),
  );
  $('#new-case').addEventListener(
    'click',
    safe(async () => {
      const result = await modal(
        '調査案件を作成',
        [field('案件名', el('input', { name: 'title', required: '', maxlength: '128' }))],
        '作成',
      );
      if (!result) return;
      const id = await api.call('case.save', { title: result.title, note: '' });
      await boot();
      await openCase(id);
    }),
  );
  document.addEventListener('click', (event) => {
    const menu = $('#context-menu');
    if (!menu.hidden && (!event.target.closest('.more') || event.target.closest('#context-menu')))
      menu.hidden = true;
    if (
      state.detail &&
      event.target.closest('#article-scroll') &&
      !event.target.closest('.article-info') &&
      !event.target.closest('.star-button') &&
      !event.target.closest('input')
    )
      closeDetail();
  });
  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      page('reader');
      $('#search').focus();
    }
    if (event.key === 'Escape') {
      $('#context-menu').hidden = true;
      if (!$('#dialog').open) closeDetail();
    }
  });
  window.addEventListener(
    'popstate',
    safe(async (event) => {
      if (event.state?.article) await openArticle(event.state.article, false);
      else closeDetail(false);
    }),
  );
  const resize = $('#resize');
  let start;
  resize.addEventListener('pointerdown', (event) => {
    start = { x: event.clientX, width: state.boot.settings.sidebar };
    resize.setPointerCapture(event.pointerId);
  });
  resize.addEventListener('pointermove', (event) => {
    if (start)
      document.documentElement.style.setProperty(
        '--sidebar-width',
        `${Math.min(520, Math.max(180, start.width + event.clientX - start.x))}px`,
      );
  });
  resize.addEventListener(
    'pointerup',
    safe(async (event) => {
      if (!start) return;
      const width = Math.min(520, Math.max(180, start.width + event.clientX - start.x));
      start = null;
      await saveSettings({ sidebar: width });
    }),
  );
  resize.addEventListener(
    'keydown',
    safe(async (event) => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        await saveSettings({
          sidebar: Math.min(
            520,
            Math.max(180, state.boot.settings.sidebar + (event.key === 'ArrowRight' ? 10 : -10)),
          ),
        });
      }
    }),
  );
}
async function init() {
  if (!api) throw new Error('Electronからアプリを起動してください');
  wireEvents();
  await boot();
  await loadArticles(true);
  if (typeof initSocialAI === 'function') initSocialAI();
}
init().catch((e) => {
  $('#articles').replaceChildren(empty('ライブラリを開けませんでした', message(e)));
  toast(message(e), true);
});
