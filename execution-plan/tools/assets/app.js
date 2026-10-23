(function () {
  var root = document.documentElement;
  try { var saved = localStorage.getItem('execution-plan-theme'); if (saved) root.setAttribute('data-theme', saved); } catch (e) {}
  function isDark() {
    var t = root.getAttribute('data-theme');
    if (t) return t === 'dark';
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  var btns = document.querySelectorAll('.theme-btn');
  function label() { Array.prototype.forEach.call(btns, function (b) { b.textContent = isDark() ? 'Light mode' : 'Dark mode'; }); }
  label();
  Array.prototype.forEach.call(btns, function (b) {
    b.addEventListener('click', function () {
      var next = isDark() ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('execution-plan-theme', next); } catch (e) {}
      label();
    });
  });

  // Generic filtering: [data-item] elements with data-cat (space list), data-risk, text content.
  var items = Array.prototype.slice.call(document.querySelectorAll('[data-item]'));
  if (!items.length) return;
  var search = document.getElementById('search');
  var countEl = document.getElementById('count');
  var emptyEl = document.getElementById('empty');
  var state = { cat: 'all', risk: 'all', q: '' };
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip[data-group]'));
  chips.forEach(function (c) {
    c.addEventListener('click', function () {
      var g = c.getAttribute('data-group');
      state[g] = c.getAttribute('data-value');
      chips.forEach(function (o) { if (o.getAttribute('data-group') === g) o.setAttribute('aria-pressed', o === c ? 'true' : 'false'); });
      apply();
    });
  });
  if (search) search.addEventListener('input', function () { state.q = search.value.trim().toLowerCase(); apply(); });
  function apply() {
    var shown = 0;
    items.forEach(function (it) {
      var cats = (it.getAttribute('data-cat') || '').split(' ');
      var ok = (state.cat === 'all' || cats.indexOf(state.cat) !== -1) &&
               (state.risk === 'all' || it.getAttribute('data-risk') === state.risk) &&
               (!state.q || it.textContent.toLowerCase().indexOf(state.q) !== -1);
      it.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-group-rows]'), function (g) {
      var name = g.getAttribute('data-group-rows');
      var any = items.some(function (it) { return (it.getAttribute('data-in') || '').split(' ').indexOf(name) !== -1 && it.style.display !== 'none'; });
      g.style.display = any ? '' : 'none';
    });
    var filtered = state.cat !== 'all' || state.risk !== 'all' || state.q;
    if (countEl) countEl.textContent = filtered ? shown + ' of ' + items.length + ' shown' : items.length + ' ' + (countEl.getAttribute('data-noun') || 'items');
    if (emptyEl) emptyEl.style.display = shown ? 'none' : 'block';
  }
  apply();
})();
