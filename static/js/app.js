/* Miniread — Main App JS | Chrome 91+ | /main */
(function(){'use strict';
var D=document,DE=D.documentElement,
  byId=function(id){return D.getElementById(id)},
  U=null,T='reading',B=[],CB=null,CI=0,CH=[],RM='scroll',
  RS={fs:18,bg:'#f8f9fb',tc:'#1a1c2e',ls:1.8,ps:1.2,ws:0,ff:'serif'},
  SD=[],DT=[],SO=false,RM='continuous',
  esc=function(s){return s?String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'):''},
  fts=function(ts){if(!ts)return'';var d=new Date(ts*1000);return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())},
  p=function(n){return n<10?'0'+n:''+n},
  api=function(url,opt){opt=opt||{};opt.credentials='same-origin';return fetch(url,opt).then(function(r){return r.json()})},
  $=function(s){return D.querySelector(s)},$$=function(s){return D.querySelectorAll(s)};

/* Theme */
window.toggleTheme=function(){var c=DE.getAttribute('data-theme'),n=c==='dark'?'light':'dark';DE.setAttribute('data-theme',n);localStorage.setItem('miniread-theme',n);var b=byId('themeBtn');if(b)b.textContent=n==='dark'?'☾':'☀'};
(function(){var t=localStorage.getItem('miniread-theme')||'light';DE.setAttribute('data-theme',t);setTimeout(function(){var b=byId('themeBtn');if(b)b.textContent=t==='dark'?'☾':'☀'},0)})();

/* Init */
window.onload=function(){api('/api/auth/check').then(function(d){if(d.code===200&&d.data.authenticated){U=d.data;var u=byId('hdrUser');if(u)u.textContent=U.username;var ba=byId('btnAdmin');if(ba&&U.role==='admin')ba.style.display='inline-flex';initApp()}else window.location.href='/login'}).catch(function(){window.location.href='/login'})};
function initApp(){loadB();loadDC();loadBanned();refDT();checkAnnouncements();if(U)connSSE();
  // Admin welcome popup
  if(U&&U.role==='admin'&&localStorage.getItem('miniread-admin-welcome')){
    localStorage.removeItem('miniread-admin-welcome');
    setTimeout(function(){alert('欢迎管理员！\n\n右上角可进入后台管理\n进入后台后左下角可返回前台')},600)
  }}

/* Tabs */
window.swTab=function(t){T=t;[].forEach.call($$('.tab-content'),function(e){e.classList.remove('active')});var el=byId('tab-'+t);if(el)el.classList.add('active');[].forEach.call($$('.header-nav button'),function(b){b.classList.remove('active')});var hb=$('.header-nav button[data-tab="'+t+'"]');if(hb)hb.classList.add('active');[].forEach.call($$('.mobile-nav button'),function(b){b.classList.remove('active')});var mb=$('.mobile-nav button[data-mtab="'+t+'"]');if(mb)mb.classList.add('active');if(t==='reading')loadB();if(t==='download'){loadDC();refDT()}};
window.doLogout=function(){fetch('/api/auth/logout',{method:'POST',credentials:'same-origin'}).then(function(){window.location.href='/login'})};

/* Banned */
function loadBanned(){api('/api/public/banned-log?limit=1').then(function(d){if(d.code===200&&d.data&&d.data.length>0){var it=d.data[0];var bn=byId('bannedBnr'),bo=byId('bannedOne');if(bn)bn.style.display='block';if(bo)bo.innerHTML='<b>'+(it.action==='ban'?'封禁':'删除')+'</b> '+it.username+' — '+(it.reason||'—')+' ('+fts(it.created_at)+')'}})}

/* ══════ Announcement Popups ══════ */
function checkAnnouncements(){api('/api/public/announcements').then(function(d){if(d.code!==200||!d.data||!d.data.length)return;d.data.forEach(function(ann){var key='miniread-ann-'+ann.id,stored=D.cookie.match('(^|;)\\s*'+key+'\\s*=\\s*([^;]+)'),lastUpd=stored?stored.pop():'';if(!stored||lastUpd!==String(ann.updated_at||ann.created_at)){showAnnPopup(ann)}})})}
function showAnnPopup(ann){var ex=D.querySelector('.ann-popup-overlay[data-ann="'+ann.id+'"]');if(ex&&ex.parentNode)ex.parentNode.removeChild(ex);var ov=D.createElement('div');ov.className='ann-popup-overlay';ov.setAttribute('data-ann',ann.id);var annTitle=ann.title?'<div style="font-size:16px;font-weight:700;margin-bottom:8px;color:var(--text)">'+esc(ann.title)+'</div>':'';ov.innerHTML='<div class="ann-popup-box"><div class="ann-popup-body">'+annTitle+MdToolbar.render(ann.content)+'</div><div class="ann-popup-foot">'+(ann.show_dismiss?'<label class="ann-popup-dismiss"><input type="checkbox" id="annDismiss'+ann.id+'"> 不再提示</label>':'')+'<button class="btn btn-sm" onclick="closeAnnPopup('+ann.id+','+ann.pinned+',\''+(ann.updated_at||ann.created_at)+'\')">关闭</button></div></div>';if(ann.pinned){var ep=D.querySelectorAll('.ann-popup-overlay');for(var i=0;i<ep.length;i++){if(ep[i].parentNode)ep[i].parentNode.removeChild(ep[i])}}D.body.appendChild(ov);ov.addEventListener('click',function(e){if(e.target===ov)closeAnnPopup(ann.id,ann.pinned,ann.updated_at||ann.created_at)})}
window.closeAnnPopup=function(annId,pinned,updatedAt){var cb=D.getElementById('annDismiss'+annId);if(cb&&cb.checked){D.cookie='miniread-ann-'+annId+'='+updatedAt+';path=/;max-age='+(30*86400)+';SameSite=Lax'}var ov=D.querySelector('.ann-popup-overlay[data-ann="'+annId+'"]');if(ov&&ov.parentNode)ov.parentNode.removeChild(ov)}

/* Books */
function loadB(){api('/api/books').then(function(d){if(d.code===200){B=d.data||[];renderS()}})}
function renderS(){var g=byId('booksGrid');if(!g)return;if(!B.length){g.innerHTML='<div class="empty-state"><div class="icon">+</div><p>书架为空</p></div>';return}var h='';B.forEach(function(b){var bg=b.cover_url?' style="background-image:url(\''+b.cover_url+'\');background-size:cover;background-position:center"':'';var ci=b.cover_url?'<img src="'+b.cover_url+'" style="display:none" onerror="var p=this.parentNode;p.style.backgroundImage=\'none\';var s=p.querySelector(\'span\');if(s)s.style.display=\'\'">':'';var ts=b.cover_url?' style="display:none"':'';h+='<div class="book-card"><div class="book-cover" onclick="openR('+b.id+')"'+bg+'>'+ci+'<span'+ts+'>'+esc(b.title)+'</span><span class="book-fmt">'+b.format.toUpperCase()+'</span><div class="book-prg" style="width:'+(b.last_read_percent||0)+'%"></div></div><div class="book-info"><div class="bt">'+esc(b.title)+'</div><div class="ba">'+(b.author||'?')+'</div>'+(b.note?'<div style="font-size:10px;color:var(--accent);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+esc(b.note).substring(0,30)+'</div>':'')+'</div><div class="book-acts"><button onclick="openR('+b.id+')">阅读</button><button onclick="editBook('+b.id+')">编辑</button><button onclick="dlBook('+b.id+')">下载</button><button class="danger" onclick="delBook('+b.id+')">删除</button></div></div>'});g.innerHTML=h}
window.upBooks=function(inp){var fs=inp.files;if(!fs||!fs.length)return;var z=byId('upZone'),t=fs.length,u=0;
  showUpToast('上传中...',0);if(z){z.style.opacity='.5';var dl=z.querySelector('div:last-child');if(dl)dl.textContent='上传中 '}
  (function nx(i){if(i>=t){
    showUpToast('解析中...',80);
    setTimeout(function(){showUpToast('上传完成',100);setTimeout(function(){hideUpToast();loadB();if(z){z.style.opacity='1';var d2=z.querySelector('div:last-child');if(d2)d2.textContent='导入电子书'}},1500)},300);
    inp.value='';return
  }var fd=new FormData();fd.append('file',fs[i]);fetch('/api/books/upload',{method:'POST',credentials:'same-origin',body:fd}).then(function(){u++;showUpToast('上传中 '+(u/t*100).toFixed(0)+'%',(u/t*70));if(z){var d3=z.querySelector('div:last-child');if(d3)d3.textContent='已传 '+u+'/'+t}nx(i+1)}).catch(function(){nx(i+1)})})(0)};;
window.delBook=function(id){if(!confirm('删除？'))return;fetch('/api/books/'+id,{method:'DELETE',credentials:'same-origin'}).then(function(){loadB()})}
window.dlBook=function(id){window.open('/api/books/'+id+'/download','_blank')}
/* Edit book */
var _editBid=null;
window.editBook=function(id){_editBid=id;var bk=B.find(function(b){return b.id===id});if(!bk)return;
  byId('editTitle').value=bk.title||'';byId('editAuthor').value=bk.author||'';byId('editNote').value=bk.note||'';
  var dlg=byId('editBookDlg');if(dlg)dlg.style.display='flex'};
window.closeEditBook=function(){var dlg=byId('editBookDlg');if(dlg)dlg.style.display='none';_editBid=null};
window.saveEditBook=function(){if(!_editBid)return;var cf=byId('editCover'),coverFile=(cf&&cf.files&&cf.files[0])||null;
  var fd=new FormData();fd.append('title',byId('editTitle').value.trim());fd.append('author',byId('editAuthor').value.trim());fd.append('note',byId('editNote').value.trim());
  if(coverFile)fd.append('cover',coverFile);
  fetch('/api/books/'+_editBid,{method:'PUT',credentials:'same-origin',body:fd}).then(function(){closeEditBook();loadB()})};
// Also close when clicking overlay background
D.addEventListener('click',function(e){if(e.target===byId('editBookDlg'))closeEditBook()});

/* Reader */
window.openR=function(bid){
  _contDivs={};var rp=byId('readerPage');if(rp)rp.innerHTML='<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';
  CB=B.find(function(b){return b.id===bid});if(!CB)return;
  showR();api('/api/books/'+bid+'/toc').then(function(td){api('/api/reading/'+bid+'/settings').then(function(sd){
    if(td.code===200)CH=td.data||[];if(!CH.length)CH=[{title:CB.title,index:0,position:0}];
    if(sd.code===200&&sd.data){RS.fs=sd.data.font_size||18;RS.bg=sd.data.background_color||'#f8f9fb';RS.tc=sd.data.text_color||'#1a1c2e';RS.ls=sd.data.line_spacing||1.8;RS.ps=sd.data.paragraph_spacing||1.2;RS.ws=sd.data.word_spacing||0;RS.ff=sd.data.font_family||'serif'}
    CI=0;if(CB&&CB.last_read_chapter&&CH.length)for(var i=0;i<CH.length;i++)if(CH[i].title===CB.last_read_chapter){CI=i;break}
    loadCh(CI);applyRS()
  })})};
var _contDivs={};
var _contDivs={},_contPending={};
function showR(){var ro=byId('readerOverlay');if(ro)ro.classList.add('show');D.body.style.overflow='hidden';_setupContinuous()}
window.closeReader=function(){var ro=byId('readerOverlay');if(ro)ro.classList.remove('show');D.body.style.overflow='';var rs=byId('rdrSetPanel');if(rs)rs.classList.remove('show');closeBkm();closeHl();
  if(CB&&CH[CI]){var rc2=byId('readerContent'),sc=rc2?rc2.scrollTop:0,sh=rc2?rc2.scrollHeight:1;
    fetch('/api/reading/'+CB.id+'/bookmarks',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({chapter:CH[CI].title,position:sc/sh,note:'自动书签'})})}
  if(CB)api('/api/books/'+CB.id+'/cache-clear',{method:'POST'});CB=null;CI=0;CH=[];  _contDivs={};_contPending={};loadB()}

function loadCh(i){
  var jump=Math.abs(i-CI)>1;
  if(jump){_contDivs={};var rp=byId('readerPage');if(rp)rp.innerHTML='';}

  _contLoad(i,false)
}
function _contLoad(i,preload){
  var rp=byId('readerPage'),div=byId('ch-'+i);
  if(!div){div=D.createElement('div');div.id='ch-'+i;div.style.cssText='margin-bottom:8px';
    if(i<CI)rp.insertBefore(div,rp.firstChild);else rp.appendChild(div)}
  if(_contDivs[i])return;
  if(_contPending[i])return;
  _contPending[i]=true;
  var prevCI=CI;if(!preload){CI=i;var rt=byId('rdrChap');if(rt)rt.textContent=CH[i].title}
  div.innerHTML='<div style="text-align:center;padding:20px"><div class="spinner"></div></div>';
  api('/api/books/'+CB.id+'/content?chapter='+i).then(function(d){
    if(d.code===200){div.innerHTML=d.data.content;_contDivs[i]=true}
    else div.innerHTML='<p style="color:var(--red)">加载失败</p>'
    _contPending[i]=false;_loadingLock=false;if(!preload){savePos();upNav({prevChapter:CI>0?CI-1:null,nextChapter:CI<CH.length-1?CI+1:null})}
    // Purge DOM cache: keep only CI-3 to CI+3
    var _keepMin=Math.max(0,CI-3),_keepMax=Math.min(CH.length-1,CI+3);
    for(var _k in _contDivs){
      if(_k< _keepMin||_k>_keepMax){var _el=byId('ch-'+_k);if(_el&&_el.parentNode)_el.parentNode.removeChild(_el);delete _contDivs[_k]}
    }
  })
}

function _setupContinuous(){
  var rc=byId('readerContent');if(!rc)return;
  var rp=byId('readerPage');if(rp)rp.style.cssText='max-width:780px;margin:0 auto';
  rc.onscroll=function(){
    if(_loadingLock)return;
    var sh=rc.scrollHeight-rc.clientHeight;if(sh<60)return;
    var pct=rc.scrollTop/sh;
    // Scroll down: find next unloaded chapter after CI
    if(pct>0.3){
      var nxt=CI;while(nxt<CH.length-1&&_contDivs[nxt+1])nxt++;
      if(nxt<CH.length-1&&!_contDivs[nxt+1]&&!_contPending[nxt+1])_contLoad(nxt+1,true)
    }
    if(pct>0.65){
      var nxt2=CI;while(nxt2<CH.length-1&&_contDivs[nxt2+1])nxt2++;
      if(nxt2<CH.length-1&&!_contDivs[nxt2+1]&&!_contPending[nxt2+1]){_loadingLock=true;_contLoad(nxt2+1,false)}
    }
    // Scroll up: find previous unloaded chapter
    if(pct<0.3){
      var prv=CI;while(prv>0&&_contDivs[prv-1])prv--;
      if(prv>0&&!_contDivs[prv-1]&&!_contPending[prv-1])_contLoad(prv-1,true)
    }
    if(pct<0.05){
      var prv2=CI;while(prv2>0&&_contDivs[prv2-1])prv2--;
      if(prv2>0&&!_contDivs[prv2-1]&&!_contPending[prv2-1]){var oh2=rc.scrollHeight;_loadingLock=true;_contUpLoad(prv2-1)}
    }
    // Auto-detect which chapter user is in based on actual div positions
    var _divs=rc.querySelectorAll('[id^="ch-"]'),_vpTop=rc.scrollTop+rc.clientHeight*0.2;
    for(var _di=0;_di<_divs.length;_di++){
      var _id=parseInt(_divs[_di].id.replace('ch-',''),10);
      if(!isNaN(_id)&&_divs[_di].offsetTop<_vpTop)CI=_id
    }
    var _rt=byId('rdrChap');if(_rt){var _newTitle=CH[CI]?CH[CI].title:'';if(_rt.textContent!==_newTitle)_rt.textContent=_newTitle}
  };
}
function _contUpLoad(i){
  var rp=byId('readerPage'),div=byId('ch-'+i);
  if(!div){div=D.createElement('div');div.id='ch-'+i;div.style.cssText='margin-bottom:8px';rp.insertBefore(div,rp.firstChild)}
  if(_contDivs[i]||_contPending[i]){_loadingLock=false;return}
  _contPending[i]=true;
  div.innerHTML='<div style="text-align:center;padding:20px"><div class="spinner"></div></div>';
  var rc=byId('readerContent'),oldH=rc.scrollHeight;
  api('/api/books/'+CB.id+'/content?chapter='+i).then(function(d){
    if(d.code===200){div.innerHTML=d.data.content;_contDivs[i]=true}
    else div.innerHTML='<p style="color:var(--red)">加载失败</p>'
    CI=i;var rt=byId('rdrChap');if(rt)rt.textContent=CH[i].title;
    _contPending[i]=false;_loadingLock=false;savePos();upNav({prevChapter:CI>0?CI-1:null,nextChapter:CI<CH.length-1?CI+1:null});
    // Purge DOM cache: keep only CI-3 to CI+3
    var _keepMin=Math.max(0,CI-3),_keepMax=Math.min(CH.length-1,CI+3);
    for(var _k in _contDivs){
      if(_k<_keepMin||_k>_keepMax){var _el=byId('ch-'+_k);if(_el&&_el.parentNode)_el.parentNode.removeChild(_el);delete _contDivs[_k]}
    }
    // Compensate scroll: keep user at same visual position
    var newH=rc.scrollHeight;rc.scrollTop=newH-oldH
  })
}
function upNav(d){var bp=byId('btnPrevCh'),bn=byId('btnNextCh'),cf=byId('chFill');
  if(bp)bp.disabled=!d.prevChapter&&d.prevChapter!==0;if(bn)bn.disabled=!d.nextChapter&&d.nextChapter!==0;
  if(cf)cf.style.width=((CI+1)/Math.max(CH.length,1)*100)+'%'}
function savePos(){if(!CB)return;api('/api/reading/'+CB.id+'/position',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({position:CI/Math.max(CH.length-1,1),chapter:CH[CI]?CH[CI].title:''})})}
window.prevCh=function(){if(CI>0)loadCh(CI-1)};
var _loadingLock=false;
window.nextCh=function(){if(_loadingLock)return;if(CI<CH.length-1){_loadingLock=true;loadCh(CI+1)}};

/* Bookmarks */
window.addBkm=function(){var rc=byId('readerContent'),sc=rc?rc.scrollTop:0,sh=rc?rc.scrollHeight:1;
  api('/api/reading/'+CB.id+'/bookmarks').then(function(bd){if(bd.code===200&&bd.data&&bd.data.some(function(b){return b.chapter===CH[CI].title})){showDlToast('该章节已有书签');return}
  api('/api/reading/'+CB.id+'/bookmarks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chapter:CH[CI].title,position:sc/sh})}).then(function(d){if(d.code===200){var rs=byId('rdrSetPanel');if(rs)rs.classList.remove('show');showBkms()}})})};
window.showBkms=function(){api('/api/reading/'+CB.id+'/bookmarks').then(function(d){var bd=byId('bkmBody'),data=d.code===200?d.data||[]:[];if(!bd)return;if(!data.length){bd.innerHTML='<div class="empty-state" style="padding:30px"><p>暂无书签</p></div>'}else{var h='';data.forEach(function(m){h+='<div class="bkm-item" onclick="jumpBkm('+m.position+',\''+esc(m.chapter)+'\')"><div class="bkm-info"><div>'+esc(m.chapter).substring(0,40)+'</div><div class="bkm-chapter">'+fts(m.created_at)+'</div></div><button class="bkm-del" onclick="event.stopPropagation();delBkm('+m.id+')">✕</button></div>'});bd.innerHTML=h}var bp=byId('bkmPanel');if(bp)bp.classList.add('show')})}
window.closeBkm=function(){var bp=byId('bkmPanel');if(bp)bp.classList.remove('show')}
window.jumpBkm=function(pos,ch){closeBkm();for(var i=0;i<CH.length;i++){if(CH[i].title===ch){loadCh(i);var rc=byId('readerContent');setTimeout(function(){if(rc)rc.scrollTop=pos*(rc.scrollHeight||1)},100);break}}}
window.delBkm=function(id){api('/api/reading/'+CB.id+'/bookmarks/'+id,{method:'DELETE'}).then(function(){showBkms()})}

/* Highlights */
window.showHls=function(){api('/api/reading/'+CB.id+'/highlights').then(function(d){var bd=byId('hlBody'),data=d.code===200?d.data||[]:[];if(!bd)return;if(!data.length){bd.innerHTML='<div class="empty-state" style="padding:30px"><p>暂无收藏</p></div>'}else{var h='';data.forEach(function(hl){h+='<div class="hl-item"><div class="hl-text">'+esc(hl.selected_text).substring(0,200)+'</div><div class="hl-meta"><span>'+esc(hl.chapter).substring(0,30)+'</span><button class="hl-del" onclick="delHl('+hl.id+')">✕</button></div></div>'});bd.innerHTML=h}var hp=byId('hlPanel');if(hp)hp.classList.add('show')})}
window.closeHl=function(){var hp=byId('hlPanel');if(hp)hp.classList.remove('show')}
window.delHl=function(id){api('/api/reading/'+CB.id+'/highlights/'+id,{method:'DELETE'}).then(function(){showHls()})}
D.addEventListener('mouseup',function(){var ro=byId('readerOverlay');if(!ro||!ro.classList.contains('show'))return;var t=window.getSelection().toString().trim();if(t.length>4&&confirm('收藏选中文字？')){api('/api/reading/'+CB.id+'/highlights',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,chapter:CH[CI].title,position:CI/Math.max(CH.length-1,1)})}).then(function(){var rs=byId('rdrSetPanel');if(rs)rs.classList.remove('show');showHls()})}});
/* Auto-close settings on content click */
D.addEventListener('click',function(e){var rs=byId('rdrSetPanel');if(!rs||!rs.classList.contains('show'))return;var rc=byId('readerContent');if(rc&&rc.contains(e.target)){rs.classList.remove('show')}});

/* TOC */
window.showToc=function(){var l=byId('tocList'),h='';if(!l)return;CH.forEach(function(c,i){h+='<div class="toc-item'+(i===CI?' current':'')+'" onclick="goCh('+i+')">'+esc(c.title)+'</div>'});l.innerHTML=h;var to=byId('tocOL');if(to)to.classList.add('show')}
window.closeToc=function(){var to=byId('tocOL');if(to)to.classList.remove('show')}
window.goCh=function(i){closeToc();_contDivs={};_contPending={};var rp=byId('readerPage');if(rp)rp.innerHTML='';loadCh(i)}

/* Settings */
window.togRdrSet=function(){var rs=byId('rdrSetPanel');if(rs)rs.classList.toggle('show')}
function applyRS(){var ro=byId('readerOverlay');if(ro)ro.style.background=RS.bg;var rp=byId('readerPage');if(rp){rp.style.maxWidth='780px';rp.style.fontSize=RS.fs+'px';rp.style.lineHeight=RS.ls;rp.style.letterSpacing=RS.ws+'px';rp.style.color=RS.tc;rp.style.fontFamily=RS.ff}var ps=$$('.reader-content p');for(var i=0;i<ps.length;i++)ps[i].style.marginBottom=RS.ps+'em';
  var fsS=byId('fsS'),fsV=byId('fsV'),lsS=byId('lsS'),lsV=byId('lsV'),psS=byId('psS'),psV=byId('psV'),wsS=byId('wsS'),wsV=byId('wsV');
  if(fsS)fsS.value=RS.fs;if(fsV)fsV.textContent=RS.fs;if(lsS)lsS.value=RS.ls;if(lsV)lsV.textContent=RS.ls;if(psS)psS.value=RS.ps;if(psV)psV.textContent=RS.ps;if(wsS)wsS.value=RS.ws;if(wsV)wsV.textContent=RS.ws;
  if(CB)api('/api/reading/'+CB.id+'/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({font_size:RS.fs,background_color:RS.bg,text_color:RS.tc,line_spacing:RS.ls,paragraph_spacing:RS.ps,word_spacing:RS.ws,font_family:RS.ff})})}
window.upFs=function(v){RS.fs=parseInt(v);var fv=byId('fsV');if(fv)fv.textContent=v;applyRS()}
window.upLs=function(v){RS.ls=parseFloat(v);var lv=byId('lsV');if(lv)lv.textContent=v;applyRS()}
window.upPs=function(v){RS.ps=parseFloat(v);var pv=byId('psV');if(pv)pv.textContent=v;applyRS()}
window.upWs=function(v){RS.ws=parseFloat(v);var wv=byId('wsV');if(wv)wv.textContent=v;applyRS()}
window.upBg=function(c){RS.bg=c;if(c==='#0b0b12'){RS.tc='#e2e4f0';var tc=byId('tcS');if(tc)tc.value='#e2e4f0'}else{RS.tc='#1a1c2e';var tc=byId('tcS');if(tc)tc.value='#1a1c2e'}applyRS()}
window.upFf=function(v){RS.ff=v;applyRS()};window.upTc=function(v){RS.tc=v;applyRS()}

/* Download */
function loadDC(){api('/api/download/config').then(function(d){if(d.code===200&&d.data){var su=byId('snUrl'),st=byId('snToken');if(su)su.value=d.data.serverUrl||'';if(st)st.value=d.data.apiToken||''}})}
window.togDlCfg=function(){var dp=byId('dlCfgPanel');if(dp)dp.classList.toggle('show')}
window.saveDlCfg=function(){var msg=byId('dlCfgMsg'),su=byId('snUrl'),st=byId('snToken');if(msg)msg.textContent='';if(!su||!st)return;api('/api/download/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({serverUrl:su.value.trim(),apiToken:st.value.trim()})}).then(function(d){if(msg)msg.textContent=d.code===200?'✓':'✗ '+d.message;var dp=byId('dlCfgPanel');if(dp)dp.classList.remove('show')})}
window.doSearch=function(){var si=byId('searchInp'),kw=si?si.value.trim():'';if(!kw)return;var st=byId('searchStatus'),sb=byId('searchBtn');
  var url=byId('snUrl'),tok=byId('snToken');if((!url||!url.value.trim())||(!tok||!tok.value.trim())){showDlToast('请先配置服务器，<a href="/sonovelwebguide" target="_blank" style="color:var(--accent);text-decoration:underline">查看配置教程</a>');return}
  if(st)st.style.display='block';if(sb)sb.disabled=true;
  api('/api/download/search?kw='+encodeURIComponent(kw)).then(function(d){if(st)st.style.display='none';if(sb)sb.disabled=false;
    if(d.code===200&&d.data){SD=d.data;renderSR()}
    else showDlToast(d.message||'搜索失败')
  }).catch(function(){if(st)st.style.display='none';if(sb)sb.disabled=false;showDlToast('网络错误，请检查搜书服务器连接')})};
window.dlSN=function(i){var b=SD[i],fmt=byId('fmt'+i),f=fmt?fmt.value:'epub';showDlMini();showDlToast('已添加下载任务');
  api('/api/download/fetch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:b.url,format:f,bookName:b.bookName,author:b.author,sourceName:b.sourceName})}).then(function(d){if(d.code===200){refDT()}else showDlToast(d.message||'下载失败')}).catch(function(){showDlToast('下载请求失败')})};
window.togDlMgr=function(){var dm=byId('dlMgrPanel');if(dm)dm.classList.toggle('show');
  var mb=byId('dlMiniBar');if(mb&&dm.classList.contains('show'))mb.style.display='none';
  else if(mb&&DT.length>0)mb.style.display='flex';if(dm&&dm.classList.contains('show'))refDT()};
function showDlMini(){var mb=byId('dlMiniBar');if(mb)mb.style.display='flex'}
function refDT(){api('/api/download/tasks').then(function(d){if(d.code===200){DT=d.data||[];renderDT();var mb=byId('dlMiniBar'),dm=byId('dlMgrPanel');if(mb&&DT.length>0&&(!dm||!dm.classList.contains('show')))mb.style.display='flex';if(!DT.length&&mb)mb.style.display='none'}})}
function renderDT(){var c=byId('dlMgrBody');if(!c)return;if(!DT.length){c.innerHTML='<div style="text-align:center;color:var(--text-muted);padding:20px">暂无下载任务</div>';return}
  var total=0,done=0;DT.forEach(function(t){total++;if(t.status==='completed'||t.status==='failed')done++});
  var h='';DT.forEach(function(t){var pct=t.progress||0;var sc=t.status==='completed'?'var(--green)':t.status==='failed'?'var(--red)':t.status==='downloading'?'var(--accent)':'var(--text-muted)';
  h+='<div class="dl-task"><div class="dl-name"><div>'+esc(t.book_name||'?')+'</div><div style="font-size:10px;color:var(--text-muted)">'+t.format.toUpperCase()+'</div><div class="dl-bar"><div class="fill" style="width:'+pct+'%"></div></div></div><span class="dl-status" style="color:'+sc+'">'+(t.status==='completed'?'✓完成':t.status==='failed'?'✗失败':t.status==='downloading'?pct+'%':'等待')+'</span>'+(t.status!=='completed'&&t.status!=='failed'?'<button class="dl-cancel" onclick="cancelDl('+t.id+')">✕</button>':'')+'</div>'});c.innerHTML=h;
  // Update mini progress
  var allPct=total>0?Math.round((done/total)*100):0;var mf=byId('dlMiniFill');if(mf)mf.style.width=allPct+'%'}
window.cancelDl=function(id){fetch('/api/download/tasks/'+id,{method:'DELETE',credentials:'same-origin'}).then(function(){refDT()})};
function renderSR(){var c=byId('searchRes');if(!c)return;if(!SD.length){c.innerHTML='<div class="empty-state"><p>无结果</p></div>';return}var h='<div class="card"><table><thead><tr><th>书名</th><th>作者</th><th>最新章节</th><th>来源</th><th>操作</th></tr></thead><tbody>';SD.forEach(function(b,i){h+='<tr><td>'+esc(b.bookName||'')+'</td><td>'+esc(b.author||'')+'</td><td>'+esc(b.latestChapter||'')+'</td><td>'+esc(b.sourceName||'')+'</td><td><select class="format-sel" id="fmt'+i+'"><option value="epub">EPUB</option><option value="txt">TXT</option><option value="html">HTML</option><option value="pdf">PDF</option></select><button class="btn btn-primary btn-sm" onclick="dlSN('+i+')">下载</button></td></tr>'});h+='</tbody></table></div>';c.innerHTML=h}
function connSSE(){if(SO)return;SO=true;var es=new EventSource('/api/download/progress');es.onmessage=function(e){try{var m=JSON.parse(e.data);
  if(m.type==='download-complete'){showDlToast(m.message||'下载完成');loadB();refDT()}
  else if(m.type==='download-error'){showDlToast(m.error||'下载失败');refDT()}
  else if(m.type==='download-progress'){refDT()}}catch(x){};};es.onerror=function(){SO=false;setTimeout(connSSE,5000)}}
// Poll tasks every 2s for live progress
setInterval(function(){if(DT.length>0&&DT.some(function(t){return t.status==='downloading'}))refDT()},2000);
function showDlToast(msg){var t=D.createElement('div');t.style.cssText='position:fixed;bottom:80px;left:50%;transform:translateX(-50%);z-index:10000;background:var(--surface);border:1px solid var(--border);padding:10px 20px;border-radius:10px;font-size:13px;box-shadow:0 4px 12px rgba(0,0,0,.12);animation:toastIn .25s ease;max-width:90vw;text-align:center';t.innerHTML=msg;D.body.appendChild(t);setTimeout(function(){t.style.opacity='0';t.style.transition='opacity .3s';setTimeout(function(){if(t.parentNode)t.parentNode.removeChild(t)},300)},2500)}
// Rocket button visibility
window.addEventListener('scroll',function(){var r=byId('rocketBtn');if(r)r.style.display=window.scrollY>300?'block':'none'});

/* User */
window.chUser=function(){var n=byId('umgr'),nv=n?n.value.trim():'';if(nv.length<4){var m=byId('umgrMsg');if(m)m.textContent='≥4字符';return}api('/api/auth/change-username',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:nv})}).then(function(d){var m=byId('umgrMsg');if(m)m.textContent=d.message||'OK';if(d.code===200){var hu=byId('hdrUser');if(hu)hu.textContent=nv;U.username=nv}})}
window.chPwd=function(){var o=byId('pmgrO'),no=byId('pmgrN'),ov=o?o.value.trim():'',nv=no?no.value.trim():'';if(!ov||!nv){var m=byId('pmgrMsg');if(m)m.textContent='请填写';return}if(nv.length<4){var m=byId('pmgrMsg');if(m)m.textContent='≥4位';return}api('/api/auth/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({oldPassword:ov,newPassword:nv})}).then(function(d){var m=byId('pmgrMsg');if(m)m.textContent=d.message||'OK'})};

/* Upload toast */
function showUpToast(msg,pct){var t=byId('upToast'),b=byId('upBar'),p=byId('upProgress');if(t)t.style.display='flex';if(t)byId('upMsg').textContent=msg;if(p){p.style.display='block';if(b)b.style.width=pct+'%'}if(pct>=100){if(t)t.className='upload-toast success';setTimeout(function(){if(p)p.style.display='none'},1500)}}
function hideUpToast(){var t=byId('upToast'),p=byId('upProgress');if(t)t.style.display='none';if(p)p.style.display='none'}

/* ════════════════════════════════════════════
   TUTORIAL SYSTEM — disabled
   ════════════════════════════════════════════ */
var _tutSteps={};
function startTutorial(page){}

window.startTutorial=function(){};

/* Progress bar drag/jump */
window.jumpByProgress=function(e){var p=byId('chProg');if(!p)return;var r=p.getBoundingClientRect(),pct=(e.clientX-r.left)/r.width,ch=Math.round(pct*(CH.length-1));goCh(ch)};
window.showChapterAt=function(e){var p=byId('chProg'),h=byId('chHint');if(!p||!h)return;var r=p.getBoundingClientRect(),pct=(e.clientX-r.left)/r.width,ch=Math.round(pct*(CH.length-1));h.textContent=CH[ch]?CH[ch].title:'';h.style.display='block';h.style.left=(e.clientX-60)+'px'};
window.hideChapterHint=function(){var h=byId('chHint');if(h)h.style.display='none'};
})();
