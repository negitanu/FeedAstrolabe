(() => {
  'use strict';
  const key = 'feedastrolabe.article-layout.v1';
  const layouts = ['standard', 'line', 'tiles'];
  const list = document.querySelector('[data-article-layout]');
  const controls = document.querySelector('.article-layout-switch');
  if (!list || !controls) return;
  const buttons = [...controls.querySelectorAll('[data-article-layout-choice]')];

  function apply(layout) {
    list.dataset.articleLayout = layout;
    for (const button of buttons) {
      button.setAttribute('aria-pressed', String(button.dataset.articleLayoutChoice === layout));
    }
  }

  let layout = layouts.includes(list.dataset.articleLayout) ? list.dataset.articleLayout : 'standard';
  try {
    const raw = localStorage.getItem(key);
    if (raw && raw.length <= 128) {
      const saved = JSON.parse(raw);
      if (saved && saved.version === 1 && layouts.includes(saved.layout)) layout = saved.layout;
    }
  } catch { /* Default presentation works without browser storage. */ }
  apply(layout);
  controls.hidden = false;
  for (const button of buttons) {
    button.addEventListener('click', () => {
      const selected = button.dataset.articleLayoutChoice;
      if (!layouts.includes(selected)) return;
      apply(selected);
      try { localStorage.setItem(key, JSON.stringify({version: 1, layout: selected})); }
      catch { /* Switching the current page still works. */ }
    });
  }
})();
