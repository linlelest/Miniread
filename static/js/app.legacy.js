(function () {
  function esc(s) {
    s = s == null ? '' : String(s);
    return s.replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || 'GET', headers: {} };
    if (opts.json !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.json);
    } else if (opts.form) {
      init.body = opts.form;
    }
    return fetch(path, init).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (body) {
        if (!res.ok || (body && body.code >= 400)) {
          var err = new Error((body && body.message) || ('请求失败 (' + res.status + ')'));
          err.code = body ? body.code : res.status;
          throw err;
        }
        return body ? body.data : null;
      });
    });
  }

  function toastHost() {
    var host = document.querySelector('.toasts');
    if (!host) {
      host = document.createElement('div');
      host.className = 'toasts';
      document.body.appendChild(host);
    }
    return host;
  }

  function toast(msg, type, ms) {
    type = type || 'info';
    ms = ms || 3200;
    var el = document.createElement('div');
    el.className = 'toast toast-' + type;
    el.textContent = msg;
    toastHost().appendChild(el);
    setTimeout(function () {
      el.style.opacity = '0';
      el.style.transform = 'translateY(-6px)';
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 220);
    }, ms);
  }

  function modal(cfg) {
    var backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML =
      '<div class="modal" role="dialog" aria-modal="true">' +
      '<div class="modal-header"><h3>' + esc(cfg.title) + '</h3>' +
      '<button class="btn btn-ghost btn-icon" data-close aria-label="关闭">' +
      '<svg><use href="#icon-x"/></svg></button></div>' +
      '<div class="modal-body">' + cfg.body + '</div>' +
      (cfg.footer ? '<div class="modal-footer">' + cfg.footer + '</div>' : '') +
      '</div>';
    function close() {
      if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
    }
    backdrop.addEventListener('click', function (e) {
      if (e.target === backdrop || e.target.closest('[data-close]')) close();
    });
    document.body.appendChild(backdrop);
    if (cfg.onOpen) cfg.onOpen(backdrop, close);
    return { el: backdrop, close: close };
  }

  function confirmDialog(title, message, danger) {
    return new Promise(function (resolve) {
      modal({
        title: title,
        body: '<p>' + esc(message) + '</p>',
        footer: '<button class="btn" data-close>取消</button>' +
          '<button class="btn ' + (danger === false ? 'btn-primary' : 'btn-danger btn-solid') + '" data-ok>确定</button>',
        onOpen: function (el, close) {
          el.querySelector('[data-ok]').addEventListener('click', function () {
            close();
            resolve(true);
          });
          el.addEventListener('click', function (e) {
            if (e.target === el || e.target.closest('[data-close]')) resolve(false);
          });
        }
      });
    });
  }

  function fmtSize(n) {
    if (!n) return '0 B';
    var units = ['B', 'KB', 'MB', 'GB'];
    var i = 0;
    var v = n;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return v.toFixed(v >= 100 || i === 0 ? 0 : 1) + ' ' + units[i];
  }

  function fmtDate(ts) {
    if (!ts) return '';
    var d = new Date(ts * 1000);
    function p(x) { return String(x).length < 2 ? '0' + x : String(x); }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
      ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments;
      var self = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(self, args); }, ms);
    };
  }

  function getBlob(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('下载失败');
      return r.blob();
    });
  }

  function saveBlob(blob, name) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  }

  window.MR = {
    esc: esc,
    api: api,
    toast: toast,
    modal: modal,
    confirmDialog: confirmDialog,
    fmtSize: fmtSize,
    fmtDate: fmtDate,
    debounce: debounce,
    getBlob: getBlob,
    saveBlob: saveBlob
  };
})();
