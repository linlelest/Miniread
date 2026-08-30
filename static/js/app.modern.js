const MR = (() => {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);

  async function api(path, opts = {}) {
    const init = { method: opts.method || 'GET', headers: {} };
    if (opts.json !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.json);
    } else if (opts.form) {
      init.body = opts.form;
    }
    const res = await fetch(path, init);
    let body = null;
    try { body = await res.json(); } catch { body = null; }
    if (!res.ok || (body && body.code >= 400)) {
      const err = new Error((body && body.message) || `请求失败 (${res.status})`);
      err.code = body ? body.code : res.status;
      throw err;
    }
    return body ? body.data : null;
  }

  function toastHost() {
    let host = document.querySelector('.toasts');
    if (!host) {
      host = document.createElement('div');
      host.className = 'toasts';
      document.body.appendChild(host);
    }
    return host;
  }

  function toast(msg, type = 'info', ms = 3200) {
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    toastHost().appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(-6px)';
      setTimeout(() => el.remove(), 220);
    }, ms);
  }

  function modal({ title, body, footer, onOpen }) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true">
        <div class="modal-header"><h3>${esc(title)}</h3>
          <button class="btn btn-ghost btn-icon" data-close aria-label="关闭">
            <svg><use href="#icon-x"/></svg></button></div>
        <div class="modal-body">${body}</div>
        ${footer ? `<div class="modal-footer">${footer}</div>` : ''}
      </div>`;
    const close = () => backdrop.remove();
    backdrop.addEventListener('click', e => {
      if (e.target === backdrop || e.target.closest('[data-close]')) close();
    });
    document.body.appendChild(backdrop);
    if (onOpen) onOpen(backdrop, close);
    return { el: backdrop, close };
  }

  function confirmDialog(title, message, danger = true) {
    return new Promise(resolve => {
      const m = modal({
        title,
        body: `<p>${esc(message)}</p>`,
        footer: `<button class="btn" data-close>取消</button>
                 <button class="btn ${danger ? 'btn-danger btn-solid' : 'btn-primary'}" data-ok>确定</button>`,
        onOpen(el, close) {
          el.querySelector('[data-ok]').addEventListener('click', () => { close(); resolve(true); });
          el.addEventListener('click', e => {
            if (e.target === el || e.target.closest('[data-close]')) resolve(false);
          });
        }
      });
    });
  }

  const fmtSize = n => {
    if (!n) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0, v = n;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
  };

  const fmtDate = ts => {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const p = x => String(x).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  };

  const debounce = (fn, ms) => {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  };

  function getBlob(url) {
    return fetch(url).then(r => {
      if (!r.ok) throw new Error('下载失败');
      return r.blob();
    });
  }

  function saveBlob(blob, name) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  function mdAnn(t) {
    const codes = [];
    t = String(t || '').replace(/```([\s\S]*?)```/g, (_, code) => {
      codes.push('<pre style="overflow:auto;background:var(--bg);padding:10px;border-radius:8px"><code>' + code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</code></pre>');
      return '\u0000C' + (codes.length - 1) + '\u0000';
    });
    t = t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    t = t
      .replace(/\[\[video:([^\]]+)\]\]/g, '<video controls preload="metadata" src="$1" style="width:100%;max-height:420px;border-radius:8px;margin:8px 0"></video>')
      .replace(/^### (.*)$/gm, '<h3 style="margin:.6em 0 .3em">$1</h3>')
      .replace(/^## (.*)$/gm, '<h2 style="margin:.7em 0 .4em">$1</h2>')
      .replace(/^# (.*)$/gm, '<h2 style="margin:.7em 0 .4em">$1</h2>')
      .replace(/^---+\s*$/gm, '<hr style="border:none;border-top:1px solid var(--hairline)">')
      .replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, '<img src="$2" alt="$1" loading="lazy" style="max-width:100%;border-radius:8px;margin:6px 0">')
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:var(--primary)">$1</a>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code style="background:var(--bg);padding:2px 6px;border-radius:6px">$1</code>')
      .replace(/^\s*[-*] (.*)$/gm, '<li>$1</li>')
      .replace(/^\s*\d+\. (.*)$/gm, '<li>$1</li>')
      .replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, '<ul style="padding-left:1.4em;margin:.4em 0">$1</ul>')
      .replace(/\n{2,}/g, '<br><br>').replace(/\n/g, '<br>');
    t = t.replace(/\u0000C(\d+)\u0000/g, (_, i) => codes[+i]);
    return t;
  }

  return { esc, api, toast, modal, confirmDialog, fmtSize, fmtDate, debounce, getBlob, saveBlob, mdAnn };
})();

window.MR = MR;
