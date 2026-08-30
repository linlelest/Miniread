export async function openPdf(container, fileUrl, hooks) {
  const pdfjs = await window.MRLoad.pdfjs();
  const doc = await pdfjs.getDocument({ url: fileUrl }).promise;
  const mode0 = hooks.mode === 'paged' ? 'paged' : 'scroll';

  let mode = mode0;
  let pageNum = hooks.startPage && hooks.startPage >= 1 ? Math.min(Math.floor(hooks.startPage), doc.numPages || hooks.startPage) : 1;
  let zoom = 0;
  let lastScale = 1;
  let fitPage = false;
  let destroyed = false;

  const rootEl = document.createElement('div');
  rootEl.style.cssText = 'position:absolute;inset:0;touch-action:pan-y';
  container.appendChild(rootEl);
  const s0 = hooks.getSettings();
  if (s0.theme_preset === 'slate' || s0.theme_preset === 'ink') rootEl.classList.add('theme-invert');

  let controls = null;
  let stage = null;
  let scroller = null;
  let canvases = [];
  let placeholders = [];
  let io = null;
  let posLabel = null;

  function clampZoom(z) {
    return Math.min(4, Math.max(0.3, z));
  }

  async function baseViewport() {
    const p = await doc.getPage(1);
    return p.getViewport({ scale: 1 });
  }

  function calcScale(baseW, double) {
    let scale = zoom || 1;
    if (zoom === 0) {
      const wrap = (stage ? stage.clientWidth : rootEl.clientWidth) - (double ? 32 : 0) - 16;
      scale = Math.min(2.4, Math.max(0.4, wrap / baseW));
      if (fitPage && mode === 'paged') {
        scale = Math.min(scale, (rootEl.clientHeight - 140) / (baseW * 1.414));
      }
    }
    return scale;
  }

  async function renderPage(n, canvas, scale) {
    const page = await doc.getPage(n);
    const viewport = page.getViewport({ scale });
    const dpr = window.devicePixelRatio > 1 ? 1.5 : 1;
    canvas.width = viewport.width * dpr;
    canvas.height = viewport.height * dpr;
    canvas.style.width = viewport.width + 'px';
    canvas.style.height = viewport.height + 'px';
    await page.render({
      canvasContext: canvas.getContext('2d'),
      viewport,
      transform: dpr > 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined
    }).promise;
    canvas.dataset.rendered = String(scale);
    lastScale = scale;
  }

  function doubleMode() {
    return mode === 'paged' && window.innerWidth > 1024 && fitPage;
  }

  function updateLabel() {
    if (!posLabel) return;
    const d = doubleMode();
    posLabel.textContent = d && pageNum < doc.numPages
      ? `${pageNum}-${pageNum + 1} / ${doc.numPages}`
      : `${pageNum} / ${doc.numPages}`;
    if (hooks.onProgress) hooks.onProgress(pageNum / doc.numPages, `第 ${pageNum} 页`, pageNum);
  }

  function getFrac() {
    if (mode === 'scroll' && scroller) {
      const total = scroller.scrollHeight - scroller.clientHeight;
      if (total <= 0) return 0;
      return (scroller.scrollTop + scroller.clientHeight * 0.35) / (total + scroller.clientHeight * 0.35);
    }
    return pageNum / doc.numPages;
  }

  function restoreFrac(frac) {
    if (mode === 'scroll' && scroller) {
      const total = scroller.scrollHeight - scroller.clientHeight;
      scroller.scrollTop = Math.max(0, Math.min(total, frac * (total + scroller.clientHeight * 0.35) - scroller.clientHeight * 0.35));
    } else {
      pageNum = Math.max(1, Math.min(doc.numPages, Math.round(frac * doc.numPages)));
    }
  }

  function buildControls() {
    controls = document.createElement('div');
    controls.className = 'row gap-2';
    controls.style.cssText = 'position:sticky;top:0;z-index:3;background:var(--surface);padding:8px 12px;border-radius:var(--r-md);box-shadow:var(--shadow-1);flex-wrap:wrap;row-gap:6px';
    controls.innerHTML = `
      <button class="btn btn-icon" data-a="first"><svg><use href="#icon-skip-first"/></svg></button>
      <button class="btn btn-icon" data-a="prev"><svg><use href="#icon-chevron-left"/></svg></button>
      <span style="font-size:var(--fs-sm);min-width:96px;text-align:center" id="pdfPos">1 / ${doc.numPages}</span>
      <button class="btn btn-icon" data-a="next"><svg><use href="#icon-chevron-right"/></svg></button>
      <button class="btn btn-icon" data-a="last"><svg><use href="#icon-skip-last"/></svg></button>
      <button class="btn btn-icon" data-a="zoomout"><svg><use href="#icon-zoom-out"/></svg></button>
      <button class="btn btn-icon" data-a="zoomin"><svg><use href="#icon-zoom-in"/></svg></button>
      <button class="btn btn-sm" data-a="fitw">适应宽度</button>
      <button class="btn btn-sm" data-a="fitp">适应页面</button>
      <button class="btn btn-icon" data-a="rotate" title="旋转"><svg><use href="#icon-refresh"/></svg></button>
      <button class="btn btn-icon" data-a="hidebar" style="margin-left:auto" title="收起工具栏"><svg><use href="#icon-chevron-up"/></svg></button>`;
    posLabel = controls.querySelector('#pdfPos');
    controls.addEventListener('click', async e => {
      const btn = e.target.closest('[data-a]');
      if (!btn) return;
      const a = btn.dataset.a;
      if (a === 'hidebar') { collapseToolbar(); return; }
      if (a === 'prev') goToPage(pageNum - (doubleMode() ? 2 : 1));
      else if (a === 'next') goToPage(pageNum + (doubleMode() ? 2 : 1));
      else if (a === 'first') goToPage(1);
      else if (a === 'last') goToPage(doc.numPages);
      else if (a === 'zoomin') { zoom = clampZoom((zoom || lastScale) * 1.2); rerender(); }
      else if (a === 'zoomout') { zoom = clampZoom((zoom || lastScale) / 1.2); rerender(); }
      else if (a === 'fitw') { zoom = 0; fitPage = false; rerender(); }
      else if (a === 'fitp') { zoom = 0; fitPage = true; rerender(); }
      else if (a === 'rotate') {
        rotation = (rotation + 90) % 360;
        if (mode === 'scroll') applyRotationToDom();
        else rerender();
      }
    });
    rootEl.appendChild(controls);
  }

  function collapseToolbar() {
    if (controls) controls.style.display = 'none';
    const tocBtn = document.getElementById('rdToc');
    if (tocBtn && !document.getElementById('rdTools')) {
      const tools = document.createElement('button');
      tools.id = 'rdTools';
      tools.className = 'btn btn-ghost btn-icon';
      tools.title = '显示工具栏';
      tools.innerHTML = '<svg><use href="#icon-chevron-down"/></svg>';
      tools.addEventListener('click', expandToolbar);
      tocBtn.parentNode.insertBefore(tools, tocBtn);
    }
  }

  function expandToolbar() {
    if (controls) controls.style.display = 'flex';
    const tools = document.getElementById('rdTools');
    if (tools) tools.remove();
  }

  let rotation = 0;

  function rotSwap() {
    return rotation % 180 === 90;
  }

  function applyCanvasRotation(c, w, h) {
    if (rotSwap()) {
      c.style.position = 'absolute';
      c.style.width = h + 'px';
      c.style.height = w + 'px';
      c.style.left = Math.round((w - h) / 2) + 'px';
      c.style.top = Math.round((h - w) / 2) + 'px';
    } else {
      c.style.position = 'static';
      c.style.width = w + 'px';
      c.style.height = h + 'px';
    }
    c.style.transform = rotation ? `rotate(${rotation}deg)` : 'none';
  }

  function applyRotationToDom() {
    for (let n = 0; n < placeholders.length; n++) {
      const ph = placeholders[n];
      const w = Number(ph.dataset.w);
      const h = Number(ph.dataset.h);
      if (!w || !h) continue;
      if (rotSwap()) {
        ph.style.width = h + 'px';
        ph.style.height = w + 'px';
      } else {
        ph.style.width = w + 'px';
        ph.style.height = h + 'px';
      }
      const cv = canvases[n];
      if (cv && cv.style.display !== 'none') applyCanvasRotation(cv, w, h);
    }
  }

  function goToPage(n) {
    n = Math.max(1, Math.min(doc.numPages, n));
    if (mode === 'scroll') {
      const ph = placeholders[n - 1];
      if (ph && scroller) scroller.scrollTop = ph.offsetTop - 12;
      pageNum = n;
      updateLabel();
    } else {
      pageNum = n;
      rerender();
    }
  }

  function rerender() {
    const frac = getFrac();
    if (mode === 'scroll') return buildScroll(frac);
    return renderPaged();
  }

  function clearHost() {
    if (io) { io.disconnect(); io = null; }
    rootEl.querySelectorAll('.pdf-scroll, .pdf-stage').forEach(el => el.remove());
    canvases = [];
    placeholders = [];
    stage = null;
    scroller = null;
  }

  async function renderPaged() {
    clearHost();
    mode = 'paged';
    stage = document.createElement('div');
    stage.className = 'pdf-stage';
    stage.style.cssText = 'position:relative;display:flex;gap:16px;align-items:flex-start;justify-content:center;width:100%;padding:var(--s-4)';
    rootEl.appendChild(stage);
    const wantDouble = doubleMode() && pageNum < doc.numPages;
    const pages = wantDouble ? [pageNum, pageNum + 1] : [pageNum];
    for (let i = 0; i < pages.length; i++) {
      const c = document.createElement('canvas');
      stage.appendChild(c);
      canvases.push(c);
    }
    const bv = await baseViewport();
    const scale = calcScale(bv.width, wantDouble);
    for (let i = 0; i < pages.length; i++) {
      const c = canvases[i];
      if (pages[i] <= doc.numPages && !destroyed) {
        await renderPage(pages[i], c, scale);
        const w = c.style.width ? parseFloat(c.style.width) : c.width;
        const h = c.style.height ? parseFloat(c.style.height) : c.height;
        c.dataset.dw = w;
        c.dataset.dh = h;
        applyCanvasRotation(c, w, h);
      }
    }
    updateLabel();
  }

  async function buildScroll(keepFrac) {
    clearHost();
    mode = 'scroll';
    scroller = document.createElement('div');
    scroller.className = 'pdf-scroll';
    scroller.style.cssText = 'position:absolute;inset:0;overflow-y:auto;display:flex;flex-direction:column;align-items:center;gap:var(--s-3);padding:var(--s-4)';
    rootEl.appendChild(scroller);
    const bv = await baseViewport();
    const scale = calcScale(bv.width, false);
    const page1 = await doc.getPage(1);
    const vp1 = page1.getViewport({ scale });
    const ratio = vp1.height / vp1.width;

    for (let n = 1; n <= doc.numPages; n++) {
      const ph = document.createElement('div');
      ph.className = 'pdf-ph';
      ph.dataset.page = String(n);
      ph.dataset.w = String(Math.round(vp1.width));
      ph.dataset.h = String(Math.round(vp1.width * ratio));
      const dispW = rotSwap() ? Math.round(vp1.width * ratio) : Math.round(vp1.width);
      const dispH = rotSwap() ? Math.round(vp1.width) : Math.round(vp1.width * ratio);
      ph.style.cssText = `position:relative;flex:none;width:${dispW}px;height:${dispH}px;background:var(--hairline);border-radius:var(--r-sm);display:flex;align-items:center;justify-content:center`;
      const c = document.createElement('canvas');
      c.style.display = 'none';
      ph.appendChild(c);
      scroller.appendChild(ph);
      placeholders.push(ph);
      canvases.push(c);
    }

    if (typeof keepFrac === 'number' && keepFrac > 0) restoreFrac(keepFrac);
    else if (pageNum > 1) scheduleRestore(pageNum - 1);
    else pendingRestoreIdx = null;

    const queue = new Set();
    let pump = null;
    const pumpQueue = () => {
      if (pump) return;
      pump = setInterval(async () => {
        const n = queue.values().next().value;
        if (n == null) { clearInterval(pump); pump = null; return; }
        queue.delete(n);
        const ph = placeholders[n - 1];
        const c = canvases[n - 1];
        if (!ph || !c || destroyed) return;
        try {
          await renderPage(n, c, scale);
          c.style.display = 'block';
        } catch {}
      }, 60);
    };

    io = new IntersectionObserver(entries => {
      for (const en of entries) {
        if (!en.isIntersecting) continue;
        const n = parseInt(en.target.dataset.page, 10);
        const c = canvases[n - 1];
        if (c && !c.dataset.rendered) queue.add(n);
        if (n > 0) {
          pageNum = n;
          updateLabel();
        }
      }
      pumpQueue();
    }, { root: scroller, rootMargin: '600px 0px' });
    placeholders.forEach(ph => io.observe(ph));
    updateLabel();
  }

  let pendingRestoreIdx = null;
  function scheduleRestore(idx) {
    pendingRestoreIdx = idx;
    const tryScroll = () => {
      if (destroyed || pendingRestoreIdx == null || mode !== 'scroll' || !scroller) return;
      const ph = placeholders[pendingRestoreIdx];
      if (!ph) { pendingRestoreIdx = null; return; }
      const expectedH = Number(ph.dataset.h) || 0;
      const expectedTotal = placeholders.length * expectedH;
      if (expectedH > 0 && scroller.scrollHeight >= expectedTotal * 0.95 && ph.offsetTop > 0) {
        scroller.scrollTop = Math.max(0, ph.offsetTop - 12);
        pendingRestoreIdx = null;
      } else {
        setTimeout(tryScroll, 120);
      }
    };
    setTimeout(tryScroll, 80);
  }

  function setMode(m) {
    if (m === mode) return;
    const frac = getFrac();
    if (m === 'paged') {
      pageNum = Math.max(1, Math.round(frac * doc.numPages));
      renderPaged();
    } else {
      buildScroll(frac);
    }
  }

  function activeLayer() {
    return mode === 'scroll' ? scroller : stage;
  }

  let pinch = null;
  let lastTap = 0;

  function touchDist(t) {
    const dx = t[0].clientX - t[1].clientX;
    const dy = t[0].clientY - t[1].clientY;
    return Math.hypot(dx, dy);
  }

  function onTouchStart(e) {
    if (e.touches.length === 2) {
      const layer = activeLayer();
      if (!layer) return;
      const rect = layer.getBoundingClientRect();
      pinch = {
        d0: touchDist(e.touches),
        z0: lastScale,
        cx: (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left,
        cy: (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top
      };
      e.preventDefault();
    } else if (e.touches.length === 1) {
      const now = Date.now();
      if (now - lastTap < 320) {
        const layer = activeLayer();
        if (layer) {
          const rect = layer.getBoundingClientRect();
          const z = (zoom || lastScale) > 1.6 ? 0 : 2.5;
          const keepFrac = getFrac();
          zoom = z;
          if (mode === 'scroll') buildScroll(keepFrac);
          else renderPaged();
        }
        lastTap = 0;
      } else {
        lastTap = now;
      }
    }
  }

  function onTouchMove(e) {
    if (!pinch || e.touches.length < 2) return;
    e.preventDefault();
    const layer = activeLayer();
    if (!layer) return;
    const z = clampZoom(pinch.z0 * touchDist(e.touches) / pinch.d0);
    layer.style.transform = `scale(${z})`;
    layer.style.transformOrigin = `${pinch.cx}px ${pinch.cy}px`;
  }

  function onTouchEnd(e) {
    if (pinch && e.touches.length < 2) {
      const layer = activeLayer();
      const applied = layer ? parseFloat((layer.style.transform.match(/scale\(([\d.]+)\)/) || [])[1]) : NaN;
      if (layer) {
        layer.style.transform = 'none';
        layer.style.transformOrigin = '';
      }
      if (!isNaN(applied)) {
        zoom = clampZoom(applied);
        const frac = getFrac();
        if (mode === 'scroll') buildScroll(frac);
        else renderPaged();
      }
      pinch = null;
    }
  }

  rootEl.addEventListener('touchstart', onTouchStart, { passive: false });
  rootEl.addEventListener('touchmove', onTouchMove, { passive: false });
  rootEl.addEventListener('touchend', onTouchEnd);
  rootEl.addEventListener('dblclick', () => {
    const z = (zoom || lastScale) > 1.6 ? 0 : 2.5;
    zoom = z;
    rerender();
  });

  let resizeT;
  const onResize = () => {
    clearTimeout(resizeT);
    resizeT = setTimeout(() => {
      if (mode === 'paged') rerender();
      else if (zoom !== 0) {
        const frac = getFrac();
        buildScroll(frac);
      }
    }, 250);
  };
  window.addEventListener('resize', onResize);

  buildControls();
  if (mode === 'paged') await renderPaged();
  else await buildScroll(0);

  return {
    setMode,
    goToPage,
    destroy() {
      destroyed = true;
      window.removeEventListener('resize', onResize);
      if (io) io.disconnect();
      const tools = document.getElementById('rdTools');
      if (tools) tools.remove();
      rootEl.remove();
    }
  };
}
