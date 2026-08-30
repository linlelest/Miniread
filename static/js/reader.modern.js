const MR = window.MR;

const state = {
  bookId: null,
  book: null,
  kind: null,
  manifest: null,
  settings: null,
  view: null,
  engine: 'none',
  sections: new Map(),
  currentSection: 0,
  saveTimer: null,
  lastSave: 0,
  lastProgressData: null,
  foliateStyled: false
};

const root = () => document.getElementById('reader');
const $ = sel => root().querySelector(sel);

const DEFAULTS = {
  font_family: 'serif', font_size: 18, font_weight: 400,
  line_spacing: 1.8, paragraph_spacing: 1.2,
  word_spacing: 0, letter_spacing: 0, text_indent: 2,
  indent: 1, justify: 1, theme_preset: 'paper',
  background_color: '', text_color: '', accent_color: '',
  page_mode: 'scroll', transition: 'slide',
  page_width: '720px', v_margin: 32, tap_zones: 1
};

const THEMES = {
  paper: { bg: '#f7f4ec', fg: '#2c2a25' },
  parchment: { bg: '#f0e4cd', fg: '#4a3b28' },
  gray: { bg: '#e8e8e6', fg: '#33363a' },
  slate: { bg: '#2b3037', fg: '#b8bdc4' },
  ink: { bg: '#16181d', fg: '#a8adb5' }
};

function settingsOf() {
  return Object.assign({}, DEFAULTS, state.settings || {});
}

function canPage() {
  if (state.kind === 'native') return true;
  if (state.kind === 'canonical') return state.book && state.book.format !== 'docx';
  return false;
}

