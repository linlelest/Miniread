import hashlib
import json
import os
import re
import shutil
import time
from html import escape

import charset_normalizer
from bs4 import BeautifulSoup

from config import Config
from services.parser_docx import parse_docx
from services.parser_epub import parse_epub
from services.parser_fb2 import parse_fb2
from services.parser_html import split_html
from services.sanitizer import sanitize_fragment

DEFAULT_CHAPTER_RE = re.compile(
    r'^\s*(?:'
    r'第\s*[0-9〇零一二三四五六七八九十百千万两]+\s*[章节卷回部篇集回幕]'
    r'|Chapter\s+[\dIVXLCDMivxlcdm]+'
    r'|Chapter\s+(?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve|Thirteen|Fourteen|Fifteen|Sixteen|Seventeen|Eighteen|Nineteen|Twenty|Thirty|Forty|Fifty|Sixty|Seventy|Eighty|Ninety|Hundred)'
    r'|(?:Part|Book|Volume)\s+(?:[\dIVXLCDMivxlcdm]+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)'
    r'|Prologue|Epilogue|Interlude|Preface|Foreword|Afterword|Postscript|Epigraph|Conclusion|Appendix'
    r'|序章|楔子|引子|前言|自序|序言|尾声|后记|番外|终章|结局|附录|番外篇'
    r'|[（(]\s*[0-9一二三四五六七八九十]{1,3}\s*[)）]\s*[^。！？\s][^。！？]{0,40}'
    r'|[一二三四五六七八九十]{1,3}\s*、\s*[^。！？\s][^。！？]{0,40}'
    r'|[0-9]{1,2}\s*[、\.]\s*[^。！？\s][^。！？]{0,30}'
    r')\s*[^。！？]{0,80}\s*$',
    re.I,
)

_CANONICAL_FORMATS = {'txt', 'epub', 'docx', 'fb2', 'html', 'htm', 'md', 'markdown', 'rtf'}
_ASSET_NAME_RE = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]{0,120}$')
MAX_SECTIONS = 5000


def book_dir(book_id):
    return os.path.join(Config.CANONICAL_DIR, str(int(book_id)))


def _chapters_dir(book_id):
    return os.path.join(book_dir(book_id), 'chapters')


def _assets_dir(book_id):
    return os.path.join(book_dir(book_id), 'assets')


def manifest_path(book_id):
    return os.path.join(book_dir(book_id), 'manifest.json')


