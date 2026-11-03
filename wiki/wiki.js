/* R3DACTED-Wiki – Sprache, Suche, Item-Liste, Quest-/FAQ-Filter. Vanilla JS, kein Framework, keine Drittanbieter. */
(function () {
  'use strict';
  var D = document, H = D.documentElement;
  function $(s, r) { return (r || D).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || D).querySelectorAll(s)); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  var lang = H.getAttribute('data-lang') === 'en' ? 'en' : 'de';
  var langHooks = [];
  function T(de, en) { return lang === 'en' ? en : de; }

  /* ---------- Sprache ---------- */
  function syncLangUI() {
    $$('[data-set-lang]').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-set-lang') === lang ? 'true' : 'false'); });
    $$('[data-ph-de]').forEach(function (e) { e.setAttribute('placeholder', e.getAttribute('data-ph-' + lang)); });
    $$('[data-t-de]').forEach(function (e) { e.textContent = e.getAttribute('data-t-' + lang); });
    $$('[data-al-de]').forEach(function (e) { e.setAttribute('aria-label', e.getAttribute('data-al-' + lang)); });
    var t = D.body.getAttribute('data-title-' + lang);
    if (t) { D.title = t; }
  }
  function setLang(l) {
    lang = l === 'en' ? 'en' : 'de';
    H.setAttribute('data-lang', lang);
    H.setAttribute('lang', lang);
    try { localStorage.setItem('r3dLang', lang); } catch (e) { /* privater Modus */ }
    syncLangUI();
    langHooks.forEach(function (fn) { fn(); });
  }
  D.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-set-lang]') : null;
    if (b) { setLang(b.getAttribute('data-set-lang')); return; }
    var s = e.target.closest ? e.target.closest('.spoiler') : null;
    if (s) { s.classList.toggle('open'); }
  });
  D.addEventListener('keydown', function (e) {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('spoiler')) {
      e.preventDefault(); e.target.classList.toggle('open');
    }
  });
  syncLangUI();

  /* ---------- Normalisierung + Suche ---------- */
  // Umlaute/ß/Akzente glätten, ae/oe/ue -> a/o/u (Zuendkerze == Zündkerze), alles Nicht-Alphanumerische -> Leerzeichen
  function fold(s) {
    return String(s == null ? '' : s).toLowerCase().replace(/ß/g, 'ss').normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/([aou])e/g, '$1').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
  }
  function mk(s) { var f = fold(s); return { s: f, c: f.replace(/ /g, '') }; }
  function sf(f, t) {            // Treffer-Güte eines Tokens in einem Feld
    var c = f.c;
    if (!c) { return 0; }
    var base = 0;
    if (c === t) { base = 100; }
    else if (c.indexOf(t) === 0) { base = 80; }
    else if ((' ' + f.s).indexOf(' ' + t) >= 0) { base = 60; }
    else if (c.indexOf(t) >= 0) { base = 40; }
    return base ? base + 15 * t.length / c.length : 0;
  }
  function scoreFields(fields, toks, qc) {
    var i, j, best, sc, tot = 0;
    if (toks.length > 1) {       // "m4 a1" soll auch "M4-A1" (kompakt "m4a1") finden
      best = 0;
      for (j = 0; j < fields.length; j++) { sc = sf(fields[j].f, qc) * fields[j].w; if (sc > best) { best = sc; } }
      if (best) { return best * 0.95; }
    }
    for (i = 0; i < toks.length; i++) {
      best = 0;
      for (j = 0; j < fields.length; j++) { sc = sf(fields[j].f, toks[i]) * fields[j].w; if (sc > best) { best = sc; } }
      if (!best) { return 0; }
      tot += best;
    }
    return tot;
  }
  function osa(a, b, max) {       // Damerau-Levenshtein (OSA) mit Abbruchschwelle
    var la = a.length, lb = b.length, i, j, cost, d = [], row, min;
    if (Math.abs(la - lb) > max) { return max + 1; }
    for (i = 0; i <= la; i++) { d[i] = [i]; }
    for (j = 1; j <= lb; j++) { d[0][j] = j; }
    for (i = 1; i <= la; i++) {
      min = 99;
      for (j = 1; j <= lb; j++) {
        cost = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
        row = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
        if (i > 1 && j > 1 && a.charAt(i - 1) === b.charAt(j - 2) && a.charAt(i - 2) === b.charAt(j - 1)) { row = Math.min(row, d[i - 2][j - 2] + 1); }
        d[i][j] = row;
        if (row < min) { min = row; }
      }
      if (min > max) { return max + 1; }
    }
    return d[la][lb];
  }
  function fuzzyFields(fields, toks) {
    var i, j, k, best, tot = 0, t, max, words, w, d;
    for (i = 0; i < toks.length; i++) {
      t = toks[i]; best = 0;
      max = t.length >= 8 ? 2 : (t.length >= 4 ? 1 : 0);
      for (j = 0; j < fields.length; j++) {
        if (fields[j].w < 0.3) { continue; }
        words = fields[j].f.ws || (fields[j].f.ws = fields[j].f.s.split(' '));
        for (k = 0; k < words.length; k++) {
          w = words[k];
          if (w === t) { best = Math.max(best, 40); continue; }
          if (!max) { continue; }
          d = osa(t, w, max);
          if (d <= max) { best = Math.max(best, 30 - d * 8); }
          else if (w.length > t.length) {
            d = osa(t, w.slice(0, t.length), max);
            if (d <= max) { best = Math.max(best, 22 - d * 8); }
          }
        }
      }
      if (!best) { return 0; }
      tot += best;
    }
    return tot;
  }

  /* ---------- Daten ---------- */
  var dataP = null, DB = null;
  function loadData() {
    if (dataP) { return dataP; }
    dataP = fetch('search.json').then(function (r) {
      if (!r.ok) { throw new Error('HTTP ' + r.status); }
      return r.json();
    }).then(prepare);
    return dataP;
  }
  function prepare(d) {
    var i, r, x;
    d.I = new Array(d.items.length);
    for (i = 0; i < d.items.length; i++) {
      r = d.items[i];
      x = d.mods[r[3]][0] + ' ' + d.cats[r[7]][0] + ' ' + d.cats[r[7]][1];
      for (var h = 0; h < d.hand.length; h++) { if (r[6] & (1 << h)) { x += ' ' + d.hand[h]; } }
      d.I[i] = { r: r, fields: [{ f: mk(r[1]), w: 1 }, { f: mk(r[2] || r[1]), w: 1 }, { f: mk(r[0]), w: 1 }, { f: mk(x), w: 0.12 }] };
    }
    d.Tp = d.topics.map(function (t) {
      return { r: t, fields: [{ f: mk(t[2]), w: 1 }, { f: mk(t[3]), w: 1 }, { f: mk(t[6] + ' ' + t[7]), w: 0.5 }, { f: mk(t[8] + ' ' + t[9]), w: 0.15 }] };
    });
    d.Q = d.quests.map(function (q) {
      return { r: q, fields: [{ f: mk(q[3]), w: 1 }, { f: mk(q[4]), w: 1 }, { f: mk(q[0] + ' ' + ('00' + q[0]).slice(-3)), w: 0.9 }, { f: mk(q[5] + ' ' + q[6] + ' ' + q[7] + ' ' + q[8] + ' ' + q[2]), w: 0.3 }] };
    });
    d.F = d.faq.map(function (f) {
      return { r: f, fields: [{ f: mk(f[3]), w: 1 }, { f: mk(f[4]), w: 1 }, { f: mk(f[5] + ' ' + f[6]), w: 0.2 }] };
    });
    DB = d;
    return d;
  }
  function runGroup(list, toks, qc, fuzzy, seen) {
    var out = [], i, sc;
    for (i = 0; i < list.length; i++) {
      if (seen && seen[i]) { continue; }
      sc = fuzzy ? fuzzyFields(list[i].fields, toks) : scoreFields(list[i].fields, toks, qc);
      if (sc > 0) { out.push({ i: i, sc: sc }); }
    }
    out.sort(function (a, b) { return b.sc - a.sc || a.i - b.i; });
    return out;
  }
  function searchAll(d, q) {
    var toks = fold(q).split(' ').filter(Boolean), qc = toks.join(''), res = { items: [], quests: [], topics: [], faq: [] };
    if (!toks.length) { return res; }
    res.items = runGroup(d.I, toks, qc, false);
    res.topics = runGroup(d.Tp, toks, qc, false);
    res.quests = runGroup(d.Q, toks, qc, false);
    res.faq = runGroup(d.F, toks, qc, false);
    var total = res.items.length + res.topics.length + res.quests.length + res.faq.length;
    if (total < 3) {   // Tippfehler-Toleranz nur als Fallback
      var f = { items: d.I, topics: d.Tp, quests: d.Q, faq: d.F };
      Object.keys(f).forEach(function (k) {
        var seen = {}; res[k].forEach(function (h) { seen[h.i] = 1; });
        res[k] = res[k].concat(runGroup(f[k], toks, qc, true, seen));
      });
    }
    return res;
  }
  W_exports();
  function W_exports() { window.R3DWiki = { fold: fold, searchAll: searchAll, loadData: loadData }; }

  /* ---------- Formatierung ---------- */
  function nf(n) { return new Intl.NumberFormat(lang === 'en' ? 'en-US' : 'de-DE').format(n); }
  function rc(n) { return n == null ? null : nf(n) + ' RC'; }
  function catName(d, i) { return d.cats[i][lang === 'en' ? 1 : 0] || d.cats[i][0]; }
  function itemName(r) { return lang === 'en' ? (r[2] || r[1]) : r[1]; }
  function haendlerList(d, mask) {
    var o = [];
    for (var h = 0; h < d.hand.length; h++) { if (mask & (1 << h)) { o.push(d.hand[h]); } }
    return o;
  }
  function itemCard(d, r) {
    var name = itemName(r), other = lang === 'en' ? r[1] : (r[2] || ''), hs = haendlerList(d, r[6]);
    var img = r[8] ? '<img src="' + esc(r[8]) + '" alt="" loading="lazy" decoding="async">' : '';
    return '<article class="icard">' + img + '<h3>' + esc(name) + '</h3>' +
      (other && other !== name ? '<div class="alt">' + esc(other) + '</div>' : '') +
      '<div class="kl">' + esc(r[0]) + '</div>' +
      '<div class="preise"><div><small>' + T('Kauf', 'Buy') + '</small>' + (r[4] == null ? '<span class="nein">–</span>' : '<b>' + rc(r[4]) + '</b>') + '</div>' +
      '<div><small>' + T('Verkauf', 'Sell') + '</small>' + (r[5] == null ? '<span class="nein">–</span>' : '<b>' + rc(r[5]) + '</b>') + '</div></div>' +
      '<div class="chips"><span class="chip mod" title="' + esc(d.mods[r[3]][1]) + '">' + esc(d.mods[r[3]][0]) + '</span>' +
      '<span class="chip">' + esc(catName(d, r[7])) + '</span>' +
      hs.map(function (h) { return '<span class="chip">' + esc(h) + '</span>'; }).join('') + '</div></article>';
  }
  function updateQS(params) {
    try {
      var p = new URLSearchParams(), k;
      for (k in params) { if (params[k]) { p.set(k, params[k]); } }
      var s = p.toString();
      history.replaceState(null, '', location.pathname + (s ? '?' + s : '') + location.hash);
    } catch (e) { /* ignore */ }
  }
  function qsGet(k) { try { return new URLSearchParams(location.search).get(k) || ''; } catch (e) { return ''; } }
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }

  /* ---------- Startseite: Gruppierte Suche ---------- */
  function initIndex() {
    var inp = $('#q'), res = $('#results'), start = $('#start'), status = $('#status'), expand = {};
    var data = null;
    function row(g, h) {
      var d = DB, e, x, nm;
      if (g === 'topics') {
        e = d.Tp[h.i].r;
        nm = lang === 'en' ? e[3] : e[2];
        return '<a class="res" href="themen/' + esc(e[0]) + '.html"><span class="rt"><span class="ri">' + esc(e[1]) + '</span> ' + esc(nm) + '</span><span class="rs">' + esc(lang === 'en' ? e[5] : e[4]) + '</span></a>';
      }
      if (g === 'items') {
        e = d.I[h.i].r;
        return '<a class="res" href="items.html?q=' + encodeURIComponent(e[0]) + '"><span class="rt">' + esc(itemName(e)) + '</span><code>' + esc(e[0]) + '</code><span class="rs">' +
          T('Kauf', 'Buy') + ': ' + (rc(e[4]) || '–') + ' · ' + T('Verkauf', 'Sell') + ': ' + (rc(e[5]) || '–') + ' · ' + esc(d.mods[e[3]][0]) +
          (e[6] ? ' · ' + esc(haendlerList(d, e[6]).join(', ')) : '') + '</span></a>';
      }
      if (g === 'quests') {
        e = d.Q[h.i].r;
        return '<a class="res" href="quests.html#q' + e[0] + '"><span class="rt">#' + ('00' + e[0]).slice(-3) + ' ' + esc(lang === 'en' ? e[4] : e[3]) + '</span><span class="rs">' +
          esc(lang === 'en' ? e[8] : e[7]) + ' · ' + esc(e[2]) + '</span></a>';
      }
      e = d.F[h.i].r;
      return '<a class="res" href="faq.html#f' + e[0] + '"><span class="rt">' + esc(lang === 'en' ? e[4] : e[3]) + '</span><span class="rs">' + esc(lang === 'en' ? e[2] : e[1]) + '</span></a>';
    }
    var LABEL = { items: ['Items', 'Items'], quests: ['Quests', 'Quests'], topics: ['Themen', 'Topics'], faq: ['FAQ', 'FAQ'] };
    function run() {
      var q = inp.value;
      if (!fold(q)) { res.hidden = true; res.innerHTML = ''; start.hidden = false; status.textContent = ''; return; }
      if (!DB) { return; }
      var r = searchAll(DB, q), keys = ['items', 'quests', 'topics', 'faq'], total = 0, html = '';
      keys.forEach(function (k) { total += r[k].length; });
      keys.sort(function (a, b) { return (r[b][0] ? r[b][0].sc : 0) - (r[a][0] ? r[a][0].sc : 0); });
      keys.forEach(function (k) {
        if (!r[k].length) { return; }
        var lim = expand[k] ? 60 : (k === 'items' ? 8 : 6), list = r[k].slice(0, lim);
        html += '<section class="rgroup" aria-label="' + esc(LABEL[k][lang === 'en' ? 1 : 0]) + '"><h2>' + esc(LABEL[k][lang === 'en' ? 1 : 0]) +
          ' <small>(' + nf(r[k].length) + ')</small></h2>' + list.map(function (h) { return row(k, h); }).join('');
        if (r[k].length > lim) {
          html += '<button type="button" class="rmore" data-more="' + k + '">' + T('Mehr anzeigen', 'Show more') + '</button>';
        }
        if (expand[k] && k === 'items' && r[k].length > lim) {
          html += ' <a href="items.html?q=' + encodeURIComponent(q) + '">' + T('Alle in der Item-Liste', 'All in the item list') + '</a>';
        }
        html += '</section>';
      });
      if (!total) { html = '<p class="leer">' + T('Nichts gefunden für „', 'Nothing found for “') + esc(q) + T('“. Anderen Begriff oder weniger Wörter probieren.', '”. Try another term or fewer words.') + '</p>'; }
      res.innerHTML = html; res.hidden = false; start.hidden = true;
      status.textContent = total + ' ' + T('Treffer', 'results');
    }
    res.addEventListener('click', function (e) {
      var b = e.target.closest('[data-more]');
      if (b) { expand[b.getAttribute('data-more')] = true; run(); }
    });
    var runDeb = debounce(function () { updateQS({ q: inp.value }); run(); }, 90);
    inp.addEventListener('input', runDeb);
    $('#sform').addEventListener('submit', function (e) {
      e.preventDefault(); var f = $('.res', res); if (f) { f.click(); }
    });
    inp.value = qsGet('q');
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { var f = $('.res', res); if (f) { e.preventDefault(); f.focus(); } }
      else if (e.key === 'Escape') { inp.value = ''; expand = {}; updateQS({}); run(); }
    });
    res.addEventListener('keydown', function (e) {
      var all = $$('.res', res), i = all.indexOf(D.activeElement);
      if (e.key === 'ArrowDown' && i >= 0) { e.preventDefault(); (all[i + 1] || all[i]).focus(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); if (i <= 0) { inp.focus(); } else { all[i - 1].focus(); } }
      else if (e.key === 'Escape') { inp.focus(); }
    });
    D.addEventListener('keydown', function (e) {
      if (e.key === '/' && D.activeElement !== inp && !/^(INPUT|TEXTAREA|SELECT)$/.test(D.activeElement.tagName)) { e.preventDefault(); inp.focus(); inp.select(); }
    });
    langHooks.push(run);
    loadData().then(function () { run(); }).catch(function () {
      status.textContent = T('Suchdaten konnten nicht geladen werden.', 'Could not load search data.');
    });
  }

  /* ---------- Item-Liste ---------- */
  function initItems() {
    var iq = $('#iq'), selC = $('#icat'), selM = $('#imod'), selH = $('#ih'), selS = $('#isort'), grid = $('#igrid'), more = $('#imore'), cnt = $('#icount');
    var PAGE = 60, shown = 0, list = [], orderCache = {};
    function nameOrder(d) {
      if (orderCache[lang]) { return orderCache[lang]; }
      var col = new Intl.Collator(lang === 'en' ? 'en' : 'de', { numeric: true, sensitivity: 'base' }), idx = [];
      for (var i = 0; i < d.items.length; i++) { idx.push(i); }
      idx.sort(function (a, b) { return col.compare(itemName(d.items[a]), itemName(d.items[b])) || a - b; });
      return (orderCache[lang] = idx);
    }
    function fillSelects(d) {
      var cur = { c: selC.value, m: selM.value, h: selH.value, s: selS.value }, i, o;
      var cc = new Array(d.cats.length), mm = new Array(d.mods.length), hh = new Array(d.hand.length);
      cc.fill(0); mm.fill(0); hh.fill(0);
      d.items.forEach(function (r) {
        cc[r[7]]++; mm[r[3]]++;
        for (var h = 0; h < d.hand.length; h++) { if (r[6] & (1 << h)) { hh[h]++; } }
      });
      var col = new Intl.Collator(lang === 'en' ? 'en' : 'de');
      var cats = d.cats.map(function (c, k) { return k; }).sort(function (a, b) { return col.compare(catName(d, a), catName(d, b)); });
      var mods = d.mods.map(function (c, k) { return k; }).sort(function (a, b) { return d.mods[a][0] < d.mods[b][0] ? -1 : 1; });
      selC.innerHTML = '<option value="">' + T('Alle Kategorien', 'All categories') + '</option>' + cats.map(function (k) { return '<option value="' + k + '">' + esc(catName(d, k)) + ' (' + cc[k] + ')</option>'; }).join('');
      selM.innerHTML = '<option value="">' + T('Alle Mods', 'All mods') + '</option>' + mods.map(function (k) { return '<option value="' + k + '">' + esc(d.mods[k][0] + ' – ' + d.mods[k][1]) + ' (' + mm[k] + ')</option>'; }).join('');
      selH.innerHTML = '<option value="">' + T('Alle Händler', 'All traders') + '</option>' + d.hand.map(function (h, k) { return hh[k] ? '<option value="' + k + '">' + esc(h) + ' (' + hh[k] + ')</option>' : ''; }).join('');
      selS.innerHTML = [['rel', 'Relevanz / Name', 'Relevance / name'], ['name', 'Name A–Z', 'Name A–Z'], ['kauf-', 'Kaufpreis ↑', 'Buy price ↑'], ['kauf+', 'Kaufpreis ↓', 'Buy price ↓'], ['verk+', 'Verkaufspreis ↓', 'Sell price ↓']]
        .map(function (o) { return '<option value="' + o[0] + '">' + T(o[1], o[2]) + '</option>'; }).join('');
      selC.value = cur.c; selM.value = cur.m; selH.value = cur.h; selS.value = cur.s || 'rel';
      if (selC.value !== cur.c) { selC.value = ''; }
    }
    function compute() {
      var d = DB, q = iq.value, base, i, out = [];
      var sort = selS.value || 'rel';
      if (fold(q)) { base = searchAll(d, q).items.map(function (h) { return h.i; }); }
      else { base = nameOrder(d); }
      var c = selC.value, m = selM.value, h = selH.value;
      for (i = 0; i < base.length; i++) {
        var r = d.items[base[i]];
        if (c !== '' && r[7] !== +c) { continue; }
        if (m !== '' && r[3] !== +m) { continue; }
        if (h !== '' && !(r[6] & (1 << +h))) { continue; }
        out.push(base[i]);
      }
      if (sort === 'name' && fold(q)) {
        var no = nameOrder(d), pos = {}; no.forEach(function (k, p) { pos[k] = p; });
        out.sort(function (a, b) { return pos[a] - pos[b]; });
      } else if (sort === 'kauf-' || sort === 'kauf+' || sort === 'verk+') {
        var f = sort === 'verk+' ? 5 : 4, dir = sort === 'kauf-' ? 1 : -1;
        out = out.filter(function (k) { return d.items[k][f] != null; });
        out.sort(function (a, b) { return dir * (d.items[a][f] - d.items[b][f]) || a - b; });
      }
      list = out;
    }
    function render(reset) {
      if (reset) { shown = 0; grid.innerHTML = ''; }
      var d = DB, end = Math.min(list.length, shown + PAGE), html = '';
      for (var i = shown; i < end; i++) { html += itemCard(d, d.items[list[i]]); }
      grid.insertAdjacentHTML('beforeend', html);
      shown = end;
      cnt.textContent = nf(list.length) + ' ' + T('Items', 'items') + (list.length ? ' · ' + T('angezeigt: ', 'showing: ') + nf(shown) : '');
      if (shown < list.length) { more.hidden = false; more.textContent = T('Mehr anzeigen', 'Show more') + ' (' + nf(list.length - shown) + ')'; }
      else { more.hidden = true; }
      if (!list.length) { grid.innerHTML = '<p class="leer">' + T('Keine Items gefunden.', 'No items found.') + '</p>'; }
    }
    function apply() {
      compute(); render(true);
      updateQS({ q: iq.value, kat: selC.value, mod: selM.value, h: selH.value, s: selS.value !== 'rel' ? selS.value : '' });
    }
    var applyDeb = debounce(apply, 120);
    iq.addEventListener('input', applyDeb);
    [selC, selM, selH, selS].forEach(function (s) { s.addEventListener('change', apply); });
    more.addEventListener('click', function () { render(false); });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (en) { if (en[0].isIntersecting && !more.hidden) { render(false); } }, { rootMargin: '600px' }).observe(more.parentNode);
    }
    loadData().then(function (d) {
      fillSelects(d);
      iq.value = qsGet('q'); selC.value = qsGet('kat'); selM.value = qsGet('mod'); selH.value = qsGet('h'); selS.value = qsGet('s') || 'rel';
      compute(); render(true);
      langHooks.push(function () { fillSelects(d); compute(); render(true); });
    }).catch(function () { cnt.textContent = T('Daten konnten nicht geladen werden.', 'Could not load data.'); });
  }

  /* ---------- Quests + FAQ: Textfilter ---------- */
  function initFilterList() {
    var inp = $('#fq'), cnt = $('#fcount'), root = $('#fliste');
    var cards = $$('.qcard', root), faqs = $$('.fq', root), nodes = cards.length ? cards : faqs;
    var typ = $('#ftyp'), geb = $('#fgeber');
    var keys = nodes.map(function (n) { return fold(n.textContent).replace(/ /g, ''); });
    var words = nodes.map(function (n) { return fold(n.textContent); });
    function apply() {
      var toks = fold(inp.value).split(' ').filter(Boolean), n = 0;
      nodes.forEach(function (el, i) {
        var ok = true;
        toks.forEach(function (t) { if (keys[i].indexOf(t) < 0) { ok = false; } });
        if (ok && typ && typ.value && el.getAttribute('data-typ') !== typ.value) { ok = false; }
        if (ok && geb && geb.value && el.getAttribute('data-geber') !== geb.value) { ok = false; }
        el.hidden = !ok; if (ok) { n++; }
      });
      $$('.fgruppe', root).forEach(function (g) { g.hidden = !$$('.fq', g).some(function (e) { return !e.hidden; }); });
      cnt.textContent = n + ' / ' + nodes.length + ' ' + (cards.length ? 'Quests' : T('Fragen', 'questions'));
    }
    inp.addEventListener('input', debounce(apply, 100));
    [typ, geb].forEach(function (s) { if (s) { s.addEventListener('change', apply); } });
    langHooks.push(apply);
    inp.value = qsGet('q'); apply();
    function hash() {
      var id = location.hash.slice(1), el = id && D.getElementById(id);
      if (el) { if (el.tagName === 'DETAILS') { el.open = true; } el.scrollIntoView(); }
    }
    window.addEventListener('hashchange', hash); hash();
    void words;
  }

  /* ---------- Kopfzeilen-Suche (alle Unterseiten): Enter -> Wiki-Startseite mit ?q= (reines GET-Formular) ---------- */
  var page = D.body.getAttribute('data-page');
  if (page === 'index') { initIndex(); }
  else if (page === 'items') { initItems(); }
  else if (page === 'quests' || page === 'faq') { initFilterList(); }
})();
