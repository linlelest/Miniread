export async function openPptx(container, fileUrl, hooks) {
  await window.MRLoad.pptx();
  const lib = window.PptxViewJS && window.PptxViewJS.PPTXViewer ? window.PptxViewJS : (window.PptxViewJS && window.PptxViewJS.default) || window.PptxViewJS;
  const ViewerCtor = lib && (lib.PPTXViewer || (lib.default && lib.default.PPTXViewer));
  if (!ViewerCtor) throw new Error('PPTX 渲染库不可用');

  const blob = await window.MR.getBlob(fileUrl);
  const file = new File([blob], 'deck.pptx', {
    type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
  });

  let slideW = 12192000;
  let slideH = 6858000;
  try {
    const zip = await window.JSZip.loadAsync(blob);
    const presFile = zip.file('ppt/presentation.xml');
    if (presFile) {
      const xml = await presFile.async('string');
      const szm = xml.match(/<p:sldSz[^>]*>/);
      if (szm) {
        const cx = (szm[0].match(/cx="(\d+)"/) || [])[1];
        const cy = (szm[0].match(/cy="(\d+)"/) || [])[1];
        if (cx && cy && Number(cx) > 0) {
          slideW = Number(cx);
          slideH = Number(cy);
        }
      }
    }
  } catch {}

  const root = document.createElement('div');
  root.className = 'pptx-root';
  root.style.cssText += ';display:flex;flex-direction:column;align-items:center;gap:var(--s-3);overflow:auto';
  container.appendChild(root);

  let controls = null;
  let posLabel = null;
  let zoomLabel = null;
  let stage = null;
  let canvas = null;
  let rotation = 0;
  let zoom = 1;
  let fitW = 0;
  const total = { n: 1 };
  let current = 1;

  function applyRatio() {
    if (!stage) return;
    stage.style.aspectRatio = `${slideW} / ${slideH}`;
  }

  function applyRotation() {
    if (!canvas || !stage) return;
    if (rotation % 180 === 90) {
      const W = stage.clientWidth;
      const H = stage.clientHeight;
      const cw = canvas.clientWidth || canvas.width;
      const chh = canvas.clientHeight || canvas.height;
      if (!W || !H || !cw || !chh) return;
      const s = Math.min(W / chh, H / cw);
      canvas.style.position = 'static';
      canvas.style.transform = `rotate(${rotation}deg) scale(${s})`;
    } else {
      canvas.style.position = 'static';
      canvas.style.transform = rotation ? `rotate(${rotation}deg)` : 'none';
    }
  }

  function fitStage() {
    if (!stage) return;
    const W = container.clientWidth || 900;
    const H = container.clientHeight || 620;
    const ar = slideW / slideH;
    const availH = Math.max(180, H - 70);
    fitW = Math.max(240, Math.min(W - 16, availH * ar));
    applyZoom();
    if (controls) controls.style.maxWidth = Math.round(fitW) + 'px';
  }

  function applyZoom() {
    if (!stage) return;
    const ww = Math.round(fitW * zoom);
    stage.style.width = ww + 'px';
    stage.style.maxWidth = 'none';
  }

  function zoomLabelUpdate() {
    if (zoomLabel) zoomLabel.textContent = Math.round(zoom * 100) + '%';
  }

  function buildStage() {
    stage = document.createElement('div');
    stage.style.cssText = 'width:100%;position:relative;display:flex;justify-content:center;align-items:center;overflow:hidden;background:#fff;border-radius:var(--r-sm);box-shadow:var(--shadow-2)';
    root.appendChild(stage);
    canvas = document.createElement('canvas');
    canvas.style.cssText = 'display:block;max-width:100%;max-height:100%;border-radius:var(--r-sm)';
    stage.appendChild(canvas);
    applyRatio();
    fitStage();
    applyRotation();
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

  function label() {
    const shown = Math.min(total.n, Math.max(1, current));
    if (posLabel) posLabel.textContent = `${shown} / ${total.n}`;
    if (hooks.onProgress) hooks.onProgress(shown / total.n, `幻灯片 ${shown} / ${total.n}`);
  }

  async function goTo(idx) {
    idx = Math.max(0, Math.min(total.n - 1, idx));
    const renderOpts = { quality: 'high' };
    try {
      if (typeof viewer.renderSlide === 'function') {
        await viewer.renderSlide(idx, canvas, renderOpts);
      } else {
        await viewer.goToSlide(idx);
        await viewer.render(canvas, renderOpts);
      }
      current = idx + 1;
      label();
      applyRotation();
    } catch (e) {
      try { await viewer.render(canvas, renderOpts); } catch {}
    }
  }

  function buildControls() {
    controls = document.createElement('div');
    controls.style.cssText = 'position:sticky;top:0;z-index:3;display:flex;gap:8px;align-items:center;background:var(--surface);padding:8px 12px;border-radius:var(--r-md);box-shadow:var(--shadow-1);flex-wrap:wrap;row-gap:6px;width:100%;max-width:960px';
    controls.innerHTML = `
      <button class="btn btn-icon" data-a="first"><svg><use href="#icon-skip-first"/></svg></button>
      <button class="btn btn-icon" data-a="prev"><svg><use href="#icon-chevron-left"/></svg></button>
      <span style="font-size:var(--fs-sm);min-width:96px;text-align:center" id="pptxPos">1 / 1</span>
      <button class="btn btn-icon" data-a="next"><svg><use href="#icon-chevron-right"/></svg></button>
      <button class="btn btn-icon" data-a="last"><svg><use href="#icon-skip-last"/></svg></button>
      <button class="btn btn-icon" data-a="zoomout" title="缩小"><svg><use href="#icon-zoom-out"/></svg></button>
      <span style="font-size:var(--fs-sm);min-width:52px;text-align:center" id="pptxZoom">100%</span>
      <button class="btn btn-icon" data-a="zoomin" title="放大"><svg><use href="#icon-zoom-in"/></svg></button>
      <button class="btn btn-icon" data-a="rotate" title="旋转"><svg><use href="#icon-refresh"/></svg></button>
      <button class="btn btn-icon" data-a="hidebar" style="margin-left:auto" title="收起工具栏"><svg><use href="#icon-chevron-up"/></svg></button>`;
    posLabel = controls.querySelector('#pptxPos');
    zoomLabel = controls.querySelector('#pptxZoom');
    controls.addEventListener('click', async e => {
      const btn = e.target.closest('[data-a]');
      if (!btn) return;
      const a = btn.dataset.a;
      if (a === 'hidebar') { collapseToolbar(); return; }
      if (a === 'zoomin') { zoom = Math.min(2.5, Math.round((zoom + 0.25) * 100) / 100); applyZoom(); zoomLabelUpdate(); return; }
      if (a === 'zoomout') { zoom = Math.max(0.5, Math.round((zoom - 0.25) * 100) / 100); applyZoom(); zoomLabelUpdate(); return; }
      if (a === 'rotate') {
        rotation = (rotation + 90) % 360;
        applyRatio();
        applyRotation();
        return;
      }
      if (a === 'prev') return goTo(current - 2);
      if (a === 'next') return goTo(current);
      if (a === 'first') return goTo(0);
      if (a === 'last') return goTo(total.n - 1);
    });
    root.appendChild(controls);
  }

  function onKey(e) {
    if (e.key === 'ArrowRight') goTo(current);
    else if (e.key === 'ArrowLeft') goTo(current - 2);
  }

  buildStage();
  buildControls();

  const viewer = new ViewerCtor({
    canvas,
    slideSizeMode: 'fit',
    backgroundColor: '#ffffff',
    quality: 'high',
    dpi: 192,
    pixelRatio: Math.max(2, window.devicePixelRatio || 1),
    enableTextAntialiasing: true,
    enableShapeAntialiasing: true
  });
  await viewer.loadFile(file);
  total.n = (typeof viewer.getSlideCount === 'function' && viewer.getSlideCount()) || 1;
  await viewer.render(canvas, { quality: 'high' });
  current = 1;
  applyRatio();
  fitStage();
  applyRotation();
  label();
  const startSlide = hooks.startSlide && hooks.startSlide >= 1 ? Math.floor(hooks.startSlide) : 1;
  if (startSlide > 1) await goTo(startSlide - 1);

  document.addEventListener('keydown', onKey);
  let resizeT;
  const onResize = () => {
    clearTimeout(resizeT);
    resizeT = setTimeout(() => { fitStage(); applyRatio(); goTo(current - 1); }, 200);
  };
  window.addEventListener('resize', onResize);

  return {
    destroy() {
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', onResize);
      const tools = document.getElementById('rdTools');
      if (tools) tools.remove();
      try { if (typeof viewer.destroy === 'function') viewer.destroy(); } catch {}
      root.remove();
    }
  };
}
