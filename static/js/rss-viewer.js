/*
 * 极读 Miniread · RSS 阅读视图（V2.1）
 * ------------------------------------------------------------
 * 普通 script（非 ES 模块），脚本加载即定义 window.MRRssViewer，
 * 不依赖 DOMContentLoaded，可被 main.modern.js / MRLoad.script 按需引入。
 *
 * 对外接口：
 *   window.MRRssViewer.open(book)  book = { id, title, kind }
 *
 * 数据来源：GET /api/rss/<bookId>/items?page=N&size=20
 *   通过 window.MR.api 发起（返回解析后的 data 字段；不可用时退化为裸 fetch）。
 *
 * 兼容目标：Chrome 91（无 import/export，无 top-level await）。
 */
(function () {
  'use strict';

  var PAGE_SIZE = 20;        // 每页条数，与后端约定一致
  var SUMMARY_LEN = 200;     // 摘要截断长度（字符）
  var Z_INDEX = 95;          // 高于书架内容，低于模态（.modal-backdrop 为 100）
  var STYLE_ID = 'mr-rss-viewer-styles';
  var EXPAND_MS = 200;       // 展开动画时长（毫秒），满足 <=200ms 要求

  /* ---------------- 手绘线条风 SVG 图标（无表情符号） ---------------- */

  // 返回左箭头
  var ICON_BACK =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M15 5l-7 7 7 7"/></svg>';

  // 外部链接
  var ICON_LINK =
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M14 4h6v6"/><path d="M20 4L11 13"/>' +
    '<path d="M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6"/></svg>';

  // 空态：RSS 波纹
  var ICON_EMPTY =
    '<svg viewBox="0 0 48 48" width="46" height="46" fill="none" stroke="currentColor" ' +
    'stroke-width="2.5" stroke-linecap="round" aria-hidden="true">' +
    '<circle cx="12" cy="36" r="4" fill="currentColor" stroke="none"/>' +
    '<path d="M9 21c10.5 0 19 8.5 19 19"/><path d="M9 10c16.5 0 30 13.5 30 30"/></svg>';

  // 错误态：圆圈叹号
  var ICON_ERROR =
    '<svg viewBox="0 0 48 48" width="44" height="44" fill="none" stroke="currentColor" ' +
    'stroke-width="2.5" stroke-linecap="round" aria-hidden="true">' +
    '<circle cx="24" cy="24" r="16"/><path d="M24 16v10"/><path d="M24 31.5h.01"/></svg>';

  /* ---------------- 样式（一次性注入，全部走主题 CSS 变量） ---------------- */

  var CSS_TEXT = [
    '.mr-rss{position:fixed;inset:0;z-index:' + Z_INDEX + ';display:flex;flex-direction:column;',
    'background:var(--surface);color:var(--text);',
    'transition:opacity 180ms var(--ease-out),transform 180ms var(--ease-out)}',
    '.mr-rss-enter{opacity:0;transform:translateY(14px)}',
    '.mr-rss-closing{opacity:0;transform:translateY(10px);pointer-events:none}',

    /* 顶部工具栏 */
    '.mr-rss-bar{flex:none;display:flex;align-items:center;gap:12px;height:56px;padding:0 16px;',
    'border-bottom:1px solid var(--border);background:var(--surface)}',
    '.mr-rss-back{flex:none;display:inline-flex;align-items:center;justify-content:center;',
    'width:34px;height:34px;border:1px solid var(--border);border-radius:var(--r-full);',
    'background:var(--surface);color:var(--text-2);cursor:pointer;',
    'transition:color var(--t-fast) var(--ease-out),border-color var(--t-fast) var(--ease-out),',
    'background-color var(--t-fast) var(--ease-out)}',
    '.mr-rss-back:hover{color:var(--accent);border-color:var(--accent);background:var(--accent-soft)}',
    '.mr-rss-title{flex:1;min-width:0;font-family:var(--font-serif);font-size:var(--fs-lg);',
    'font-weight:var(--fw-semibold);line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '.mr-rss-badge{flex:none;padding:3px 10px;border-radius:var(--r-full);background:var(--bg-soft);',
    'color:var(--text-2);font-size:var(--fs-xs);font-weight:var(--fw-medium)}',

    /* 滚动区与内容列（720px 居中，移动端自适应收窄） */
    '.mr-rss-scroll{flex:1;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain}',
    '.mr-rss-col{max-width:720px;margin:0 auto;padding:20px 16px 72px;min-width:0}',

    /* 日期分隔条：小字加粗、上下留白、右侧细线 */
    '.mr-rss-day{display:flex;align-items:center;gap:12px;margin:26px 0 12px;',
    'font-size:var(--fs-xs);font-weight:var(--fw-semibold);letter-spacing:.04em;color:var(--text-3)}',
    '.mr-rss-day::after{content:"";flex:1;height:1px;background:var(--hairline)}',

    /* 文章卡片 */
    '.mr-rss-list{display:grid;gap:10px}',
    '.mr-rss-item{border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface);',
    'box-shadow:var(--shadow-1);padding:14px 16px;cursor:pointer;',
    'transition:background-color 150ms ease,border-color 150ms ease}',
    '.mr-rss-item:hover{background:var(--surface-2);border-color:var(--border-strong)}',
    '.mr-rss-item-title{margin:0;font-size:var(--fs-md);font-weight:var(--fw-semibold);',
    'line-height:1.55;color:var(--text);transition:color 150ms ease;overflow-wrap:anywhere}',
    '.mr-rss-item:hover .mr-rss-item-title{color:var(--accent)}',
    '.mr-rss-item-title:focus-visible{outline:none;box-shadow:var(--ring);border-radius:var(--r-sm)}',
    '.mr-rss-item-meta{margin-top:4px;font-size:var(--fs-xs);color:var(--text-3)}',
    '.mr-rss-item-summary{margin:8px 0 0;font-size:var(--fs-sm);line-height:1.7;color:var(--text-2)}',

    /* 展开正文：max-height 过渡（Chrome 91 稳妥方案），装饰全部放在内层避免占位 */
    '.mr-rss-item-body{max-height:0;overflow:hidden;transition:max-height ' + EXPAND_MS + 'ms var(--ease-out)}',
    '.mr-rss-article{padding-top:12px;border-top:1px solid var(--hairline);',
    'font-size:var(--fs-md);line-height:1.85;color:var(--text);overflow-wrap:break-word}',
    '.mr-rss-article p{margin:0 0 12px}',
    '.mr-rss-article img{max-width:100%;height:auto;border-radius:var(--r-sm)}',
    '.mr-rss-article a{color:var(--accent)}',
    '.mr-rss-article a:hover{color:var(--accent-strong)}',
    '.mr-rss-article [style]{color:var(--text) !important;background-color:transparent !important;background-image:none !important}',
    /* feed 文章常带内联固定宽度（style="width:800px" 等），手机上会撑破内容列 —— 一律约束到容器宽 */
    '.mr-rss-article img,.mr-rss-article video,.mr-rss-article iframe{max-width:100% !important;',
    'width:auto !important;height:auto !important}',
    '.mr-rss-article table{display:block;width:auto !important;max-width:100% !important;overflow-x:auto}',
    '.mr-rss-article pre{max-width:100%}',
    '.mr-rss-article a[href]{color:var(--accent) !important}',
    '.mr-rss-article a[href]:hover{color:var(--accent-strong) !important}',
    '.mr-rss-article h1{font-size:var(--fs-xl);margin:18px 0 10px}',
    '.mr-rss-article h2{font-size:var(--fs-lg);margin:16px 0 8px}',
    '.mr-rss-article h3,.mr-rss-article h4{font-size:var(--fs-md);margin:14px 0 8px}',
    '.mr-rss-article pre{overflow:auto;background:var(--bg-soft);border:1px solid var(--border);',
    'border-radius:var(--r-sm);padding:12px;font-size:var(--fs-sm)}',
    '.mr-rss-article code{font-family:var(--font-mono);font-size:var(--fs-sm)}',
    '.mr-rss-article blockquote{margin:0 0 12px;padding:2px 0 2px 14px;',
    'border-left:3px solid var(--border-strong);color:var(--text-2)}',
    '.mr-rss-article table{border-collapse:collapse;max-width:100%}',
    '.mr-rss-article th,.mr-rss-article td{border:1px solid var(--border);padding:4px 8px;font-size:var(--fs-sm)}',
    '.mr-rss-article hr{border:none;border-top:1px solid var(--hairline);margin:16px 0}',
    '.mr-rss-source{display:inline-flex;align-items:center;gap:6px;margin-top:2px;',
    'font-size:var(--fs-sm);color:var(--accent);text-decoration:none}',
    '.mr-rss-source:hover{color:var(--accent-strong)}',
    '.mr-rss-source svg{flex:none}',

    /* 底部状态区：加载三点 / 错误重试 / 空态 / 全部加载完成 */
    '.mr-rss-status{padding:28px 0 8px;text-align:center;font-size:var(--fs-sm);color:var(--text-2)}',
    '.mr-rss-notice{display:flex;flex-direction:column;align-items:center;gap:10px;padding:8px 0;color:var(--text-3)}',
    '.mr-rss-notice-title{font-size:var(--fs-md);font-weight:var(--fw-medium);color:var(--text-2)}',
    '.mr-rss-notice-sub{font-size:var(--fs-xs);color:var(--text-3)}',
    '.mr-rss-btn{appearance:none;border:1px solid var(--border-strong);background:var(--surface);',
    'color:var(--text);padding:6px 22px;border-radius:var(--r-full);font-size:var(--fs-sm);',
    'font-family:inherit;cursor:pointer;transition:color var(--t-fast) var(--ease-out),',
    'border-color var(--t-fast) var(--ease-out),background-color var(--t-fast) var(--ease-out)}',
    '.mr-rss-btn:hover{color:var(--accent);border-color:var(--accent);background:var(--accent-soft)}',
    '.mr-rss-dots{display:inline-flex;gap:6px;vertical-align:middle}',
    '.mr-rss-dots i{width:6px;height:6px;border-radius:50%;background:var(--text-3);',
    'animation:mrRssDot 1.1s infinite ease-in-out}',
    '.mr-rss-dots i:nth-child(2){animation-delay:.15s}',
    '.mr-rss-dots i:nth-child(3){animation-delay:.3s}',
    '@keyframes mrRssDot{0%,60%,100%{opacity:.25;transform:translateY(0)}30%{opacity:1;transform:translateY(-4px)}}',
    '.mr-rss-sentinel{height:1px}',

    /* 移动端自适应 */
    '@media (max-width:640px){',
    '.mr-rss-col{padding:16px 12px 56px}',
    '.mr-rss-bar{height:52px;padding:0 10px;gap:8px}',
    '.mr-rss-title{font-size:var(--fs-md)}',
    '.mr-rss-day{margin:20px 0 10px}',
    '.mr-rss-item{padding:12px 14px}',
    '.mr-rss-article{font-size:var(--fs-sm);line-height:1.75}}'
  ].join('\n');

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var tag = document.createElement('style');
    tag.id = STYLE_ID;
    tag.textContent = CSS_TEXT;
    document.head.appendChild(tag);
  }

  /* ---------------- 小工具 ---------------- */

  function el(tag, cls) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    return n;
  }

  // 去标签取纯文本（正则去标签 + textarea 实体解码，不触发图片加载）
  function stripHtml(html) {
    if (!html) return '';
    var text = String(html)
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<[^>]*>/g, ' ');
    var box = document.createElement('textarea');
    box.innerHTML = text;
    return String(box.value).replace(/\s+/g, ' ').trim();
  }

  function summaryOf(content) {
    var text = stripHtml(content);
    if (!text) return '（无摘要）';
    return text.length > SUMMARY_LEN ? text.slice(0, SUMMARY_LEN) + '…' : text;
  }

  function dayKey(d) {
    return d.getFullYear() + '-' + d.getMonth() + '-' + d.getDate();
  }

  // 友好日期：今天 / 昨天 / M月D日 / 跨年 YYYY年M月D日（zh-CN）
  function dayLabel(d, now) {
    var k = dayKey(d);
    if (k === dayKey(now)) return '今天';
    if (k === dayKey(new Date(now.getTime() - 86400000))) return '昨天';
    var md = d.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
    return d.getFullYear() === now.getFullYear() ? md : d.getFullYear() + '年' + md;
  }

  function timeLabel(d) {
    var p = function (x) { return String(x).padStart(2, '0'); };
    return p(d.getHours()) + ':' + p(d.getMinutes());
  }

  // 数据请求：优先 MR.api（返回 data 字段），缺失时退化为裸 fetch
  function request(path) {
    if (window.MR && typeof window.MR.api === 'function') return window.MR.api(path);
    return fetch(path).then(function (r) { return r.json(); }).then(function (body) {
      if (!body || (body.code && body.code >= 400)) {
        throw new Error((body && body.message) || '请求失败');
      }
      return body ? body.data : null;
    });
  }

  /* ---------------- 卡片展开 / 收起（max-height 精确值动画） ---------------- */

  function toggleItem(item) {
    var body = item.querySelector('.mr-rss-item-body');
    if (!body) return;
    if (item.classList.contains('open')) {
      // 收起：先把 max-height 从 none 拉回具体像素，再过渡到 0
      body.style.maxHeight = body.scrollHeight + 'px';
      void body.offsetHeight; // 强制回流，保证过渡生效
      item.classList.remove('open');
      body.style.maxHeight = '0px';
      return;
    }
    // 展开：过渡到内容实际高度，结束后放开为 none 以适应图片加载后的高度变化
    item.classList.add('open');
    body.style.maxHeight = body.scrollHeight + 'px';
    var onEnd = function (e) {
      if (e.target !== body || e.propertyName !== 'max-height') return;
      body.removeEventListener('transitionend', onEnd);
      body.style.maxHeight = 'none';
    };
    body.addEventListener('transitionend', onEnd);
  }

  /* ---------------- 列表构建 ---------------- */

  function buildDayDivider(d, now) {
    var div = el('div', 'mr-rss-day');
    div.setAttribute('aria-hidden', 'false');
    div.textContent = dayLabel(d, now);
    return div;
  }

  function buildSourceLink(link) {
    var a = el('a', 'mr-rss-source');
    a.href = link;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.innerHTML = ICON_LINK;
    a.appendChild(document.createTextNode('查看原文'));
    return a;
  }

  function buildCard(it, d) {
    var item = el('article', 'mr-rss-item');

    var title = el('h3', 'mr-rss-item-title');
    title.tabIndex = 0;
    title.textContent = (it && it.title) || '（无标题）';

    var meta = el('div', 'mr-rss-item-meta');
    meta.textContent = d ? timeLabel(d) : '';

    var summary = el('p', 'mr-rss-item-summary');
    summary.textContent = summaryOf(it && it.content);

    var body = el('div', 'mr-rss-item-body');
    var article = el('div', 'mr-rss-article');
    // 服务端已净化的 HTML，直接渲染
    article.innerHTML = (it && it.content) || '';
    if (it && it.link) article.appendChild(buildSourceLink(it.link));
    body.appendChild(article);

    item.appendChild(title);
    item.appendChild(meta);
    item.appendChild(summary);
    item.appendChild(body);
    return item;
  }

  // 批量插入一页数据，按相邻日期变化插入分隔条（DocumentFragment 一次入库）
  function appendItems(state, items) {
    var frag = document.createDocumentFragment();
    var now = new Date();
    for (var i = 0; i < items.length; i++) {
      var it = items[i] || {};
      var ts = Number(it.published);
      var d = Number.isFinite(ts) && ts > 0 ? new Date(ts * 1000) : null;
      var key = d ? dayKey(d) : '?';
      if (key !== state.lastDayKey) {
        state.lastDayKey = key;
        if (d) frag.appendChild(buildDayDivider(d, now));
      }
      frag.appendChild(buildCard(it, d));
      state.loadedCount += 1;
    }
    state.list.appendChild(frag);
  }

  /* ---------------- 底部状态区 ---------------- */

  function setStatus(state, kind, msg) {
    var box = state.status;
    if (kind === 'hidden') {
      box.hidden = true;
      box.innerHTML = '';
      return;
    }
    box.hidden = false;
    if (kind === 'loading') {
      box.innerHTML =
        '<span class="mr-rss-dots" role="status" aria-label="正在加载"><i></i><i></i><i></i></span>';
    } else if (kind === 'error') {
      box.innerHTML =
        '<div class="mr-rss-notice">' + ICON_ERROR +
        '<div class="mr-rss-notice-title">加载失败</div>' +
        '<div class="mr-rss-notice-sub"></div>' +
        '<button type="button" class="mr-rss-btn">重试</button></div>';
      box.querySelector('.mr-rss-notice-sub').textContent = msg || '网络似乎不太顺畅';
      box.querySelector('.mr-rss-btn').addEventListener('click', function () {
        loadPage(state);
      });
    } else if (kind === 'empty') {
      box.innerHTML =
        '<div class="mr-rss-notice">' + ICON_EMPTY +
        '<div class="mr-rss-notice-title">暂无文章，试试手动同步</div></div>';
    } else if (kind === 'done') {
      var n = state.total > 0 ? state.total : state.loadedCount;
      box.textContent = '已加载全部 ' + n + ' 篇';
    }
  }

  function updateBadge(state) {
    var n = state.total > 0 ? state.total : state.loadedCount;
    state.badge.textContent = n + ' 篇';
  }

  /* ---------------- 分页加载（含无限滚动） ---------------- */

  function loadPage(state) {
    if (state.loading || state.done || state.destroyed) return;
    state.loading = true;
    state.seq += 1;
    var seq = state.seq;
    setStatus(state, 'loading');
    var path = '/api/rss/' + encodeURIComponent(state.bookId) +
      '/items?page=' + state.page + '&size=' + PAGE_SIZE;
    request(path).then(function (data) {
      if (state.destroyed || seq !== state.seq) return; // 实例已关闭或请求已过期
      state.loading = false;
      var items = data && Array.isArray(data.items) ? data.items : [];
      if (data && typeof data.total === 'number') state.total = data.total;
      appendItems(state, items);
      state.page += 1;
      updateBadge(state);
      if (state.loadedCount >= state.total || items.length === 0) {
        state.done = true;
        if (state.observer) state.observer.disconnect();
        setStatus(state, state.loadedCount > 0 ? 'done' : 'empty');
      } else {
        setStatus(state, 'hidden'); // 等待哨兵再次触底
      }
    }).catch(function (err) {
      if (state.destroyed || seq !== state.seq) return;
      state.loading = false;
      setStatus(state, 'error', err && err.message);
    });
  }

  /* ---------------- 列表交互（事件委托） ---------------- */

  function bindListEvents(state) {
    var list = state.list;

    list.addEventListener('click', function (e) {
      // 正文内链接：新窗口打开，且不触发卡片收起
      var a = e.target.closest ? e.target.closest('a') : null;
      if (a) {
        if (!a.classList.contains('mr-rss-source')) {
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
        }
        return;
      }
      var item = e.target.closest ? e.target.closest('.mr-rss-item') : null;
      if (!item || !list.contains(item)) return;
      // 展开区内点击可收起；但用户正在选择文本时不收起
      if (item.classList.contains('open') && e.target.closest('.mr-rss-article')) {
        var sel = window.getSelection();
        if (sel && String(sel).length > 0) return;
      }
      toggleItem(item);
    });

    // 键盘可达性：标题获得焦点时 Enter / 空格切换展开
    list.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      var t = e.target;
      if (!t || !t.classList || !t.classList.contains('mr-rss-item-title')) return;
      e.preventDefault();
      var item = t.closest('.mr-rss-item');
      if (item) toggleItem(item);
    });
  }

  /* ---------------- 全屏壳的创建与销毁 ---------------- */

  function buildShell(state, book) {
    var root = el('div', 'mr-rss');
    root.setAttribute('role', 'region');
    root.setAttribute('aria-label', 'RSS 阅读视图');
    root.innerHTML =
      '<header class="mr-rss-bar">' +
        '<button type="button" class="mr-rss-back" aria-label="返回">' + ICON_BACK + '</button>' +
        '<div class="mr-rss-title"></div>' +
        '<span class="mr-rss-badge">加载中</span>' +
      '</header>' +
      '<div class="mr-rss-scroll">' +
        '<div class="mr-rss-col">' +
          '<div class="mr-rss-list"></div>' +
          '<div class="mr-rss-status" hidden></div>' +
          '<div class="mr-rss-sentinel" aria-hidden="true"></div>' +
        '</div>' +
      '</div>';

    root.querySelector('.mr-rss-title').textContent = book.title || 'RSS 订阅';

    state.root = root;
    state.scroll = root.querySelector('.mr-rss-scroll');
    state.list = root.querySelector('.mr-rss-list');
    state.status = root.querySelector('.mr-rss-status');
    state.sentinel = root.querySelector('.mr-rss-sentinel');
    state.badge = root.querySelector('.mr-rss-badge');

    root.querySelector('.mr-rss-back').addEventListener('click', function () { close(); });

    bindListEvents(state);
  }

  function destroy(state, immediate) {
    if (!state || state.destroyed) return;
    state.destroyed = true;
    if (state.observer) state.observer.disconnect();
    if (state.onKey) document.removeEventListener('keydown', state.onKey, true);
    document.body.style.overflow = state.prevBodyOverflow;
    active = null;
    if (immediate) {
      if (state.root.parentNode) state.root.parentNode.removeChild(state.root);
      return;
    }
    // 优雅淡出后再移除 DOM
    state.root.classList.add('mr-rss-closing');
    setTimeout(function () {
      if (state.root.parentNode) state.root.parentNode.removeChild(state.root);
    }, 200);
  }

  /* ---------------- 对外入口 ---------------- */

  var active = null; // 当前唯一实例

  function open(book) {
    if (!book || !book.id) return;
    if (active) destroy(active, true); // 重复调用时先立即关闭已有实例

    injectStyle();

    var state = {
      bookId: book.id,
      bookTitle: book.title || 'RSS 订阅',
      page: 1,
      total: 0,
      loadedCount: 0,
      loading: false,
      done: false,
      destroyed: false,
      seq: 0,
      lastDayKey: null,
      observer: null,
      prevBodyOverflow: document.body.style.overflow || ''
    };

    buildShell(state, book);
    active = state;

    // 打开时锁定 body 滚动
    document.body.style.overflow = 'hidden';

    // Esc 键快速返回
    state.onKey = function (e) {
      if (e.key === 'Escape') { e.stopPropagation(); close(); }
    };
    document.addEventListener('keydown', state.onKey, true);

    document.body.appendChild(state.root);

    // 淡入：下一帧移除初始位移态，触发过渡
    state.root.classList.add('mr-rss-enter');
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        if (!state.destroyed) state.root.classList.remove('mr-rss-enter');
      });
    });

    // 无限滚动哨兵：提前 300px 预加载
    state.observer = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].isIntersecting) { loadPage(state); break; }
      }
    }, { rootMargin: '300px' });
    state.observer.observe(state.sentinel);

    loadPage(state); // 首次打开立即加载第 1 页
  }

  function close() {
    if (active) destroy(active, false);
  }

  window.MRRssViewer = { open: open, close: close };
})();
