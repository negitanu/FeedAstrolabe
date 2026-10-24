/* Direct manipulation shares the same CSRF-protected move operation as forms. */
(() => {
  'use strict';
  for (const list of document.querySelectorAll('[data-folder-order]')) {
    const rows = () => [...list.children].filter(node => node.hasAttribute('data-folder'));
    const status = list.parentElement.querySelector('[data-order-status]');
    let drag = null;
    let saving = false;
    let frame = 0;

    function announce(message, error = false) {
      status.textContent = message;
      status.classList.toggle('sr-only', !error);
      status.classList.toggle('notice', error);
      status.classList.toggle('error', error);
      status.setAttribute('role', error ? 'alert' : 'status');
    }
    function restore(order) { for (const row of order) list.append(row); }
    async function save(row, original) {
      const position = rows().indexOf(row);
      if (position === original.indexOf(row)) return;
      saving = true;
      list.setAttribute('aria-busy', 'true');
      list.classList.add('order-saving');
      announce('表示順を保存中…');
      try {
        const response = await fetch(list.dataset.orderUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: {'Accept': 'application/json'},
          body: new URLSearchParams({csrf: list.dataset.csrf, folder: row.dataset.folder,
            move: 'position', position: String(position + 1)}),
          signal: AbortSignal.timeout(15000)
        });
        if (!response.ok) throw new Error('save failed');
        const saved = await response.json();
        if (!Array.isArray(saved.folders)) throw new Error('invalid response');
        const known = new Map(rows().map(item => [item.dataset.folder, item]));
        for (const name of saved.folders) if (known.has(name)) list.append(known.get(name));
        announce(`${row.dataset.folder || '未分類'} を ${rows().indexOf(row) + 1} 番目に移動しました。`);
      } catch {
        restore(original);
        announce('表示順の保存を確認できませんでした。再読み込みして確認してください。', true);
      } finally {
        saving = false;
        list.removeAttribute('aria-busy');
        list.classList.remove('order-saving');
        row.querySelector('[data-drag-handle]').focus({preventScroll: true});
      }
    }
    function reorder(y) {
      const others = rows().filter(row => row !== drag.row);
      const next = others.find(row => {
        const box = row.getBoundingClientRect();
        return y < box.top + box.height / 2;
      });
      list.insertBefore(drag.row, next || null);
    }
    function scroll() {
      if (!drag?.active) return;
      const top = 90; // Keep the drop target clear of the sticky application nav.
      const bottom = innerHeight - 55;
      const distance = drag.y < top ? -12 : drag.y > bottom ? 12 : 0;
      if (distance) { window.scrollBy(0, distance); reorder(drag.y); }
      frame = requestAnimationFrame(scroll);
    }
    function finish(cancelled) {
      if (!drag) return;
      const current = drag;
      drag = null;
      cancelAnimationFrame(frame);
      current.row.classList.remove('is-dragging');
      list.classList.remove('is-sorting');
      if (list.hasPointerCapture(current.id)) list.releasePointerCapture(current.id);
      if (cancelled) {
        restore(current.original);
        announce('並べ替えを取り消しました。');
      } else if (current.active) {
        void save(current.row, current.original);
      }
    }
    for (const row of rows()) {
      const handle = row.querySelector('[data-drag-handle]');
      handle.hidden = rows().length < 2;
      handle.setAttribute('aria-description', 'ドラッグ、または上下矢印キーで移動。Escapeで取り消し。');
      handle.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); });
      handle.addEventListener('pointerdown', event => {
        if (saving || drag || event.button !== 0 || !event.isPrimary) return;
        event.preventDefault(); event.stopPropagation();
        handle.focus({preventScroll: true});
        drag = {row, id: event.pointerId, startY: event.clientY, y: event.clientY,
          original: rows(), active: false};
        list.setPointerCapture(event.pointerId);
      });
      handle.addEventListener('keydown', event => {
        if (!['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        if (saving || drag) return;
        const original = rows();
        const index = original.indexOf(row);
        const target = event.key === 'Home' ? 0 : event.key === 'End' ? original.length - 1 :
          Math.max(0, Math.min(original.length - 1, index + (event.key === 'ArrowUp' ? -1 : 1)));
        if (target !== index) {
          list.insertBefore(row, target < index ? original[target] : original[target].nextSibling);
          void save(row, original);
        }
      });
    }
    list.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      drag.y = event.clientY;
      if (!drag.active && Math.abs(drag.y - drag.startY) >= 6) {
        drag.active = true;
        drag.row.classList.add('is-dragging');
        list.classList.add('is-sorting');
        frame = requestAnimationFrame(scroll);
      }
      if (drag.active) { event.preventDefault(); reorder(drag.y); }
    });
    list.addEventListener('pointerup', () => finish(false));
    list.addEventListener('pointercancel', () => finish(true));
    list.addEventListener('lostpointercapture', () => finish(true));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && drag) { event.preventDefault(); finish(true); }
    });
    // Avoid concurrent form mutations while a drag save is in flight.
    list.addEventListener('submit', event => { if (saving || drag) event.preventDefault(); });
  }
})();
