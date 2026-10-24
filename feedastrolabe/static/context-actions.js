/* Context actions share server-rendered editors and their existing CSRF validation. */
(() => {
  'use strict';
  const menu = document.getElementById('object-menu');
  const dialog = document.getElementById('object-dialog');
  if (!menu || !dialog) return;
  const body = dialog.querySelector('[data-editor-body]');
  const title = dialog.querySelector('h2');
  const feedback = dialog.querySelector('[data-editor-feedback]');
  const close = dialog.querySelector('[data-editor-close]');
  const headers = {'X-Context-Editor': '1'};
  let trigger, editor, busy = false, changed = false, destination = location.href;
  const dirty = new Set();
  let loadVersion = 0, menuVersion = 0;
  document.querySelector('[data-settings-export]')?.addEventListener('submit',event=>{
    const values={};
    try{const saved=JSON.parse(localStorage.getItem('feedastrolabe.sidebar-width.v1'));if(saved?.version===1 && Number.isInteger(saved.width) && saved.width>=200 && saved.width<=480)values.width=saved.width;}catch{}
    try{const saved=JSON.parse(localStorage.getItem('feedastrolabe.article-layout.v1'));if(saved?.version===1 && ['standard','line','tiles'].includes(saved.layout))values.layout=saved.layout;}catch{}
    try{const saved=JSON.parse(localStorage.getItem('feedastrolabe.feed-folders.v2'));if(saved?.version===2 && saved.states && typeof saved.states==='object' && !Array.isArray(saved.states))values.disclosure=Object.fromEntries(Object.entries(saved.states).filter(([name,value])=>name.length<=80 && typeof value==='boolean'));}catch{}
    event.target.querySelector('[name=presentation]').value=JSON.stringify(values);
  });

  function objectURL(link) {
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin) return null;
    if (/^\/settings\/items\/(feeds|workspaces|watchlists|security|network|ai)\/\d+$/.test(url.pathname)) return url.pathname;
    const routes = [[/^\/workspaces\/(\d+)$/, 'workspaces'], [/^\/triage\/watchlists\/(\d+)$/, 'watchlists'],
      [/^\/security\/watches\/(\d+)$/, 'security'], [/^\/network\/watches\/(\d+)$/, 'network'],
      [/^\/ai-research\/watches\/(\d+)$/, 'ai'], [/^\/social-research\/(\d+)$/, 'feeds']];
    for (const [pattern, kind] of routes) {
      const match = url.pathname.match(pattern);
      if (match) return `/settings/items/${kind}/${match[1]}`;
    }
    if (url.pathname === '/' && /^\d+$/.test(url.searchParams.get('feed') || '')) return `/settings/items/feeds/${url.searchParams.get('feed')}`;
    return null;
  }
  // Add the same controls to registered object links throughout the application.
  for (const link of document.querySelectorAll('a[href]')) {
    if (link.closest('.prose,.article-list,.article-detail,[data-context-editor],[data-context-folder]')) continue;
    const url = objectURL(link);
    if (!url) continue;
    const wrapper = document.createElement('span');
    wrapper.className = 'context-object';
    wrapper.dataset.contextEditor = url;
    wrapper.dataset.contextLabel = link.textContent.trim();
    link.before(wrapper); wrapper.append(link);
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'context-trigger'; button.dataset.contextTrigger = '';
    button.textContent = '⋯'; button.setAttribute('aria-label', `${link.textContent.trim()} の操作`);
    button.setAttribute('aria-haspopup', 'menu'); wrapper.append(button);
  }
  document.querySelectorAll('[data-context-trigger]').forEach(button => { button.hidden = false; });

  function targetFor(node) { return node.closest('[data-context-folder],[data-context-editor]'); }
  function hideMenu(restore = false) {
    menu.hidden = true; menuVersion++;
    if (restore) trigger?.focus({preventScroll: true});
  }
  function message(text, error = false) {
    feedback.textContent = text;
    feedback.className = text ? `notice ${error ? 'error' : 'success'}` : '';
    feedback.setAttribute('role', error ? 'alert' : 'status');
  }
  function setBusy(value) {
    busy = value; close.disabled = value; body.inert = value;
    body.setAttribute('aria-busy', String(value));
  }
  function start(label) {
    hideMenu(); dirty.clear(); changed = false; destination = location.href;
    body.replaceChildren(); title.textContent = label; message('読み込み中…');
    dialog.showModal(); setBusy(true);
  }
  async function fetchEditor() {
    const response = await fetch(editor, {headers, signal: AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error('設定を読み込めませんでした。閉じてからもう一度開いてください。');
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    const content = doc.querySelector('[data-editor-content]');
    if (!content) throw new Error('設定を読み込めませんでした。');
    // Never import scripts, even if a future template accidentally adds one.
    content.querySelectorAll('script').forEach(node => node.remove());
    // Isolate IDs from forms already present behind the dialog (e.g. workspace creation).
    const ids = new Map([...content.querySelectorAll('[id]')].map(node => [node.id, `editor-${node.id}`]));
    for (const node of content.querySelectorAll('[id]')) node.id = ids.get(node.id);
    for (const node of content.querySelectorAll('[for],[aria-labelledby],[aria-describedby]')) {
      for (const attr of ['for', 'aria-labelledby', 'aria-describedby']) {
        if (node.hasAttribute(attr)) node.setAttribute(attr, node.getAttribute(attr).split(' ').map(id => ids.get(id) || id).join(' '));
      }
    }
    return content;
  }
  async function openEditor(url, focus) {
    editor = url; const version = ++loadVersion;
    start('設定');
    try {
      const content = await fetchEditor();
      if (version !== loadVersion) return;
      title.textContent = content.dataset.editorTitle; body.replaceChildren(content); message(''); setBusy(false);
      if (focus === 'delete') {
        const form = body.querySelector('form[action$="/delete"]');
        if (form) { form.closest('details').open = true; form.querySelector('button').focus(); }
      } else {
        (focus === 'folder' ? body.querySelector('[name="folder"]') : body.querySelector('input:not([type=hidden]),select,textarea'))?.focus();
      }
    } catch (error) { message(error.message, true); }
    finally { setBusy(false); }
  }
  function openRename(target) {
    editor = null; ++loadVersion;
    start('フォルダー名を変更');
    const form = document.createElement('form'); form.dataset.renameFolder = target.dataset.contextFolder;
    const label = document.createElement('label'); label.textContent = 'フォルダー名';
    const input = document.createElement('input'); input.name = 'name'; input.required = true; input.maxLength = 80;
    input.value = target.dataset.contextFolder; label.append(input);
    const save = document.createElement('button'); save.textContent = '保存';
    form.append(label, save); body.append(form); setBusy(false); message(''); input.focus(); input.select();
  }
  function showMenu(target, x, y, source) {
    if (dialog.open || document.querySelector('.is-sorting,.order-saving')) return;
    trigger = source || target.querySelector('a,button') || target;
    menu.replaceChildren();
    const action = (label, callback) => {
      const button = document.createElement('button'); button.type = 'button'; button.role = 'menuitem'; button.textContent = label;
      button.addEventListener('click', callback); menu.append(button); return button;
    };
    if (target.hasAttribute('data-context-folder')) {
      action('記事を表示', () => { location.href = target.querySelector('.folder-link').href; });
      action('名前を変更…', () => openRename(target));
    } else {
      const url = target.dataset.contextEditor;
      action('設定…', () => openEditor(url));
      if (url.includes('/feeds/')) {
        const subscription=action('購読状態を確認中…',()=>{});subscription.disabled=true;
        const version=++menuVersion;
        const endpoint=`/feeds/${url.split('/').at(-1)}/subscription`;
        fetch(endpoint,{signal:AbortSignal.timeout(10000)}).then(response=>{if(!response.ok)throw new Error();return response.json();}).then(state=>{
          if(version!==menuVersion)return;
          subscription.textContent=state.enabled?'購読停止':'購読再開';subscription.disabled=!state.enabled&&!state.resumable;
          subscription.onclick=async()=>{
            editor=null;start(state.enabled?'購読停止':'購読再開');
            try{
              const response=await fetch(endpoint,{method:'POST',headers:{Accept:'application/json'},body:new URLSearchParams({csrf:dialog.dataset.csrf,enabled:state.enabled?'0':'1'}),signal:AbortSignal.timeout(15000)});
              const result=await response.json();if(!response.ok)throw new Error(result.error||'保存できませんでした。');
              changed=true;setBusy(false);await leave();
            }catch(error){message(error.message,true);setBusy(false);}
          };
        }).catch(()=>{if(version===menuVersion){subscription.textContent='購読設定…';subscription.disabled=false;subscription.onclick=()=>openEditor(url);}});
        action('フォルダーを変更…', () => openEditor(url, 'folder'));
        action('削除…', () => openEditor(url, 'delete'));
      }
    }
    menu.hidden = false;
    const rect = menu.getBoundingClientRect();
    menu.style.left = `${Math.max(8, Math.min(x, innerWidth - rect.width - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(y, innerHeight - rect.height - 8))}px`;
    menu.querySelector('button').focus({preventScroll: true});
  }
  document.addEventListener('contextmenu', event => {
    const target = targetFor(event.target);
    if (!target || dialog.open) return;
    event.preventDefault();
    showMenu(target, event.clientX, event.clientY, event.target.closest('a,button,summary'));
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-context-trigger]');
    if (button) {
      event.preventDefault(); event.stopPropagation();
      const box = button.getBoundingClientRect(); showMenu(targetFor(button), box.left, box.bottom, button); return;
    }
    const link = event.target.closest('a[href]');
    if (link && !dialog.contains(link) && !event.ctrlKey && !event.metaKey && !event.shiftKey && event.button === 0) {
      const url = new URL(link.href);
      if (url.origin === location.origin && /^\/settings\/items\//.test(url.pathname) && objectURL(link)) {
        event.preventDefault(); trigger = link; void openEditor(url.pathname); return;
      }
    }
    if (!menu.contains(event.target)) hideMenu();
  });
  document.addEventListener('keydown', event => {
    if ((event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) && targetFor(event.target)) {
      event.preventDefault(); const box = event.target.getBoundingClientRect();
      showMenu(targetFor(event.target), box.left, box.bottom, event.target);
    }
    if (menu.hidden) return;
    const items = [...menu.querySelectorAll('button')];
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault(); const index = items.indexOf(document.activeElement);
      items[event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length].focus({preventScroll: true});
    }
    if (event.key === 'Escape') { event.preventDefault(); hideMenu(true); }
    if (event.key === 'Tab') hideMenu();
  });
  window.addEventListener('resize', () => hideMenu());
  window.addEventListener('wheel', () => hideMenu(), {passive:true});
  window.addEventListener('touchmove', () => hideMenu(), {passive:true});
  document.addEventListener('pointerdown', event => { if (!menu.contains(event.target)) hideMenu(); });
  body.addEventListener('input', event => { const form = event.target.closest('form'); if (form) dirty.add(form.getAttribute('action') || 'rename'); });

  async function leave() {
    if (busy || (dirty.size && !confirm('保存していない変更を破棄して閉じますか？'))) return;
    dialog.close(); ++loadVersion; trigger?.focus({preventScroll: true});
    if (changed) {
      // A removed feed/folder can invalidate the original reading filter.
      try { const response = await fetch(destination); if (!response.ok) destination = '/'; }
      catch { /* Navigation can recover from a temporary fetch failure. */ }
      location.assign(destination);
    }
  }
  close.addEventListener('click', () => void leave());
  dialog.addEventListener('cancel', event => { event.preventDefault(); void leave(); });
  body.addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    const form = event.target; setBusy(true); message('保存中…');
    try {
      if (form.hasAttribute('data-rename-folder')) {
        const old = form.dataset.renameFolder;
        const response = await fetch(dialog.dataset.renameUrl, {method: 'POST', headers: {'Accept':'application/json'},
          body: new URLSearchParams({csrf:dialog.dataset.csrf, folder:old, name:new FormData(form).get('name')}), signal:AbortSignal.timeout(15000)});
        const result = await response.json(); if (!response.ok) throw new Error(result.error || '保存できませんでした。');
        const key = 'feedastrolabe.feed-folders.v2';
        try {
          const value = JSON.parse(localStorage.getItem(key));
          if (value?.version === 2 && value.states && Object.hasOwn(value.states, old)) {
            const states = new Map(Object.entries(value.states)); const open = states.get(old);
            states.delete(old); states.set(result.name, open); value.states = Object.fromEntries(states);
            localStorage.setItem(key, JSON.stringify(value));
          }
        } catch { /* Renaming remains usable without browser storage. */ }
        const url = new URL(destination); if (url.searchParams.get('folder') === old) url.searchParams.set('folder', result.name);
        destination = url.href; changed = true; dirty.clear(); setBusy(false); await leave(); return;
      }
      const values = new URLSearchParams(new FormData(form));
      if (event.submitter?.name) values.set(event.submitter.name, event.submitter.value);
      const response = await fetch(form.action, {method:'POST', headers, body:values, signal:AbortSignal.timeout(20000)});
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const error = doc.querySelector('[data-flash="error"]');
      if (!response.ok || error) throw new Error(error?.textContent.trim() || doc.querySelector('.error-page p')?.textContent.trim() || '保存できませんでした。入力内容と接続を確認してください。');
      changed = true; dirty.delete(form.getAttribute('action'));
      if (new URL(form.action).pathname.endsWith('/delete')) {
        body.replaceChildren(); message('削除しました。'); setBusy(false); await leave(); return;
      }
      const content = await fetchEditor();
      for (const pending of body.querySelectorAll('form')) {
        if (!dirty.has(pending.getAttribute('action'))) continue;
        const fresh = [...content.querySelectorAll('form')].find(node => node.getAttribute('action') === pending.getAttribute('action'));
        fresh?.replaceWith(pending);
      }
      title.textContent = content.dataset.editorTitle; body.replaceChildren(content); message('保存しました。');
    } catch (error) { message(error instanceof TypeError || error.name === 'TimeoutError' ? '保存を確認できませんでした。接続を確認してから設定を開き直してください。' : error.message, true); }
    finally { setBusy(false); }
  });
})();