def load_manifest(book_id):
    try:
        with open(manifest_path(book_id), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read_section(book_id, n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    path = os.path.join(_chapters_dir(book_id), '%04d.html' % n)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except OSError:
        return None


def section_etag(book_id, n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    path = os.path.join(_chapters_dir(book_id), '%04d.html' % n)
    try:
        st = os.stat(path)
    except OSError:
        return None
    return hashlib.md5(('%d:%d' % (int(st.st_mtime), st.st_size)).encode()).hexdigest()


def asset_path(book_id, name):
    if not name or not _ASSET_NAME_RE.match(name):
        return None
    path = os.path.join(_assets_dir(book_id), name)
    real_root = os.path.realpath(_assets_dir(book_id))
    real_path = os.path.realpath(path)
    if not real_path.startswith(real_root + os.sep):
        return None
    if not os.path.isfile(real_path):
        return None
    return real_path


def remove_canonical(book_id):
    shutil.rmtree(book_dir(book_id), ignore_errors=True)


def needs_build(row):
    try:
        status = row['canonical_status'] if not isinstance(row, dict) else row.get('canonical_status')
    except (KeyError, IndexError):
        status = None
    if status == 'ready':
        return load_manifest(_row_id(row)) is None
    return True


def _row_id(row):
    try:
        return row['id'] if not isinstance(row, dict) else row.get('id')
    except (KeyError, IndexError):
        return None


class AssetStore:
    def __init__(self, book_id):
        self.book_id = int(book_id)
        self.dir = _assets_dir(self.book_id)
        os.makedirs(self.dir, exist_ok=True)

    def add(self, data, ext):
        if not data:
            return None
        ext = (ext or 'bin').lower().strip('.')
        if not re.match(r'^[a-z0-9]{1,5}$', ext):
            ext = 'bin'
        name = '%s.%s' % (hashlib.sha1(data).hexdigest()[:16], ext)
        path = os.path.join(self.dir, name)
        if not os.path.exists(path):
            with open(path, 'wb') as f:
                f.write(data)
        return '/api/books/%d/asset/%s' % (self.book_id, name)

    def add_cover(self, data, ext):
        if not data:
            return None
        ext = (ext or 'jpg').lower().strip('.')
        if not re.match(r'^[a-z0-9]{1,5}$', ext):
            ext = 'jpg'
        name = 'cover.%s' % ext
        path = os.path.join(self.dir, name)
        with open(path, 'wb') as f:
            f.write(data)
        return '/api/books/%d/asset/%s' % (self.book_id, name)


def _text_to_sections(text, options):
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    custom = (options or {}).get('chapter_regex') or ''
    if custom:
        try:
            chapter_re = re.compile(custom)
        except re.error:
            raise ValueError('自定义分章正则无效')
    else:
        chapter_re = DEFAULT_CHAPTER_RE

    marks = [i for i, ln in enumerate(lines) if ln.strip() and chapter_re.match(ln.strip())]
    marks = marks[:MAX_SECTIONS]
    if (options or {}).get('strip_toc'):
        marks = _strip_toc_block(lines, marks)

    sections = []
    if not marks:
        chunks = [lines[i:i + 400] for i in range(0, len(lines), 400)] or [lines]
        if len(chunks) <= 1:
            body = _lines_to_html(lines).strip()
            if body:
                sections.append({'title': '全文', 'html': body})
            return sections
        total = len(chunks)
        for ci, ch in enumerate(chunks):
            body = _lines_to_html(ch).strip()
            if not body:
                continue
            sections.append({'title': '全文 %d/%d' % (ci + 1, total), 'html': body})
        if not sections:
            sections.append({'title': '全文', 'html': '<div class="ln"></div>'})
        return sections

    for idx, start in enumerate(marks):
        end = marks[idx + 1] if idx + 1 < len(marks) else len(lines)
        title = lines[start].strip()[:80] or ('第 %d 章' % (idx + 1))
        body = _lines_to_html(lines[start + 1:end])
        sections.append({'title': escape(title), 'html': body})
    return sections


def _strip_toc_block(lines, marks):
    if len(marks) < 8:
        return marks
    limit = min(len(lines), max(30, len(lines) // 5))
    run = []
    runs = []
    prev = None
    for m in marks:
        if m >= limit:
            break
        if prev is None or m == prev + 1:
            run.append(m)
        else:
            if len(run) >= 5:
                runs.append(run)
            run = [m]
        prev = m
    if len(run) >= 5:
        runs.append(run)
    for run in runs:
        texts = set(lines[m].strip() for m in run)
        later = sum(1 for i, ln in enumerate(lines) if i > run[-1] and ln.strip() in texts)
        if later >= len(run) * 0.5:
            return [m for m in marks if m not in set(run)]
    return marks


def _lines_to_html(lines):
    parts = []
    prev_blank = True
    for ln in lines:
        s = ln.rstrip()
        if not s.strip():
            if not prev_blank:
                parts.append('<div class="ln-gap"></div>')
            prev_blank = True
            continue
        lead = len(ln) - len(ln.lstrip(' '))
        html = '\u00a0' * lead + escape(s.strip())
        parts.append('<div class="ln">%s</div>' % html)
        prev_blank = False
    return ''.join(parts)


_CJK_RE = re.compile(r'[\u4e00-\u9fff]')
_HANGUL_RE = re.compile(r'[\uac00-\ud7af]')
_KANA_RE = re.compile(r'[\u3040-\u30ff]')
_BAD_RE = re.compile(r'[\ufffd\u25a1\ufffe]')


def _score_text(s):
    n = max(1, len(s))
    cjk = len(_CJK_RE.findall(s)) / n
    hangul = len(_HANGUL_RE.findall(s)) / n
    kana = len(_KANA_RE.findall(s)) / n
    bad = len(_BAD_RE.findall(s)) / n
    return 3 * cjk - 3 * hangul - 2 * kana - 4 * bad + 0.2 * (1 - cjk - hangul - kana - bad)


def _decode_auto(data):
    try:
        return data.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError:
        pass
    candidates = []
    best = charset_normalizer.from_bytes(data).best()
    if best is not None and best.encoding:
        candidates.append(best.encoding)
    candidates += ['gb18030', 'big5', 'utf-16', 'euc-kr', 'shift_jis']
    winner = None
    for enc in candidates:
        try:
            text = data.decode(enc)
        except (LookupError, UnicodeDecodeError, UnicodeError):
            continue
        if not text:
            continue
        sc = _score_text(text)
        if winner is None or sc > winner[0] + 1e-9:
            winner = (sc, text, enc)
    if winner is None:
        return data.decode('utf-8', errors='replace'), 'utf-8'
    return winner[1], winner[2]


def _parse_txt_like(file_path, options):
    with open(file_path, 'rb') as f:
        data = f.read()
    enc = (options or {}).get('encoding') or 'auto'
    if enc and enc != 'auto':
        try:
            text = data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            raise ValueError('指定编码 %s 无法解码该文件' % enc)
        used = enc
    else:
        text, used = _decode_auto(data)
    sections = _text_to_sections(text, options)
    meta = {'encoding': used}
    return meta, sections


def build_canonical(book_id, fmt, file_path, options=None):
    options = dict(options or {})
    fmt = (fmt or '').lower().lstrip('.')
    if fmt not in _CANONICAL_FORMATS:
        raise ValueError('不支持的规范书格式：%s' % fmt)
    if not os.path.isfile(file_path):
        raise ValueError('书籍文件不存在')

    remove_canonical(book_id)
    os.makedirs(_chapters_dir(book_id), exist_ok=True)
    store = AssetStore(book_id)

    meta = {}
    toc = []
    if fmt == 'epub':
        meta, sections, toc = parse_epub(file_path, store, options)
    elif fmt == 'docx':
        meta, sections, toc = parse_docx(file_path, store, options)
    elif fmt == 'fb2':
        meta, sections, toc = parse_fb2(file_path, store, options)
    elif fmt in ('html', 'htm'):
        meta, sections, toc = split_html_file(file_path, options)
    elif fmt in ('md', 'markdown'):
        meta, sections, toc = split_md_file(file_path, options)
    elif fmt == 'rtf':
        meta, sections, toc = split_rtf_file(file_path, options)
    else:
        meta, sections = _parse_txt_like(file_path, options)
        toc = [{'title': s['title'], 'section': i, 'children': []} for i, s in enumerate(sections)]

    if not sections:
        raise ValueError('未解析出任何章节内容')
    if len(sections) <= 1:
        toc = []

    cover_url = None
    cover = meta.pop('cover', None)
    if cover:
        data, ext = cover
        cover_url = store.add_cover(data, ext)

    manifest_sections = []
    for i, sec in enumerate(sections[:MAX_SECTIONS]):
        html = sanitize_fragment(sec['html'])
        rel = 'chapters/%04d.html' % i
        path = os.path.join(_chapters_dir(book_id), '%04d.html' % i)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(html)
        manifest_sections.append({
            'title': sec.get('title') or ('第 %d 节' % (i + 1)),
            'path': rel,
            'size': os.path.getsize(path),
        })

    manifest = {
        'version': 1,
        'gen': 4,
        'format': fmt,
        'title': meta.get('title') or '',
        'author': meta.get('author') or '',
        'language': meta.get('language') or '',
        'cover': cover_url,
        'toc': toc,
        'sections': manifest_sections,
        'import_options': {k: options.get(k) for k in ('encoding', 'chapter_regex', 'toc_mode', 'strip_toc', 'heading_level') if k in options},
        'built_at': int(time.time()),
    }
    for k in ('encoding',):
        if k in meta and meta[k]:
            manifest['import_options'][k] = meta[k]
    with open(manifest_path(book_id), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False)
    return manifest


def split_html_file(file_path, options):
    with open(file_path, 'rb') as f:
        data = f.read()
    soup = BeautifulSoup(data, 'html.parser')
    for t in soup.find_all(['script', 'style', 'noscript']):
        t.decompose()
    title = ''
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    body = soup.body or soup
    level = int(options.get('heading_level') or 2)
    sections = split_html(str(body.decode_contents() if body.name == 'body' else str(body)), level)
    if not sections:
        text = body.get_text('\n', strip=True)
        if text:
            sections = [{'title': '全文', 'html': '<p>%s</p>' % escape(text[:200000])}]
    toc = [{'title': s['title'], 'section': i, 'children': []} for i, s in enumerate(sections)]
    return {'title': title}, sections, toc


def split_md_file(file_path, options):
    import markdown
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    level = int(options.get('heading_level') or 2)
    html = markdown.markdown(text, extensions=['extra', 'toc'])
    sections = split_html(html, level)
    if not sections:
        sections = [{'title': '全文', 'html': html}]
    toc = [{'title': s['title'], 'section': i, 'children': []} for i, s in enumerate(sections)]
    return {}, sections, toc


def split_rtf_file(file_path, options):
    from striprtf.striprtf import rtf_to_text
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()
    try:
        text = rtf_to_text(raw)
    except Exception:
        text = raw
    opts = dict(options or {})
    opts.setdefault('chapter_regex', '')
    sections = _text_to_sections(text, opts)
    toc = [{'title': s['title'], 'section': i, 'children': []} for i, s in enumerate(sections)]
    return {}, sections, toc
