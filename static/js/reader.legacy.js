(function () {
  var MR = window.MR;
  var state = {
    bookId: null, book: null, kind: null, manifest: null,
    settings: null, sections: new Map(), currentSection: 0,
    page: 0, pages: 1, lastSave: 0, saveTimer: null, viewer: null
  };

  var DEFAULTS = {
    font_family: 'serif', font_size: 18, font_weight: 400,
    line_spacing: 1.8, paragraph_spacing: 1.2, word_spacing: 0,
    letter_spacing: 0, text_indent: 2, indent: 1, justify: 1,
    theme_preset: 'paper', background_color: '', text_color: '',
    page_mode: 'scroll', page_width: '720px', v_margin: 32, tap_zones: 1
  };
  var THEMES = {
    paper: { bg: '#f7f4ec', fg: '#2c2a25' },
    parchment: { bg: '#f0e4cd', fg: '#4a3b28' },
    gray: { bg: '#e8e8e6', fg: '#33363a' },
    slate: { bg: '#2b3037', fg: '#b8bdc4' },
    ink: { bg: '#16181d', fg: '#a8adb5' }
  };

  function root() { return document.getElementById('reader'); }
  function $(sel) { return root().querySelector(sel); }
  function settingsOf() {
    var s = {};
    for (var k in DEFAULTS) s[k] = DEFAULTS[k];
    if (state.settings) for (var k2 in state.settings) if (state.settings[k2] != null) s[k2] = state.settings[k2];
    return s;
  }

  function buildSkeleton(title) {
    var r = root();
    r.hidden = false;
    document.body.style.overflow = 'hidden';
    r.innerHTML =
      '<div id="readerToolbar" class="reader-toolbar">' +
      '<button class="btn btn-ghost btn-icon" id="rdBack"><svg><use href="#icon-arrow-left"/></svg></button>' +
      '<div class="rt-title" id="rdTitle">' + MR.esc(title || '') + '</div>' +
      '<button class="btn btn-ghost btn-icon" id="rdToc"><svg><use href="#icon-list"/></svg></button>' +
      '<button class="btn btn-ghost btn-icon" id="rdBm"><svg><use href="#icon-bookmark"/></svg></button>' +
      '<button class="btn btn-ghost btn-icon" id="rdSet"><svg><use href="#icon-sliders"/></svg></button></div>' +
      '<div class="reader-body" id="readerBody">' +
      '<div class="reader-scroll" id="readerScroll" hidden><div class="reader-content" id="readerContent"></div></div>' +
      '<div id="pagedHost" hidden style="position:absolute;inset:0;overflow:hidden">' +
      '<div id="pagedInner" style="height:100%;will-change:transform"></div></div>' +
      '<div class="tap-zones" id="tapZones" hidden><div data-tap="prev"></div><div data-tap="menu"></div><div data-tap="next"></div></div></div>' +
      '<div id="readerFooter" class="reader-footer">' +
      '<span class="rf-pos" id="rdPos">0%</span>' +
      '<div class="progress" id="rdBar"><i style="width:0%"></i></div>' +
      '<span class="rf-pos" id="rdChapter">--</span></div>';
    $('#rdBack').addEventListener('click', close);
    $('#rdToc').addEventListener('click', openTocDrawer);
    $('#rdSet').addEventListener('click', openSettingsDrawer);
    $('#rdBm').addEventListener('click', openBmDrawer);
    $('#tapZones').addEventListener('click', function (e) {
      var zone = e.target.closest('[data-tap]');
      if (!zone) return;
      if (zone.dataset.tap === 'next') next();
      else if (zone.dataset.tap === 'prev') prev();
    });
    $('#rdBar').addEventListener('click', function (e) {
      var rect = e.currentTarget.getBoundingClientRect();
      jumpFraction((e.clientX - rect.left) / rect.width);
    });
    document.addEventListener('keydown', onKey);
  }

  function onKey(e) {
    if (root().hidden) return;
    if (e.key === 'ArrowRight' || e.key === 'PageDown') { next(); e.preventDefault(); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { prev(); e.preventDefault(); }
    else if (e.key === 'Escape') close();
  }

  function next() {
    if (state.mode === 'paged') pageTurn(1);
    else {
      var sc = $('#readerScroll');
      sc.scrollTop += sc.clientHeight * 0.9;
    }
  }

  function prev() {
    if (state.mode === 'paged') pageTurn(-1);
    else {
      var sc = $('#readerScroll');
      sc.scrollTop -= sc.clientHeight * 0.9;
    }
  }

  function close() {
    saveProgress(true);
    if (state.viewer && state.viewer.destroy) state.viewer.destroy();
    state.viewer = null;
    root().hidden = true;
    root().innerHTML = '';
    document.body.style.overflow = '';
    state.bookId = null;
    state.sections = new Map();
    document.removeEventListener('keydown', onKey);
  }

  function fetchSection(n) {
    if (state.sections.has(n)) return Promise.resolve(state.sections.get(n));
    return fetch('/api/books/' + state.bookId + '/section/' + n).then(function (r) {
      if (!r.ok) throw new Error('章节加载失败');
      return r.text();
    }).then(function (html) {
      state.sections.set(n, html);
      return html;
    });
  }

  function canPage() {
  if (state.kind === 'native') return true;
  if (state.kind === 'canonical') return !!(state.book && state.book.format !== 'docx');
  return false;
}

function showReaderLoading() {
  var body = document.getElementById('readerBody');
  if (!body || document.getElementById('rdLoading')) return;
  var ld = document.createElement('div');
  ld.id = 'rdLoading';
  ld.style.cssText = 'position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;z-index:6';
  ld.innerHTML = '<div style="display:flex;align-items:center;gap:8px;color:var(--accent)">' +
    '<svg style="width:30px;height:30px"><use href="#icon-logo"/></svg>' +
    '<span style="font-weight:600;font-size:17px;color:var(--text)">极读</span></div>' +
    '<div style="width:28px;height:28px;border-radius:50%;border:3px solid var(--border);border-top-color:var(--accent);animation:mrLoaderSpin .8s linear infinite"></div>';
  body.appendChild(ld);
}

function hideReaderLoading() {
  var ld = document.getElementById('rdLoading');
  if (ld && ld.parentNode) ld.parentNode.removeChild(ld);
}

function applyTheme() {
    var s = settingsOf();
    var t = THEMES[s.theme_preset] || THEMES.paper;
    var r = root();
    r.style.background = s.background_color || t.bg;
    var fg = s.text_color || t.fg;
    ['readerBody', 'readerToolbar', 'readerFooter'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      el.style.color = fg;
      if (id !== 'readerBody') el.style.background = s.background_color || t.bg;
    });
    var font = s.font_family === 'serif' ? 'var(--font-serif)' : s.font_family === 'mono' ? 'var(--font-mono)' : 'var(--font-sans)';
    ['#readerContent', '#pagedInner'].forEach(function (sel) {
      var box = $(sel);
      if (!box) return;
      box.style.fontFamily = font;
      box.style.fontSize = s.font_size + 'px';
      box.style.fontWeight = s.font_weight;
      box.style.lineHeight = s.line_spacing;
      box.style.wordSpacing = s.word_spacing + 'px';
      box.style.letterSpacing = s.letter_spacing + 'px';
      box.style.textAlign = s.justify ? 'justify' : 'start';
      var ps = box.querySelectorAll('p');
      for (var i = 0; i < ps.length; i++) {
        ps[i].style.marginBottom = s.paragraph_spacing + 'em';
        ps[i].style.textIndent = s.indent ? '2em' : '0';
      }
      var hs = box.querySelectorAll('h1,h2,h3,h4,h5,h6');
      for (var j = 0; j < hs.length; j++) {
        hs[j].style.color = fg;
      }
      var lns = box.querySelectorAll('div.ln, div.ln-gap');
      for (var k = 0; k < lns.length; k++) {
        lns[k].style.textIndent = '0';
        lns[k].style.marginBottom = '0';
      }
    });
    var content = $('#readerContent');
    if (content) {
      content.style.maxWidth = s.page_width;
      content.style.paddingTop = s.v_margin + 'px';
      content.style.paddingBottom = s.v_margin + 'px';
    }
  }

  function updateFooter(frac, chapterTitle) {
    $('#rdBar').firstElementChild.style.width = (Math.min(1, frac) * 100).toFixed(1) + '%';
    $('#rdPos').textContent = (Math.min(1, frac) * 100).toFixed(1) + '%';
    if (chapterTitle !== undefined) $('#rdChapter').textContent = chapterTitle || '--';
  }

  function saveProgress(immediate, data) {
    if (!state.bookId) return;
    state.lastSave = Date.now();
    var payload = { position: 0, chapter_title: '', position_data: null };
    if (data) {
      if (data.type === 'canonical') {
        payload.position_data = { type: 'canonical', chapter: data.chapter, offset: data.offset || 0 };
        payload.position = state.manifest ? data.chapter / state.manifest.sections.length : 0;
        payload.chapter_title = state.manifest && state.manifest.sections[data.chapter] ? state.manifest.sections[data.chapter].title : '';
      } else if (data.type === 'page') {
        payload.position_data = { type: 'canonical', chapter: data.chapter, offset: data.offset || 0 };
        payload.position = state.manifest ? data.chapter / state.manifest.sections.length : 0;
        payload.chapter_title = state.manifest && state.manifest.sections[data.chapter] ? state.manifest.sections[data.chapter].title : '';
      }
    }
    var body = JSON.stringify(payload);
    if (!immediate) {
      clearTimeout(state.saveTimer);
      state.saveTimer = setTimeout(function () {
        MR.api('/api/reading/' + state.bookId + '/position', { method: 'PUT', json: payload }).catch(function () {});
      }, 1500);
    } else {
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/reading/' + state.bookId + '/position', new Blob([body], { type: 'application/json' }));
      } else {
        MR.api('/api/reading/' + state.bookId + '/position', { method: 'PUT', json: payload }).catch(function () {});
      }
    }
  }

  function openCanonicalScroll(startPos) {
    $('#readerScroll').hidden = false;
    $('#pagedHost').hidden = true;
    $('#tapZones').hidden = true;
    state.mode = 'scroll';
    var content = $('#readerContent');
    content.innerHTML = '';
    var total = state.manifest.sections.length;
    var rendered = {};
    var current = startPos ? startPos.chapter || 0 : 0;

    function ensure(n) {
      if (n < 0 || n >= total || rendered[n]) return Promise.resolve();
      rendered[n] = true;
      var sec = document.createElement('section');
      sec.id = 'sec-' + n;
      var h = document.createElement('h2');
      h.textContent = state.manifest.sections[n].title;
      sec.appendChild(h);
      var body = document.createElement('div');
      sec.appendChild(body);
      content.appendChild(sec);
      return fetchSection(n).then(function (html) {
        body.innerHTML = html;
        applyTheme();
      });
    }

    function trim(around) {
      for (var n in rendered) {
        if (Math.abs(Number(n) - around) > 4) {
          delete rendered[n];
          var el = content.querySelector('#sec-' + n);
          if (el && el.parentNode) el.parentNode.removeChild(el);
        }
      }
    }

    var chain = Promise.resolve();
    for (var i = Math.max(0, current - 1); i <= Math.min(total - 1, current + 2); i++) {
      (function (idx) { chain = chain.then(function () { return ensure(idx); }); })(i);
    }

    var scroller = $('#readerScroll');
    var ticking = false;
    scroller.addEventListener('scroll', function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        ticking = false;
        var pos = scroller.scrollTop + scroller.clientHeight * 0.4;
        var idx = 0;
        var secs = content.querySelectorAll('section');
        for (var j = 0; j < secs.length; j++) {
          if (secs[j].offsetTop <= pos) idx = parseInt(secs[j].id.slice(4), 10);
        }
        current = idx;
        state.currentSection = idx;
        var secEl = content.querySelector('#sec-' + idx);
        var inner = secEl ? Math.min(1, Math.max(0, (pos - secEl.offsetTop) / Math.max(1, secEl.offsetHeight))) : 0;
        updateFooter(Math.min(1, (idx + inner) / total), state.manifest.sections[idx].title);
        if (Date.now() - state.lastSave > 4000) {
          var offset = secEl ? Math.max(0, Math.round((pos - secEl.offsetTop) * 4)) : 0;
          saveProgress(false, { type: 'canonical', chapter: idx, offset: offset });
        }
        ensure(idx + 2).then(function () { return ensure(idx - 1); }).then(trim.bind(null, idx));
      });
    }, { passive: true });

    chain.then(function () {
      if (startPos && startPos.offset) {
        var el = content.querySelector('#sec-' + current);
        if (el) scroller.scrollTop = el.offsetTop + startPos.offset / 4;
      } else if (startPos && startPos.chapter) {
        var el2 = content.querySelector('#sec-' + current);
        if (el2) scroller.scrollTop = el2.offsetTop;
      }
      updateFooter(0, state.manifest.sections[current].title);
      applyTheme();
    });
  }

  function openCanonicalPaged(startPos) {
    $('#readerScroll').hidden = true;
    $('#pagedHost').hidden = false;
    $('#tapZones').hidden = !settingsOf().tap_zones;
    state.mode = 'paged';
    var host = $('#pagedHost');
    var inner = $('#pagedInner');
    var total = state.manifest.sections.length;
    var section = startPos ? startPos.chapter || 0 : 0;
    var estOffset = startPos ? startPos.offset || 0 : 0;

    function loadSection(n) {
      state.currentSection = n;
      return fetchSection(n).then(function (html) {
        inner.innerHTML = '<div class="reader-content" style="max-width:none;margin:0;height:100%">' + html + '</div>';
        applyTheme();
        layout();
      });
    }

    function layout() {
      var w = host.clientWidth;
      var h = host.clientHeight;
      inner.style.height = h + 'px';
      inner.style.columnWidth = w + 'px';
      inner.style.columnGap = w + 'px';
      inner.style.columnFill = 'auto';
      inner.style.width = w + 'px';
      inner.style.overflow = 'hidden';
      var contentW = inner.scrollWidth;
      state.pages = Math.max(1, Math.round(contentW / (w + 1)));
      state.page = Math.min(state.page, state.pages - 1);
      apply();
    }

    function apply() {
      var w = host.clientWidth;
      inner.style.transform = 'translateX(' + (-state.page * (w)) + 'px)';
      var frac = (section + (state.page + 1) / state.pages) / total;
      updateFooter(Math.min(1, frac), state.manifest.sections[section].title);
      saveProgress(false, { type: 'page', chapter: section, offset: Math.round((state.page / Math.max(1, state.pages)) * 20000) });
    }

    function pageTurn(dir) {
      state.page += dir;
      if (state.page < 0) {
        if (section > 0) { section--; state.page = 99999; loadSection(section).then(function () { state.page = state.pages - 1; apply(); }); return; }
        state.page = 0;
      } else if (state.page >= state.pages) {
        if (section < total - 1) { section++; state.page = 0; loadSection(section); return; }
        state.page = state.pages - 1;
      }
      apply();
    }

    state.pageTurn = pageTurn;
    window.addEventListener('resize', function () {
      if (state.mode === 'paged' && !root().hidden) layout();
    });
    var startPage = Math.min(50, Math.floor((estOffset / 20000) * 40));
    loadSection(section).then(function () {
      state.page = Math.min(state.pages - 1, startPage);
      apply();
    });
  }

  function jumpFraction(frac) {
    var total = state.manifest.sections.length;
    var idx = Math.min(total - 1, Math.floor(frac * total));
    var pos = { chapter: idx, offset: 0 };
    if (state.mode === 'paged') openCanonicalPaged(pos);
    else openCanonicalScroll(pos);
  }

  function open(bookId, book) {
    var prep = book ? Promise.resolve(book) : MR.api('/api/books/' + bookId);
    return prep.then(function (b) {
      state.bookId = bookId;
      state.book = b;
      state.kind = b.read_kind;
      return MR.api('/api/reading/' + bookId + '/settings').then(function (s) {
        state.settings = s || {};
      }).catch(function () { state.settings = {}; });
    }).then(function () {
      return MR.api('/api/books/' + bookId + '/manifest');
    }).then(function (m) {
      buildSkeleton(state.book.title);
    showReaderLoading();
      if (state.kind === 'canonical') {
        state.manifest = m;
        var pos = state.book.position && state.book.position.type === 'canonical' ? state.book.position : null;
        if (canPage() && settingsOf().page_mode === 'paged') openCanonicalPaged(pos);
        else openCanonicalScroll(pos);
      } else if (state.kind === 'pdf') {
        return import('/static/js/pdf-viewer.js?v=' + (window.STATIC_V || '')).then(function (mod) {
          var s = settingsOf();
          return mod.openPdf($('#readerBody'), m.file_url, {
            getSettings: settingsOf,
            onProgress: function (frac, label) { updateFooter(frac, label); }
          });
        }).then(function (v) { state.viewer = v; });
      } else if (state.kind === 'pptx') {
        return pollManifest(bookId, m).then(function (mm) {
          if (mm && mm.format === 'pdf') {
            return import('/static/js/pdf-viewer.js?v=' + (window.STATIC_V || '')).then(function (mod) {
              return mod.openPdf($('#readerBody'), mm.file_url, {
                getSettings: settingsOf,
                onProgress: function (frac, label) { updateFooter(frac, label); }
              });
            }).then(function (v) { state.viewer = v; });
          }
          return import('/static/js/pptx-viewer.js?v=' + (window.STATIC_V || '')).then(function (mod) {
            return mod.openPptx($('#readerBody'), m.file_url, {
              onProgress: function (frac, label) { updateFooter(frac, label); }
            });
          }).then(function (v) { state.viewer = v; });
        });
      } else {
        MR.toast('此格式需要较新的浏览器（Chrome 100+）才能打开', 'error');
        close();
      }
    }).then(function () { hideReaderLoading(); }).catch(function (e) {
      MR.toast((e && e.message) || '打开失败', 'error');
      close();
    });
  }

  function drawerShell(title, bodyHTML) {
    var old = root().querySelector('.drawer-backdrop');
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var bd = document.createElement('div');
    bd.className = 'drawer-backdrop';
    bd.innerHTML =
      '<div class="drawer drawer-right open">' +
      '<div class="drawer-header"><h3>' + MR.esc(title) + '</h3>' +
      '<button class="btn btn-ghost btn-icon" data-close><svg><use href="#icon-x"/></svg></button></div>' +
      '<div class="drawer-body">' + bodyHTML + '</div></div>';
    bd.addEventListener('click', function (e) {
      if (e.target === bd || e.target.closest('[data-close]')) {
        if (bd.parentNode) bd.parentNode.removeChild(bd);
      }
    });
    root().appendChild(bd);
    return bd;
  }

  function openTocDrawer() {
    if (!state.manifest) return;
    var list = '';
    for (var i = 0; i < state.manifest.sections.length; i++) {
      list += '<button class="toc-item" data-sec="' + i + '">' + MR.esc(state.manifest.sections[i].title) + '</button>';
    }
    var bd = drawerShell('目录', '<div>' + (list || '无目录') + '</div>');
    bd.addEventListener('click', function (e) {
      var item = e.target.closest('[data-sec]');
      if (!item) return;
      if (bd.parentNode) bd.parentNode.removeChild(bd);
      var idx = parseInt(item.dataset.sec, 10);
      if (state.mode === 'paged') openCanonicalPaged({ chapter: idx, offset: 0 });
      else openCanonicalScroll({ chapter: idx, offset: 0 });
    });
  }

  function openSettingsDrawer() {
    var s = settingsOf();
    var rows = '';
    [['font_size', '字号', 12, 32, 1], ['line_spacing', '行高', 1.2, 2.6, 0.1],
     ['paragraph_spacing', '段距', 0.4, 3, 0.1], ['letter_spacing', '字间距', 0, 4, 0.5],
     ['word_spacing', '词间距', 0, 8, 0.5], ['v_margin', '页边距', 8, 96, 4]].forEach(function (cfg) {
      rows += '<div class="setting-row"><label>' + cfg[1] + '</label>' +
        '<input type="range" class="range" id="st_' + cfg[0] + '" min="' + cfg[2] + '" max="' + cfg[3] + '" step="' + cfg[4] + '" value="' + s[cfg[0]] + '">' +
        '<span class="text-3" style="width:44px;text-align:right" id="stv_' + cfg[0] + '">' + s[cfg[0]] + '</span></div>';
    });
    var dots = '';
    for (var k in THEMES) {
      dots += '<div class="theme-dot ' + (s.theme_preset === k ? 'active' : '') + '" data-tp="' + k + '" style="background:' + THEMES[k].bg + '"></div>';
    }
    var bd = drawerShell('阅读设置',
      '<div class="theme-dots">' + dots + '</div>' +
      '<div class="setting-row"><label>字体</label><select class="select" style="width:150px" id="stFont">' +
      '<option value="serif"' + (s.font_family === 'serif' ? ' selected' : '') + '>衬线</option>' +
      '<option value="sans"' + (s.font_family === 'sans' ? ' selected' : '') + '>无衬线</option>' +
      '<option value="mono"' + (s.font_family === 'mono' ? ' selected' : '') + '>等宽</option></select></div>' +
      rows +
      '<label class="setting-row"><label>两端对齐</label><span class="switch"><input type="checkbox" id="st_justify"' + (s.justify ? ' checked' : '') + '><span class="track"></span></span></label>' +
      '<label class="setting-row"><label>首行缩进</label><span class="switch"><input type="checkbox" id="st_indent"' + (s.indent ? ' checked' : '') + '><span class="track"></span></span></label>' +
      '<div class="setting-row" id="stModeRow"><label>阅读模式</label><select class="select" style="width:150px" id="stMode">' +
      '<option value="scroll"' + (s.page_mode === 'scroll' ? ' selected' : '') + '>上下滚动</option>' +
      '<option value="paged"' + (s.page_mode === 'paged' ? ' selected' : '') + '>左右翻页</option></select></div>' +
      '<button class="btn w-full mt-3" id="stReset">恢复默认</button>');

    function save(patch) {
      for (var p in patch) state.settings[p] = patch[p];
      applyTheme();
      clearTimeout(bd._t);
      bd._t = setTimeout(function () {
        MR.api('/api/reading/' + state.bookId + '/settings', { method: 'PUT', json: patch }).catch(function () {});
      }, 400);
    }

    var dots2 = bd.querySelectorAll('.theme-dot');
    for (var d = 0; d < dots2.length; d++) {
      (function (el) {
        el.addEventListener('click', function () {
          for (var x = 0; x < dots2.length; x++) dots2[x].classList.remove('active');
          el.classList.add('active');
          save({ theme_preset: el.dataset.tp });
        });
      })(dots2[d]);
    }
    bd.querySelector('#stFont').addEventListener('change', function (e) { save({ font_family: e.target.value }); });
    bd.querySelector('#stTextColor').addEventListener('change', function (e) {
      bd.querySelector('#stTextColorCustom').value = e.target.value || '#1d1c19';
      save({ text_color: e.target.value });
    });
    bd.querySelector('#stTextColorCustom').addEventListener('input', MR.debounce(function (e) {
      bd.querySelector('#stTextColor').value = e.target.value;
      save({ text_color: e.target.value });
    }, 300));
    ['font_size', 'line_spacing', 'paragraph_spacing', 'letter_spacing', 'word_spacing', 'v_margin'].forEach(function (k) {
      var inp = bd.querySelector('#st_' + k);
      if (!inp) return;
      inp.addEventListener('input', function () {
        bd.querySelector('#stv_' + k).textContent = inp.value;
        var patch = {};
        patch[k] = parseFloat(inp.value);
        save(patch);
      });
    });
    ['justify', 'indent'].forEach(function (k) {
      bd.querySelector('#st_' + k).addEventListener('change', function (e) {
        var patch = {};
        patch[k] = e.target.checked ? 1 : 0;
        save(patch);
      });
    });
    if (!canPage()) {
        var _r = bd.querySelector('#stModeRow');
        if (_r) _r.parentNode.removeChild(_r);
      }
      bd.querySelector('#stMode').addEventListener('change', function (e) {
      save({ page_mode: e.target.value });
      if (state.kind !== 'canonical') {
        if (state.kind === 'pdf' && state.viewer && state.viewer.setMode) {
          state.viewer.setMode(e.target.value === 'paged' ? 'paged' : 'scroll');
        }
        return;
      }
      var pos = { chapter: state.currentSection, offset: 0 };
      if (e.target.value === 'paged') openCanonicalPaged(pos);
      else openCanonicalScroll(pos);
    });
    bd.querySelector('#stReset').addEventListener('click', function () {
      state.settings = {};
      applyTheme();
      if (bd.parentNode) bd.parentNode.removeChild(bd);
      openSettingsDrawer();
    });
  }

  function openBmDrawer() {
    Promise.all([
      MR.api('/api/reading/' + state.bookId + '/bookmarks').catch(function () { return []; }),
      MR.api('/api/reading/' + state.bookId + '/highlights').catch(function () { return []; })
    ]).then(function (res) {
      var bookmarks = res[0] || [];
      var highlights = res[1] || [];
      var bmHtml = '';
      for (var i = 0; i < bookmarks.length; i++) {
        var b = bookmarks[i];
        bmHtml += '<div class="bm-item" data-bm-go="' + b.id + '">' +
          '<div class="row gap-2"><span class="flex-1 truncate">' + MR.esc(b.note || b.chapter || '书签') + '</span>' +
          '<button class="btn btn-ghost btn-icon btn-sm" data-bm-edit="' + b.id + '" title="重命名"><svg><use href="#icon-edit"/></svg></button>' +
          '<button class="btn btn-ghost btn-icon btn-sm" data-bm-del="' + b.id + '" title="删除"><svg><use href="#icon-trash"/></svg></button></div>' +
          '<div class="bm-sub">' + MR.esc(b.chapter || '') + ' · ' + MR.fmtDate(b.created_at) + '</div></div>';
      }
      var hlHtml = '';
      for (var j = 0; j < highlights.length; j++) {
        var h = highlights[j];
        hlHtml += '<div class="bm-item" style="border-left:3px solid ' + MR.esc(h.color) + '">' +
          '<div class="row gap-2"><span class="flex-1">' + MR.esc(String(h.selected_text).slice(0, 60)) + '</span>' +
          '<button class="btn btn-ghost btn-icon btn-sm" data-hl-del="' + h.id + '" title="删除"><svg><use href="#icon-trash"/></svg></button></div>' +
          '<div class="bm-sub">' + MR.esc(h.chapter || '') + ' · ' + MR.fmtDate(h.created_at) + '</div></div>';
      }
      var bd = drawerShell('书签与标注',
        '<button class="btn w-full" id="bmAdd"><svg><use href="#icon-bookmark-add"/></svg>在此处添加书签</button>' +
        '<div class="mt-3">' + (bmHtml || '<div class="text-3" style="font-size:var(--fs-sm)">暂无书签</div>') + '</div>' +
        '<h4 class="mt-3">标注</h4><div>' + (hlHtml || '<div class="text-3" style="font-size:var(--fs-sm)">暂无标注</div>') + '</div>');

      function refresh() {
        if (bd.parentNode) bd.parentNode.removeChild(bd);
        openBmDrawer();
      }

      bd.querySelector('#bmAdd').addEventListener('click', function () {
        var note = prompt('书签备注（可留空）') || '';
        var secTitle = state.manifest && state.manifest.sections[state.currentSection] ? state.manifest.sections[state.currentSection].title : '';
        var data = {
          chapter: secTitle,
          position_data: { type: 'canonical', chapter: state.currentSection },
          note: note
        };
        MR.api('/api/reading/' + state.bookId + '/bookmarks', { method: 'POST', json: data })
          .then(function () { MR.toast('书签已添加', 'success'); refresh(); })
          .catch(function (e) { MR.toast(e.message, 'error'); });
      });

      bd.addEventListener('click', function (e) {
        var editBtn = e.target.closest('[data-bm-edit]');
        if (editBtn) {
          e.stopPropagation();
          var target = null;
          for (var a = 0; a < bookmarks.length; a++) {
            if (bookmarks[a].id === parseInt(editBtn.dataset.bmEdit, 10)) target = bookmarks[a];
          }
          var newName = prompt('重命名书签：', (target && target.note) || '');
          if (newName === null) return;
          MR.api('/api/reading/' + state.bookId + '/bookmarks/' + editBtn.dataset.bmEdit, { method: 'PUT', json: { note: newName } })
            .then(refresh)
            .catch(function (err) { MR.toast(err.message, 'error'); });
          return;
        }
        var delBtn = e.target.closest('[data-bm-del]');
        if (delBtn) {
          e.stopPropagation();
          MR.confirmDialog('删除书签', '确定删除该书签？').then(function (ok) {
            if (!ok) return;
            MR.api('/api/reading/' + state.bookId + '/bookmarks/' + delBtn.dataset.bmDel, { method: 'DELETE' })
              .then(refresh)
              .catch(function (err) { MR.toast(err.message, 'error'); });
          });
          return;
        }
        var hlDel = e.target.closest('[data-hl-del]');
        if (hlDel) {
          e.stopPropagation();
          MR.confirmDialog('删除标注', '确定删除该标注？').then(function (ok) {
            if (!ok) return;
            MR.api('/api/reading/' + state.bookId + '/highlights/' + hlDel.dataset.hlDel, { method: 'DELETE' })
              .then(refresh)
              .catch(function (err) { MR.toast(err.message, 'error'); });
          });
          return;
        }
        var go = e.target.closest('[data-bm-go]');
        if (go) {
          if (bd.parentNode) bd.parentNode.removeChild(bd);
          var bm = null;
          for (var c = 0; c < bookmarks.length; c++) {
            if (bookmarks[c].id === parseInt(go.dataset.bmGo, 10)) bm = bookmarks[c];
          }
          var pd = null;
          try { pd = typeof bm.position === 'string' ? JSON.parse(bm.position) : bm.position; } catch (err2) { pd = null; }
          if (pd && pd.type === 'canonical' && pd.chapter != null) {
            if (state.mode === 'paged') openCanonicalPaged({ chapter: pd.chapter, offset: pd.offset || 0 });
            else openCanonicalScroll({ chapter: pd.chapter, offset: pd.offset || 0 });
          }
        }
      });
    });
  }

  window.MRReader = { open: open };

  function boot() {
    var m = location.pathname.match(/^\/old\/main\/b\/(.+)$/);
    if (!m) return;
    MR.api('/api/books/by-fp/' + m[1]).then(function (book) { open(book.id, book); })
      .catch(function (e) { MR.toast(e.message, 'error'); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
