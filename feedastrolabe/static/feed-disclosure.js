(() => {
  'use strict';
  const key = 'feedastrolabe.feed-folders.v2';
  const legacyFolderKey = 'feedastrolabe.feed-folders.v1';
  const groups = [...document.querySelectorAll('.feed-folder[data-folder]')];
  const allowed = new Set(groups.map(group => group.dataset.folder));
  const observed = new Map();

  function readStates(storageKey, version, names) {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw || raw.length > 65536) return null;
      const saved = JSON.parse(raw);
      if (!saved || saved.version !== version || !saved.states ||
          typeof saved.states !== 'object' || Array.isArray(saved.states)) return null;
      return new Map(Object.entries(saved.states)
        .filter(([name, value]) => names.has(name) && typeof value === 'boolean'));
    } catch {
      return null;
    }
  }

  function save(states) {
    try {
      const encoded = JSON.stringify({version: 2, states: Object.fromEntries(states)});
      if (encoded.length <= 65536) localStorage.setItem(key, encoded);
    } catch { /* Native disclosure still works when storage is denied. */ }
  }

  let states = readStates(key, 2, allowed);
  if (!states) {
    states = new Map();
    const legacyNames = new Set(groups.flatMap(group => group.dataset.sourceTypes.split(' ')
      .map(type => JSON.stringify([type, group.dataset.folder]))));
    const legacy = readStates(legacyFolderKey, 1, legacyNames);
    if (legacy) {
      for (const group of groups) {
        const previous = group.dataset.sourceTypes.split(' ')
          .map(type => JSON.stringify([type, group.dataset.folder]));
        if (previous.some(name => legacy.has(name))) {
          // New/mixed kinds remain visible; only an entirely closed folder closes.
          states.set(group.dataset.folder, !previous.every(name => legacy.get(name) === false));
        }
      }
      if (states.size) save(states);
    }
  }

  for (const group of groups) {
    const name = group.dataset.folder;
    if (states.has(name)) group.open = states.get(name);
    observed.set(group, group.open);
    group.addEventListener('toggle', () => {
      if (observed.get(group) === group.open) return;
      observed.set(group, group.open);
      const latest = readStates(key, 2, allowed) || new Map();
      latest.set(name, group.open);
      save(latest);
    });
  }

  const navigation = document.querySelector('.sidebar-navigation');
  if (navigation) {
    const mobile = matchMedia('(max-width:700px)');
    navigation.open = !mobile.matches;
    mobile.addEventListener('change', event => { navigation.open = !event.matches; });
  }
})();
