/* ═══════════════════════════════════════════
   Miniread (极读) — 管理后台 JS (ES5)
   Chrome 91+ 兼容
   ═══════════════════════════════════════════ */
(function(){'use strict';
var admTab='announcements';

/* Theme */
window.toggleTheme=function(){
  var e=document.documentElement,c=e.getAttribute('data-theme'),n=c==='dark'?'light':'dark';
  e.setAttribute('data-theme',n);localStorage.setItem('miniread-theme',n);
  document.getElementById('themeBtn').textContent=n==='dark'?'☾':'☀';
};
(function(){var t=localStorage.getItem('miniread-theme')||'light';document.documentElement.setAttribute('data-theme',t);
  var b=document.getElementById('themeBtn');if(b)b.textContent=t==='dark'?'☾':'☀';})();

/* Init */
window.onload=function(){
  fetch('/api/auth/check',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){
    if(d.code===200&&d.data.authenticated&&d.data.role==='admin')initAdmin();
    else window.location.href='/login';
  }).catch(function(){window.location.href='/login';});
};
function initAdmin(){loadAnn();loadUsers();loadBannedLog();loadInvites();loadInvCfg();loadMaint();loadVer();window.switchTab=switchTab;
  MdToolbar.init('annContent','annPreview');
  MdToolbar.init('maintContent','maintPreview');
}

/* Tabs */
function switchTab(t){admTab=t;
  var ss=document.querySelectorAll('.tab-section');for(var i=0;i<ss.length;i++)ss[i].classList.remove('active');
  document.getElementById('tab-'+t).classList.add('active');
  var ls=document.querySelectorAll('.sidebar nav a');for(var j=0;j<ls.length;j++)ls[j].classList.remove('active');
  var a=document.querySelector('.sidebar nav a[onclick="switchTab(\''+t+'\')"]');if(a)a.classList.add('active');
  if(t==='announcements')loadAnn();if(t==='users'){loadUsers();loadBannedLog();}if(t==='invites'){loadInvites();loadInvCfg();}if(t==='maintenance'){loadMaint();loadVer();}
}

/* ====== 公告 ====== */
function loadAnn(){
  fetch('/api/admin/announcements',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){
    if(d.code===200){var h='<table><thead><tr><th></th><th>标题</th><th>预览</th><th>范围</th><th>置顶</th><th>状态</th><th>操作</th></tr></thead><tbody>';
      (d.data||[]).forEach(function(a){h+='<tr draggable="true" data-id="'+a.id+'" ondragstart="ds(event)" ondragover="dp(event)" ondrop="dd(event)"><td><span class="drag-handle">☰</span></td>'+
        '<td><b>'+esc((a.title||'无标题').substring(0,20))+'</b></td>'+
        '<td><div style="max-height:40px;overflow:hidden;font-size:12px">'+MdToolbar.render((a.content||'').substring(0,100))+'</div></td><td><span class="badge '+(a.visibility==='all'?'badge-accent':'badge-muted')+'">'+(a.visibility==='all'?'公开':'注册')+'</span></td>'+
        '<td>'+(a.pinned?'📌':'-')+'</td><td><span class="badge '+(a.active?'badge-green':'badge-red')+'">'+(a.active?'启用':'禁用')+'</span></td>'+
        '<td><button class="btn btn-sm" onclick="editAnn('+a.id+')">编辑</button><button class="btn btn-danger btn-sm" onclick="delAnn('+a.id+')">删除</button></td></tr>';});
      h+='</tbody></table>';document.getElementById('annList').innerHTML=h;}
  });
}
window.showAnnEditor=function(){
  document.getElementById('annEditId').value='';document.getElementById('annEditorTitle').textContent='新建公告';
  document.getElementById('annTitle').value='';document.getElementById('annContent').value='';document.getElementById('annVis').value='all';document.getElementById('annDismiss').checked=false;
  document.getElementById('annPinned').checked=false;document.getElementById('annActive').checked=true;
  document.getElementById('annEditor').style.display='block';};
window.editAnn=function(id){fetch('/api/admin/announcements',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){
  var a=(d.data||[]).find(function(x){return x.id===id;});if(!a)return;
  document.getElementById('annEditId').value=a.id;document.getElementById('annEditorTitle').textContent='编辑公告';
  document.getElementById('annTitle').value=a.title||'';document.getElementById('annContent').value=a.content;document.getElementById('annVis').value=a.visibility;
  document.getElementById('annDismiss').checked=a.show_dismiss===1;document.getElementById('annPinned').checked=a.pinned===1;
  document.getElementById('annActive').checked=a.active===1;document.getElementById('annEditor').style.display='block';});};