function showReaderLoading() {
  const body = $('#readerBody');
  if (!body || $('#rdLoading')) return;
  const ld = document.createElement('div');
  ld.id = 'rdLoading';
  ld.style.cssText = 'position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;z-index:6';
  ld.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;color:var(--accent)">
      <svg style="width:30px;height:30px"><use href="#icon-logo"/></svg>
      <span style="font-weight:var(--fw-semibold);font-size:var(--fs-lg);color:var(--text)">极读</span>
    </div>
    <div style="width:28px;height:28px;border-radius:50%;border:3px solid var(--border);border-top-color:var(--accent);animation:mrLoaderSpin .8s linear infinite"></div>`;
  body.appendChild(ld);
}

function hideReaderLoading() {
  const ld = $('#rdLoading');
  if (ld) ld.remove();
}

function applyTheme() {
  const s = settingsOf();
  const t = THEMES[s.theme_preset] || THEMES.paper;
  const r = root();
  r.style.background = s.background_color || t.bg;
  const fg = s.text_color || t.fg;
  const content = $('#readerBody');
  if (content) {
    content.style.color = fg;
    content.style.background = 'transparent';
  }
  const bar = $('#readerToolbar');
  const foot = $('#readerFooter');
  [bar, foot].forEach(el => {
    if (!el) return;
    el.style.background = s.background_color || t.bg;
    el.style.color = fg;
  });
  applyTypography();
}

function applyTypography() {
  const s = settingsOf();
  const t = THEMES[s.theme_preset] || THEMES.paper;
  const fg = s.text_color || t.fg;
  const bgc = s.background_color || t.bg;
  const el = $('#readerContent');
  const inner = $('#readerEngine');
  const css = {
    fontFamily: s.font_family === 'serif' ? 'var(--font-serif)' : s.font_family === 'mono' ? 'var(--font-mono)' : 'var(--font-sans)',
    fontSize: s.font_size + 'px',
    fontWeight: s.font_weight,
    lineHeight: s.line_spacing,
    maxWidth: s.page_width,
    paddingTop: s.v_margin + 'px',
    paddingBottom: s.v_margin + 'px',
    wordSpacing: s.word_spacing + 'px',
    letterSpacing: s.letter_spacing + 'px',
    textAlign: s.justify ? 'justify' : 'start'
  };
  [el, inner].forEach(box => {
    if (!box) return;
    Object.assign(box.style, css);
    // 翻页（foliate）模式：容器必须全屏，页宽/上下留白交给 foliate 网格居中，
    // 否则 absolute + max-width 会让双栏内容整体靠左
    if (box === inner && state.engine === 'foliate') {
      box.style.maxWidth = 'none';
      box.style.paddingTop = '0';
      box.style.paddingBottom = '0';
    }
    box.style.textIndent = s.indent ? '2em' : '0';
    box.querySelectorAll('p').forEach(p => {
      p.style.marginBottom = s.paragraph_spacing + 'em';
      p.style.textIndent = s.indent ? '2em' : '0';
    });
    box.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(h => {
      h.style.color = fg;
    });
    box.querySelectorAll('div.ln').forEach(d => {
      d.style.textIndent = '0';
      d.style.marginBottom = '0';
    });
    box.querySelectorAll('div.ln-gap').forEach(d => {
      d.style.textIndent = '0';
      d.style.marginBottom = '0';
    });
  });
  if (state.view && state.view.renderer && state.view.renderer.setStyles) {
    // 注意：iframe 文档 canvas 在根元素背景透明时默认白色（CSS 背景传播规则），
    // 因此 html 必须直接注入主题背景色，透明无法透出宿主背景
    state.view.renderer.setStyles(`
      html { background: ${bgc} !important; }
      body { color: ${fg} !important;
        background: transparent !important;
        font-family: ${css.fontFamily}; font-size: ${s.font_size}px; font-weight: ${s.font_weight};
        line-height: ${s.line_spacing}; word-spacing: ${s.word_spacing}px; letter-spacing: ${s.letter_spacing}px;
        text-align: ${s.justify ? 'justify' : 'start'}; }
      h1,h2,h3,h4,h5,h6 { color: ${fg} !important; }
      p { margin: 0 0 ${s.paragraph_spacing}em !important; ${s.indent ? 'text-indent: 2em !important;' : ''} }
    `);
  }
}

function buildSkeleton(title) {
  const r = root();
  r.hidden = false;
  document.body.style.overflow = 'hidden';
  r.innerHTML = `
    <div id="readerToolbar" class="reader-toolbar">
      <button class="btn btn-ghost btn-icon" id="rdBack" title="返回书架"><svg><use href="#icon-arrow-left"/></svg></button>
      <div class="rt-title" id="rdTitle">${MR.esc(title || '')}</div>
      <button class="btn btn-ghost btn-icon" id="rdToc" title="目录"><svg><use href="#icon-list"/></svg></button>
      <button class="btn btn-ghost btn-icon" id="rdBm" title="书签与标注"><svg><use href="#icon-bookmark"/></svg></button>
      <button class="btn btn-ghost btn-icon" id="rdSet" title="阅读设置"><svg><use href="#icon-sliders"/></svg></button>
    </div>
    <div class="reader-body" id="readerBody">
      <div id="readerEngine" style="position:absolute;inset:0"></div>
      <div class="reader-scroll" id="readerScroll" hidden><div class="reader-content" id="readerContent"></div></div>
      <div class="tap-zones" id="tapZones" hidden><div data-tap="prev"></div><div data-tap="menu"></div><div data-tap="next"></div></div>
    </div>
    <div id="readerFooter" class="reader-footer">
      <span class="rf-pos" id="rdPos">0%</span>
      <div class="progress" id="rdBar" title="点击跳转章节"><i style="width:0%"></i></div>
      <span class="rf-pos" id="rdChapter">--</span>
    </div>`;
  $('#rdBack').addEventListener('click', close);
  $('#rdToc').addEventListener('click', () => openTocDrawer());
  $('#rdSet').addEventListener('click', () => openSettingsDrawer());
  $('#rdBm').addEventListener('click', () => openBmDrawer());
  $('#tapZones').addEventListener('click', e => {
    const zone = e.target.closest('[data-tap]');
    if (!zone) return;
    const a = zone.dataset.tap;
    if (a === 'next') next();
    else if (a === 'prev') prev();
  });
  $('#rdBar').addEventListener('click', e => {
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    jumpToFraction(frac);
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
  if (state.view) state.view.goRight();
  else if ($('#tapZones') && !$('#tapZones').hidden) pageNextManual();
}

function prev() {
  if (state.view) state.view.goLeft();
  else if ($('#tapZones') && !$('#tapZones').hidden) pagePrevManual();
}

function close() {
  saveProgress(true, state.lastProgressData);
  destroyEngine();
  root().hidden = true;
  root().innerHTML = '';
  document.body.style.overflow = '';
  state.bookId = null;
  state.view = null;
  state.foliateSource = null;
  state.lastRelocate = null;
  state.lastProgressData = null;
  state.foliateStyled = false;
  state.sections.clear();
  document.removeEventListener('keydown', onKey);
}

function destroyEngine() {
  if (state.view) {
    try { state.view.close(); } catch {}
    state.view = null;
  }
  state.jumpToSection = null;
  const engine = $('#readerEngine');
  if (engine) engine.innerHTML = '';
}

async function fetchSection(n) {
  if (state.sections.has(n)) return state.sections.get(n);
  const html = await fetch(`/api/books/${state.bookId}/section/${n}`).then(r => {
    if (!r.ok) throw new Error('章节加载失败');
    return r.text();
  });
  state.sections.set(n, html);
  return html;
}

async function openCanonicalScroll(startPos) {
  destroyEngine();
  $('#readerScroll').hidden = false;
  $('#tapZones').hidden = true;
  const content = $('#readerContent');
  content.innerHTML = '';
  const total = state.manifest.sections.length;
  const sectionTitles = state.manifest.sections.map(s => s.title);
  const rendered = new Set();
  let current = startPos ? startPos.chapter || 0 : 0;

  async function ensure(n) {
    if (n < 0 || n >= total || rendered.has(n)) return;
    rendered.add(n);
    const sec = document.createElement('section');
    sec.id = 'sec-' + n;
    const h = document.createElement('h2');
    h.textContent = state.manifest.sections[n].title;
    sec.appendChild(h);
    const body = document.createElement('div');
    body.innerHTML = await fetchSection(n);
    sec.appendChild(body);
    content.appendChild(sec);
    applyTypography();
  }

  async function trim(around) {
    for (const n of Array.from(rendered)) {
      if (Math.abs(n - around) > 4) {
        rendered.delete(n);
        const el = content.querySelector('#sec-' + n);
        if (el) el.remove();
      }
    }
  }

  for (let i = Math.max(0, current - 1); i <= Math.min(total - 1, current + 2); i++) await ensure(i);

  const scroller = $('#readerScroll');
  const titles = sectionTitles;
  let ticking = false;
  scroller.addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(async () => {
      ticking = false;
      const st = scroller.scrollTop;
      const visBottom = st + scroller.clientHeight;
      let idx = 0;
      for (const sec of content.querySelectorAll('section')) {
        if (sec.offsetTop <= visBottom) idx = parseInt(sec.id.slice(4), 10);
      }
      current = idx;
      const frac = (st + scroller.clientHeight * 0.4) / Math.max(1, scroller.scrollHeight - scroller.clientHeight);
      const secEl = content.querySelector('#sec-' + idx);
      let offset = 0;
      if (secEl) offset = Math.max(0, Math.round((st - secEl.offsetTop) * 4));
      updateFooter(Math.min(1, (idx + (secEl ? Math.min(1, Math.max(0, visBottom - secEl.offsetTop)) / Math.max(1, secEl.offsetHeight) : 0)) / total), titles[idx]);
      state.currentSection = idx;
      if (Date.now() - state.lastSave > 4000) saveProgress(false, { chapter: idx, offset, frac });
      await ensure(idx + 2);
      await ensure(idx - 1);
      trim(idx);
    });
  }, { passive: true });

  state.jumpToSection = async idx => {
    idx = Math.max(0, Math.min(total - 1, idx));
    await ensure(idx);
    await ensure(idx + 1);
    trim(idx);
    const el = content.querySelector('#sec-' + idx);
    if (el) scroller.scrollTop = el.offsetTop;
  };

  if (startPos && startPos.offset) {
    setTimeout(() => {
      const secEl = content.querySelector('#sec-' + current);
      if (secEl) scroller.scrollTop = secEl.offsetTop + startPos.offset / 4;
      else scroller.scrollTop = current * scroller.clientHeight;
    }, 100);
  } else if (startPos && startPos.chapter) {
    setTimeout(() => {
      const secEl = content.querySelector('#sec-' + current);
      if (secEl) scroller.scrollTop = secEl.offsetTop;
    }, 100);
  }
  state.engine = 'scroll';
  applyTheme();
  updateFooter(0, titles[current]);
}

function updateFooter(frac, chapterTitle) {
  $('#rdBar').firstElementChild.style.width = (Math.min(1, frac) * 100).toFixed(1) + '%';
  $('#rdPos').textContent = (Math.min(1, frac) * 100).toFixed(1) + '%';
  if (chapterTitle !== undefined) $('#rdChapter').textContent = chapterTitle || '--';
}

async function jumpToFraction(frac) {
  const total = state.manifest ? state.manifest.sections.length : 0;
  if (state.view && state.view.renderer) {
    const loc = state.view.renderer.goToFraction ? state.view.renderer.goToFraction(frac) : null;
    if (loc) return;
  }
  const idx = Math.min(total - 1, Math.floor(frac * total));
  if (state.view) state.view.goTo(idx);
  else {
    const scroller = $('#readerScroll');
    const secEl = $('#readerContent').querySelector('#sec-' + idx);
    if (secEl) scroller.scrollTop = secEl.offsetTop;
  }
}

async function openFoliate(source) {
  destroyEngine();
  state.foliateSource = source;
  $('#readerScroll').hidden = true;
  $('#tapZones').hidden = settingsOf().tap_zones ? false : true;
  await window.MRLoad.script('/static/js/app.legacy.js').catch(() => {});
  const { setupFoliateView } = await import('./foliate-bridge.js');
  state.view = await setupFoliateView($('#readerEngine'), source, {
    onRelocate: loc => {
      state.lastRelocate = loc;
      // foliate iframe 首个文档渲染完成（relocate）后才能注入样式：
      // 文档连接前调 setStyles 会被 paginator 丢弃，导致翻页模式白底黑字
      if (!state.foliateStyled) { state.foliateStyled = true; applyTheme(); }
      const frac = loc.fraction || (loc.location && loc.location.current && loc.location.total
        ? loc.location.current / loc.location.total : 0);
      // SectionProgress 的 section 是 {current,total} 对象；数字仅来自旧实现
      const secIdx = loc.section != null
        ? (typeof loc.section === 'number' ? loc.section : loc.section.current)
        : null;
      const sec = secIdx != null && state.manifest && state.manifest.sections && state.manifest.sections[secIdx];
      const title = sec ? sec.title : (loc.tocItem && loc.tocItem.label) || '--';
      updateFooter(frac || 0, title);
      if (Date.now() - state.lastSave > 4000) saveProgress(false, { cfi: loc.cfi, section: secIdx, frac: frac || 0 });
    },
    mode: settingsOf().page_mode === 'scroll' ? 'scrolled' : 'paginated'
  });
  state.engine = 'foliate';
  applyTheme();
}

let convertNoticeEl = null;
function showConvertNotice() {
  if (!convertNoticeEl) {
    convertNoticeEl = document.createElement('div');
    convertNoticeEl.style.cssText = 'position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:260;display:flex;align-items:center;gap:8px;background:var(--surface);color:var(--text);padding:8px 16px;border-radius:999px;box-shadow:var(--shadow-2);font-size:var(--fs-sm)';
    convertNoticeEl.innerHTML = '<span style="width:14px;height:14px;border:2px solid var(--border);border-top-color:var(--primary);border-radius:50%;display:inline-block;animation:mrSpin 1s linear infinite"></span>正在后台转换为 PDF…';
    document.body.appendChild(convertNoticeEl);
  }
  convertNoticeEl.style.display = 'flex';
}

function hideConvertNotice() {
  if (convertNoticeEl) convertNoticeEl.style.display = 'none';
}

async function open(bookId, book) {
  try {
    if (!book) book = await MR.api('/api/books/' + bookId);
    state.bookId = bookId;
    state.book = book;
    state.kind = book.read_kind;
    state.settings = await MR.api('/api/reading/' + bookId + '/settings').catch(() => ({}));
    if (!state.settings || typeof state.settings !== 'object') state.settings = {};
    // 该书从未保存过阅读设置时，默认主题跟随书架明暗（dark→ink、light→paper）
    if (!state.settings.theme_preset && !state.settings.background_color) {
      let shelfTheme = 'light';
      try { shelfTheme = (window.MRTheme && MRTheme.resolve()) || document.documentElement.dataset.theme || 'light'; } catch {}
      state.settings.theme_preset = shelfTheme === 'dark' ? 'ink' : 'paper';
    }
    if (!state.manifest || state.manifestId !== bookId) {
      state.manifest = null;
    }
    buildSkeleton(book.title);
    showReaderLoading();
    if (state.kind === 'canonical') {
      const m = await MR.api('/api/books/' + bookId + '/manifest');
      state.manifest = m;
      state.manifestId = bookId;
      $('#rdTitle').textContent = book.title;
      const pd = book.position;
      let pos = null;
      if (pd && pd.type === 'canonical') pos = pd;
      else if (pd && pd.type === 'cfi' && pd.section != null) pos = { type: 'canonical', chapter: pd.section, offset: 0 };
      if (canPage() && settingsOf().page_mode === 'paged') {
        await openCanonicalFoliate(pos);
      } else {
        await openCanonicalScroll(pos);
      }
    } else if (state.kind === 'native') {
      const m = await MR.api('/api/books/' + bookId + '/manifest');
      await openFoliate(m.file_url);
      const posData = book.position && book.position.type === 'cfi' ? book.position : null;
      if (posData && posData.cfi) {
        try { await state.view.goTo(posData.cfi); }
        catch { if (posData.section != null) { try { await state.view.goTo(posData.section); } catch {} } }
      } else if (posData && posData.section != null) {
        try { await state.view.goTo(posData.section); } catch {}
      }
    } else if (state.kind === 'pdf') {
      const m = await MR.api('/api/books/' + bookId + '/manifest');
      const { openPdf } = await import('./pdf-viewer.js');
      const posData = book.position && book.position.type === 'pdf' ? book.position : null;
      const startPage = posData && posData.page ? Math.floor(posData.page) : 1;
      state.viewer = await openPdf($('#readerEngine'), m.file_url, {
        getSettings: settingsOf, applyTheme,
        mode: 'scroll',
        startPage,
        onProgress: (frac, label, page) => {
          updateFooter(frac, label);
          if (page != null) saveProgress(false, { frac, pdfPage: page, label });
        }
      });
      if (startPage > 1) {
        const t0 = Date.now();
        const ensureRestore = () => {
          if (state.engine !== 'pdf' || !state.viewer || root().hidden) return;
          const st = document.querySelector('.pdf-scroll');
          if (st && st.scrollTop < 80 && Date.now() - t0 < 9000) {
            try { state.viewer.goToPage(startPage); } catch {}
            setTimeout(ensureRestore, 500);
          }
        };
        setTimeout(ensureRestore, 400);
      }
      state.engine = 'pdf';
    } else if (state.kind === 'pptx') {
      let m = await MR.api('/api/books/' + bookId + '/manifest');
      let tries = 0;
      while (m.convert_status === 'pending' && tries < 150) {
        showConvertNotice();
        await new Promise(r => setTimeout(r, 2500));
        try {
          m = await MR.api('/api/books/' + bookId + '/manifest');
        } catch (err) {
          break;
        }
        tries++;
      }
      hideConvertNotice();
      if (m.format === 'pdf') {
        const { openPdf } = await import('./pdf-viewer.js');
        const posData = book.position && book.position.type === 'pdf' ? book.position : null;
        state.viewer = await openPdf($('#readerEngine'), m.file_url, {
          getSettings: settingsOf, applyTheme,
          mode: 'scroll',
          startPage: posData && posData.page ? posData.page : 1,
          onProgress: (frac, label, page) => {
            updateFooter(frac, label);
            if (page != null) saveProgress(false, { frac, pdfPage: page, label });
          }
        });
        state.kind = 'pdf';
        state.engine = 'pdf';
        return;
      }
      const { openPptx } = await import('./pptx-viewer.js');
      const slidePos = book.position && book.position.type === 'pptx' ? book.position : null;
      await openPptx($('#readerEngine'), m.file_url, {
        startSlide: slidePos && slidePos.slide ? slidePos.slide : 1,
        onProgress: (frac, label, slide) => {
          updateFooter(frac, label);
          if (slide != null) saveProgress(false, { frac, pptxSlide: slide, label });
        }
      });
      state.engine = 'pptx';
    } else {
      MR.toast('该格式需要重新上传', 'error');
      close();
    }
    hideReaderLoading();
  } catch (e) {
    MR.toast(e.message || '打开失败', 'error');
    close();
  }
}

async function openCanonicalFoliate(pos) {
  const sections = state.manifest.sections.map((s, i) => ({
    id: 'sec' + i,
    load: async () => {
      const html = await fetchSection(i);
      const blob = new Blob([`<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>${html}</body></html>`], { type: 'text/html' });
      // foliate-js 约定：load 必须返回 URL 字符串（返回对象会抛 "is not string"）
      return URL.createObjectURL(blob);
    },
    size: s.size || 1000,
    linear: 'yes'
  }));
  const secIdOf = n => 'sec' + (parseInt(n, 10) || 0);
  const book = {
    sections,
    metadata: { title: state.book.title, author: state.book.author },
    toc: (state.manifest.toc || []).map(t => ({ label: t.title, href: secIdOf(t.section), subitems: (t.children || []).map(c => ({ label: c.title, href: secIdOf(c.section) })) })),
    resolveHref: href => ({ index: parseInt(String(href).replace('sec', ''), 10) || 0, anchor: null }),
    // 提供 splitTOCHef/getTOCFragment 使 view.js 建立 SectionProgress/TOCProgress，
    // relocate 事件才有 fraction/section/章名（否则页脚永远 0.0% 与 '--'）
    splitTOCHref: href => [secIdOf(href), ''],
    getTOCFragment: () => null,
    splitTOC: []
  };
  await openFoliate(book);
  const total = sections.length;
  const target = pos ? (pos.chapter || 0) : 0;
  if (pos && pos.cfi) await state.view.goTo(pos.cfi).catch(() => state.view.goTo(target));
  else await state.view.goTo(target);
}

function saveProgress(immediate, data) {
  if (!state.bookId) return;
  state.lastSave = Date.now();
  if (data) state.lastProgressData = data;
  const payload = { position: data && data.frac != null ? data.frac : 0, chapter_title: '' };
  if (data) {
    if (data.pdfPage != null) {
      payload.position_data = { type: 'pdf', page: data.pdfPage };
      payload.chapter_title = data.label || ('第 ' + data.pdfPage + ' 页');
    } else if (data.pptxSlide != null) {
      payload.position_data = { type: 'pptx', slide: data.pptxSlide };
      payload.chapter_title = data.label || ('幻灯片 ' + data.pptxSlide);
    } else {
      if (data.cfi) payload.position_data = { type: 'cfi', cfi: data.cfi, section: data.section };
      else if (data.chapter != null) payload.position_data = { type: 'canonical', chapter: data.chapter, offset: data.offset || 0 };
      const secIdx = data.chapter != null ? data.chapter : data.section;
      if (state.manifest && state.manifest.sections && secIdx != null && state.manifest.sections[secIdx]) {
        payload.chapter_title = state.manifest.sections[secIdx].title;
        if (data.frac == null) payload.position = secIdx / Math.max(1, state.manifest.sections.length);
      }
    }
    if (data.frac != null) payload.position = data.frac;
  }
  const doSave = () => {
    navigator.sendBeacon
      ? navigator.sendBeacon(`/api/reading/${state.bookId}/position`, new Blob([JSON.stringify(payload)], { type: 'application/json' }))
      : MR.api(`/api/reading/${state.bookId}/position`, { method: 'PUT', json: payload }).catch(() => {});
  };
  if (immediate) {
    clearTimeout(state.saveTimer);
    doSave();
  } else {
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(doSave, 1500);
  }
}

function drawerShell(title, bodyHTML) {
  const old = root().querySelector('.drawer-backdrop');
  if (old) old.remove();
  const bd = document.createElement('div');
  bd.className = 'drawer-backdrop';
  bd.innerHTML = `
    <div class="drawer drawer-right open">
      <div class="drawer-header"><h3>${MR.esc(title)}</h3>
        <button class="btn btn-ghost btn-icon" data-close><svg><use href="#icon-x"/></svg></button></div>
      <div class="drawer-body">${bodyHTML}</div>
    </div>`;
  bd.addEventListener('click', e => {
    if (e.target === bd || e.target.closest('[data-close]')) bd.remove();
  });
  root().appendChild(bd);
  return bd;
}

function openTocDrawer() {
  if (!state.manifest) return;
  const render = (items, cls) => (items || []).map(t =>
    `<button class="toc-item ${cls || ''}" data-sec="${t.section}">${MR.esc(t.title)}</button>` +
    (t.children && t.children.length ? `<div class="toc-children">${render(t.children, '')}</div>` : '')
  ).join('');
  const list = state.engine === 'scroll'
    ? (state.manifest.sections || []).map((s, i) => ({ title: s.title, section: i })).map(t =>
        `<button class="toc-item" data-sec="${t.section}">${MR.esc(t.title)}</button>`).join('')
    : render(state.manifest.toc);
  const bd = drawerShell('目录', `<div>${list || '<div class="empty"><div class="empty-title">无目录</div></div>'}</div>`);
  bd.addEventListener('click', async e => {
    const item = e.target.closest('[data-sec]');
    if (!item) return;
    bd.remove();
    const idx = parseInt(item.dataset.sec, 10);
    if (isNaN(idx) || idx < 0) return;
    if (state.engine === 'scroll' && typeof state.jumpToSection === 'function') {
      await state.jumpToSection(idx);
    } else if (state.view) {
      try { await state.view.goTo(idx); }
      catch { await jumpToFraction((idx + 0.5) / Math.max(1, state.manifest.sections.length)); }
    } else {
      const secEl = $('#readerContent').querySelector('#sec-' + idx);
      if (secEl) $('#readerScroll').scrollTop = secEl.offsetTop;
    }
  });
}

function openSettingsDrawer() {
  const s = settingsOf();
  const bd = drawerShell('阅读设置', `
    <div class="theme-dots">
      ${Object.entries(THEMES).map(([k, v]) =>
        `<div class="theme-dot ${s.theme_preset === k ? 'active' : ''}" data-theme-preset="${k}" style="background:${v.bg}" title="${k}"></div>`).join('')}
    </div>
    <div class="setting-row"><label>文字颜色</label>
      <div style="display:flex;align-items:center;gap:8px">
        <select class="select" style="width:118px" id="stTextColor">
          <option value="">跟随主题</option>
          <option value="#1d1c19">墨黑</option>
          <option value="#4a3b28">棕褐</option>
          <option value="#37474f">石板青</option>
          <option value="#5d4037">咖啡</option>
          <option value="#00695c">松绿</option>
          <option value="#4527a0">黛紫</option>
        </select>
        <input type="color" id="stTextColorCustom" value="${s.text_color || '#1d1c19'}" title="自定义颜色" style="width:34px;height:30px;padding:2px;border:1px solid var(--border);border-radius:var(--r-sm);background:var(--surface);cursor:pointer">
      </div>
    </div>
    <div class="setting-row"><label>字体</label>
      <select class="select" style="width:150px" id="stFont">
        <option value="serif" ${s.font_family === 'serif' ? 'selected' : ''}>衬线</option>
        <option value="sans" ${s.font_family === 'sans' ? 'selected' : ''}>无衬线</option>
        <option value="mono" ${s.font_family === 'mono' ? 'selected' : ''}>等宽</option>
      </select></div>
    ${[['font_size', '字号', 12, 32, 1], ['line_spacing', '行高', 1.2, 2.6, 0.1],
       ['paragraph_spacing', '段距', 0.4, 3, 0.1], ['letter_spacing', '字间距', 0, 4, 0.5],
       ['word_spacing', '词间距', 0, 8, 0.5], ['v_margin', '页边距', 8, 96, 4]]
      .map(([k, label, min, max, step]) => `
      <div class="setting-row"><label>${label}</label>
        <input type="range" class="range" id="st_${k}" min="${min}" max="${max}" step="${step}" value="${s[k]}">
        <span class="text-3" style="width:44px;text-align:right" id="stv_${k}">${s[k]}</span></div>`).join('')}
    <label class="setting-row"><label>两端对齐</label>
      <span class="switch"><input type="checkbox" id="st_justify" ${s.justify ? 'checked' : ''}><span class="track"></span></span></label>
    <label class="setting-row"><label>首行缩进</label>
      <span class="switch"><input type="checkbox" id="st_indent" ${s.indent ? 'checked' : ''}><span class="track"></span></span></label>
    <div class="setting-row" id="stModeRow"><label>阅读模式</label>
      <select class="select" style="width:150px" id="stMode">
        <option value="scroll" ${s.page_mode === 'scroll' ? 'selected' : ''}>上下滚动</option>
        <option value="paged" ${s.page_mode === 'paged' ? 'selected' : ''}>左右翻页</option>
      </select></div>
    <div class="setting-row"><label>翻页动画</label>
      <select class="select" style="width:150px" id="stTrans">
        <option value="slide" ${s.transition === 'slide' ? 'selected' : ''}>滑动</option>
        <option value="none" ${s.transition === 'none' ? 'selected' : ''}>无</option>
      </select></div>
    <button class="btn w-full mt-3" id="stReset">恢复默认</button>
  `);
  const save = async patch => {
    Object.assign(state.settings, patch);
    applyTheme();
    clearTimeout(bd._t);
    bd._t = setTimeout(() => MR.api(`/api/reading/${state.bookId}/settings`, { method: 'PUT', json: patch }).catch(() => {}), 400);
  };
  bd.querySelectorAll('.theme-dot').forEach(d => d.addEventListener('click', () => {
    bd.querySelectorAll('.theme-dot').forEach(x => x.classList.remove('active'));
    d.classList.add('active');
    save({ theme_preset: d.dataset.themePreset });
  }));
  bd.querySelector('#stFont').addEventListener('change', e => save({ font_family: e.target.value }));
  const stColor = bd.querySelector('#stTextColor');
  if (stColor) stColor.value = s.text_color || '';
  bd.querySelector('#stTextColor').addEventListener('change', e => {
    bd.querySelector('#stTextColorCustom').value = e.target.value || '#1d1c19';
    save({ text_color: e.target.value });
  });
  bd.querySelector('#stTextColorCustom').addEventListener('input', MR.debounce(e => {
    bd.querySelector('#stTextColor').value = e.target.value;
    save({ text_color: e.target.value });
  }, 300));
  [['font_size'], ['line_spacing'], ['paragraph_spacing'], ['letter_spacing'], ['word_spacing'], ['v_margin']].forEach(([k]) => {
    const inp = bd.querySelector('#st_' + k);
    if (!inp) return;
    inp.addEventListener('input', () => {
      bd.querySelector('#stv_' + k).textContent = inp.value;
      save({ [k]: parseFloat(inp.value) });
    });
  });
  ['justify', 'indent'].forEach(k => {
    bd.querySelector('#st_' + k).addEventListener('change', e => save({ [k]: e.target.checked ? 1 : 0 }));
  });
  if (!canPage()) {
    const _r = bd.querySelector('#stModeRow');
    if (_r) _r.remove();
  }
  const stMode = bd.querySelector('#stMode');
  if (stMode) stMode.addEventListener('change', async e => {
    await save({ page_mode: e.target.value });
    if (state.kind === 'canonical') {
      const pos = state.engine === 'scroll' ? { chapter: state.currentSection, offset: 0 } : null;
      if (e.target.value === 'paged') await openCanonicalFoliate(pos);
      else await openCanonicalScroll(pos);
    } else if (state.kind === 'pdf' && state.viewer && state.viewer.setMode) {
      state.viewer.setMode(e.target.value === 'paged' ? 'paged' : 'scroll');
    } else if (state.kind === 'native' && state.foliateSource) {
      const loc = state.lastRelocate;
      await openFoliate(state.foliateSource);
      if (loc && loc.cfi) { try { await state.view.goTo(loc.cfi); } catch {} }
    }
  });
  bd.querySelector('#stReset').addEventListener('click', () => {
    state.settings = {};
    applyTheme();
    bd.remove();
    openSettingsDrawer();
  });
}

async function openBmDrawer() {
  let bookmarks = [];
  let highlights = [];
  try {
    bookmarks = await MR.api(`/api/reading/${state.bookId}/bookmarks`) || [];
    highlights = await MR.api(`/api/reading/${state.bookId}/highlights`) || [];
  } catch {}
  const bmHtml = bookmarks.map(b => `
    <div class="bm-item" data-bm-go="${b.id}">
      <div class="row gap-2">
        <span class="flex-1 truncate">${MR.esc(b.note || b.chapter || '书签')}</span>
        <button class="btn btn-ghost btn-icon btn-sm" data-bm-edit="${b.id}" title="重命名"><svg><use href="#icon-edit"/></svg></button>
        <button class="btn btn-ghost btn-icon btn-sm" data-bm-del="${b.id}" title="删除"><svg><use href="#icon-trash"/></svg></button>
      </div>
      <div class="bm-sub">${MR.esc(b.chapter || '')} · ${MR.fmtDate(b.created_at)}</div>
    </div>`).join('') || '<div class="text-3" style="font-size:var(--fs-sm)">暂无书签</div>';
  const hlHtml = highlights.map(h => `
    <div class="bm-item" style="border-left:3px solid ${MR.esc(h.color)}">
      <div class="row gap-2">
        <span class="flex-1">${MR.esc(h.selected_text.slice(0, 60))}</span>
        <button class="btn btn-ghost btn-icon btn-sm" data-hl-del="${h.id}" title="删除"><svg><use href="#icon-trash"/></svg></button>
      </div>
      <div class="bm-sub">${MR.esc(h.note || h.chapter || '')} · ${MR.fmtDate(h.created_at)}</div>
    </div>`).join('') || '<div class="text-3" style="font-size:var(--fs-sm)">暂无标注</div>';
  const bd = drawerShell('书签与标注', `
    <button class="btn w-full" id="bmAdd"><svg><use href="#icon-bookmark-add"/></svg>在此处添加书签</button>
    <div class="mt-3">${bmHtml}</div>
    <h4 class="mt-3">标注</h4>
    <div>${hlHtml}</div>`);
  const refresh = () => { bd.remove(); openBmDrawer(); };
  bd.querySelector('#bmAdd').addEventListener('click', async () => {
    try {
      const note = prompt('书签备注（可留空）') || '';
      const sec = state.manifest && state.manifest.sections[state.currentSection];
      const data = state.engine === 'scroll'
        ? { chapter: sec ? sec.title : '', position_data: { type: 'canonical', chapter: state.currentSection }, note }
        : { chapter: $('#rdChapter').textContent, position_data: { type: 'cfi' }, note };
      await MR.api(`/api/reading/${state.bookId}/bookmarks`, { method: 'POST', json: data });
      MR.toast('书签已添加', 'success');
      refresh();
    } catch (e) { MR.toast(e.message, 'error'); }
  });
  bd.addEventListener('click', async e => {
    const editBtn = e.target.closest('[data-bm-edit]');
    if (editBtn) {
      e.stopPropagation();
      const bm = bookmarks.find(x => x.id === parseInt(editBtn.dataset.bmEdit, 10));
      const note = prompt('重命名书签：', (bm && bm.note) || '');
      if (note === null) return;
      try {
        await MR.api(`/api/reading/${state.bookId}/bookmarks/${editBtn.dataset.bmEdit}`, { method: 'PUT', json: { note } });
        refresh();
      } catch (err) { MR.toast(err.message, 'error'); }
      return;
    }
    const delBtn = e.target.closest('[data-bm-del]');
    if (delBtn) {
      e.stopPropagation();
      if (!(await MR.confirmDialog('删除书签', '确定删除该书签？'))) return;
      try {
        await MR.api(`/api/reading/${state.bookId}/bookmarks/${delBtn.dataset.bmDel}`, { method: 'DELETE' });
        refresh();
      } catch (err) { MR.toast(err.message, 'error'); }
      return;
    }
    const hlDel = e.target.closest('[data-hl-del]');
    if (hlDel) {
      e.stopPropagation();
      if (!(await MR.confirmDialog('删除标注', '确定删除该标注？'))) return;
      try {
        await MR.api(`/api/reading/${state.bookId}/highlights/${hlDel.dataset.hlDel}`, { method: 'DELETE' });
        refresh();
      } catch (err) { MR.toast(err.message, 'error'); }
      return;
    }
    const go = e.target.closest('[data-bm-go]');
    if (go) {
      bd.remove();
      const bm = bookmarks.find(x => x.id === parseInt(go.dataset.bmGo, 10));
      let pd = null;
      try { pd = typeof bm.position === 'string' ? JSON.parse(bm.position) : bm.position; } catch { pd = null; }
      if (pd && pd.type === 'canonical' && pd.chapter != null) {
        if (state.view) await state.view.goTo(pd.chapter);
        else {
          const secEl = $('#readerContent').querySelector('#sec-' + pd.chapter);
          if (secEl) $('#readerScroll').scrollTop = secEl.offsetTop;
        }
      }
    }
  });
}

window.MRReader = { open };

function boot() {
  const m = location.pathname.match(/^\/main\/b\/(.+)$/);
  if (!m) return;
  MR.api('/api/books/by-fp/' + m[1]).then(book => open(book.id, book)).catch(e => MR.toast(e.message, 'error'));
}

document.addEventListener('DOMContentLoaded', boot);
