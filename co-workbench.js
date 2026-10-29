(() => {
  'use strict';
  const PROGRESS_KEY = 'co-notes.progress.v1';
  const READING_KEY = 'co-notes.reading.v1';
  const allowedPath = /^\/ZYK_408\/co\/(?:system|data|memory|instructions|cpu|bus|io|complete|topics\/[a-z-]+|wangdao(?:\/(?:[1-7]-[1-7]|worked))?)\/$/;
  function safeReading(value) {
    if (!value || typeof value.href !== 'string' || typeof value.label !== 'string') return null;
    try {
      const url = new URL(value.href, location.origin);
      if (url.origin !== location.origin || !allowedPath.test(url.pathname)) return null;
      return { href: url.pathname + url.hash, label: value.label.slice(0, 100) };
    } catch { return null; }
  }
  function read(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
  }
  function boot() {
    const root = document.getElementById('co-workbench');
    if (!root || root.dataset.bound) return;
    root.dataset.bound = 'true';
    const $ = selector => root.querySelector(selector);
    const all = selector => [...root.querySelectorAll(selector)];
    const switches = all('[data-chapter]');
    const panels = all('[data-chapter-panel]');
    const views = all('[data-view]');
    const panes = all('[data-pane]');
    const checks = all('[data-mastered]');
    const input = $('#co-search-input');
    const results = $('#co-search-results');
    const resultList = $('#co-results-list');
    const empty = $('#co-search-empty');
    const rawProgress = read(PROGRESS_KEY, []);
    const known = new Set(checks.map(check => check.dataset.mastered));
    const mastered = new Set(Array.isArray(rawProgress) ? rawProgress.filter(id => known.has(id)) : []);
    let currentChapter = location.hash.match(/^#chapter-([1-7])$/)?.[1] || '1';
    let currentView = 'chapters';
    const searchItems = all('[data-search-item]').map(item => {
      const link = item.matches('a') ? item : item.querySelector('a');
      const label = link.querySelector('strong')?.textContent || link.textContent.trim();
      const number = link.querySelector('.co-section-number')?.textContent || '';
      return { href: link.getAttribute('href'), label: `${number ? number + ' ' : ''}${label}`, text: (item.textContent + ' ' + (item.dataset.searchKeywords || '')).toLowerCase().replace(/\s/g, ''), kind: item.dataset.kind };
    });
    function paintProgress() {
      checks.forEach(check => {
        check.checked = mastered.has(check.dataset.mastered);
        check.closest('.co-section-row').classList.toggle('is-mastered', check.checked);
      });
      $('#co-progress').max = checks.length;
      $('#co-progress').value = mastered.size;
      $('#co-progress-count').textContent = `${mastered.size} / ${checks.length}`;
      $('#co-progress-percent').textContent = `${Math.round(mastered.size / checks.length * 100)}%`;
      switches.forEach(button => {
        const panel = panels.find(item => item.dataset.chapterPanel === button.dataset.chapter);
        const ids = [...panel.querySelectorAll('[data-mastered]')].map(item => item.dataset.mastered);
        button.querySelector('[data-chapter-progress]').textContent = `${ids.filter(id => mastered.has(id)).length} / ${ids.length} 已掌握`;
      });
    }
    function display() {
      results.hidden = true;
      panes.forEach(pane => { pane.hidden = pane.dataset.pane !== currentView; });
      panels.forEach(panel => { panel.hidden = panel.dataset.chapterPanel !== currentChapter; });
      switches.forEach(button => { button.setAttribute('aria-current', String(button.dataset.chapter === currentChapter)); });
      views.forEach(button => { button.setAttribute('aria-pressed', String(button.dataset.view === currentView)); });
    }
    function search() {
      const query = input.value.toLowerCase().trim().replace(/\s/g, '');
      if (!query) { display(); return; }
      panes.forEach(pane => { pane.hidden = true; });
      results.hidden = false;
      const matches = searchItems.filter(item => item.text.includes(query));
      resultList.replaceChildren();
      matches.forEach(item => {
        const a = document.createElement('a');
        a.className = 'co-result';
        a.href = item.href;
        a.dataset.readingLink = '';
        const kind = document.createElement('small');
        kind.textContent = item.kind;
        const title = document.createElement('strong');
        title.textContent = item.label;
        a.append(kind, title);
        resultList.append(a);
      });
      $('#co-search-count').textContent = `${matches.length} 项匹配`;
      empty.hidden = matches.length !== 0;
    }
    switches.forEach(button => button.addEventListener('click', event => {
      event.preventDefault();
      currentChapter = button.dataset.chapter;
      currentView = 'chapters';
      input.value = '';
      history.replaceState(null, '', `#chapter-${currentChapter}`);
      display();
    }));
    views.forEach(button => button.addEventListener('click', () => {
      currentView = button.dataset.view;
      input.value = '';
      display();
    }));
    checks.forEach(check => check.addEventListener('change', () => {
      if (check.checked) mastered.add(check.dataset.mastered); else mastered.delete(check.dataset.mastered);
      if (!write(PROGRESS_KEY, [...mastered])) $('#co-storage-note').textContent = '当前浏览器无法保存，进度仅在本次访问中有效。';
      paintProgress();
    }));
    input.addEventListener('input', search);
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') { input.value = ''; display(); input.blur(); }
    });
    $('#co-clear-search').addEventListener('click', () => { input.value = ''; display(); input.focus(); });
    const lastReading = safeReading(read(READING_KEY, null));
    if (lastReading) {
      $('#co-resume-link').href = lastReading.href;
      $('#co-resume-label').textContent = lastReading.label;
      $('#co-resume-note').textContent = '上次打开的内容，接着往下读。';
    }
    paintProgress();
    display();
    root.classList.add('co-ready');
  }
  // One document-level listener survives Butterfly PJAX page transitions.
  if (!window.coNotesWorkbenchLoaded) {
    window.coNotesWorkbenchLoaded = true;
    document.addEventListener('pjax:complete', boot);
    document.addEventListener('click', event => {
      const link = event.target.closest?.('a');
      if (!link || !link.closest('.co-notes-content') || link.closest('.co-notes-nav')) return;
      const reading = safeReading({ href: link.getAttribute('href'), label: link.querySelector('strong')?.textContent.trim() || link.textContent.trim().replace(/[↗→]/g, '').trim() });
      if (reading) write(READING_KEY, reading);
    });
    document.addEventListener('keydown', event => {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || event.target.closest?.('input, textarea, select, [contenteditable="true"]')) return;
      const input = document.getElementById('co-search-input');
      if (input) { event.preventDefault(); input.focus(); }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
})();
