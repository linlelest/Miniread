(() => {
  const { api, esc, toast, modal, confirmDialog, fmtDate } = window.MR;
  const $ = s => document.querySelector(s);

  document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    ['users', 'ann', 'invite', 'system'].forEach(k => {
      $('#tab-' + k).hidden = t.dataset.tab !== k;
    });
  }));

  async function loadUsers() {
    const list = await api('/api/admin/users') || [];
    const users = Array.isArray(list) ? list : list.users || [];
    $('#usersTable tbody').innerHTML = users.map(u => `
      <tr>
        <td>${u.id}</td>
        <td class="bold">${esc(u.username)}</td>
        <td>${u.role === 'admin' ? '<span class="badge badge-accent">管理员</span>' : '用户'}</td>
        <td>${u.banned ? '<span class="badge badge-danger">已封禁</span>' : '<span class="badge badge-success">正常</span>'}</td>
        <td>${fmtDate(u.created_at)}</td>
        <td>
          ${u.role !== 'admin' ? `
            <button class="btn btn-sm ${u.banned ? '' : 'btn-danger'}" data-uact="${u.banned ? 'unban' : 'ban'}" data-id="${u.id}" data-name="${esc(u.username)}">${u.banned ? '解封' : '封禁'}</button>
            <button class="btn btn-sm btn-danger" data-uact="delete" data-id="${u.id}" data-name="${esc(u.username)}">删除</button>` : ''}
        </td>
      </tr>`).join('');
  }

  async function loadAnn() {
    const list = await api('/api/admin/announcements') || [];
    $('#annList').innerHTML = list.map((a, i) => `
      <div class="card mb-3">
        <div class="row">
          <div class="flex-1">
            <div class="bold">${esc(a.title || '(无标题)')} ${a.pinned ? '<span class="badge badge-accent">置顶</span>' : ''} ${a.active ? '<span class="badge badge-success">已发布</span>' : '<span class="badge">草稿</span>'}</div>
            <div class="text-3" style="font-size:var(--fs-xs)">${fmtDate(a.created_at)} · ${a.visibility === 'all' ? '全体用户' : a.visibility === 'login' ? '仅登录用户' : '仅未登录用户'}${a.show_dismiss ? ' · 可关闭' : ''}</div>
          </div>
          <button class="btn btn-sm" data-ord="up" data-id="${a.id}" ${i === 0 ? 'disabled' : ''} title="上移">↑</button>
          <button class="btn btn-sm" data-ord="down" data-id="${a.id}" ${i === list.length - 1 ? 'disabled' : ''} title="下移">↓</button>
          <button class="btn btn-sm" data-aact="pub" data-id="${a.id}" data-active="${a.active ? 0 : 1}">${a.active ? '转为草稿' : '发布'}</button>
          <button class="btn btn-sm" data-aact="edit" data-id="${a.id}">编辑</button>
          <button class="btn btn-sm btn-danger" data-aact="del" data-id="${a.id}">删除</button>
        </div>
        <p class="mt-2 mb-0" style="font-size:var(--fs-sm);white-space:pre-wrap">${esc(a.content)}</p>
      </div>`).join('') || '<div class="empty"><div class="empty-title">暂无公告</div></div>';
  }

  function annForm(a) {
    modal({
      title: a ? '编辑公告' : '新建公告',
      body: `
        <div class="field"><label>标题</label><input class="input" id="annTitle" value="${esc(a && a.title || '')}"></div>
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:6px" id="annToolbar">
          <button type="button" class="btn btn-sm" data-md="bold" title="加粗"><b>B</b></button>
          <button type="button" class="btn btn-sm" data-md="italic" title="斜体"><i>I</i></button>
          <button type="button" class="btn btn-sm" data-md="h1">H1</button>
          <button type="button" class="btn btn-sm" data-md="h2">H2</button>
          <button type="button" class="btn btn-sm" data-md="h3">H3</button>
          <button type="button" class="btn btn-sm" data-md="quote" title="引用">❝</button>
          <button type="button" class="btn btn-sm" data-md="ul">• 列表</button>
          <button type="button" class="btn btn-sm" data-md="ol">1. 列表</button>
          <button type="button" class="btn btn-sm" data-md="code" title="行内代码">&lt;/&gt;</button>
          <button type="button" class="btn btn-sm" data-md="link" title="链接"><svg style="width:14px;height:14px"><use href="#icon-link"/></svg></button>
          <button type="button" class="btn btn-sm" data-md="hr" title="分割线">—</button>
          <button type="button" class="btn btn-sm" data-md="image" title="上传图片"><svg style="width:14px;height:14px"><use href="#icon-image"/></svg> 图片</button>
          <button type="button" class="btn btn-sm" data-md="video" title="上传视频"><svg style="width:14px;height:14px"><use href="#icon-video"/></svg> 视频</button>
          <button type="button" class="btn btn-sm" id="annPreviewBtn" style="margin-left:auto">预览</button>
        </div>
        <input type="file" id="annImgFile" accept="image/*" hidden>
        <input type="file" id="annVidFile" accept="video/*" hidden>
        <textarea class="textarea" id="annContent" style="min-height:220px;font-family:var(--font-mono);display:block">${esc(a && a.content || '')}</textarea>
        <div id="annPreview" class="mt-2" style="display:none;border:1px solid var(--hairline);border-radius:var(--r-md);padding:12px;min-height:220px;max-height:340px;overflow:auto;background:var(--bg);font-size:var(--fs-sm);line-height:1.8"></div>
        <div class="field mt-3"><label>可见范围</label>
          <select class="select" id="annVis">
            <option value="all" ${!a || a.visibility === 'all' ? 'selected' : ''}>全体用户（含未登录访客）</option>
            <option value="login" ${a && a.visibility === 'login' ? 'selected' : ''}>仅登录用户</option>
            <option value="guest" ${a && a.visibility === 'guest' ? 'selected' : ''}>仅未登录用户</option>
          </select></div>
        <label class="setting-row"><label>立即发布（取消则保存为草稿）</label>
          <span class="switch"><input type="checkbox" id="annActive" ${!a || a.active ? 'checked' : ''}><span class="track"></span></span></label>
        <label class="setting-row"><label>允许用户"不再显示"</label>
          <span class="switch"><input type="checkbox" id="annDismiss" ${!a || a.show_dismiss ? 'checked' : ''}><span class="track"></span></span></label>
        <label class="setting-row"><label>置顶</label>
          <span class="switch"><input type="checkbox" id="annPinned" ${a && a.pinned ? 'checked' : ''}><span class="track"></span></span></label>`,
      footer: `<button class="btn" data-close>取消</button><button class="btn btn-primary" data-ok>保存</button>`,
      onOpen(el, close) {
        const mcard = el.querySelector('.modal');
        if (mcard) { mcard.style.width = 'min(780px, 94vw)'; mcard.style.maxWidth = '94vw'; }
        const ta = el.querySelector('#annContent');
        const preview = el.querySelector('#annPreview');
        el.querySelector('#annPreviewBtn').addEventListener('click', () => {
          const on = preview.style.display === 'none';
          el.querySelector('#annPreviewBtn').textContent = on ? '编辑' : '预览';
          ta.style.display = on ? 'none' : 'block';
          preview.style.display = on ? 'block' : 'none';
          if (on) preview.innerHTML = MR.mdAnn(ta.value);
        });
        function surround(before, after) {
          const s = ta.selectionStart, e2 = ta.selectionEnd;
          const sel = ta.value.slice(s, e2) || '文本';
          ta.setRangeText(before + sel + after, s, e2, 'select');
          ta.focus();
        }
        function linePrefix(p) {
          const s = ta.selectionStart;
          const ls = ta.value.lastIndexOf('\n', Math.max(0, s - 1)) + 1;
          ta.setRangeText(p, ls, ls, 'end');
          ta.focus();
        }
        async function upload(file, kind, tpl, btn) {
          if (!file) return;
          btn.disabled = true;
          try {
            const fd = new FormData();
            fd.append('file', file);
            fd.append('kind', kind);
            const r = await fetch('/api/admin/announcements/upload', { method: 'POST', body: fd, credentials: 'same-origin' });
            const j = await r.json();
            if (j.code !== 200) throw new Error(j.message || '上传失败');
            const s = ta.selectionStart;
            ta.setRangeText(tpl(j.data.url), s, s, 'end');
            ta.focus();
            toast('上传成功', 'success');
          } catch (err) { toast(err.message, 'error'); }
          btn.disabled = false;
        }
        el.querySelector('#annToolbar').addEventListener('click', ev => {
          const b = ev.target.closest('[data-md]');
          if (!b) return;
          const k = b.dataset.md;
          if (k === 'bold') surround('**', '**');
          else if (k === 'italic') surround('*', '*');
          else if (k === 'h1') linePrefix('# ');
          else if (k === 'h2') linePrefix('## ');
          else if (k === 'h3') linePrefix('### ');
          else if (k === 'quote') linePrefix('> ');
          else if (k === 'ul') linePrefix('- ');
          else if (k === 'ol') linePrefix('1. ');
          else if (k === 'code') surround('`', '`');
          else if (k === 'link') surround('[', '](https://)');
          else if (k === 'hr') { const s = ta.selectionStart; ta.setRangeText('\n---\n', s, s, 'end'); ta.focus(); }
          else if (k === 'image') el.querySelector('#annImgFile').click();
          else if (k === 'video') el.querySelector('#annVidFile').click();
        });
        el.querySelector('#annImgFile').addEventListener('change', e => {
          const b = el.querySelector('[data-md="image"]');
          upload(e.target.files[0], 'image', u => `![图片](${u})`, b);
          e.target.value = '';
        });
        el.querySelector('#annVidFile').addEventListener('change', e => {
          const b = el.querySelector('[data-md="video"]');
          upload(e.target.files[0], 'video', u => `\n[[video:${u}]]\n`, b);
          e.target.value = '';
        });
        el.querySelector('[data-ok]').addEventListener('click', async () => {
          try {
            const json = {
              title: el.querySelector('#annTitle').value,
              content: ta.value,
              visibility: el.querySelector('#annVis').value,
              pinned: el.querySelector('#annPinned').checked,
              showDismiss: el.querySelector('#annDismiss').checked,
              active: el.querySelector('#annActive').checked
            };
            if (a) await api('/api/admin/announcements/' + a.id, { method: 'PUT', json });
            else await api('/api/admin/announcements', { method: 'POST', json });
            toast('已保存', 'success');
            close();
            loadAnn();
          } catch (e) { toast(e.message, 'error'); }
        });
      }
    });
  }

  async function loadInvite() {
    const list = await api('/api/admin/invite-codes') || [];
    const codes = Array.isArray(list) ? list : list.codes || [];
    $('#invTable tbody').innerHTML = codes.map(c => `
      <tr>
        <td class="bold" style="font-family:var(--font-mono)">${esc(c.code)}</td>
        <td>${c.used_count} / ${c.max_uses}</td>
        <td>${esc(c.note || '')}</td>
        <td><button class="btn btn-sm btn-danger" data-iact="del" data-id="${c.id}">删除</button></td>
      </tr>`).join('') || '<tr><td colspan="4" class="text-3">暂无邀请码</td></tr>';
    try {
      const st = await api('/api/public/invite-status');
      $('#invEnabled').checked = !!(st && st.enabled);
    } catch {}
  }

  async function loadSystem() {
    try {
      const m = await api('/api/admin/maintenance');
      $('#maintOn').checked = !!(m && m.mode);
      $('#maintMsg').value = (m && m.content) || '';
    } catch {}
    try {
      const v = await api('/api/public/update-status');
      $('#sysVersion').textContent = '当前版本：V' + ((v && v.version) || '未知');
    } catch {
      $('#sysVersion').textContent = '当前版本：未知';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadUsers();
    const themeBtn = $('#btnTheme');
    const refresh = () => themeBtn.querySelector('use').setAttribute('href', window.MRTheme.resolve() === 'dark' ? '#icon-sun' : '#icon-moon');
    refresh();
    themeBtn.addEventListener('click', () => { window.MRTheme.toggle(); refresh(); });

    $('#btnReloadUsers').addEventListener('click', loadUsers);
    $('#btnAddAnn').addEventListener('click', () => annForm(null));
    $('#btnGenInv').addEventListener('click', async () => {
      try {
        await api('/api/admin/invite-codes/generate', { method: 'POST', json: { count: parseInt($('#invCount').value, 10) || 10 } });
        toast('已生成', 'success');
        loadInvite();
      } catch (e) { toast(e.message, 'error'); }
    });
    $('#invEnabled').addEventListener('change', async e => {
      try {
        await api('/api/admin/invite-codes/config', { method: 'PUT', json: { enabled: e.target.checked ? 1 : 0 } });
        toast('已保存', 'success');
      } catch (err) { toast(err.message, 'error'); }
    });
    $('#btnSaveMaint').addEventListener('click', async () => {
      try {
        await api('/api/admin/maintenance', { method: 'PUT', json: { mode: $('#maintOn').checked ? 1 : 0, content: $('#maintMsg').value } });
        toast('已保存', 'success');
      } catch (e) { toast(e.message, 'error'); }
    });
    $('#btnCheckUpdate').addEventListener('click', async () => {
      const btn = $('#btnCheckUpdate');
      btn.disabled = true;
      $('#updateResult').textContent = '检查中…';
      try {
        const r = await api('/api/admin/update/check');
        $('#updateResult').textContent = r && r.hasUpdate
          ? `发现新版本 ${r.latest || r.version}，可在服务器上执行更新`
          : '已是最新版本';
      } catch (e) { $('#updateResult').textContent = e.message; }
      btn.disabled = false;
    });
    $('#btnExport').addEventListener('click', async () => {
      try {
        const blob = await window.MR.getBlob('/api/admin/export');
        window.MR.saveBlob(blob, 'miniread-backup.zip');
      } catch (e) { toast(e.message, 'error'); }
    });
    $('#btnImport').addEventListener('click', () => $('#importFile').click());
    $('#importFile').addEventListener('change', async e => {
      const file = e.target.files[0];
      if (!file) return;
      if (!(await confirmDialog('导入备份', '导入将覆盖当前全部数据（书籍、设置、用户），并可能需要重新登录。确定继续？'))) return;
      try {
        const fd = new FormData();
        fd.append('file', file);
        const r = await fetch('/api/admin/import', { method: 'POST', body: fd, credentials: 'same-origin' });
        const j = await r.json();
        if (j.code !== 200) throw new Error(j.message || '导入失败');
        toast('导入完成，即将刷新页面', 'success');
        setTimeout(() => location.reload(), 1200);
      } catch (err) { toast(err.message, 'error'); }
    });

    document.addEventListener('click', async e => {
      const u = e.target.closest('[data-uact]');
      if (u) {
        const act = u.dataset.uact;
        const uid = parseInt(u.dataset.id, 10);
        const uname = u.dataset.name;
        try {
          if (act === 'ban' || act === 'unban') {
            await api('/api/admin/users/ban', { method: 'POST', json: { userId: uid, action: act } });
            toast(act === 'ban' ? '已封禁' : '已解封', 'success');
            loadUsers();
          } else if (act === 'delete') {
            deleteUserForm(uid, uname);
          }
        } catch (err) { toast(err.message, 'error'); }
        return;
      }
      const ord = e.target.closest('[data-ord]');
      if (ord) {
        try {
          const list = await api('/api/admin/announcements') || [];
          const ids = list.map(x => x.id);
          const at = ids.indexOf(parseInt(ord.dataset.id, 10));
          const swap = ord.dataset.ord === 'up' ? at - 1 : at + 1;
          if (at !== -1 && swap >= 0 && swap < ids.length) {
            const t = ids[at]; ids[at] = ids[swap]; ids[swap] = t;
            await api('/api/admin/announcements/reorder', { method: 'PUT', json: { order: ids } });
            loadAnn();
          }
        } catch (err) { toast(err.message, 'error'); }
        return;
      }
      const a = e.target.closest('[data-aact]');
      if (a) {
        try {
          if (a.dataset.aact === 'pub') {
            await api('/api/admin/announcements/' + a.dataset.id, { method: 'PUT', json: { active: a.dataset.active === '1' } });
            toast(a.dataset.active === '1' ? '已发布' : '已转为草稿', 'success');
            loadAnn();
            return;
          }
          if (a.dataset.aact === 'del') {
            if (await confirmDialog('删除公告', '确定删除该公告？')) {
              await api('/api/admin/announcements/' + a.dataset.id, { method: 'DELETE' });
              loadAnn();
            }
          } else {
            const list = await api('/api/admin/announcements') || [];
            const target = list.find(x => x.id === parseInt(a.dataset.id, 10));
            annForm(target);
          }
        } catch (err) { toast(err.message, 'error'); }
        return;
      }
      const iv = e.target.closest('[data-iact]');
      if (iv && iv.dataset.iact === 'del') {
        try {
          await api('/api/admin/invite-codes/' + iv.dataset.id, { method: 'DELETE' });
          loadInvite();
        } catch (err) { toast(err.message, 'error'); }
      }
    });
  });
})();
