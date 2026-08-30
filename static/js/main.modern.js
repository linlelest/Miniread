(() => {
  const { api, esc, toast, modal, confirmDialog, fmtSize, fmtDate, debounce } = window.MR;
  let shelfView = localStorage.getItem('mr-shelf-view') || 'grid';
  let downloadES = null;
  let booksCache = [];
  let groupsCache = [];
  let groupCoversCache = {};
  let currentGroupId = null;
  let currentGroupName = '';
  let searchKw = '';
  let selectedMode = false;
  let selectedIds = new Set();
  let isAdmin = false;
  let adminUsersCache = null;
  let lastLongPress = 0;
  let suppressClick = false;

  const $ = sel => document.querySelector(sel);

  // 分组封面占位渐变色板（低饱和手绘感配色，按分组序号取色）
  const GROUP_TINTS = [
    'linear-gradient(135deg,#8ec5a3,#5a8f74)',
    'linear-gradient(135deg,#a8c5e0,#6f92b8)',
    'linear-gradient(135deg,#e0bfa3,#b8875f)',
    'linear-gradient(135deg,#c5a8d8,#8f6fb0)',
    'linear-gradient(135deg,#d8c9a3,#a8925f)',
    'linear-gradient(135deg,#a3d0c9,#5f9a90)'
  ];
  const groupTint = n => GROUP_TINTS[Math.abs(parseInt(n, 10) || 0) % GROUP_TINTS.length];

  function show(view) {
    $('#view-shelf').hidden = view !== 'shelf';
    $('#view-download').hidden = view !== 'download';
    document.querySelectorAll('[data-nav]').forEach(a => {
      a.classList.toggle('active', a.dataset.nav === view);
    });
    if (view === 'download') refreshTasks();
    history.replaceState(null, '', '#' + view);
  }

  function bookCardHtml(b) {
    const cover = b.cover_url
      ? `<img src="${esc(b.cover_url)}" alt="" loading="lazy">`
      : '<svg><use href="#icon-book"/></svg>';
    const sub = b.unsupported
      ? '<span class="badge badge-warning">不受支持</span>'
      : esc(b.author || (b.format || '').toUpperCase());
    const pct = Math.min(100, b.last_read_percent || 0);
    const rssBadge = b.kind === 'rss'
      ? '<span class="rss-badge" title="RSS 订阅"><svg><use href="#icon-rss"/></svg></span>'
      : '';
    const coverBox = b.convert_status === 'pending'
      ? `<div class="book-cover converting">${cover}<div class="cover-overlay"><span class="cvr-spin"></span><span>转换中</span></div></div>`
      : `<div class="book-cover">${cover}${rssBadge}</div>`;
    return `<article class="book-card${selectedIds.has(b.id) ? ' selected' : ''}" data-book="${b.id}" data-fp="${esc(b.fingerprint || '')}" data-kind="${esc(b.kind || '')}">
      ${coverBox}
      <div class="card-check"><svg><use href="#icon-check"/></svg></div>
      <div class="book-meta">
        <div class="book-title">${esc(b.title)}</div>
        <div class="book-sub">${sub}</div>
        <div class="book-sub">${fmtDate(b.created_at)}</div>
        ${pct > 0 ? `<div class="book-progress"><i style="width:${pct}%"></i></div>` : ''}
      </div>
    </article>`;
  }

  function groupGridHtml(g) {
    const covers = groupCoversCache[g.id] || [];
    if (!covers.length) {
      return '<div class="group-grid gg-empty"><svg><use href="#icon-folder"/></svg></div>';
    }
    let cells = '';
    for (let i = 0; i < 4; i++) {
      cells += covers[i]
        ? `<div class="gg-cell"><img src="${esc(covers[i])}" alt="" loading="lazy"></div>`
        : `<div class="gg-cell"><div class="gg-ph" style="background:${groupTint((g.id || 0) * 4 + i)}"></div></div>`;
    }
    return `<div class="group-grid">${cells}</div>`;
  }

  function groupCardHtml(g) {
    return `<article class="group-card" data-group="${g.id}" data-gname="${esc(g.name)}">
      ${groupGridHtml(g)}
      <div class="group-meta">
        <div class="group-name">${esc(g.name)}</div>
        <div class="group-sub">${g.member_count || 0} 本</div>
      </div>
    </article>`;
  }

  // 拉取各组前 4 本封面用于 2×2 网格（无缓存时异步填充对应卡片）
  function loadGroupCovers() {
    groupsCache.forEach(g => {
      if (groupCoversCache[g.id]) return;
      api('/api/books?group=' + g.id).then(books => {
        groupCoversCache[g.id] = (books || []).slice(0, 4).map(b => b.cover_url).filter(Boolean);
        const gc = $('#shelf').querySelector(`.group-card[data-group="${g.id}"]`);
        if (!gc) return;
        const meta = gc.querySelector('.group-meta');
        gc.innerHTML = groupGridHtml(g);
        if (meta) gc.appendChild(meta);
      }).catch(() => {});
    });
  }

  function renderShelf(books) {
    const shelf = $('#shelf');
    const searching = searchKw.length > 0;
    const showGroups = !searching && currentGroupId === null && shelfView === 'grid' && groupsCache.length > 0;
    shelf.classList.toggle('selecting', selectedMode);
    shelf.classList.toggle('shelf-grid', shelfView === 'grid');
    shelf.classList.toggle('shelf-list', shelfView === 'list');
    let html = '';
    if (showGroups) {
      html += `<div class="shelf-section">分组</div>`;
      html += groupsCache.map(g => groupCardHtml(g)).join('');
      html += `<div class="shelf-section">书籍</div>`;
    }
    html += books.map(bookCardHtml).join('');
    shelf.innerHTML = html;
    const empty = books.length === 0 && !showGroups;
    $('#shelfEmpty').hidden = !empty;
    if (empty) {
      $('#shelfEmpty .empty-title').textContent = searching
        ? '未找到匹配内容'
        : (currentGroupId !== null ? '该分组还没有书籍' : '书架还是空的');
      $('#btnUploadEmpty').style.display = (!searching && currentGroupId === null) ? '' : 'none';
    }
    if (showGroups) loadGroupCovers();
  }

  // 管理员：搜索词非空时在结果上方显示账号分区（全量拉取后本地过滤）
  async function renderAdminMatches(kw) {
    const box = $('#adminUsers');
    if (!box) return;
    try {
      if (!adminUsersCache) adminUsersCache = (await api('/api/admin/users')) || [];
      const list = adminUsersCache
        .filter(u => (u.username || '').toLowerCase().includes(kw.toLowerCase()))
        .slice(0, 8);
      box.innerHTML = list.length
        ? `<div class="admin-sec"><div class="admin-sec-title">账号</div>${list.map(u => `
          <div class="admin-user" data-admin-user="${u.id}">
            <svg><use href="#icon-user"/></svg>
            <span class="au-name">${esc(u.username)}</span>
            <span class="badge${u.role === 'admin' ? ' badge-accent' : ''}">${u.role === 'admin' ? '管理员' : '用户'}</span>
          </div>`).join('')}</div>`
        : '';
    } catch {}
  }

  let shelfPollT = null;
  async function loadShelf(opts = {}) {
    try {
      if (opts.resetCovers) groupCoversCache = {};
      const params = new URLSearchParams();
      if (searchKw) params.set('query', searchKw);
      params.set('group', currentGroupId === null ? 'root' : currentGroupId);
      const [books, groups] = await Promise.all([
        api('/api/books?' + params.toString()),
        api('/api/groups').catch(() => [])
      ]);
      booksCache = books || [];
      groupsCache = groups || [];
      renderShelf(booksCache);
      clearTimeout(shelfPollT);
      if (booksCache.some(b => b.convert_status === 'pending')) {
        shelfPollT = setTimeout(() => loadShelf(), 4000);
      }
    } catch (e) {
      if (e.code === 401) return location.replace('/login');
      toast(e.message, 'error');
    }
  }

  // 书架搜索：300ms 防抖，清空恢复当前层级完整列表
  const doShelfSearch = debounce(async kw => {
    searchKw = kw;
    $('#adminUsers').innerHTML = '';
    try {
      const params = new URLSearchParams();
      params.set('query', kw);
      params.set('group', currentGroupId === null ? 'root' : currentGroupId);
      booksCache = (await api('/api/books?' + params.toString())) || [];
      if (searchKw !== kw) return;
      renderShelf(booksCache);
      if (kw && isAdmin) renderAdminMatches(kw);
    } catch (e) {
      toast(e.message, 'error');
    }
  }, 300);

  function enterGroup(id, name) {
    exitSelectMode();
    currentGroupId = id;
    currentGroupName = name || '';
    searchKw = '';
    const si = $('#shelfSearch');
    if (si) si.value = '';
    $('#shelfSearchWrap').classList.remove('has-value');
    $('#adminUsers').innerHTML = '';
    $('#btnGroupBack').hidden = false;
    $('#shelfTitle').textContent = currentGroupName;
    loadShelf();
  }

  function exitGroup() {
    exitSelectMode();
    currentGroupId = null;
    currentGroupName = '';
    searchKw = '';
    const si = $('#shelfSearch');
    if (si) si.value = '';
    $('#shelfSearchWrap').classList.remove('has-value');
    $('#adminUsers').innerHTML = '';
    $('#btnGroupBack').hidden = true;
    $('#shelfTitle').textContent = '我的书架';
    loadShelf();
  }

  function dismissedIds() {
    try { return JSON.parse(localStorage.getItem('mr-ann-dismissed') || '[]'); } catch (e) { return []; }
  }

  function dismissedKeys() {
    try { return JSON.parse(localStorage.getItem('mr-ann-seen') || '[]'); } catch (e) { return []; }
  }

  let annListCache = [];

  function openAnnModal(list, start = 0) {
    if (!list.length) return;
    let idx = Math.max(0, Math.min(list.length - 1, start));
    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:fixed;inset:0;z-index:300;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.5);padding:16px';
    wrap.innerHTML = `<div style="width:min(560px,94vw);max-height:82vh;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--hairline);border-radius:var(--r-lg);box-shadow:var(--shadow-2);overflow:hidden">
      <div style="display:flex;align-items:center;gap:8px;padding:14px 16px;border-bottom:1px solid var(--hairline)">
        <svg style="width:18px;height:18px;color:var(--accent);flex-shrink:0"><use href="#icon-megaphone"/></svg>
        <b style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" id="annMTitle"></b>
        <button class="btn btn-ghost btn-icon" id="annMClose" style="width:30px;height:30px" title="关闭">×</button>
      </div>
      <div id="annMBody" style="padding:16px;overflow:auto;flex:1;font-size:var(--fs-sm);line-height:1.9"></div>
      <div style="display:flex;align-items:center;gap:8px;padding:10px 14px;border-top:1px solid var(--hairline)">
        <button class="btn btn-sm" id="annMPrev">‹</button>
        <span class="text-3" style="font-size:var(--fs-xs);flex:1;text-align:center" id="annMPos"></span>
        <button class="btn btn-sm" id="annMNext">›</button>
        <button class="btn btn-sm" id="annMDismiss" style="margin-left:auto">不再显示</button>
      </div>
    </div>`;
    document.body.appendChild(wrap);
    const q = s => wrap.querySelector(s);
    function markSeen(a) {
      if (!a.show_dismiss) return;
      const keys = dismissedKeys();
      const k = a.id + ':' + (a.updated_at || 0);
      if (!keys.includes(k)) { keys.push(k); localStorage.setItem('mr-ann-seen', JSON.stringify(keys.slice(-100))); }
    }
    function render() {
      const a = list[idx];
      q('#annMTitle').textContent = a.title || '公告';
      q('#annMBody').innerHTML = MR.mdAnn(a.content);
      q('#annMPos').textContent = `${idx + 1} / ${list.length}${a.pinned ? ' · 置顶' : ''}`;
      q('#annMPrev').disabled = idx === 0;
      q('#annMNext').disabled = idx === list.length - 1;
      q('#annMDismiss').style.display = a.show_dismiss ? '' : 'none';
    }
    function close() { wrap.remove(); loadAnnouncements(); }
    q('#annMClose').addEventListener('click', () => { markSeen(list[idx]); close(); });
    wrap.addEventListener('click', e => { if (e.target === wrap) { markSeen(list[idx]); close(); } });
    q('#annMPrev').addEventListener('click', () => { if (idx > 0) { idx--; render(); } });
    q('#annMNext').addEventListener('click', () => { if (idx < list.length - 1) { idx++; render(); } });
    q('#annMDismiss').addEventListener('click', () => { markSeen(list[idx]); close(); });
    render();
  }

  async function loadAnnouncements() {
    try {
      const gone = dismissedKeys();
      const list = (await api('/api/public/announcements') || [])
        .filter(a => !gone.includes(a.id + ':' + (a.updated_at || 0)));
      annListCache = list;
      $('#annBanner').innerHTML = list.length
        ? `<div class="ann-banner row gap-2" style="cursor:pointer" id="annOpen">
            <svg style="width:18px;height:18px;flex-shrink:0"><use href="#icon-megaphone"/></svg>
            <span class="flex-1">${list.length} 条公告 · 点击查看</span>
          </div>`
        : '';
      if (list.length && !sessionStorage.getItem('mr-ann-shown')) {
        sessionStorage.setItem('mr-ann-shown', '1');
        openAnnModal(list);
      }
    } catch {}
  }

  // ===== 多文件上传（并发 3，上传 0-50% + 解析 50-100%，PDF 纯上传） =====
  const UPLOAD_CONCURRENCY = 3;
  const UPLOAD_ACCEPT = /\.(txt|epub|pdf|mobi|azw|azw3|prc|fb2|html?|md|markdown|docx|rtf|cbz|pptx?)$/i;
  const uploadQueue = { items: [], active: 0, listEl: null, onAllDone: null };

  function uploadKind(name) {
    const m = name.toLowerCase().match(/\.(\w+)$/);
    const ext = m ? m[1] : '';
    if (ext === 'pdf' || ext === 'mobi' || ext === 'azw' || ext === 'azw3' || ext === 'prc' || ext === 'cbz') return 'native';
    if (ext === 'ppt' || ext === 'pptx') return 'pptx';
    return 'canonical';
  }

  function upItemHtml(item) {
    const color = item.status === 'done' ? 'var(--success, #3a9e5f)' : item.status === 'failed' ? 'var(--danger, #d64545)' : 'var(--text-3, #8a8f98)';
    const barColor = item.status === 'failed' ? 'var(--danger, #d64545)' : item.status === 'done' ? 'var(--success, #3a9e5f)' : 'var(--accent)';
    return `<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;min-width:0">
        <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:var(--fs-sm)">${esc(item.name)}</span>
        <span style="font-size:var(--fs-xs);color:${color};white-space:nowrap">${esc(item.label)}</span>
      </div>
      <div class="progress mt-1"><div class="bar" style="width:${item.pct}%;background:${barColor}"></div></div>`;
  }

  function upRenderItem(item) {
    const el = item.el;
    if (!el) return;
    el.innerHTML = upItemHtml(item);
  }

  function upSet(item, pct, label, status) {
    item.pct = Math.max(0, Math.min(100, Math.round(pct)));
    item.label = label;
    if (status) item.status = status;
    upRenderItem(item);
  }

  function upFail(item, msg) {
    if (item.timer) { clearInterval(item.timer); item.timer = null; }
    item.status = 'failed';
    upSet(item, item.pct, msg, 'failed');
  }

  function upPump() {
    while (uploadQueue.active < UPLOAD_CONCURRENCY) {
      const item = uploadQueue.items.find(i => i.status === 'queued');
      if (!item) break;
      item.status = 'uploading';
      uploadQueue.active++;
      upRun(item).catch(() => {}).finally(() => {
        uploadQueue.active--;
        upPump();
        if (uploadQueue.active === 0 && !uploadQueue.items.some(i => i.status === 'queued' || i.status === 'uploading')) {
          if (uploadQueue.onAllDone) { const cb = uploadQueue.onAllDone; uploadQueue.onAllDone = null; cb(); }
        }
      });
    }
  }

  function upPollConvert(item) {
    return new Promise(resolve => {
      const started = Date.now();
      let fails = 0;
      const tick = async () => {
        try {
          const d = await api('/api/books/' + item.bookId);
          fails = 0;
          const cs = d && d.convert_status;
          if (cs === 'done') { upSet(item, 100, '转换完成', 'done'); resolve(); return; }
          // 本机无 LibreOffice（none）或转换失败：书已入库，打开时走内置 PPTX 预览兜底
          if (cs === 'none') { upSet(item, 100, '就绪（使用内置预览）', 'done'); resolve(); return; }
          if (cs === 'failed') { upSet(item, 100, '转换失败，使用内置预览', 'done'); resolve(); return; }
        } catch (e) {
          // 查询连续失败（书 ID 异常/网络抖动等）：数次后按就绪处理，绝不无限等待
          if (++fails >= 5) { upSet(item, 100, '就绪（使用内置预览）', 'done'); resolve(); return; }
        }
        if (Date.now() - started > 10 * 60 * 1000) { upSet(item, 100, '转换超时，使用内置预览', 'done'); resolve(); return; }
        const sim = 100 + Math.min(45, (Date.now() - started) / 10000);
        item.pct = Math.max(item.pct, Math.min(95, sim));
        item.label = '转换中…';
        upRenderItem(item);
        setTimeout(tick, 1500);
      };
      tick();
    });
  }

  function upRun(item) {
    return new Promise(resolve => {
      const fd = new FormData();
      fd.append('file', item.file);
      fd.append('import_options', JSON.stringify(item.options));
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/books/upload');
      xhr.upload.onprogress = e => {
        if (!e.lengthComputable || item.status === 'failed') return;
        const pct = e.loaded / e.total;
        if (item.kind === 'native') {
          upSet(item, pct * 100, '上传中 ' + Math.round(pct * 100) + '%');
        } else if (item.kind === 'pptx') {
          // PPTX 只有"上传"与"转换"两段，上传阶段不出现"解析中"字样
          upSet(item, pct * 50, '上传中 ' + Math.round(pct * 50) + '%');
        } else {
          upSet(item, pct * 50, pct >= 1 ? '解析中…' : '上传中 ' + Math.round(pct * 50) + '%');
          if (pct >= 1 && !item.timer) {
            item.timer = setInterval(() => {
              if (item.status === 'failed') return clearInterval(item.timer);
              item.pct = Math.min(95, item.pct + 0.5);
              upRenderItem(item);
            }, 400);
          }
        }
      };
      xhr.onload = async () => {
        if (item.timer) { clearInterval(item.timer); item.timer = null; }
        try {
          let body = null;
          try { body = JSON.parse(xhr.responseText); } catch {}
          if (xhr.status >= 400 || !body || body.code >= 400) {
            upFail(item, (body && body.message) || '上传失败');
            return;
          }
          item.bookId = body.data && body.data.book && body.data.book.id;
          if (item.kind === 'pptx') {
            // 后端已预检 LibreOffice：不可用时响应即为 none，无需显示"转换中"，直接完成走兜底
            const cs0 = body.data && body.data.book && body.data.book.convert_status;
            if (cs0 && cs0 !== 'pending') {
              upSet(item, 100, cs0 === 'none' ? '就绪（使用内置预览）' : '转换失败，使用内置预览', 'done');
            } else {
              upSet(item, 55, '转换中…');
              await upPollConvert(item);
            }
          } else if (item.kind === 'native') {
            upSet(item, 100, '上传完成', 'done');
          } else {
            const sec = body.data && body.data.summary && body.data.summary.sections;
            upSet(item, 100, sec == null ? '导入完成' : `完成：${sec} 个章节`, 'done');
          }
        } catch (e) {
          // 响应处理异常时绝不卡死条目：PPTX 必有内置预览兜底，其余按完成处理
          if (item.kind === 'pptx') upSet(item, 100, '就绪（使用内置预览）', 'done');
          else upSet(item, 100, '上传完成', 'done');
        } finally {
          resolve();
        }
      };
      xhr.onerror = () => { upFail(item, '网络错误'); resolve(); };
      xhr.send(fd);
    });
  }

  function upCollectOptions(el) {
    return {
      encoding: el.querySelector('#upEncoding').value,
      chapter_regex: el.querySelector('#upRegex').value.trim(),
      heading_level: parseInt(el.querySelector('#upHeading').value, 10),
      strip_toc: el.querySelector('#upStripToc').checked
    };
  }

  function upAddFiles(files, options) {
    for (const f of files) {
      if (!UPLOAD_ACCEPT.test(f.name)) { toast(`跳过不支持的文件：${f.name}`, 'error'); continue; }
      uploadQueue.items.push({ file: f, name: f.name, kind: uploadKind(f.name), options, status: 'queued', pct: 0, label: '排队中' });
    }
    if (uploadQueue.listEl) {
      uploadQueue.items.forEach(item => {
        if (item.el) return;
        const row = document.createElement('div');
        row.style.cssText = 'padding:8px 2px';
        row.innerHTML = upItemHtml(item);
        uploadQueue.listEl.appendChild(row);
        item.el = row;
      });
    }
  }

  function openUpload() {
    uploadQueue.items = [];
    uploadQueue.active = 0;
    uploadQueue.onAllDone = null;
    modal({
      title: '上传书籍',
      body: `
        <div class="field"><label>文件（可按住 Ctrl / Shift 多选，或拖拽文件到书架）</label>
          <input type="file" id="upFile" class="input" multiple accept=".txt,.epub,.pdf,.mobi,.azw,.azw3,.prc,.fb2,.html,.htm,.md,.markdown,.docx,.rtf,.cbz,.pptx,.ppt"></div>
        <details class="mt-3"><summary class="text-2 clickable" style="font-size:var(--fs-sm)">导入选项（可选，对本次所有文件生效）</summary>
          <div class="field mt-3"><label>文本编码（TXT/RTF）</label>
            <select id="upEncoding" class="select">
              <option value="auto">自动检测</option>
              <option value="utf-8">UTF-8</option><option value="gb18030">GB18030 / GBK</option>
              <option value="big5">Big5 繁体</option><option value="utf-16">UTF-16</option>
            </select></div>
          <div class="field"><label>自定义分章正则（留空用默认规则）</label>
            <input id="upRegex" class="input" placeholder="例如：^卷?[一二三四五六七八九十百千\\d]+.*$"></div>
          <div class="field"><label>标题切分层级（MD/HTML/DOCX）</label>
            <select id="upHeading" class="select">
              <option value="2">h1–h2（默认）</option><option value="1">仅 h1</option>
              <option value="3">h1–h3</option><option value="4">h1–h4</option>
            </select></div>
          <label class="setting-row"><label>剔除开头目录块</label>
            <span class="switch"><input type="checkbox" id="upStripToc" checked><span class="track"></span></span></label>
          <label class="setting-row"><label>保存为我的默认</label>
            <span class="switch"><input type="checkbox" id="upSetDefault" checked><span class="track"></span></span></label>
        </details>
        <div id="upList" class="mt-3" style="display:flex;flex-direction:column;gap:10px;max-height:260px;overflow:auto"></div>
        <div class="progress mt-2" id="upProgress" hidden><i style="width:0%"></i></div>`,
      footer: `<button class="btn" data-close>取消</button>
               <button class="btn btn-primary" data-upload>开始上传</button>`,
      onOpen(el, close) {
        api('/api/import/defaults').then(d => {
          if (d && d.encoding) $('#upEncoding').value = d.encoding;
          if (d && d.chapter_regex) $('#upRegex').value = d.chapter_regex;
          if (d && d.strip_toc === false) $('#upStripToc').checked = false;
        }).catch(() => {});
        uploadQueue.listEl = el.querySelector('#upList');
        el.querySelector('#upFile').addEventListener('change', e => {
          upAddFiles([...e.target.files], upCollectOptions(el));
          e.target.value = '';
        });
        el.querySelector('[data-upload]').addEventListener('click', async () => {
          const btn = el.querySelector('[data-upload]');
          const pending = uploadQueue.items.filter(i => i.status === 'queued');
          if (!pending.length && !uploadQueue.items.some(i => i.status === 'uploading')) return toast('请先选择文件', 'error');
          if (el.querySelector('#upSetDefault').checked) {
            api('/api/import/defaults', { method: 'PUT', json: upCollectOptions(el) }).catch(() => {});
          }
          btn.disabled = true;
          btn.textContent = '上传中…';
          uploadQueue.onAllDone = () => {
            const failed = uploadQueue.items.filter(i => i.status === 'failed').length;
            const ok = uploadQueue.items.length - failed;
            toast(failed ? `上传完成：${ok} 成功，${failed} 失败` : `成功导入 ${ok} 本书`, failed ? 'error' : 'success');
            loadShelf();
            setTimeout(close, 900);
          };
          upPump();
        });
      }
    });
  }

  function openDropUpload(files) {
    uploadQueue.items = [];
    uploadQueue.active = 0;
    uploadQueue.onAllDone = null;
    modal({
      title: '上传书籍',
      body: `<div class="text-3" style="font-size:var(--fs-sm)">正在上传 ${files.length} 个文件</div>
        <div id="upList" class="mt-3" style="display:flex;flex-direction:column;gap:10px;max-height:320px;overflow:auto"></div>`,
      onOpen(el, close) {
        uploadQueue.listEl = el.querySelector('#upList');
        upAddFiles(files, {});
        uploadQueue.onAllDone = () => {
          const failed = uploadQueue.items.filter(i => i.status === 'failed').length;
          const ok = uploadQueue.items.length - failed;
          toast(failed ? `上传完成：${ok} 成功，${failed} 失败` : `成功导入 ${ok} 本书`, failed ? 'error' : 'success');
          loadShelf();
          setTimeout(close, 900);
        };
        upPump();
      }
    });
  }

  function openServerCfg() {
    api('/api/download/config').then(cfg => {
      modal({
        title: 'SoNovel 服务器配置',
        body: `
          <div class="field"><label>服务器地址</label>
            <input id="cfgUrl" class="input" placeholder="http://127.0.0.1:7765" value="${esc(cfg && cfg.serverUrl || '')}"></div>
          <div class="field"><label>API Token</label>
            <input id="cfgToken" class="input" type="password" placeholder="${cfg && cfg.hasToken ? '已配置，留白保持不变' : 'sonovel_xxx'}"></div>
          <div class="text-3" style="font-size:var(--fs-xs)">在 SoNovel 服务器网页端「API Token」页面创建 Token 后填入此处。</div>`,
        footer: `<button class="btn" data-close>取消</button>
                 <button class="btn btn-primary" data-save>保存</button>
                 <a class="btn btn-ghost" style="margin-left:auto" href="/sonovelwebguide" target="_blank" rel="noopener">详细教程</a>`,
        onOpen(el, close) {
          el.querySelector('[data-save]').addEventListener('click', async () => {
            try {
              await api('/api/download/config', {
                method: 'PUT',
                json: {
                  serverUrl: el.querySelector('#cfgUrl').value.trim(),
                  apiToken: el.querySelector('#cfgToken').value.trim()
                }
              });
              toast('配置已保存', 'success');
              close();
            } catch (e) { toast(e.message, 'error'); }
          });
        }
      });
    }).catch(e => toast(e.message, 'error'));
  }

  const SEARCH_PAGE_SIZE = 10;
  const DOWNLOAD_FORMATS = ['txt', 'html', 'pdf'];
  let searchState = { kw: '', all: [], page: 1 };

  function pagerPages(cur, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const pages = [1];
    if (cur > 3) pages.push('...');
    for (let i = Math.max(2, cur - 1); i <= Math.min(total - 1, cur + 1); i++) pages.push(i);
    if (cur < total - 2) pages.push('...');
    pages.push(total);
    return pages;
  }

  function searchCard(it) {
    const base = { url: it.url || it.bookUrl, bookName: it.bookName || it.book_name,
                   author: it.author || '', sourceName: it.sourceName || it.source_name || '' };
    const payload = esc(JSON.stringify(base));
    const others = DOWNLOAD_FORMATS.map(f =>
      `<button data-dl='${esc(JSON.stringify({ ...base, format: f }))}'>${f.toUpperCase()}</button>`).join('');
    return `
    <div class="search-result">
      <div class="sr-main">
        <div class="sr-title">${esc(base.bookName)}</div>
        <div class="sr-sub">${esc(base.author || '佚名')} · ${esc(base.sourceName)}${it.latestChapter ? ' · ' + esc(it.latestChapter) : ''}</div>
      </div>
      <div class="menu-anchor dl-group">
        <button class="btn btn-sm" data-dl='${payload}'><svg><use href="#icon-download"/></svg>下载 EPUB</button>
        <button class="btn btn-sm dl-other" data-dlother title="其他格式"><svg><use href="#icon-download"/></svg>其他格式<svg style="width:10px;height:10px"><use href="#icon-cloud-down"/></svg></button>
        <div class="menu dl-menu" hidden>${others}</div>
      </div>
    </div>`;
  }

  function renderSearchPage() {
    const box = $('#searchResults');
    const total = Math.max(1, Math.ceil(searchState.all.length / SEARCH_PAGE_SIZE));
    searchState.page = Math.min(Math.max(1, searchState.page), total);
    const cur = searchState.page;
    const slice = searchState.all.slice((cur - 1) * SEARCH_PAGE_SIZE, cur * SEARCH_PAGE_SIZE);
    const pages = pagerPages(cur, total);
    const arrowL = '<svg style="transform:rotate(180deg)"><use href="#icon-arrow-left"/></svg>';
    const pager = `
      <div class="pager">
        <button class="pager-btn" data-page="${cur - 1}" ${cur <= 1 ? 'disabled' : ''} title="上一页">${arrowL}</button>
        ${pages.map(p => p === '...'
          ? '<span class="pager-ellipsis">…</span>'
          : `<button class="pager-btn ${p === cur ? 'active' : ''}" data-page="${p}">${p}</button>`).join('')}
        <input class="pager-input" id="pagerJump" type="number" min="1" max="${total}" value="${cur}" title="输入页码回车跳转">
        <button class="pager-btn" data-page="${cur + 1}" ${cur >= total ? 'disabled' : ''} title="下一页"><svg><use href="#icon-arrow-left"/></svg></button>
        <span class="pager-info">共 ${searchState.all.length} 本 · ${total} 页</span>
      </div>`;
    box.innerHTML = slice.map(searchCard).join('') + pager;
  }

  async function doSearch(kw) {
    const box = $('#searchResults');
    box.innerHTML = '<div class="skeleton" style="height:64px"></div><div class="skeleton mt-2" style="height:64px"></div>';
    try {
      const list = await api('/api/download/search?kw=' + encodeURIComponent(kw));
      const arr = Array.isArray(list) ? list : (list && list.results) || [];
      if (!arr.length) {
        box.innerHTML = '<div class="empty"><svg><use href="#icon-search"/></svg><div class="empty-title">没有找到结果</div></div>';
        return;
      }
      searchState = { kw, all: arr, page: 1 };
      renderSearchPage();
    } catch (e) {
      box.innerHTML = `<div class="empty"><svg><use href="#icon-alert"/></svg><div class="empty-title">${esc(e.message)}</div></div>`;
    }
  }

  async function startDownload(payload) {
    try {
      if (!payload.format) payload.format = 'epub';
      await api('/api/download/fetch', { method: 'POST', json: payload });
      toast(`任务已创建（${payload.format.toUpperCase()}），完成后自动加入书架`, 'success');
      show('download');
      refreshTasks();
    } catch (e) { toast(e.message, 'error'); }
  }

  function renderTasks(tasks) {
    const box = $('#taskList');
    if (!tasks.length) {
      box.innerHTML = '<div class="empty" style="padding:32px"><svg><use href="#icon-cloud-down"/></svg><div class="empty-title">暂无任务</div></div>';
      return;
    }
    box.innerHTML = tasks.map(t => {
      const statusMap = {
        pending: ['badge', '排队中'], downloading: ['badge badge-accent', '下载中'],
        completed: ['badge badge-success', '已完成'], failed: ['badge badge-danger', '失败'],
        abandoned: ['badge', '已停止跟踪']
      };
      const [cls, label] = statusMap[t.status] || ['badge', t.status];
      const pct = t.status === 'completed' ? 100 : (t.progress || 0);
      const detail = (t.index || t.total)
        ? `第 ${t.index || 0} / ${t.total || '?'} 章${t.estimated ? ' · 预估' : ''}`
        : esc(t.error_message || '');
      return `<div class="task-row">
        <div class="tk-main">
          <div class="tk-title">${esc(t.book_name)}</div>
          <div class="tk-sub">${esc(t.source_name || '')} ${detail ? '· ' + detail : ''}</div>
        </div>
        <span class="${cls}">${label}</span>
        ${t.status === 'downloading' || t.status === 'pending' ? `<div class="progress"><div class="bar" style="width:${pct}%"></div></div>` : ''}
        <button class="btn btn-ghost btn-icon" data-del="${t.id}" title="删除任务"><svg><use href="#icon-trash"/></svg></button>
      </div>`;
    }).join('');
  }

  async function refreshTasks() {
    try {
      renderTasks(await api('/api/download/tasks') || []);
    } catch {}
  }

  function watchProgress() {
    if (downloadES) return;
    try {
      downloadES = new EventSource('/api/download/progress');
      downloadES.onmessage = ev => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'progress' && msg.tasks) {
            renderTasks(msg.tasks);
            if (!$('#view-download').hidden) return;
          }
        } catch {}
      };
      setInterval(refreshTasks, 10000);
    } catch { downloadES = null; }
  }

  function closeBookMenu() {
    document.querySelectorAll('.menu[data-bookmenu]').forEach(m => m.remove());
  }

  function openBookMenu(card, x, y) {
    closeBookMenu();
    const id = parseInt(card.dataset.book, 10);
    const isRss = card.dataset.kind === 'rss';
    const menu = document.createElement('div');
    menu.className = 'menu';
    menu.dataset.bookmenu = '1';
    menu.style.cssText = `position:fixed;left:${Math.max(8, Math.min(x, innerWidth - 190))}px;top:${Math.max(8, Math.min(y, innerHeight - 310))}px;z-index:150`;
    menu.innerHTML = `
      <button data-mact="open"><svg><use href="#icon-book"/></svg>${isRss ? '打开订阅' : '打开'}</button>
      <button data-mact="props"><svg><use href="#icon-edit"/></svg>属性</button>
      <button data-mact="move"><svg><use href="#icon-folder-plus"/></svg>加入分组</button>
      <button data-mact="select"><svg><use href="#icon-check-square"/></svg>${selectedMode ? '退出多选' : '多选'}</button>
      ${isRss ? '' : '<button data-mact="reparse"><svg><use href="#icon-refresh"/></svg>重新解析</button>'}
      <button data-mact="del" class="menu-danger"><svg><use href="#icon-trash"/></svg>删除</button>`;
    document.body.appendChild(menu);
    setTimeout(() => document.addEventListener('click', closeBookMenu, { once: true }), 0);
    menu.addEventListener('click', async e => {
      const act = e.target.closest('[data-mact]');
      if (!act) return;
      let book = booksCache.find(b => b.id === id);
      if (!book) {
        try { book = await api('/api/books/' + id); } catch {}
      }
      if (!book) { closeBookMenu(); return; }
      closeBookMenu();
      if (act.dataset.mact === 'open') {
        if (book.kind === 'rss') openRssViewer(book);
        else location.href = '/main/b/' + (book ? book.fingerprint : card.dataset.fp);
      } else if (act.dataset.mact === 'props') {
        openBookProps(book);
      } else if (act.dataset.mact === 'move') {
        openGroupPicker([id]);
      } else if (act.dataset.mact === 'select') {
        if (selectedMode) exitSelectMode();
        else enterSelectMode(id);
      } else if (act.dataset.mact === 'reparse') {
        try {
          const r = await api(`/api/books/${id}/reparse`, { method: 'POST' });
          toast(`重新解析完成：${r.sections} 个章节`, 'success');
          loadShelf();
        } catch (err) { toast(err.message, 'error'); }
      } else if (act.dataset.mact === 'del') {
        if (await confirmDialog('删除书籍', `确定删除《${book ? book.title : ''}》？原文件与阅读数据将一并删除。`)) {
          try {
            await api('/api/books/' + id, { method: 'DELETE' });
            toast('已删除', 'success');
            loadShelf({ resetCovers: true });
          } catch (err) { toast(err.message, 'error'); }
        }
      }
    });
  }

  // 分组卡片右键 / 长按菜单
  function openGroupMenu(card, x, y) {
    closeBookMenu();
    const id = parseInt(card.dataset.group, 10);
    const g = groupsCache.find(it => it.id === id) || { id, name: card.dataset.gname || '' };
    const menu = document.createElement('div');
    menu.className = 'menu';
    menu.dataset.bookmenu = '1';
    menu.style.cssText = `position:fixed;left:${Math.max(8, Math.min(x, innerWidth - 190))}px;top:${Math.max(8, Math.min(y, innerHeight - 150))}px;z-index:150`;
    menu.innerHTML = `
      <button data-mact="gopen"><svg><use href="#icon-folder"/></svg>打开分组</button>
      <button data-mact="grename"><svg><use href="#icon-edit"/></svg>重命名分组</button>
      <button data-mact="gdel" class="menu-danger"><svg><use href="#icon-trash"/></svg>删除分组</button>`;
    document.body.appendChild(menu);
    setTimeout(() => document.addEventListener('click', closeBookMenu, { once: true }), 0);
    menu.addEventListener('click', async e => {
      const act = e.target.closest('[data-mact]');
      if (!act) return;
      closeBookMenu();
      if (act.dataset.mact === 'gopen') {
        enterGroup(g.id, g.name);
      } else if (act.dataset.mact === 'grename') {
        openRenameGroupModal(g);
      } else if (act.dataset.mact === 'gdel') {
        if (await confirmDialog('删除分组', `确定删除分组「${g.name}」？组内内容将回到未分组。`)) {
          try {
            await api('/api/groups/' + g.id, { method: 'DELETE' });
            toast('分组已删除', 'success');
            if (currentGroupId === g.id) {
              currentGroupId = null;
              currentGroupName = '';
              $('#btnGroupBack').hidden = true;
              $('#shelfTitle').textContent = '我的书架';
            }
            loadShelf({ resetCovers: true });
          } catch (err) { toast(err.message, 'error'); }
        }
      }
    });
  }

  function openBookProps(book) {
    if (!book) return;
    const isRss = book.kind === 'rss';
    modal({
      title: isRss ? 'RSS 订阅属性' : '书籍属性',
      body: `
        <div class="row gap-4" style="align-items:flex-start">
          <div style="width:110px;flex-shrink:0">
            <div class="book-cover" style="border-radius:var(--r-md);overflow:hidden" id="ppCoverBox">
              ${book.cover_url ? `<img src="${esc(book.cover_url)}">` : '<svg><use href="#icon-book"/></svg>'}
            </div>
            <input type="file" id="ppCover" accept="image/*" hidden>
            <button class="btn btn-sm w-full mt-2" id="ppCoverBtn"><svg><use href="#icon-image"/></svg>更换封面</button>
          </div>
          <div class="flex-1">
            <div class="field"><label>${isRss ? '名称' : '书名'}</label><input class="input" id="ppTitle" value="${esc(book.title)}"></div>
            ${isRss ? `
            <div class="field"><label>同步间隔（小时）</label><input class="input" id="ppInterval" type="number" min="1" step="1" value="${parseInt(book.sync_interval, 10) || 24}"></div>
            <div class="field"><label>订阅地址</label>
              <div class="prop-rss-url"><span class="pru-text" id="ppRssUrl">${esc(book.rss_url || '')}</span>
              <button type="button" id="ppCopyUrl" title="复制"><svg><use href="#icon-copy"/></svg></button></div></div>
            <div class="text-3" style="font-size:var(--fs-xs)">上次同步：${book.last_synced ? fmtDate(book.last_synced) : '从未'}</div>
            ` : `
            <div class="field"><label>作者</label><input class="input" id="ppAuthor" value="${esc(book.author || '')}"></div>
            <div class="field"><label>上传时间</label><input class="input" value="${fmtDate(book.created_at)}" disabled></div>
            <div class="field"><label>格式</label><input class="input" value="${esc((book.format || '').toUpperCase())}${book.unsupported ? '（不受支持）' : ''}" disabled></div>
            `}
          </div>
        </div>`,
      footer: `${isRss
          ? '<button class="btn" data-sync><svg><use href="#icon-refresh"/></svg>立即同步</button>'
          : '<button class="btn" data-reparse>重新解析</button>'}
        <button class="btn" data-close>取消</button><button class="btn btn-primary" data-ok>保存</button>`,
      onOpen(el, close) {
        let coverFile = null;
        const fileInput = el.querySelector('#ppCover');
        el.querySelector('#ppCoverBtn').addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', () => {
          coverFile = fileInput.files[0] || null;
          if (coverFile) {
            el.querySelector('#ppCoverBox').innerHTML = `<img src="${URL.createObjectURL(coverFile)}">`;
          }
        });
        if (isRss) {
          el.querySelector('#ppCopyUrl').addEventListener('click', () => copyText(el.querySelector('#ppRssUrl').textContent));
          el.querySelector('[data-sync]').addEventListener('click', async e => {
            const btn = e.currentTarget;
            btn.disabled = true;
            try {
              const r = await api(`/api/rss/${book.id}/sync`, { method: 'POST' });
              toast(`已同步，新增 ${r.added} 篇`, 'success');
              close();
              loadShelf();
            } catch (err) { toast(err.message, 'error'); btn.disabled = false; }
          });
        } else {
          el.querySelector('[data-reparse]').addEventListener('click', async () => {
            try {
              const r = await api(`/api/books/${book.id}/reparse`, { method: 'POST' });
              toast(`重新解析完成：${r.sections} 个章节`, 'success');
              close();
              loadShelf();
            } catch (err) { toast(err.message, 'error'); }
          });
        }
        el.querySelector('[data-ok]').addEventListener('click', async () => {
          try {
            if (isRss) {
              const interval = parseInt(el.querySelector('#ppInterval').value, 10);
              if (!(interval >= 1)) return toast('同步间隔至少为 1 小时', 'error');
              await api('/api/rss/' + book.id, {
                method: 'PUT',
                json: { name: el.querySelector('#ppTitle').value.trim(), interval }
              });
              if (coverFile) {
                const fd = new FormData();
                fd.append('cover', coverFile);
                await api('/api/books/' + book.id, { method: 'PUT', form: fd });
              }
            } else {
              const fd = new FormData();
              fd.append('title', el.querySelector('#ppTitle').value.trim());
              fd.append('author', el.querySelector('#ppAuthor').value.trim());
              if (coverFile) fd.append('cover', coverFile);
              await api('/api/books/' + book.id, { method: 'PUT', form: fd });
            }
            toast('已保存', 'success');
            close();
            loadShelf();
          } catch (err) { toast(err.message, 'error'); }
        });
      }
    });
  }

  function openNewGroupModal() {
    modal({
      title: '新增分组',
      body: `<div class="field"><label>分组名称</label><input id="ngName" class="input" placeholder="例如：小说 / 技术书籍"></div>`,
      footer: `<button class="btn" data-close>取消</button><button class="btn btn-primary" data-ok>创建</button>`,
      onOpen(el, close) {
        const input = el.querySelector('#ngName');
        setTimeout(() => input.focus(), 50);
        el.querySelector('[data-ok]').addEventListener('click', async () => {
          const name = input.value.trim();
          if (!name) return toast('请输入分组名称', 'error');
          try {
            await api('/api/groups', { method: 'POST', json: { name } });
            toast('分组已创建', 'success');
            close();
            loadShelf();
          } catch (e) { toast(e.message, 'error'); }
        });
        input.addEventListener('keydown', e => {
          if (e.key === 'Enter') el.querySelector('[data-ok]').click();
        });
      }
    });
  }

  function openRenameGroupModal(g) {
    modal({
      title: '重命名分组',
      body: `<div class="field"><label>分组名称</label><input id="rgName" class="input" value="${esc(g.name || '')}"></div>`,
      footer: `<button class="btn" data-close>取消</button><button class="btn btn-primary" data-ok>保存</button>`,
      onOpen(el, close) {
        const input = el.querySelector('#rgName');
        setTimeout(() => { input.focus(); input.select(); }, 50);
        el.querySelector('[data-ok]').addEventListener('click', async () => {
          const name = input.value.trim();
          if (!name) return toast('请输入分组名称', 'error');
          try {
            await api('/api/groups/' + g.id, { method: 'PUT', json: { name } });
            toast('已保存', 'success');
            close();
            if (currentGroupId === g.id) $('#shelfTitle').textContent = name;
            loadShelf();
          } catch (e) { toast(e.message, 'error'); }
        });
      }
    });
  }

  // 分组选择弹窗：单书加入分组 / 批量移动共用，顶部含"未分组"选项
  function openGroupPicker(ids) {
    modal({
      title: ids.length > 1 ? `移动 ${ids.length} 项至分组` : '加入分组',
      body: `<div id="gpList" style="font-size:var(--fs-sm)">加载中…</div>`,
      footer: `<button class="btn" data-close>取消</button><button class="btn btn-primary" data-ok>确定</button>`,
      onOpen(el, close) {
        api('/api/groups').then(list => {
          const groups = list || [];
          el.querySelector('#gpList').innerHTML = `
            <label class="gp-row"><input type="radio" name="gpGroup" value="" checked>
              <span class="gp-name">不分组</span></label>
            ${groups.map(g => `
            <label class="gp-row"><input type="radio" name="gpGroup" value="${g.id}">
              <span class="gp-name">${esc(g.name)}</span></label>`).join('')}`;
        }).catch(e => {
          el.querySelector('#gpList').innerHTML = `<div class="text-3">${esc(e.message)}</div>`;
        });
        el.querySelector('[data-ok]').addEventListener('click', async () => {
          const picked = el.querySelector('input[name="gpGroup"]:checked');
          if (!picked) return toast('请选择分组', 'error');
          const gid = picked.value === '' ? null : parseInt(picked.value, 10);
          try {
            await api('/api/books/batch-move', { method: 'POST', json: { ids, group_id: gid } });
            toast(gid === null ? '已移出分组' : '已移动至分组', 'success');
            close();
            exitSelectMode();
            loadShelf({ resetCovers: true });
          } catch (e) { toast(e.message, 'error'); }
        });
      }
    });
  }

  function enterSelectMode(firstId) {
    selectedMode = true;
    selectedIds = new Set(firstId != null ? [firstId] : []);
    renderShelf(booksCache);
    renderSelectBar();
  }

  function exitSelectMode() {
    if (!selectedMode) return;
    selectedMode = false;
    selectedIds = new Set();
    const bar = document.getElementById('selectBar');
    if (bar) bar.remove();
    if ($('#view-shelf').hidden) return;
    renderShelf(booksCache);
  }

  function toggleSelect(id) {
    if (selectedIds.has(id)) selectedIds.delete(id);
    else selectedIds.add(id);
    const card = document.querySelector(`.book-card[data-book="${id}"]`);
    if (card) card.classList.toggle('selected', selectedIds.has(id));
    renderSelectBar();
  }

  // 底部浮动批量操作条
  function renderSelectBar() {
    let bar = document.getElementById('selectBar');
    if (!selectedMode) {
      if (bar) bar.remove();
      return;
    }
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'selectBar';
      bar.className = 'select-bar';
      bar.innerHTML = `
        <span class="sb-count">已选 0 项</span>
        <button class="btn" id="sbMove"><svg><use href="#icon-folder-move"/></svg>移动至分组</button>
        <button class="btn btn-danger btn-solid" id="sbDelete"><svg><use href="#icon-trash"/></svg>删除</button>
        <button class="btn btn-ghost" id="sbCancel">取消</button>`;
      document.body.appendChild(bar);
      bar.querySelector('#sbCancel').addEventListener('click', exitSelectMode);
      bar.querySelector('#sbDelete').addEventListener('click', batchDeleteSelected);
      bar.querySelector('#sbMove').addEventListener('click', () => {
        if (selectedIds.size) openGroupPicker([...selectedIds]);
      });
    }
    const n = selectedIds.size;
    bar.querySelector('.sb-count').textContent = `已选 ${n} 项`;
    bar.querySelector('#sbDelete').disabled = n === 0;
    bar.querySelector('#sbMove').disabled = n === 0;
  }

  async function batchDeleteSelected() {
    const n = selectedIds.size;
    if (!n) return;
    if (!(await confirmDialog('批量删除', `确定删除选中的 ${n} 项？RSS 订阅数据将一并删除`))) return;
    try {
      await api('/api/books/batch-delete', { method: 'POST', json: { ids: [...selectedIds] } });
      toast(`已删除 ${n} 项`, 'success');
      exitSelectMode();
      loadShelf({ resetCovers: true });
    } catch (e) { toast(e.message, 'error'); }
  }

  function openRssModal() {
    modal({
      title: '添加 RSS 订阅',
      body: `
        <div class="field"><label>RSS 链接</label><input id="rssUrl" class="input" placeholder="https://example.com/feed.xml"></div>
        <div class="field"><label>名称（可选）</label><input id="rssName" class="input" placeholder="留空自动获取"></div>
        <div class="field"><label>同步间隔（小时）</label><input id="rssInterval" class="input" type="number" min="1" step="1" value="24"></div>`,
      footer: `<button class="btn" data-close>取消</button><button class="btn btn-primary" data-ok>添加</button>`,
      onOpen(el, close) {
        setTimeout(() => el.querySelector('#rssUrl').focus(), 50);
        el.querySelector('[data-ok]').addEventListener('click', async () => {
          const url = el.querySelector('#rssUrl').value.trim();
          if (!url) return toast('请输入 RSS 链接', 'error');
          const payload = { url };
          const name = el.querySelector('#rssName').value.trim();
          if (name) payload.name = name;
          const interval = parseInt(el.querySelector('#rssInterval').value, 10);
          if (interval >= 1) payload.interval = interval;
          const btn = el.querySelector('[data-ok]');
          btn.disabled = true;
          try {
            const r = await api('/api/rss', { method: 'POST', json: payload });
            toast(`订阅成功：${r.title || name || url}`, 'success');
            close();
            loadShelf();
          } catch (e) { toast(e.message, 'error'); btn.disabled = false; }
        });
      }
    });
  }

  function openRssViewer(book) {
    if (window.MRRssViewer && typeof window.MRRssViewer.open === 'function') {
      window.MRRssViewer.open(book);
    } else {
      toast('RSS 组件加载中', 'info');
    }
  }

  function copyText(text) {
    if (!text) return;
    const done = () => toast('已复制', 'success');
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
    } else {
      fallbackCopy(text, done);
    }
  }

  function fallbackCopy(text, done) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch { toast('复制失败', 'error'); }
    ta.remove();
  }

  // 移动端长按：按住 500ms 且位移小于 10px 触发菜单，与桌面 contextmenu 事件并存
  function setupLongPress() {
    let timer = null, sx = 0, sy = 0, target = null, fired = false;
    const shelf = $('#shelf');
    const cancel = () => {
      if (timer) { clearTimeout(timer); timer = null; }
      target = null;
    };
    shelf.addEventListener('touchstart', e => {
      if (e.touches.length !== 1) { cancel(); return; }
      const t = e.touches[0];
      target = t.target.closest('[data-book],[data-group]');
      if (!target) { cancel(); return; }
      sx = t.clientX;
      sy = t.clientY;
      fired = false;
      timer = setTimeout(() => {
        timer = null;
        fired = true;
        suppressClick = true;
        lastLongPress = Date.now();
        if (target.dataset.group) openGroupMenu(target, sx, sy);
        else openBookMenu(target, sx, sy);
      }, 500);
    }, { passive: true });
    shelf.addEventListener('touchmove', e => {
      if (!timer) return;
      const t = e.touches[0];
      if (Math.abs(t.clientX - sx) > 10 || Math.abs(t.clientY - sy) > 10) cancel();
    }, { passive: true });
    shelf.addEventListener('touchend', e => {
      const wasFired = fired;
      cancel();
      fired = false;
      if (wasFired) e.preventDefault();
    });
    shelf.addEventListener('touchcancel', () => {
      fired = false;
      cancel();
    });
    shelf.addEventListener('click', e => {
      if (suppressClick) {
        suppressClick = false;
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    }, true);
  }

  function openUserMenu(anchor) {
    const menu = document.createElement('div');
    menu.className = 'menu';
    menu.style.cssText = 'top:46px;right:0;position:fixed';
    menu.innerHTML = `
      <button data-act="password"><svg><use href="#icon-key"/></svg>修改密码</button>
      <button data-act="username"><svg><use href="#icon-edit"/></svg>修改用户名</button>
      <hr class="divider" style="margin:4px 0">
      <button data-act="logout" class="menu-danger"><svg><use href="#icon-logout"/></svg>退出登录</button>`;
    document.body.appendChild(menu);
    const close = () => menu.remove();
    setTimeout(() => document.addEventListener('click', close, { once: true }), 0);
    menu.addEventListener('click', async e => {
      const act = e.target.closest('[data-act]');
      if (!act) return;
      close();
      if (act.dataset.act === 'logout') {
        await api('/api/auth/logout', { method: 'POST' }).catch(() => {});
        location.href = '/login';
      } else if (act.dataset.act === 'password') {
        promptChange('修改密码', 'new_password', '新密码');
      } else if (act.dataset.act === 'username') {
        promptChange('修改用户名', 'new_username', '新用户名');
      }
    });
  }

  function promptChange(title, field, label) {
    modal({
      title,
      body: `<div class="field"><label>${label}</label><input id="pcVal" class="input" type="${field === 'new_password' ? 'password' : 'text'}"></div>`,
      footer: `<button class="btn" data-close>取消</button><button class="btn btn-primary" data-ok>保存</button>`,
      onOpen(el, close) {
        el.querySelector('[data-ok]').addEventListener('click', async () => {
          try {
            await api('/api/auth/change-' + (field === 'new_password' ? 'password' : 'username'), {
              method: 'POST', json: { [field]: el.querySelector('#pcVal').value }
            });
            toast('已保存，请重新登录', 'success');
            close();
            setTimeout(() => location.href = '/login', 900);
          } catch (e) { toast(e.message, 'error'); }
        });
      }
    });
  }

  function initThemeBtn() {
    const btn = $('#btnTheme');
    const icon = () => btn.querySelector('use');
    const refresh = () => icon().setAttribute('href', window.MRTheme.resolve() === 'dark' ? '#icon-sun' : '#icon-moon');
    refresh();
    btn.addEventListener('click', () => { window.MRTheme.toggle(); refresh(); });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initThemeBtn();
    loadShelf();
    loadAnnouncements();
    watchProgress();
    api('/api/auth/check').then(me => {
      // 后台入口默认渲染可见；此处仅按身份双向修正：
      // 管理员保持显示，非管理员隐藏；检查失败时保持默认（服务端 /admin 自有权限保护）
      const admin = !!(me && me.role === 'admin');
      isAdmin = admin;
      document.querySelectorAll('.nav-admin').forEach(a => { a.hidden = !admin; });
    }).catch(() => {});

    // 搜索结果翻页：页码输入框回车/失焦跳转
    const jumpTo = input => {
      const v = parseInt(input.value, 10);
      if (!isNaN(v)) { searchState.page = v; renderSearchPage(); }
    };
    document.addEventListener('keydown', e => {
      if (e.key === 'Enter' && e.target.id === 'pagerJump') { e.preventDefault(); jumpTo(e.target); }
    });
    document.addEventListener('change', e => {
      if (e.target.id === 'pagerJump') jumpTo(e.target);
    });

    document.addEventListener('click', async e => {
      const ax = e.target.closest('#annOpen');
      if (ax) { openAnnModal(annListCache || []); return; }
      const nav = e.target.closest('[data-nav]');
      if (nav) { e.preventDefault(); show(nav.dataset.nav); return; }
      const dl = e.target.closest('[data-dl]');
      if (dl) { startDownload(JSON.parse(dl.dataset.dl)); return; }
      const dlo = e.target.closest('[data-dlother]');
      if (dlo) {
        e.stopPropagation();
        const menu = dlo.parentElement.querySelector('.dl-menu');
        if (menu) menu.hidden = !menu.hidden;
        return;
      }
      const dli = e.target.closest('.dl-menu button');
      if (dli) { const m = dli.closest('.dl-menu'); if (m) m.hidden = true; return; }
      const pb = e.target.closest('.pager-btn[data-page]');
      if (pb && !pb.disabled) {
        searchState.page = parseInt(pb.dataset.page, 10);
        renderSearchPage();
        const box = $('#searchResults');
        if (box) box.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      const pj = e.target.closest('#pagerJump');
      if (pj) { e.stopPropagation(); return; }
      if (!e.target.closest('.dl-menu')) {
        document.querySelectorAll('.dl-menu').forEach(m => { m.hidden = true; });
      }
      const del = e.target.closest('[data-del]');
      if (del) {
        if (await confirmDialog('删除任务', '确定删除该任务记录？')) {
          try {
            await api('/api/download/tasks/' + del.dataset.del, { method: 'DELETE' });
            refreshTasks();
          } catch (err) { toast(err.message, 'error'); }
        }
        return;
      }
      const au = e.target.closest('[data-admin-user]');
      if (au) { location.href = '/admin'; return; }
      const gc = e.target.closest('[data-group]');
      if (gc) {
        const g = groupsCache.find(it => it.id === parseInt(gc.dataset.group, 10));
        if (g) enterGroup(g.id, g.name);
        return;
      }
      const card = e.target.closest('[data-book]');
      if (card) {
        const id = parseInt(card.dataset.book, 10);
        if (selectedMode) { toggleSelect(id); return; }
        const book = booksCache.find(b => b.id === id);
        if (book && book.kind === 'rss') { openRssViewer(book); return; }
        location.href = '/main/b/' + card.dataset.fp;
      }
    });

    // 添加按钮下拉面板：点击外部自动收起
    $('#btnAdd').addEventListener('click', e => {
      e.stopPropagation();
      const panel = $('#addPanel');
      panel.hidden = !panel.hidden;
    });
    $('#addPanel').addEventListener('click', e => {
      const item = e.target.closest('[data-add]');
      if (!item) return;
      $('#addPanel').hidden = true;
      if (item.dataset.add === 'upload') openUpload();
      else if (item.dataset.add === 'group') openNewGroupModal();
      else if (item.dataset.add === 'rss') openRssModal();
    });
    document.addEventListener('click', e => {
      if (!e.target.closest('#addWrap')) $('#addPanel').hidden = true;
    });

    $('#btnUploadEmpty').addEventListener('click', openUpload);

    // 书架拖拽多文件上传：拖入即开始（默认导入选项）
    {
      const zone = $('#view-shelf');
      let dragDepth = 0;
      zone.addEventListener('dragenter', e => {
        if (![...e.dataTransfer.types].includes('Files')) return;
        e.preventDefault();
        dragDepth++;
        zone.classList.add('drag-over');
      });
      zone.addEventListener('dragover', e => { e.preventDefault(); });
      zone.addEventListener('dragleave', () => {
        dragDepth = Math.max(0, dragDepth - 1);
        if (!dragDepth) zone.classList.remove('drag-over');
      });
      zone.addEventListener('drop', e => {
        e.preventDefault();
        dragDepth = 0;
        zone.classList.remove('drag-over');
        const files = [...(e.dataTransfer.files || [])].filter(f => UPLOAD_ACCEPT.test(f.name));
        if (!files.length) return;
        openDropUpload(files);
      });
    }

    $('#btnGroupBack').addEventListener('click', exitGroup);
    $('#btnServerCfg').addEventListener('click', openServerCfg);
    $('#btnUser').addEventListener('click', e => { e.stopPropagation(); openUserMenu(e.currentTarget); });
    $('#navUser').addEventListener('click', e => { e.preventDefault(); openUserMenu(e.currentTarget); });
    $('#btnViewToggle').addEventListener('click', () => {
      shelfView = shelfView === 'grid' ? 'list' : 'grid';
      localStorage.setItem('mr-shelf-view', shelfView);
      $('#btnViewToggle').querySelector('use').setAttribute('href', shelfView === 'grid' ? '#icon-rows' : '#icon-grid');
      renderShelf(booksCache);
    });
    $('#btnViewToggle').querySelector('use').setAttribute('href', shelfView === 'grid' ? '#icon-rows' : '#icon-grid');

    // 顶部搜索框（书架层）
    const searchInput = $('#shelfSearch');
    const searchWrap = $('#shelfSearchWrap');
    searchInput.addEventListener('input', () => {
      const kw = searchInput.value.trim();
      searchWrap.classList.toggle('has-value', kw.length > 0);
      doShelfSearch(kw);
    });
    $('#shelfSearchClear').addEventListener('click', () => {
      searchInput.value = '';
      searchWrap.classList.remove('has-value');
      doShelfSearch('');
      searchInput.focus();
    });
    $('#searchForm').addEventListener('submit', e => {
      e.preventDefault();
      const kw = $('#searchKw').value.trim();
      if (kw) doSearch(kw);
    });

    setupLongPress();

    document.addEventListener('contextmenu', e => {
      // 移动端长按刚触发过自定义菜单时，忽略浏览器原生菜单避免双弹
      if (Date.now() - lastLongPress < 700) { e.preventDefault(); return; }
      const gcard = e.target.closest('[data-group]');
      if (gcard) {
        e.preventDefault();
        openGroupMenu(gcard, e.clientX, e.clientY);
        return;
      }
      const card = e.target.closest('[data-book]');
      if (!card) return;
      e.preventDefault();
      openBookMenu(card, e.clientX, e.clientY);
    });

    const hash = location.hash.replace('#', '');
    if (hash === 'download') show('download');
  });
})();