window.saveAnnouncement=function(){
  var id=document.getElementById('annEditId').value,data={title:document.getElementById('annTitle').value,content:document.getElementById('annContent').value,visibility:document.getElementById('annVis').value,
    showDismiss:document.getElementById('annDismiss').checked,pinned:document.getElementById('annPinned').checked,active:document.getElementById('annActive').checked};
  fetch(id?'/api/admin/announcements/'+id:'/api/admin/announcements',{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(data)}).then(function(){cancelAnnEditor();loadAnn();showT('已保存','success');});
};
window.cancelAnnEditor=function(){document.getElementById('annEditor').style.display='none';};
window.delAnn=function(id){if(!confirm('删除?'))return;fetch('/api/admin/announcements/'+id,{method:'DELETE',credentials:'same-origin'}).then(function(){loadAnn();showT('已删除','success');});};
var dragId=null;
window.ds=function(e){dragId=e.target.closest('tr').dataset.id;};
window.dp=function(e){e.preventDefault();};
window.dd=function(e){e.preventDefault();var t=e.target.closest('tr').dataset.id;if(dragId&&t&&dragId!==t){
  var rs=document.querySelectorAll('#annList tr[data-id]'),o=[];rs.forEach(function(r){o.push(parseInt(r.dataset.id));});
  fetch('/api/admin/announcements/reorder',{method:'PUT',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({order:o})}).then(function(){loadAnn();});
}};

/* ====== 用户 ====== */
function loadUsers(){
  fetch('/api/admin/users',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){if(d.code===200){var h='';
    (d.data||[]).forEach(function(u){var sb='';if(u.deleted)sb='<span class="badge badge-red">已删除</span>';
      else if(u.banned)sb='<span class="badge badge-red">封禁</span>';else sb='<span class="badge badge-green">正常</span>';
      h+='<tr><td>'+u.id+'</td><td>'+esc(u.username)+'</td><td><span class="badge '+(u.role==='admin'?'badge-red':'badge-muted')+'">'+u.role+'</span></td><td>'+sb+'</td><td>'+fmtTs(u.created_at)+'</td><td>';
      if(!u.deleted&&u.role!=='admin'){h+=(u.banned?'<button class="btn btn-sm" onclick="unbanU('+u.id+')">解封</button> ':'<button class="btn btn-sm" onclick="banU('+u.id+')">封禁</button> ');h+='<button class="btn btn-danger btn-sm" onclick="delU('+u.id+')">删除</button>';}else h+='-';h+='</td></tr>';});
    document.getElementById('usersTbody').innerHTML=h;}});
}
window.banU=function(uid){if(!confirm('封禁该用户？IP封锁5天。'))return;fetch('/api/admin/users/ban',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({userId:uid,action:'ban'})}).then(function(r){return r.json()}).then(function(d){showT(d.message||'完成','success');loadUsers();loadBannedLog();});};
window.unbanU=function(uid){fetch('/api/admin/users/ban',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({userId:uid,action:'unban'})}).then(function(r){return r.json()}).then(function(d){showT(d.message||'完成','success');loadUsers();});};
window.delU=function(uid){var r=prompt('永久删除原因(必填):');if(!r||!r.trim())return;fetch('/api/admin/users/delete',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({userId:uid,reason:r.trim()})}).then(function(r){return r.json()}).then(function(d){showT(d.message||'完成','success');loadUsers();loadBannedLog();});};
function loadBannedLog(){fetch('/api/admin/banned-log',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){if(d.code===200){var h=''; (d.data||[]).forEach(function(l){h+='<tr><td>'+esc(l.username)+'</td><td>'+(l.action==='ban'?'封禁':'删除')+'</td><td>'+esc(l.reason||'')+'</td><td>'+fmtTs(l.created_at)+'</td></tr>';});document.getElementById('bannedLogTbody').innerHTML=h;}});}

