/* ═══════════════════════════════════════════
   Miniread — Markdown Toolbar (Chrome 91+)
   Usage: initMdToolbar('textareaId', 'previewId')
   ═══════════════════════════════════════════ */
var MdToolbar = (function(){

  function init(textareaId, previewId){
    var ta = document.getElementById(textareaId);
    if(!ta) return;

    // Create toolbar
    var bar = document.createElement('div');
    bar.className = 'md-toolbar';
    bar.innerHTML =
      '<button title="粗体" data-md="**text**">B</button>'+
      '<button title="斜体" data-md="*text*">I</button>'+
      '<button title="标题" data-md="## text">H</button>'+
      '<button title="列表" data-md="- text">•</button>'+
      '<button title="链接" data-md="[text](url)">🔗</button>'+
      '<button title="代码" data-md="`code`">&lt;/&gt;</button>'+
      '<button title="引用" data-md="> text">❝</button>'+
      '<button title="分割线" data-md="\n---\n">—</button>'+
      '<button title="预览" data-md="__preview__">👁</button>';

    ta.parentNode.insertBefore(bar, ta);

    // Click handlers
    var btns = bar.querySelectorAll('button');
    for(var i=0;i<btns.length;i++){
      btns[i].onclick = function(e){
        e.preventDefault();
        var md = this.getAttribute('data-md');
        if(md === '__preview__'){
          togglePreview(textareaId, previewId, bar);
          return;
        }
        insertMd(ta, md);
      };
    }
  }

  function insertMd(ta, template){
    var start = ta.selectionStart, end = ta.selectionEnd;
    var text = ta.value, sel = text.substring(start, end) || 'text';
    var before = text.substring(0, start), after = text.substring(end);
    var insert = template.replace('text', sel).replace('url','https://');
    // Handle line-prefixed templates
    if(template.indexOf('\n')===0){
      if(before.length>0 && before[before.length-1]!=='\n') insert = '\n'+insert;
    }
    ta.value = before + insert + after;
    ta.focus();
    // Set cursor position
    var newPos = start + insert.indexOf(sel);
    if(newPos < start) newPos = start + insert.length;
    ta.setSelectionRange(newPos, newPos + (sel==='text'?4:sel.length));
    ta.dispatchEvent(new Event('input',{bubbles:true}));
  }

  function togglePreview(textareaId, previewId, bar){
    var ta = document.getElementById(textareaId);
    var pv = document.getElementById(previewId);
    if(!pv) return;

    if(pv.style.display === 'block'){
      pv.style.display = 'none';
      ta.style.display = 'block';
      bar.querySelector('[data-md="__preview__"]').textContent = '👁';
    } else {
      var html = renderMd(ta.value);
      pv.innerHTML = html;
      pv.style.display = 'block';
      ta.style.display = 'none';
      bar.querySelector('[data-md="__preview__"]').textContent = '✎';
    }
  }

  /* Minimal Markdown → HTML renderer (Chrome 91+ safe) */
  function renderMd(md){
    if(!md) return '';
    var html = md;
    // Escape HTML first
    html = html.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    // Code blocks ```
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function(_,lang,code){
      return '<pre><code>'+code.replace(/\n$/,'')+'</code></pre>';
    });
    // Inline code
    html = html.replace(/`([^`]+)`/g,'<code>$1</code>');
    // Headers
    html = html.replace(/^#### (.+)$/gm,'<h4>$1</h4>');
    html = html.replace(/^### (.+)$/gm,'<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm,'<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm,'<h1>$1</h1>');
    // Bold & Italic
    html = html.replace(/\*\*\*(.+?)\*\*\*/g,'<b><i>$1</i></b>');
    html = html.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
    html = html.replace(/\*(.+?)\*/g,'<i>$1</i>');
    // Images
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g,'<img src="$2" alt="$1">');
    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank">$1</a>');
    // Horizontal rules
    html = html.replace(/^---$/gm,'<hr>');
    // Blockquotes
    html = html.replace(/^&gt; (.+)$/gm,'<blockquote>$1</blockquote>');
    // Unordered lists
    html = html.replace(/^- (.+)$/gm,'<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s,function(m){return '<ul>'+m+'</ul>'});
    // Ordered lists
    html = html.replace(/^\d+\. (.+)$/gm,'<li>$1</li>');
    // Paragraphs (double newline)
    var lines = html.split('\n');
    var out = [], inList = false;
    for(var i=0;i<lines.length;i++){
      var l = lines[i];
      if(l.indexOf('<li>')===0){ out.push(l); inList=true; continue; }
      if(inList && l.indexOf('<li>')!==0){ out.push('</ul>'); inList=false; }
      if(l.indexOf('<h')===0||l.indexOf('<pre')===0||l.indexOf('<hr')===0||l.indexOf('<block')===0||l.indexOf('<ul')===0){
        out.push(l);
      } else if(l.trim()){
        out.push('<p>'+l+'</p>');
      }
    }
    if(inList) out.push('</ul>');
    return out.join('\n');
  }

  return {init:init, render:renderMd};
})();
