export async function setupFoliateView(container, source, opts) {
  // 先加载 foliate-js 并注册 <foliate-view> 自定义元素，
  // 否则 whenDefined 会一直挂起、正文永不渲染
  if (window.MRLoad && typeof window.MRLoad.foliate === 'function') {
    await window.MRLoad.foliate();
  }
  const view = document.createElement('foliate-view');
  container.appendChild(view);
  await customElements.whenDefined('foliate-view');
  if (opts.onRelocate) {
    view.addEventListener('relocate', e => opts.onRelocate(e.detail));
  }
  await view.open(source);
  try {
    const r = view.renderer;
    if (opts.mode === 'scrolled') {
      r.setAttribute('flow', 'scrolled');
      r.setAttribute('scrolled', '');
    } else {
      r.setAttribute('flow', 'paginated');
      if (window.innerWidth > 1024) r.setAttribute('spread', 'auto');
    }
    r.setAttribute('margin', '8%');
  } catch {}
  return view;
}