/* ====== 邀请码 ====== */
function loadInvCfg(){fetch('/api/public/invite-status',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){if(d.code===200){document.getElementById('invEnabled').checked=d.data.enabled;document.getElementById('invPrompt').value=d.data.prompt||'';}});}
window.updateInvConfig=function(){fetch('/api/admin/invite-codes/config',{method:'PUT',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({enabled:document.getElementById('invEnabled').checked,prompt:document.getElementById('invPrompt').value})}).then(function(){showT('已更新','success');});};
function loadInvites(){fetch('/api/admin/invite-codes',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){if(d.code===200){var h=''; (d.data||[]).forEach(function(c){h+='<tr><td>'+c.id+'</td><td><span class="invite-code-box">'+esc(c.code)+'</span></td><td>'+c.used_count+'/'+(c.max_uses===0?'∞':c.max_uses)+'</td><td>'+(c.expires_at?fmtTs(c.expires_at):'永久')+'</td><td>'+esc(c.note||'')+'</td><td>'+(c.active?'启用':'禁用')+'</td><td><button class="btn btn-sm" onclick="editInv('+c.id+')">编辑</button><button class="btn btn-danger btn-sm" onclick="delInv('+c.id+')">删除</button></td></tr>';});document.getElementById('invitesTbody').innerHTML=h||'<tr><td colspan="7" class="text-center text-muted">暂无</td></tr>';}});}
window.genCodes=function(){var c=parseInt(document.getElementById('genCount').value)||10,m=parseInt(document.getElementById('genMax').value)||0,e=document.getElementById('genExp').value,nt=document.getElementById('genNote').value;var days=null;if(e){var now=new Date(),exp=new Date(e);days=Math.ceil((exp-now)/(86400000))}if(days!==null&&days<0)days=null;fetch('/api/admin/invite-codes/generate',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({count:c,maxUses:m,expiresInDays:days,note:nt})}).then(function(r){return r.json()}).then(function(d){if(d.code===200){showT('已生成 '+d.data.count+' 个','success');loadInvites();}else showT(d.message,'error');});};
window.editInv=function(id){
  fetch('/api/admin/invite-codes',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){
    var c=(d.data||[]).find(function(x){return x.id===id});if(!c)return;
    document.getElementById('invEditId').value=c.id;
    document.getElementById('invEditMax').value=c.max_uses;
    if(c.expires_at){var ed=new Date(c.expires_at*1000);document.getElementById('invEditExp').value=ed.getFullYear()+'-'+p(ed.getMonth()+1)+'-'+p(ed.getDate())}
    else document.getElementById('invEditExp').value='';
    document.getElementById('invEditNote').value=c.note||'';
    document.getElementById('invEditActive').checked=c.active===1;
    document.getElementById('invEditDlg').style.display='flex';
  });
};
window.closeInvEdit=function(){document.getElementById('invEditDlg').style.display='none'};
window.saveInvEdit=function(){
  var id=document.getElementById('invEditId').value;if(!id)return;
  var m=parseInt(document.getElementById('invEditMax').value)||0;
  var e=document.getElementById('invEditExp').value,days=null;
  if(e){var now=new Date(),exp=new Date(e);days=Math.ceil((exp-now)/(86400000))}if(days!==null&&days<0)days=null;
  var nt=document.getElementById('invEditNote').value;
  var act=document.getElementById('invEditActive').checked;
  fetch('/api/admin/invite-codes/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({maxUses:m,expiresInDays:days,note:nt,active:act})}).then(function(r){return r.json()}).then(function(d){showT(d.message||'OK','success');closeInvEdit();loadInvites()});
};
window.delInv=function(id){if(!confirm('删除?'))return;fetch('/api/admin/invite-codes/'+id,{method:'DELETE',credentials:'same-origin'}).then(function(){loadInvites();showT('已删除','success');});};

/* ====== 维护 ====== */
function loadMaint(){fetch('/api/admin/maintenance',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){if(d.code===200&&d.data){document.getElementById('maintMode').checked=d.data.mode;document.getElementById('maintContent').value=d.data.content||'';}});}
window.updateMaint=function(){fetch('/api/admin/maintenance',{method:'PUT',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({mode:document.getElementById('maintMode').checked,content:document.getElementById('maintContent').value})}).then(function(){showT('已更新','success');});};
function loadVer(){document.getElementById('curVersion').textContent='v1.0.0';}
window.checkUpdate=function(){var b=document.getElementById('btnCheckUpdate');b.disabled=true;b.textContent='检查中...';fetch('/api/admin/update/check',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){b.disabled=false;b.textContent='检查更新';if(d.code===200&&d.data&&d.data.hasUpdate){document.getElementById('updateInfo').innerHTML='<div style="color:var(--green);font-weight:600">新版本: '+d.data.latestVersion+'</div><div style="font-size:11px;color:var(--text-muted)">'+(d.data.body||'').substring(0,200)+'</div>';document.getElementById('btnApply').style.display='inline-flex';}else document.getElementById('updateInfo').innerHTML='<div style="color:var(--text-muted)">已是最新</div>';}).catch(function(){b.disabled=false;b.textContent='检查更新';});};
window.applyUpdate=function(){if(!confirm('安装更新？期间其它用户不可用。'))return;var b=document.getElementById('btnApply');b.disabled=true;b.textContent='更新中...';fetch('/api/admin/update/apply',{method:'POST',credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){if(d.code===200){showT('更新中，重启后刷新','success');setTimeout(function(){location.reload();},3000);}else{showT(d.message||'失败','error');b.disabled=false;b.textContent='安装更新';}});};

/* Export */
window.exportData=function(){
  showT('正在导出...','info');
  window.open('/api/admin/export','_blank');
  setTimeout(function(){showT('导出完成','success')},1000);
};

/* Toast */
function showT(m,t){var to=document.getElementById('toast');to.textContent=m;to.className='toast show '+(t||'info');setTimeout(function(){to.classList.remove('show');},3000);}
function esc(s){return s?String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'):'';}
function fmtTs(ts){if(!ts)return'';var d=new Date(ts*1000);return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+' '+pad(d.getHours())+':'+pad(d.getMinutes());}
function pad(n){return n<10?'0'+n:''+n;}

/* Mobile sidebar toggle */
window.toggleSidebar=function(){
  var s=document.querySelector('.sidebar'),o=document.getElementById('overlayBg');
  if(s)s.classList.toggle('open');if(o)o.classList.toggle('open');
};
})();
